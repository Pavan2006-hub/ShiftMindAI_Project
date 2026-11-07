from datetime import datetime
from flask_login import UserMixin
from database.db import db


class User(UserMixin, db.Model):

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)

    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(
        db.String(30),
        nullable=False,
        default="engineer"
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    assigned_incidents = db.relationship(
        "Incident",
        back_populates="assigned_engineer",
        foreign_keys="Incident.assigned_engineer_id"
    )

    incident_actions = db.relationship(
        "IncidentAction",
        back_populates="engineer"
    )

    outgoing_handovers = db.relationship(
        "Handover",
        back_populates="outgoing_engineer",
        foreign_keys="Handover.outgoing_engineer_id"
    )

    incoming_handovers = db.relationship(
        "Handover",
        back_populates="incoming_engineer",
        foreign_keys="Handover.incoming_engineer_id"
    )

    chat_sessions = db.relationship(
        "ChatSession",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.email}>"
