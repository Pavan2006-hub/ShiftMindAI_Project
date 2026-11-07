"""Backward-compatible shim.

The real implementation lives in services/incident_service.py (it validates and strips
input). This root-level file used to be an out-of-date duplicate, so it now simply
re-exports the maintained version to keep old imports working.
"""
from services.incident_service import (  # noqa: F401
    VALID_SEVERITIES,
    VALID_PRIORITIES,
    VALID_STATUSES,
    VALID_ACTION_OUTCOMES,
    add_incident_log,
    create_incident,
    record_action,
    update_incident_status,
)
