
from datetime import datetime

from database.db import db


class EmailOTP(db.Model):

    __tablename__ = "email_otp_verifications"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    challenge_id = db.Column(
        db.String(100),
        unique=True,
        nullable=False,
        index=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    otp_hash = db.Column(
        db.String(255),
        nullable=False
    )

    expires_at = db.Column(
        db.DateTime,
        nullable=False
    )

    attempts = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    resend_count = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    last_sent_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    used_at = db.Column(
        db.DateTime,
        nullable=True
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "email_otp_verifications",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )

    def __repr__(self):
        return f"<EmailOTP user_id={self.user_id}>"
