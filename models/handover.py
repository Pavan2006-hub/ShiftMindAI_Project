from datetime import datetime
from database.db import db


class Handover(db.Model):

    __tablename__ = "handovers"

    id = db.Column(db.Integer, primary_key=True)

    outgoing_engineer_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    incoming_engineer_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    shift_start = db.Column(db.DateTime)

    shift_end = db.Column(db.DateTime)

    summary = db.Column(db.Text)

    active_incidents = db.Column(db.JSON, default=list)

    resolved_incidents = db.Column(db.JSON, default=list)

    successful_actions = db.Column(db.JSON, default=list)

    failed_actions = db.Column(db.JSON, default=list)

    verified_findings = db.Column(db.JSON, default=list)

    pending_tasks = db.Column(db.JSON, default=list)

    recommendations = db.Column(db.JSON, default=list)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    outgoing_engineer = db.relationship(
        "User",
        back_populates="outgoing_handovers",
        foreign_keys=[outgoing_engineer_id]
    )

    incoming_engineer = db.relationship(
        "User",
        back_populates="incoming_handovers",
        foreign_keys=[incoming_engineer_id]
    )

    def __repr__(self):
        return f"<Handover {self.id}>"
