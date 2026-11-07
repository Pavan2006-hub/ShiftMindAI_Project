"""Hindsight long-term memory client (plain REST, no extra SDK required).

Endpoints used (see https://hindsight.vectorize.io):
    POST /v1/default/banks/{bank_id}/memories          -> retain
    POST /v1/default/banks/{bank_id}/memories/recall   -> recall
    POST /v1/default/banks/{bank_id}/reflect           -> reflect

Memory is OPTIONAL. If Hindsight is not configured, or a request fails, the rest of the
application keeps working and these helpers simply return empty results.
"""
from typing import Any, Dict, List, Optional

import httpx
from flask import current_app


class MemoryUnavailable(Exception):
    """Raised when Hindsight is not configured or cannot be reached."""


def _settings():
    cfg = current_app.config
    return (
        cfg.get("HINDSIGHT_BASE_URL", "").rstrip("/"),
        cfg.get("HINDSIGHT_API_KEY", ""),
        cfg.get("HINDSIGHT_BANK_ID", "shiftmind"),
    )


def is_configured() -> bool:
    base_url, api_key, bank_id = _settings()

    if not base_url or not bank_id:
        return False

    is_local = any(host in base_url for host in ("localhost", "127.0.0.1"))
    return bool(api_key) or is_local


def _request(method: str, path: str, payload: Optional[Dict[str, Any]] = None,
             timeout: float = 45.0) -> Dict[str, Any]:
    if not is_configured():
        raise MemoryUnavailable(
            "Hindsight memory is not configured. Set HINDSIGHT_API_KEY in .env."
        )

    base_url, api_key, bank_id = _settings()
    url = "{}/v1/default/banks/{}{}".format(base_url, bank_id, path)

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer {}".format(api_key)

    try:
        response = httpx.request(
            method, url, json=payload, headers=headers, timeout=timeout
        )
    except httpx.HTTPError as exc:
        current_app.logger.warning("Hindsight request failed: %s", exc)
        raise MemoryUnavailable("Could not reach the Hindsight service.") from exc

    if response.status_code in (401, 403):
        raise MemoryUnavailable("Hindsight rejected the API key (check HINDSIGHT_API_KEY).")

    if response.status_code >= 400:
        current_app.logger.warning(
            "Hindsight error %s: %s", response.status_code, response.text[:300]
        )
        raise MemoryUnavailable(
            "Hindsight returned an error ({}).".format(response.status_code)
        )

    try:
        return response.json()
    except ValueError:
        return {}


def retain(content: str, document_id: Optional[str] = None,
           context: Optional[str] = None) -> bool:
    """Store a memory. Never raises: returns True on success, False otherwise."""
    if not content or not content.strip() or not is_configured():
        return False

    item = {"content": content.strip()}
    if document_id:
        item["document_id"] = document_id
    if context:
        item["context"] = context

    try:
        _request("POST", "/memories", {"items": [item]})
        return True
    except MemoryUnavailable as exc:
        current_app.logger.warning("Memory retain skipped: %s", exc)
        return False


def recall(query: str, budget: str = "mid", limit: int = 8) -> List[Dict[str, Any]]:
    """Search memory. Returns [] when memory is off or the call fails."""
    if not query or not query.strip() or not is_configured():
        return []

    try:
        data = _request(
            "POST", "/memories/recall",
            {"query": query.strip()[:2000], "budget": budget}
        )
    except MemoryUnavailable as exc:
        current_app.logger.warning("Memory recall skipped: %s", exc)
        return []

    results = []
    for item in (data.get("results") or [])[:limit]:
        if isinstance(item, dict):
            text = item.get("text") or item.get("content") or ""
            if text:
                results.append({
                    "id": item.get("id"),
                    "text": text,
                    "type": item.get("type") or item.get("fact_type"),
                    "context": item.get("context"),
                })
    return results


def search_strict(query: str, budget: str = "mid", limit: int = 15) -> List[Dict[str, Any]]:
    """Like recall(), but raises MemoryUnavailable so the UI can show the reason."""
    if not is_configured():
        raise MemoryUnavailable(
            "Hindsight memory is not configured. Set HINDSIGHT_API_KEY in .env."
        )

    data = _request(
        "POST", "/memories/recall",
        {"query": query.strip()[:2000], "budget": budget}
    )

    results = []
    for item in (data.get("results") or [])[:limit]:
        if isinstance(item, dict):
            text = item.get("text") or item.get("content") or ""
            if text:
                results.append({
                    "id": item.get("id"),
                    "text": text,
                    "type": item.get("type") or item.get("fact_type"),
                    "context": item.get("context"),
                })
    return results


def reflect(query: str) -> str:
    """Ask Hindsight to synthesise an answer from memory. Raises MemoryUnavailable."""
    data = _request("POST", "/reflect", {"query": query.strip()[:2000]}, timeout=90.0)
    return str(data.get("text") or data.get("response") or "").strip()


def format_for_prompt(memories: List[Dict[str, Any]]) -> str:
    if not memories:
        return "No relevant past memory was found."
    return "\n".join("- {}".format(m["text"]) for m in memories)


def incident_to_memory_text(incident) -> str:
    """Plain-text experience record stored in memory when an incident is resolved."""
    parts = [
        "Incident #{}: {} (service: {}, severity: {}).".format(
            incident.id, incident.title, incident.service_name, incident.severity
        ),
        "Description: {}".format(incident.description),
    ]
    if incident.error_message:
        parts.append("Error: {}".format(incident.error_message))
    if incident.verified_root_cause:
        parts.append("Verified root cause: {}".format(incident.verified_root_cause))
    if incident.resolution_summary:
        parts.append("Resolution: {}".format(incident.resolution_summary))

    for action in incident.actions:
        parts.append(
            "Action ({}): {}{}".format(
                action.outcome,
                action.action_description,
                " -> " + action.actual_result if action.actual_result else "",
            )
        )
    return "\n".join(parts)
