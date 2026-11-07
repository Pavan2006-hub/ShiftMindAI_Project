from datetime import datetime
from database.db import db


class Incident(db.Model):

    __tablename__ = "incidents"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(
        db.String(200),
        nullable=False
    )

    service_name = db.Column(
        db.String(120),
        nullable=False,
        index=True
    )

    description = db.Column(
        db.Text,
        nullable=False
    )

    severity = db.Column(
        db.String(30),
        nullable=False,
        default="medium",
        index=True
    )
    priority = db.Column(
        db.String(20),
        nullable=False,
        default="medium",
        index=True
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="open",
        index=True
    )

    error_message = db.Column(db.Text)

    system_logs = db.Column(db.Text)

    assigned_engineer_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Only store a root cause after it has been verified.
    verified_root_cause = db.Column(db.Text)

    resolution_summary = db.Column(db.Text)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    resolved_at = db.Column(db.DateTime)

    assigned_engineer = db.relationship(
        "User",
        back_populates="assigned_incidents",
        foreign_keys=[assigned_engineer_id]
    )

    actions = db.relationship(
        "IncidentAction",
        back_populates="incident",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="IncidentAction.created_at"
    )

    logs = db.relationship(
        "IncidentLog",
        back_populates="incident",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="IncidentLog.timestamp"
    )

    def __repr__(self):
        return f"<Incident {self.id}: {self.title}>"
