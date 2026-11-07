from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import or_, func
from flask_login import login_required, current_user

from database.db import db
from models.user import User
from models.incident import Incident

from services import memory_service
from services import (
    create_incident,
    record_action,
    update_incident_status,
    add_incident_log,
    VALID_SEVERITIES,
    VALID_PRIORITIES,
    VALID_STATUSES,
    VALID_ACTION_OUTCOMES
)

incident_bp = Blueprint("incidents", __name__)


def incident_response(incident):

    return {
        "id": incident.id,
        "title": incident.title,
        "service_name": incident.service_name,
        "description": incident.description,
        "severity": incident.severity,
        "priority": incident.priority,
        "status": incident.status,
        "error_message": incident.error_message,
        "system_logs": incident.system_logs,
        "assigned_engineer": (
            {
                "id": incident.assigned_engineer.id,
                "name": incident.assigned_engineer.name
            }
            if incident.assigned_engineer else None
        ),
        "verified_root_cause": incident.verified_root_cause,
        "resolution_summary": incident.resolution_summary,
        "created_at": incident.created_at.isoformat(),
        "updated_at": (
            incident.updated_at.isoformat()
            if incident.updated_at else None
        ),
        "resolved_at": (
            incident.resolved_at.isoformat()
            if incident.resolved_at else None
        )
    }


def get_incident(incident_id):

    return db.session.get(Incident, incident_id)


def validate_engineer(engineer_id):

    if engineer_id is None:
        return None

    engineer = db.session.get(User, engineer_id)

    if (
        not engineer
        or not engineer.is_active
        or engineer.role not in {"engineer", "admin"}
    ):
        return False

    return engineer


# CREATE INCIDENT
@incident_bp.post("")
@incident_bp.post("/")
@login_required
def create():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON data is required."
        }), 400

    required = ["title", "service_name", "description"]

    for field in required:
        if not isinstance(data.get(field), str) or not data[field].strip():
            return jsonify({
                "success": False,
                "message": "{} is required.".format(field)
            }), 400

    if len(data["title"].strip()) > 200:
        return jsonify({
            "success": False,
            "message": "Title cannot exceed 200 characters."
        }), 400

    if len(data["service_name"].strip()) > 120:
        return jsonify({
            "success": False,
            "message": "Service name cannot exceed 120 characters."
        }), 400

    for optional in ("error_message", "system_logs"):
        if data.get(optional) is not None and not isinstance(data[optional], str):
            return jsonify({
                "success": False,
                "message": "{} must be text.".format(optional)
            }), 400

    severity = data.get("severity", "medium")
    priority = data.get("priority", "medium")

    if severity not in VALID_SEVERITIES:
        return jsonify({
            "success": False,
            "message": "Invalid severity."
        }), 400

    if priority not in VALID_PRIORITIES:
        return jsonify({
            "success": False,
            "message": "Invalid priority."
        }), 400

    engineer_id = data.get("assigned_engineer_id")

    if engineer_id is not None:
        if isinstance(engineer_id, bool) or not isinstance(engineer_id, int):
            return jsonify({
                "success": False,
                "message": "Invalid engineer ID."
            }), 400

        engineer = validate_engineer(engineer_id)

        if engineer is False:
            return jsonify({
                "success": False,
                "message": "Active engineer not found."
            }), 400

    try:
        incident = create_incident(data, current_user.id)

        return jsonify({
            "success": True,
            "message": "Incident created successfully.",
            "incident": incident_response(incident)
        }), 201

    except Exception:
        db.session.rollback()
        raise


# LIST AND FILTER INCIDENTS
@incident_bp.get("")
@incident_bp.get("/")
@login_required
def list_incidents():

    query = Incident.query

    status = request.args.get("status")
    severity = request.args.get("severity")
    priority = request.args.get("priority")
    service = request.args.get("service")
    search = request.args.get("search")
    assigned_to = request.args.get("assigned_to")

    if status:
        if status not in VALID_STATUSES:
            return jsonify({
                "success": False,
                "message": "Invalid status filter."
            }), 400

        query = query.filter_by(status=status)

    if severity:
        if severity not in VALID_SEVERITIES:
            return jsonify({
                "success": False,
                "message": "Invalid severity filter."
            }), 400

        query = query.filter_by(severity=severity)

    if priority:
        if priority not in VALID_PRIORITIES:
            return jsonify({
                "success": False,
                "message": "Invalid priority filter."
            }), 400

        query = query.filter_by(priority=priority)

    if service:
        query = query.filter(
            Incident.service_name.ilike("%{}%".format(service.strip()))
        )

    if search:
        term = "%{}%".format(search.strip())

        query = query.filter(
            or_(
                Incident.title.ilike(term),
                Incident.description.ilike(term),
                Incident.service_name.ilike(term)
            )
        )

    if assigned_to:
        if not assigned_to.isdigit():
            return jsonify({
                "success": False,
                "message": "Invalid assigned engineer ID."
            }), 400

        query = query.filter_by(
            assigned_engineer_id=int(assigned_to)
        )

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    if page < 1 or per_page < 1 or per_page > 100:
        return jsonify({
            "success": False,
            "message": "Invalid pagination values."
        }), 400

    pagination = query.order_by(
        Incident.created_at.desc()
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    return jsonify({
        "success": True,
        "data": [
            incident_response(item)
            for item in pagination.items
        ],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages
        }
    }), 200


# DASHBOARD STATISTICS
@incident_bp.get("/stats")
@login_required
def stats():

    total = db.session.query(func.count(Incident.id)).scalar() or 0

    by_status = dict(
        db.session.query(Incident.status, func.count(Incident.id))
        .group_by(Incident.status).all()
    )

    critical = (
        db.session.query(func.count(Incident.id))
        .filter(Incident.severity == "critical").scalar() or 0
    )

    resolved = by_status.get("resolved", 0) + by_status.get("closed", 0)

    return jsonify({
        "success": True,
        "stats": {
            "total": total,
            "active": total - resolved,
            "resolved": resolved,
            "critical": critical,
            "by_status": by_status
        }
    }), 200


# INCIDENT DETAILS
@incident_bp.get("/<int:incident_id>")
@login_required
def details(incident_id):

    incident = get_incident(incident_id)

    if not incident:
        return jsonify({
            "success": False,
            "message": "Incident not found."
        }), 404

    result = incident_response(incident)

    result["actions"] = [
        {
            "id": action.id,
            "engineer_id": action.engineer_id,
            "engineer_name": (
                action.engineer.name if action.engineer else None
            ),
            "action_description": action.action_description,
            "outcome": action.outcome,
            "actual_result": action.actual_result,
            "created_at": action.created_at.isoformat()
        }
        for action in incident.actions
    ]

    result["logs"] = [
        {
            "id": log.id,
            "log_message": log.log_message,
            "log_level": log.log_level,
            "timestamp": log.timestamp.isoformat()
        }
        for log in incident.logs
    ]

    return jsonify({
        "success": True,
        "incident": result
    }), 200


# UPDATE INCIDENT
@incident_bp.put("/<int:incident_id>")
@login_required
def update(incident_id):

    incident = get_incident(incident_id)

    if not incident:
        return jsonify({
            "success": False,
            "message": "Incident not found."
        }), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON data is required."
        }), 400

    allowed = {
        "title",
        "service_name",
        "description",
        "severity",
        "priority",
        "error_message",
        "system_logs",
        "verified_root_cause",
        "resolution_summary"
    }

    for field, value in data.items():

        if field not in allowed:
            return jsonify({
                "success": False,
                "message": "Field '{}' cannot be updated here.".format(field)
            }), 400

        if field in {"title", "service_name", "description"}:
            if not isinstance(value, str) or not value.strip():
                return jsonify({
                    "success": False,
                    "message": "{} cannot be empty.".format(field)
                }), 400

        if field in {"error_message", "system_logs", "verified_root_cause",
                     "resolution_summary"}:
            if value is not None and not isinstance(value, str):
                return jsonify({
                    "success": False,
                    "message": "{} must be text.".format(field)
                }), 400

        if field == "severity" and value not in VALID_SEVERITIES:
            return jsonify({
                "success": False,
                "message": "Invalid severity."
            }), 400

        if field == "priority" and value not in VALID_PRIORITIES:
            return jsonify({
                "success": False,
                "message": "Invalid priority."
            }), 400

        if field in {"title", "service_name"}:
            max_length = 200 if field == "title" else 120

            if len(value.strip()) > max_length:
                return jsonify({
                    "success": False,
                    "message": "{} exceeds its maximum length.".format(field)
                }), 400

    try:
        for field, value in data.items():
            setattr(
                incident,
                field,
                value.strip() if isinstance(value, str) else value
            )

        add_incident_log(
            incident.id,
            "Incident details updated.",
            "INFO"
        )

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Incident updated successfully.",
            "incident": incident_response(incident)
        }), 200

    except Exception:
        db.session.rollback()
        raise


# ASSIGN ENGINEER
@incident_bp.post("/<int:incident_id>/assign")
@login_required
def assign_engineer(incident_id):

    incident = get_incident(incident_id)

    if not incident:
        return jsonify({
            "success": False,
            "message": "Incident not found."
        }), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON data is required."
        }), 400

    engineer_id = data.get("engineer_id")

    if isinstance(engineer_id, bool) or not isinstance(engineer_id, int):
        return jsonify({
            "success": False,
            "message": "A valid engineer ID is required."
        }), 400

    engineer = validate_engineer(engineer_id)

    if engineer is False:
        return jsonify({
            "success": False,
            "message": "Active engineer not found."
        }), 404

    incident.assigned_engineer_id = engineer.id

    add_incident_log(
        incident.id,
        "Incident assigned to {}.".format(engineer.name),
        "INFO"
    )

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Engineer assigned successfully.",
        "incident": incident_response(incident)
    }), 200


# CHANGE STATUS
@incident_bp.patch("/<int:incident_id>/status")
@login_required
def change_status(incident_id):

    incident = get_incident(incident_id)

    if not incident:
        return jsonify({
            "success": False,
            "message": "Incident not found."
        }), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON data is required."
        }), 400

    status = data.get("status")

    if status not in VALID_STATUSES:
        return jsonify({
            "success": False,
            "message": "Invalid status."
        }), 400

    update_incident_status(incident, status)

    return jsonify({
        "success": True,
        "message": "Incident status updated.",
        "incident": incident_response(incident)
    }), 200


# RECORD TROUBLESHOOTING ACTION
@incident_bp.post("/<int:incident_id>/actions")
@login_required
def add_action(incident_id):

    incident = get_incident(incident_id)

    if not incident:
        return jsonify({
            "success": False,
            "message": "Incident not found."
        }), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON data is required."
        }), 400

    description = data.get("action_description")

    if not isinstance(description, str) or not description.strip():
        return jsonify({
            "success": False,
            "message": "Action description is required."
        }), 400

    outcome = data.get("outcome", "attempted")

    if outcome not in VALID_ACTION_OUTCOMES:
        return jsonify({
            "success": False,
            "message": "Invalid action outcome."
        }), 400

    action = record_action(
        incident,
        current_user.id,
        {
            "action_description": description.strip(),
            "outcome": outcome,
            "actual_result": data.get("actual_result")
        }
    )

    return jsonify({
        "success": True,
        "message": "Troubleshooting action recorded.",
        "action": {
            "id": action.id,
            "incident_id": action.incident_id,
            "action_description": action.action_description,
            "outcome": action.outcome,
            "actual_result": action.actual_result
        }
    }), 201


# ADD INCIDENT LOG
@incident_bp.post("/<int:incident_id>/logs")
@login_required
def add_log(incident_id):

    incident = get_incident(incident_id)

    if not incident:
        return jsonify({
            "success": False,
            "message": "Incident not found."
        }), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON data is required."
        }), 400

    message = data.get("log_message")
    level = data.get("log_level", "INFO")

    if not isinstance(message, str) or not message.strip():
        return jsonify({
            "success": False,
            "message": "Log message is required."
        }), 400

    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        return jsonify({
            "success": False,
            "message": "Invalid log level."
        }), 400

    add_incident_log(
        incident.id,
        message.strip(),
        level
    )

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Incident log added successfully."
    }), 201


# RESOLVE INCIDENT
@incident_bp.post("/<int:incident_id>/resolve")
@login_required
def resolve(incident_id):

    incident = get_incident(incident_id)

    if not incident:
        return jsonify({
            "success": False,
            "message": "Incident not found."
        }), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON data is required."
        }), 400

    summary = data.get("resolution_summary")
    root_cause = data.get("verified_root_cause")

    if not isinstance(summary, str) or not summary.strip():
        return jsonify({
            "success": False,
            "message": "Resolution summary is required."
        }), 400

    if root_cause is not None and (
        not isinstance(root_cause, str) or not root_cause.strip()
    ):
        return jsonify({
            "success": False,
            "message": "Verified root cause must be a non-empty string."
        }), 400

    incident.resolution_summary = summary.strip()

    if root_cause is not None:
        incident.verified_root_cause = root_cause.strip()

    update_incident_status(incident, "resolved")

    # Save the experience to long-term memory (never blocks or fails the request).
    try:
        memory_service.retain(
            memory_service.incident_to_memory_text(incident),
            document_id="incident-{}".format(incident.id),
            context="Resolved incident"
        )
    except Exception:
        current_app.logger.exception("Could not retain incident memory")

    return jsonify({
        "success": True,
        "message": "Incident resolved successfully.",
        "incident": incident_response(incident)
    }), 200


# DELETE INCIDENT - ADMIN ONLY
@incident_bp.delete("/<int:incident_id>")
@login_required
def delete_incident(incident_id):

    if current_user.role != "admin":
        return jsonify({
            "success": False,
            "message": "Administrator access required."
        }), 403

    incident = get_incident(incident_id)

    if not incident:
        return jsonify({
            "success": False,
            "message": "Incident not found."
        }), 404

    db.session.delete(incident)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Incident deleted successfully."
    }), 200