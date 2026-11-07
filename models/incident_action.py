from datetime import datetime
from database.db import db


class IncidentAction(db.Model):

    __tablename__ = "incident_actions"

    id = db.Column(db.Integer, primary_key=True)

    incident_id = db.Column(
        db.Integer,
        db.ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    engineer_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    action_description = db.Column(
        db.Text,
        nullable=False
    )

    outcome = db.Column(
        db.String(30),
        nullable=False,
        default="attempted"
    )

    actual_result = db.Column(db.Text)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    incident = db.relationship(
        "Incident",
        back_populates="actions"
    )

    engineer = db.relationship(
        "User",
        back_populates="incident_actions"
    )

    def __repr__(self):
        return f"<IncidentAction {self.id}: {self.outcome}>"
