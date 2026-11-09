from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, session
from flask_login import login_required, current_user

from database.db import db
from models.email_otp import EmailOTP

web_bp = Blueprint("web", __name__)


@web_bp.route("/login")
def login_page():

    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))

    return render_template("login.html")


# Email OTP verification page
@web_bp.route("/verify-otp")
def verify_otp_page():

    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))

    challenge_id = session.get("otp_challenge_id")

    if not challenge_id:
        return redirect(url_for("web.login_page"))

    challenge = EmailOTP.query.filter_by(
        challenge_id=challenge_id,
        used_at=None
    ).first()

    if not challenge:
        session.pop("otp_challenge_id", None)
        return redirect(url_for("web.login_page"))

    if challenge.expires_at <= datetime.utcnow():
        db.session.delete(challenge)
        db.session.commit()
        session.pop("otp_challenge_id", None)
        return redirect(url_for("web.login_page"))

    return render_template("verify_otp.html")


@web_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@web_bp.route("/incidents")
@login_required
def incidents():
    return render_template("incidents.html")


@web_bp.route("/incidents/create")
@login_required
def create_incident_page():
    return render_template("create_incident.html")


@web_bp.route("/incidents/<int:incident_id>")
@login_required
def incident_details(incident_id):
    return render_template(
        "incident_details.html",
        incident_id=incident_id
    )


@web_bp.route("/ai-analysis")
@login_required
def ai_analysis():
    return render_template("ai_analysis.html")


@web_bp.route("/ai-assistant")
@login_required
def ai_assistant():
    return render_template("ai_assistant.html")


@web_bp.route("/shift-handover")
@login_required
def shift_handover():
    return render_template("shift_handover.html")


@web_bp.route("/memory-explorer")
@login_required
def memory_explorer():
    return render_template("memory_explorer.html")


@web_bp.route("/settings")
@login_required
def settings():
    return render_template("settings.html")
