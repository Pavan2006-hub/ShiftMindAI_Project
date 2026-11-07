import io
from datetime import datetime, timedelta
import inspect
from flask import Blueprint, jsonify, request, send_file, current_app
from flask_login import login_required, current_user

from database.db import db
from models.handover import Handover
from models.incident import Incident
from models.incident_action import IncidentAction
from models.user import User
from services import ai_service, memory_service
from services.ai_service import AIUnavailable

handover_bp = Blueprint("handovers", __name__)

LIST_FIELDS = [
    "active_incidents", "resolved_incidents", "successful_actions",
    "failed_actions", "verified_findings", "pending_tasks", "recommendations"
]


def fail(message, status):
    return jsonify({"success": False, "message": message}), status


def handover_response(h, full=True):
    result = {
        "id": h.id,
        "outgoing_engineer": h.outgoing_engineer.name if h.outgoing_engineer else None,
        "incoming_engineer": h.incoming_engineer.name if h.incoming_engineer else None,
        "shift_start": h.shift_start.isoformat() if h.shift_start else None,
        "shift_end": h.shift_end.isoformat() if h.shift_end else None,
        "summary": h.summary,
        "created_at": h.created_at.isoformat()
    }
    if full:
        for field in LIST_FIELDS:
            result[field] = getattr(h, field) or []
    return result


def build_facts(start, end):
    active = Incident.query.filter(
        Incident.status.notin_(["resolved", "closed"])
    ).order_by(Incident.created_at.desc()).limit(50).all()

    resolved = Incident.query.filter(
        Incident.resolved_at.isnot(None), Incident.resolved_at >= start
    ).all()

    actions = IncidentAction.query.filter(
        IncidentAction.created_at >= start, IncidentAction.created_at <= end
    ).order_by(IncidentAction.created_at).all()

    def line(i):
        return "#{} {} [{}] - {} ({})".format(
            i.id, i.title, i.severity, i.service_name, i.status)

    def action_line(a):
        text = "#{}: {}".format(a.incident_id, a.action_description)
        return text + (" -> " + a.actual_result if a.actual_result else "")

    return {
        "active_incidents": [line(i) for i in active],
        "resolved_incidents": [line(i) for i in resolved],
        "successful_actions": [action_line(a) for a in actions if a.outcome == "successful"],
        "failed_actions": [action_line(a) for a in actions if a.outcome == "failed"],
        "verified_findings": [
            "#{} {}: {}".format(i.id, i.title, i.verified_root_cause)
            for i in resolved if i.verified_root_cause
        ],
    }


def fallback_draft(facts):
    pending = ["Follow up on: " + x for x in facts["active_incidents"]]
    recs = []
    if facts["failed_actions"]:
        recs.append("Do not repeat the failed actions listed in this handover.")
    if facts["active_incidents"]:
        recs.append("Review active incidents first and confirm their current status.")
    summary = "{} active and {} resolved incident(s) during this shift.".format(
        len(facts["active_incidents"]), len(facts["resolved_incidents"]))
    return summary, pending, recs


@handover_bp.post("")
@handover_bp.post("/")
@login_required
def create_handover():
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}

    hours = data.get("shift_hours", 8)
    if isinstance(hours, bool) or not isinstance(hours, int) or not 1 <= hours <= 72:
        return fail("Shift length must be between 1 and 72 hours.", 400)

    incoming = None
    incoming_id = data.get("incoming_engineer_id")
    if incoming_id is not None:
        incoming = db.session.get(User, incoming_id) if isinstance(incoming_id, int) else None
        if not incoming or not incoming.is_active:
            return fail("Incoming engineer not found.", 404)

    notes = data.get("notes")
    if notes is not None and not isinstance(notes, str):
        return fail("Notes must be text.", 400)

    end = datetime.utcnow()
    start = end - timedelta(hours=hours)
    facts = build_facts(start, end)

    summary, pending, recs = fallback_draft(facts)
    ai_used = False

    if ai_service.is_configured():
        fact_text = "\n".join(
            "{}:\n{}".format(k.replace("_", " ").upper(),
                             "\n".join("- " + x for x in v) or "- none")
            for k, v in facts.items()
        )
        if notes:
            fact_text += "\nENGINEER NOTES:\n" + notes.strip()
        try:
            draft = ai_service.draft_handover(
                fact_text,
                memory_service.format_for_prompt(
                    memory_service.recall("shift handover " + " ".join(facts["active_incidents"][:5]),
                                          budget="low", limit=4))
            )
            summary = draft.summary or summary
            pending = draft.pending_tasks or pending
            recs = draft.recommendations or recs
            ai_used = True
        except AIUnavailable:
            pass  # keep the rule-based draft

    if notes and notes.strip() and not ai_used:
        summary += " Notes: " + notes.strip()

    handover = Handover(
        outgoing_engineer_id=current_user.id,
        incoming_engineer_id=incoming.id if incoming else None,
        shift_start=start, shift_end=end, summary=summary,
        pending_tasks=pending, recommendations=recs,
        **{k: v for k, v in facts.items()}
    )
    db.session.add(handover)
    db.session.commit()

    memory_service.retain(
        "Shift handover by {}: {}".format(current_user.name, summary),
        document_id="handover-{}".format(handover.id), context="Shift handover")

    result = handover_response(handover)
    result["ai_generated"] = ai_used
    return jsonify({"success": True, "handover": result}), 201


@handover_bp.get("")
@handover_bp.get("/")
@login_required
def list_handovers():
    items = Handover.query.order_by(Handover.created_at.desc()).limit(30).all()
    return jsonify({"success": True,
                    "data": [handover_response(h, full=False) for h in items]}), 200


@handover_bp.get("/<int:handover_id>")
@login_required
def get_handover(handover_id):
    h = db.session.get(Handover, handover_id)
    if not h:
        return fail("Handover not found.", 404)
    return jsonify({"success": True, "handover": handover_response(h)}), 200


@handover_bp.get("/<int:handover_id>/pdf")
@login_required
def handover_pdf(handover_id):

    h = db.session.get(Handover, handover_id)

    if not h:
        return fail("Handover not found.", 404)

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer
        )
        from xml.sax.saxutils import escape

        styles = getSampleStyleSheet()

        story = [
            Paragraph(
                "ShiftMind AI - Shift Handover #{}".format(h.id),
                styles["Title"]
            ),

            Spacer(1, 12),

            Paragraph(
                "From: {} &nbsp; To: {}".format(
                    escape(h.outgoing_engineer.name if h.outgoing_engineer else "-"),
                    escape(h.incoming_engineer.name if h.incoming_engineer else "-")
                ),
                styles["Normal"]
            ),

            Spacer(1, 8),

            Paragraph(
                "Shift: {} to {} (UTC)".format(
                    h.shift_start.strftime("%Y-%m-%d %H:%M")
                    if h.shift_start else "-",
                    h.shift_end.strftime("%Y-%m-%d %H:%M")
                    if h.shift_end else "-"
                ),
                styles["Normal"]
            ),

            Spacer(1, 12),

            Paragraph("Summary", styles["Heading2"]),

            Paragraph(
                escape(str(h.summary or "-")),
                styles["Normal"]
            ),

            Spacer(1, 12)
        ]

        for field in LIST_FIELDS:

            story.append(
                Paragraph(
                    field.replace("_", " ").title(),
                    styles["Heading2"]
                )
            )

            entries = getattr(h, field, None) or []

            for entry in entries:
                story.append(
                    Paragraph(
                        "&bull; " + escape(str(entry)),
                        styles["Normal"]
                    )
                )

            if not entries:
                story.append(
                    Paragraph("None", styles["Normal"])
                )

            story.append(Spacer(1, 8))

        buffer = io.BytesIO()

        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            title="Shift Handover Report"
        )

        document.build(story)

        buffer.seek(0)

        filename = "handover-{}.pdf".format(h.id)

        download_options = {
            "mimetype": "application/pdf",
            "as_attachment": True
        }

        # Support both old and new Flask versions.
        if "download_name" in inspect.signature(send_file).parameters:
            download_options["download_name"] = filename
        else:
            download_options["attachment_filename"] = filename

        return send_file(buffer, **download_options)

    except Exception:
        current_app.logger.exception(
            "PDF generation failed for handover ID %s",
            handover_id
        )

        return fail(
            "Unable to generate the handover PDF. Check the Flask console for details.",
            500
        )