"""Groq-powered AI helpers: incident analysis, assistant chat, handover drafting."""
import json
from typing import Any, Dict, List, Optional

from flask import current_app
from pydantic import BaseModel, Field, ValidationError


class AIUnavailable(Exception):
    """Raised when Groq is not configured or the request fails."""


# ---------- structured outputs ----------

class ProbableCause(BaseModel):
    cause: str
    likelihood: str = "medium"
    reasoning: str = ""


class IncidentAnalysis(BaseModel):
    summary: str = ""
    probable_causes: List[ProbableCause] = Field(default_factory=list)
    recommended_steps: List[str] = Field(default_factory=list)
    things_to_verify: List[str] = Field(default_factory=list)
    escalation_advice: str = ""


class HandoverDraft(BaseModel):
    summary: str = ""
    pending_tasks: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


SYSTEM_RULES = (
    "You are ShiftMind AI, an assistant for Site Reliability Engineers. "
    "Be concrete and concise. Any cause you propose is an UNVERIFIED hypothesis until an "
    "engineer confirms it; never present it as fact. Do not invent logs, metrics or past "
    "incidents. Use past memory only when it is clearly relevant, and say so."
)


def is_configured() -> bool:
    return bool(current_app.config.get("GROQ_API_KEY"))


def _client():
    api_key = current_app.config.get("GROQ_API_KEY")
    if not api_key:
        raise AIUnavailable(
            "Groq is not configured. Add GROQ_API_KEY to your .env file and restart."
        )

    try:
        from groq import Groq
    except ImportError as exc:  # pragma: no cover
        raise AIUnavailable("The 'groq' package is not installed.") from exc

    return Groq(api_key=api_key, timeout=60.0)


def _complete(messages: List[Dict[str, str]], json_mode: bool = False,
              temperature: float = 0.2, max_tokens: int = 1500) -> str:
    client = _client()
    kwargs = {
        "model": current_app.config.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:  # groq raises several APIError subclasses
        name = type(exc).__name__
        current_app.logger.warning("Groq request failed: %s: %s", name, exc)

        if name == "AuthenticationError":
            raise AIUnavailable("Groq rejected the API key (check GROQ_API_KEY).") from exc
        if name == "RateLimitError":
            raise AIUnavailable("Groq rate limit reached. Wait a moment and try again.") from exc
        if name == "NotFoundError":
            raise AIUnavailable(
                "Groq model not found. Check GROQ_MODEL in .env."
            ) from exc
        raise AIUnavailable("The AI service request failed. Please try again.") from exc

    content = response.choices[0].message.content if response.choices else ""
    return (content or "").strip()


def _parse_json(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise AIUnavailable("The AI returned an unreadable response. Try again.") from exc
    if not isinstance(data, dict):
        raise AIUnavailable("The AI returned an unexpected response. Try again.")
    return data


def incident_context_text(incident, max_chars: int = 6000) -> str:
    lines = [
        "Title: {}".format(incident.title),
        "Service: {}".format(incident.service_name),
        "Severity: {} | Priority: {} | Status: {}".format(
            incident.severity, incident.priority, incident.status
        ),
        "Description: {}".format(incident.description),
    ]
    if incident.error_message:
        lines.append("Error message: {}".format(incident.error_message))
    if incident.system_logs:
        lines.append("System logs:\n{}".format(incident.system_logs[:2500]))
    if incident.verified_root_cause:
        lines.append("Verified root cause: {}".format(incident.verified_root_cause))
    for action in incident.actions[-10:]:
        lines.append(
            "Action [{}]: {}{}".format(
                action.outcome,
                action.action_description,
                " -> " + action.actual_result if action.actual_result else "",
            )
        )
    return "\n".join(lines)[:max_chars]


def analyze_incident(incident, memory_text: str) -> IncidentAnalysis:
    schema = {
        "summary": "2-3 sentence plain summary of the situation",
        "probable_causes": [
            {"cause": "string", "likelihood": "low|medium|high", "reasoning": "string"}
        ],
        "recommended_steps": ["ordered, concrete troubleshooting step"],
        "things_to_verify": ["what to check to confirm or rule out a cause"],
        "escalation_advice": "when and to whom to escalate",
    }
    user_prompt = (
        "Analyze this incident and reply with ONLY a JSON object matching this shape:\n"
        "{}\n\nINCIDENT:\n{}\n\nRELEVANT PAST MEMORY:\n{}\n\n"
        "Do not repeat steps that already FAILED in the recorded actions."
    ).format(json.dumps(schema), incident_context_text(incident), memory_text)

    raw = _complete(
        [
            {"role": "system", "content": SYSTEM_RULES},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True,
        max_tokens=1800,
    )

    try:
        return IncidentAnalysis(**_parse_json(raw))
    except ValidationError as exc:
        raise AIUnavailable("The AI response was incomplete. Please try again.") from exc


def chat_reply(history: List[Dict[str, str]], message: str, memory_text: str,
               incident_text: Optional[str] = None) -> str:
    system = SYSTEM_RULES + "\n\nRELEVANT PAST MEMORY:\n" + memory_text
    if incident_text:
        system += "\n\nINCIDENT THE ENGINEER IS WORKING ON:\n" + incident_text

    messages = [{"role": "system", "content": system}]
    messages.extend(history[-12:])
    messages.append({"role": "user", "content": message})

    reply = _complete(messages, temperature=0.3, max_tokens=1200)
    if not reply:
        raise AIUnavailable("The AI returned an empty reply. Please try again.")
    return reply


def draft_handover(facts: str, memory_text: str) -> HandoverDraft:
    schema = {
        "summary": "short narrative of the shift for the incoming engineer",
        "pending_tasks": ["task the next engineer must do"],
        "recommendations": ["advice for the next shift"],
    }
    user_prompt = (
        "Write a shift handover using ONLY the facts below. Reply with ONLY JSON of "
        "this shape:\n{}\n\nFACTS:\n{}\n\nPAST MEMORY (context only):\n{}"
    ).format(json.dumps(schema), facts[:7000], memory_text)

    raw = _complete(
        [
            {"role": "system", "content": SYSTEM_RULES},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True,
        max_tokens=1200,
    )

    try:
        return HandoverDraft(**_parse_json(raw))
    except ValidationError as exc:
        raise AIUnavailable("The AI response was incomplete. Please try again.") from exc
