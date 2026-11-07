
from datetime import datetime

from database.db import db
from models.incident import Incident
from models.incident_action import IncidentAction
from models.incident_log import IncidentLog


VALID_SEVERITIES = {"low", "medium", "high", "critical"}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_STATUSES = {
    "open",
    "investigating",
    "monitoring",
    "resolved",
    "closed"
}
VALID_ACTION_OUTCOMES = {"attempted", "successful", "failed"}


def add_incident_log(incident_id, message, level="INFO"):
    log = IncidentLog(
        incident_id=incident_id,
        log_message=message,
        log_level=level
    )
    db.session.add(log)


def create_incident(data, engineer_id=None):
    incident = Incident(
        title=data["title"].strip(),
        service_name=data["service_name"].strip(),
        description=data["description"].strip(),
        severity=data.get("severity", "medium"),
        priority=data.get("priority", "medium"),
        status="open",
        error_message=data.get("error_message"),
        system_logs=data.get("system_logs"),
        assigned_engineer_id=data.get("assigned_engineer_id")
    )

    db.session.add(incident)
    db.session.flush()

    add_incident_log(
        incident.id,
        "Incident created.",
        "INFO"
    )

    db.session.commit()
    return incident


def record_action(incident, engineer_id, data):
    action = IncidentAction(
        incident_id=incident.id,
        engineer_id=engineer_id,
        action_description=data["action_description"].strip(),
        outcome=data.get("outcome", "attempted"),
        actual_result=data.get("actual_result")
    )

    db.session.add(action)

    add_incident_log(
        incident.id,
        "Troubleshooting action recorded: "
        + data["action_description"],
        "INFO"
    )

    db.session.commit()
    return action


def update_incident_status(incident, status):
    previous_status = incident.status

    if status not in VALID_STATUSES:
        raise ValueError("Invalid incident status.")

    if previous_status == status:
        return incident

    incident.status = status

    if status == "resolved":
        incident.resolved_at = datetime.utcnow()
    elif previous_status == "resolved":
        incident.resolved_at = None

    add_incident_log(
        incident.id,
        "Status changed from {} to {}.".format(
            previous_status,
            status
        ),
        "INFO"
    )

    db.session.commit()
    return incident
