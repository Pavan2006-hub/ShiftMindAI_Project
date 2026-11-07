from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required, current_user

from database.db import db
from models.chat import ChatSession, ChatMessage
from models.incident import Incident
from services import ai_service, memory_service
from services.ai_service import AIUnavailable
from services.incident_service import add_incident_log
from services.memory_service import MemoryUnavailable

ai_bp = Blueprint("ai", __name__)
memory_bp = Blueprint("memory", __name__)


def fail(message, status):
    return jsonify({"success": False, "message": message}), status


def json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


@ai_bp.get("/status")
@login_required
def status():
    return jsonify({
        "success": True,
        "groq": {
            "configured": ai_service.is_configured(),
            "model": current_app.config.get("GROQ_MODEL")
        },
        "hindsight": {
            "configured": memory_service.is_configured(),
            "base_url": current_app.config.get("HINDSIGHT_BASE_URL"),
            "bank_id": current_app.config.get("HINDSIGHT_BANK_ID")
        }
    }), 200


@ai_bp.post("/analyze")
@login_required
def analyze():
    data = json_body()
    if data is None:
        return fail("Valid JSON data is required.", 400)

    incident_id = data.get("incident_id")
    if isinstance(incident_id, bool) or not isinstance(incident_id, int):
        return fail("A valid incident ID is required.", 400)

    incident = db.session.get(Incident, incident_id)
    if not incident:
        return fail("Incident not found.", 404)

    query = " ".join(filter(None, [
        incident.title, incident.service_name, incident.error_message
    ]))
    memories = memory_service.recall(query)

    try:
        analysis = ai_service.analyze_incident(
            incident, memory_service.format_for_prompt(memories)
        )
    except AIUnavailable as exc:
        return fail(str(exc), 503)

    add_incident_log(incident.id, "AI analysis generated (unverified).", "INFO")
    db.session.commit()

    return jsonify({
        "success": True,
        "analysis": analysis.model_dump(),
        "memories_used": memories,
        "disclaimer": "AI suggestions are unverified hypotheses. Confirm before acting."
    }), 200


@ai_bp.post("/chat")
@login_required
def chat():
    data = json_body()
    if data is None:
        return fail("Valid JSON data is required.", 400)

    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        return fail("Message is required.", 400)
    message = message.strip()
    if len(message) > 4000:
        return fail("Message cannot exceed 4000 characters.", 400)

    session_id = data.get("session_id")
    if session_id is None:
        session = ChatSession(user_id=current_user.id)
        db.session.add(session)
        db.session.flush()
    else:
        session = db.session.get(ChatSession, session_id) if isinstance(session_id, int) else None
        if not session or session.user_id != current_user.id:
            return fail("Chat session not found.", 404)

    incident_text = None
    incident_id = data.get("incident_id")
    if incident_id is not None:
        incident = db.session.get(Incident, incident_id) if isinstance(incident_id, int) else None
        if not incident:
            return fail("Incident not found.", 404)
        incident_text = ai_service.incident_context_text(incident)

    history = []
    for item in session.messages[-8:]:
        history.append({"role": "user", "content": item.message})
        if item.response:
            history.append({"role": "assistant", "content": item.response})

    memories = memory_service.recall(message, budget="low", limit=5)

    try:
        reply = ai_service.chat_reply(
            history, message, memory_service.format_for_prompt(memories), incident_text
        )
    except AIUnavailable as exc:
        db.session.rollback()
        return fail(str(exc), 503)

    db.session.add(ChatMessage(session_id=session.id, message=message, response=reply))
    db.session.commit()

    return jsonify({
        "success": True,
        "session_id": session.id,
        "reply": reply,
        "memories_used": len(memories)
    }), 200


@ai_bp.get("/chat/sessions")
@login_required
def list_sessions():
    sessions = (
        ChatSession.query.filter_by(user_id=current_user.id)
        .order_by(ChatSession.created_at.desc()).limit(30).all()
    )
    return jsonify({
        "success": True,
        "data": [
            {
                "id": s.id,
                "created_at": s.created_at.isoformat(),
                "preview": (s.messages[0].message[:70] if s.messages else "(empty)")
            }
            for s in sessions
        ]
    }), 200


@ai_bp.get("/chat/sessions/<int:session_id>")
@login_required
def session_messages(session_id):
    session = db.session.get(ChatSession, session_id)
    if not session or session.user_id != current_user.id:
        return fail("Chat session not found.", 404)

    return jsonify({
        "success": True,
        "data": [
            {"message": m.message, "response": m.response,
             "created_at": m.created_at.isoformat()}
            for m in session.messages
        ]
    }), 200


@ai_bp.delete("/chat/sessions/<int:session_id>")
@login_required
def delete_session(session_id):
    session = db.session.get(ChatSession, session_id)
    if not session or session.user_id != current_user.id:
        return fail("Chat session not found.", 404)

    db.session.delete(session)
    db.session.commit()
    return jsonify({"success": True, "message": "Chat deleted."}), 200


# ---------------- Memory Explorer ----------------

@memory_bp.post("/search")
@login_required
def search():
    data = json_body()
    query = (data or {}).get("query")
    if not isinstance(query, str) or not query.strip():
        return fail("A search query is required.", 400)

    try:
        results = memory_service.search_strict(query)
    except MemoryUnavailable as exc:
        return fail(str(exc), 503)

    return jsonify({"success": True, "data": results}), 200


@memory_bp.post("/reflect")
@login_required
def reflect():
    data = json_body()
    query = (data or {}).get("query")
    if not isinstance(query, str) or not query.strip():
        return fail("A question is required.", 400)

    try:
        text = memory_service.reflect(query)
    except MemoryUnavailable as exc:
        return fail(str(exc), 503)

    return jsonify({"success": True, "answer": text}), 200


@memory_bp.post("/retain")
@login_required
def retain():
    data = json_body()
    content = (data or {}).get("content")
    if not isinstance(content, str) or not content.strip():
        return fail("Note content is required.", 400)

    if not memory_service.is_configured():
        return fail("Hindsight memory is not configured. Set HINDSIGHT_API_KEY in .env.", 503)

    stored = memory_service.retain(
        "{} (noted by {})".format(content.strip(), current_user.name),
        context="Engineer note"
    )
    if not stored:
        return fail("Could not save to memory. Check the server log.", 502)

    return jsonify({"success": True, "message": "Saved to memory."}), 201
