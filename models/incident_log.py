from datetime import datetime
from database.db import db


class IncidentLog(db.Model):

    __tablename__ = "incident_logs"

    id = db.Column(db.Integer, primary_key=True)

    incident_id = db.Column(
        db.Integer,
        db.ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    log_message = db.Column(
        db.Text,
        nullable=False
    )

    log_level = db.Column(
        db.String(20),
        default="INFO"
    )

    timestamp = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    incident = db.relationship(
        "Incident",
        back_populates="logs"
    )

    def __repr__(self):
        return f"<IncidentLog {self.id}: {self.log_level}>"
