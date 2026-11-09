
import re
import secrets
import smtplib

from datetime import datetime, timedelta
from email.message import EmailMessage

from flask import session
from werkzeug.security import generate_password_hash, check_password_hash

from models.email_otp import EmailOTP
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_
from database.db import db
from extensions import bcrypt
from models.user import User

auth_bp = Blueprint("auth", __name__)


def validate_email(email):
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    return bool(re.match(pattern, email))


def user_response(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active
    }


# CSRF token endpoint
@auth_bp.get("/csrf")
def get_csrf_token():
    from flask_wtf.csrf import generate_csrf

    return jsonify({
        "success": True,
        "csrf_token": generate_csrf()
    }), 200


# Engineer registration
@auth_bp.post("/register")
def register():

    # Only admins may create accounts unless ALLOW_PUBLIC_REGISTRATION=true.
    if not current_app.config.get("ALLOW_PUBLIC_REGISTRATION"):
        if not current_user.is_authenticated:
            return jsonify({
                "success": False,
                "message": "Authentication required."
            }), 401

        if current_user.role != "admin":
            return jsonify({
                "success": False,
                "message": "Administrator access required."
            }), 403

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON data is required."
        }), 400

    name = str(data.get("name") or "").strip()
    email = str(data.get("email") or "").strip().lower()
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({
            "success": False,
            "message": "Name, email and password are required."
        }), 400

    if len(name) > 120:
        return jsonify({
            "success": False,
            "message": "Name must not exceed 120 characters."
        }), 400

    if not validate_email(email) or len(email) > 150:
        return jsonify({
            "success": False,
            "message": "Enter a valid email address."
        }), 400

    if not isinstance(password, str) or len(password) < 8:
        return jsonify({
            "success": False,
            "message": "Password must contain at least 8 characters."
        }), 400

    if len(password) > 72:
        return jsonify({
            "success": False,
            "message": "Password must not exceed 72 bytes of input."
        }), 400

    existing_user = User.query.filter_by(email=email).first()

    if existing_user:
        return jsonify({
            "success": False,
            "message": "An account with this email already exists."
        }), 409

    # Public registration always creates an engineer.
    # Never accept role from the request.
    hashed_password = bcrypt.generate_password_hash(
        password
    ).decode("utf-8")

    new_user = User(
        name=name,
        email=email,
        password_hash=hashed_password,
        role="engineer"
    )

    try:
        db.session.add(new_user)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Engineer account created successfully.",
            "user": user_response(new_user)
        }), 201

    except Exception:
        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Unable to create the account."
        }), 500


# Login
# Login - password verification followed by email OTP
@auth_bp.post("/login")
def login():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON data is required."
        }), 400

    email = str(data.get("email") or "").strip().lower()
    password = data.get("password")

    if not email or not isinstance(password, str) or not password:
        return jsonify({
            "success": False,
            "message": "Email and password are required."
        }), 400

    user = User.query.filter_by(email=email).first()

    if (
        not user
        or not bcrypt.check_password_hash(
            user.password_hash,
            password
        )
    ):
        return jsonify({
            "success": False,
            "message": "Invalid email or password."
        }), 401

    if not user.is_active:
        return jsonify({
            "success": False,
            "message": "Your account is inactive."
        }), 403

    # Remove any previous pending challenge for this browser session.
    old_challenge_id = session.pop("otp_challenge_id", None)

    if old_challenge_id:
        old_challenge = EmailOTP.query.filter_by(
            challenge_id=old_challenge_id,
            used_at=None
        ).first()

        if old_challenge:
            db.session.delete(old_challenge)
            db.session.commit()

    # In testing mode without explicit OTP testing, authenticate immediately.
    if current_app.config.get("TESTING") and not current_app.config.get("OTP_ENABLED_IN_TESTING", False):
        login_user(user, remember=False, fresh=True)
        return jsonify({
            "success": True,
            "message": "Login successful.",
            "user": user_response(user),
            "redirect": "/dashboard"
        }), 200

    # Do not authenticate the user before OTP verification.
    if current_user.is_authenticated:
        logout_user()

    try:
        create_and_send_otp(user)

        return jsonify({
            "success": True,
            "otp_required": True,
            "message": "A verification code has been sent to your registered email address.",
            "redirect": "/verify-otp"
        }), 200

    except Exception:
        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Unable to send the verification email. Please try again later."
        }), 503



def get_otp_setting(name, default):
    """Read an integer OTP setting safely."""
    try:
        return int(current_app.config.get(name, default))
    except (TypeError, ValueError):
        return default


def send_otp_email(email, name, otp):
    """Send the login OTP using the configured Gmail SMTP account."""

    mail_server = current_app.config.get("MAIL_SERVER", "smtp.gmail.com")
    mail_port = int(current_app.config.get("MAIL_PORT", 587))
    mail_username = current_app.config.get("MAIL_USERNAME")
    mail_password = current_app.config.get("MAIL_PASSWORD")
    mail_sender = current_app.config.get("MAIL_DEFAULT_SENDER") or mail_username

    if not mail_username or not mail_password or not mail_sender:
        raise RuntimeError("Gmail SMTP settings are not configured.")

    message = EmailMessage()
    message["Subject"] = "Your ShiftMind AI Login Verification Code"
    message["From"] = mail_sender
    message["To"] = email

    expiry_minutes = get_otp_setting("OTP_EXPIRY_MINUTES", 5)

    message.set_content(
        "Hello {name},\n\n"
        "Your ShiftMind AI login verification code is:\n\n"
        "{otp}\n\n"
        "This code expires in {expiry} minutes.\n"
        "Do not share this code with anyone.\n\n"
        "If you did not attempt to log in, you can ignore this email.\n\n"
        "Regards,\n"
        "ShiftMind AI Security Team".format(
            name=name,
            otp=otp,
            expiry=expiry_minutes
        )
    )

    use_tls = current_app.config.get("MAIL_USE_TLS", True)
    if isinstance(use_tls, str):
        use_tls = use_tls.strip().lower() in ("true", "1", "yes", "on")

    with smtplib.SMTP(mail_server, mail_port, timeout=20) as server:
        if use_tls:
            server.starttls()

        server.login(mail_username, mail_password)
        server.send_message(message)


def create_and_send_otp(user):
    """Create a new OTP challenge and email its code."""

    otp = str(secrets.randbelow(900000) + 100000)
    challenge_id = secrets.token_urlsafe(32)

    expiry_minutes = get_otp_setting("OTP_EXPIRY_MINUTES", 5)

    challenge = EmailOTP(
        challenge_id=challenge_id,
        user_id=user.id,
        otp_hash=generate_password_hash(otp),
        expires_at=datetime.utcnow() + timedelta(minutes=expiry_minutes),
        attempts=0,
        resend_count=0,
        created_at=datetime.utcnow(),
        last_sent_at=datetime.utcnow()
    )

    db.session.add(challenge)
    db.session.commit()

    try:
        send_otp_email(user.email, user.name, otp)
    except Exception:
        current_app.logger.exception("Unable to send login verification email.")
        db.session.delete(challenge)
        db.session.commit()
        raise

    session["otp_challenge_id"] = challenge_id

    return challenge

# Verify email OTP
@auth_bp.post("/verify-otp")
def verify_otp():

    challenge_id = session.get("otp_challenge_id")

    if not challenge_id:
        return jsonify({
            "success": False,
            "message": "Your verification session has expired. Please log in again."
        }), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON data is required."
        }), 400

    otp = str(data.get("otp") or "").strip()

    if not re.fullmatch(r"\d{6}", otp):
        return jsonify({
            "success": False,
            "message": "Enter a valid six-digit verification code."
        }), 400

    challenge = EmailOTP.query.filter_by(
        challenge_id=challenge_id,
        used_at=None
    ).first()

    if not challenge:
        session.pop("otp_challenge_id", None)

        return jsonify({
            "success": False,
            "message": "Verification session not found. Please log in again."
        }), 401

    if datetime.utcnow() >= challenge.expires_at:
        db.session.delete(challenge)
        db.session.commit()
        session.pop("otp_challenge_id", None)

        return jsonify({
            "success": False,
            "message": "Verification code expired. Please log in again."
        }), 401

    max_attempts = get_otp_setting("OTP_MAX_ATTEMPTS", 5)

    if challenge.attempts >= max_attempts:
        db.session.delete(challenge)
        db.session.commit()
        session.pop("otp_challenge_id", None)

        return jsonify({
            "success": False,
            "message": "Maximum verification attempts reached. Please log in again."
        }), 429

    challenge.attempts += 1

    if not check_password_hash(challenge.otp_hash, otp):
        remaining = max(0, max_attempts - challenge.attempts)
        db.session.commit()

        return jsonify({
            "success": False,
            "message": "Incorrect verification code.",
            "remaining_attempts": remaining
        }), 401

    user = db.session.get(User, challenge.user_id)

    if not user or not user.is_active:
        db.session.delete(challenge)
        db.session.commit()
        session.pop("otp_challenge_id", None)

        return jsonify({
            "success": False,
            "message": "This account is unavailable or inactive."
        }), 403

    # Mark OTP as used before authenticating.
    challenge.used_at = datetime.utcnow()
    db.session.commit()

    session.pop("otp_challenge_id", None)

    login_user(user, remember=False, fresh=True)

    return jsonify({
        "success": True,
        "message": "Email verified. Login successful.",
        "user": user_response(user),
        "redirect": "/dashboard"
    }), 200

# Resend email OTP
@auth_bp.post("/resend-otp")
def resend_otp():

    challenge_id = session.get("otp_challenge_id")

    if not challenge_id:
        return jsonify({
            "success": False,
            "message": "Verification session expired. Please log in again."
        }), 401

    challenge = EmailOTP.query.filter_by(
        challenge_id=challenge_id,
        used_at=None
    ).first()

    if not challenge:
        session.pop("otp_challenge_id", None)

        return jsonify({
            "success": False,
            "message": "Verification session not found. Please log in again."
        }), 401

    if datetime.utcnow() >= challenge.expires_at:
        db.session.delete(challenge)
        db.session.commit()
        session.pop("otp_challenge_id", None)

        return jsonify({
            "success": False,
            "message": "Verification session expired. Please log in again."
        }), 401

    cooldown = get_otp_setting("OTP_RESEND_SECONDS", 60)
    max_resends = get_otp_setting("OTP_MAX_RESENDS", 5)

    elapsed = (datetime.utcnow() - challenge.last_sent_at).total_seconds()

    if elapsed < cooldown:
        wait_seconds = max(1, int(cooldown - elapsed))

        return jsonify({
            "success": False,
            "message": "Please wait before requesting another code.",
            "retry_after": wait_seconds
        }), 429

    if challenge.resend_count >= max_resends:
        return jsonify({
            "success": False,
            "message": "Maximum resend limit reached. Please log in again."
        }), 429

    user = db.session.get(User, challenge.user_id)

    if not user or not user.is_active:
        db.session.delete(challenge)
        db.session.commit()
        session.pop("otp_challenge_id", None)

        return jsonify({
            "success": False,
            "message": "This account is unavailable or inactive."
        }), 403

    otp = str(secrets.randbelow(900000) + 100000)
    expiry_minutes = get_otp_setting("OTP_EXPIRY_MINUTES", 5)

    challenge.otp_hash = generate_password_hash(otp)
    challenge.expires_at = datetime.utcnow() + timedelta(minutes=expiry_minutes)
    challenge.attempts = 0
    challenge.resend_count += 1
    challenge.last_sent_at = datetime.utcnow()

    db.session.commit()

    try:
        send_otp_email(user.email, user.name, otp)

        return jsonify({
            "success": True,
            "message": "A new verification code has been sent to your email."
        }), 200

    except Exception:
        current_app.logger.exception("Unable to resend login verification email.")

        db.session.delete(challenge)
        db.session.commit()
        session.pop("otp_challenge_id", None)

        return jsonify({
            "success": False,
            "message": "Unable to send a new verification code. Please log in again."
        }), 503

# Logout
@auth_bp.post("/logout")
@login_required
def logout():

    logout_user()

    return jsonify({
        "success": True,
        "message": "Logout successful."
    }), 200


# Current logged-in user
@auth_bp.get("/me")
@login_required
def current_user_profile():

    return jsonify({
        "success": True,
        "user": user_response(current_user)
    }), 200


# Example admin-only endpoint
@auth_bp.get("/admin-check")
@login_required
def admin_check():

    if current_user.role != "admin":
        return jsonify({
            "success": False,
            "message": "Administrator access required."
        }), 403

    return jsonify({
        "success": True,
        "message": "Administrator access verified."
    }), 200


# Active engineers (used by assignment drop-downs)
@auth_bp.get("/engineers")
@login_required
def list_engineers():

    users = User.query.filter(
        User.is_active.is_(True),
        User.role.in_(["engineer", "admin"])
    ).order_by(User.name).all()

    return jsonify({
        "success": True,
        "data": [
            {"id": u.id, "name": u.name, "role": u.role}
            for u in users
        ]
    }), 200


# Change own password
@auth_bp.post("/change-password")
@login_required
def change_password():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON data is required."
        }), 400

    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not isinstance(current_password, str) or not isinstance(new_password, str):
        return jsonify({
            "success": False,
            "message": "Current and new password are required."
        }), 400

    if not bcrypt.check_password_hash(current_user.password_hash, current_password):
        return jsonify({
            "success": False,
            "message": "Current password is incorrect."
        }), 400

    if len(new_password) < 8 or len(new_password) > 72:
        return jsonify({
            "success": False,
            "message": "New password must contain 8 to 72 characters."
        }), 400

    current_user.password_hash = bcrypt.generate_password_hash(
        new_password
    ).decode("utf-8")
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Password changed successfully."
    }), 200
# ---------------------------------------------------------
# ADMIN-ONLY ENGINEER MANAGEMENT
# ---------------------------------------------------------

def admin_required_response():
    """Return an error response unless the current user is an admin."""
    if not current_user.is_authenticated:
        return jsonify({
            "success": False,
            "message": "Authentication required."
        }), 401

    if current_user.role != "admin":
        return jsonify({
            "success": False,
            "message": "Administrator access required."
        }), 403

    return None


def engineer_response(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": (
            user.created_at.isoformat()
            if user.created_at else None
        )
    }


# List and create engineers (Admin only)
@auth_bp.route("/admin/engineers", methods=["GET", "POST"])
@login_required
def manage_engineers():

    denied = admin_required_response()
    if denied:
        return denied

    # ==========================================
    # GET: LIST AND SEARCH ENGINEERS
    # ==========================================
    if request.method == "GET":

        search = request.args.get("search", "").strip()

        query = User.query.filter_by(role="engineer")

        # Search by engineer name or email
        if search:
            query = query.filter(
                or_(
                    User.name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%")
                )
            )

        engineers = query.order_by(
            User.created_at.desc()
        ).all()

        return jsonify({
            "success": True,
            "engineers": [
                engineer_response(engineer)
                for engineer in engineers
            ]
        }), 200

    # ==========================================
    # POST: CREATE NEW ENGINEER
    # ==========================================

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON data is required."
        }), 400

    name = str(data.get("name") or "").strip()
    email = str(data.get("email") or "").strip().lower()
    password = data.get("password")

    # Validate required fields
    if not name or not email or not password:
        return jsonify({
            "success": False,
            "message": "Name, email and password are required."
        }), 400

    # Validate name
    if len(name) > 120:
        return jsonify({
            "success": False,
            "message": "Name must not exceed 120 characters."
        }), 400

    # Validate email
    if len(email) > 150 or not validate_email(email):
        return jsonify({
            "success": False,
            "message": "Enter a valid email address."
        }), 400

    # Validate password
    if (
        not isinstance(password, str)
        or len(password) < 8
        or len(password.encode("utf-8")) > 72
    ):
        return jsonify({
            "success": False,
            "message": (
                "Password must be at least 8 characters "
                "and no more than 72 bytes."
            )
        }), 400

    # Check duplicate email
    if User.query.filter_by(email=email).first():
        return jsonify({
            "success": False,
            "message": "An account with this email already exists."
        }), 409

    try:

        engineer = User(
            name=name,
            email=email,
            password_hash=bcrypt.generate_password_hash(
                password
            ).decode("utf-8"),
            role="engineer",
            is_active=True
        )

        db.session.add(engineer)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Engineer created successfully.",
            "engineer": engineer_response(engineer)
        }), 201

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Error while creating engineer"
        )

        return jsonify({
            "success": False,
            "message": "Unable to create engineer."
        }), 500

# Edit engineer details or account status
@auth_bp.route("/admin/engineers/<int:engineer_id>", methods=["PATCH"])
@login_required
def update_engineer(engineer_id):

    denied = admin_required_response()
    if denied:
        return denied

    engineer = User.query.filter_by(
        id=engineer_id,
        role="engineer"
    ).first()

    if not engineer:
        return jsonify({
            "success": False,
            "message": "Engineer not found."
        }), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON data is required."
        }), 400

    name = str(data.get("name", engineer.name)).strip()
    email = str(data.get("email", engineer.email)).strip().lower()

    if not name or len(name) > 120:
        return jsonify({
            "success": False,
            "message": "Name is required and must not exceed 120 characters."
        }), 400

    if not validate_email(email) or len(email) > 150:
        return jsonify({
            "success": False,
            "message": "Enter a valid email address."
        }), 400

    duplicate = User.query.filter(
        User.email == email,
        User.id != engineer.id
    ).first()

    if duplicate:
        return jsonify({
            "success": False,
            "message": "Another account already uses this email."
        }), 409

    if "is_active" in data and not isinstance(data["is_active"], bool):
        return jsonify({
            "success": False,
            "message": "Account status must be true or false."
        }), 400

    try:
        engineer.name = name
        engineer.email = email

        if "is_active" in data:
            engineer.is_active = data["is_active"]

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Engineer updated successfully.",
            "engineer": engineer_response(engineer)
        }), 200

    except Exception:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": "Unable to update engineer."
        }), 500


# Permanently delete an engineer only when no linked records exist
@auth_bp.route("/admin/engineers/<int:engineer_id>", methods=["DELETE"])
@login_required
def delete_engineer(engineer_id):

    denied = admin_required_response()
    if denied:
        return denied

    engineer = User.query.filter_by(
        id=engineer_id,
        role="engineer"
    ).first()

    if not engineer:
        return jsonify({
            "success": False,
            "message": "Engineer not found."
        }), 404

    try:
        has_linked_records = any([
            bool(engineer.assigned_incidents),
            bool(engineer.incident_actions),
            bool(engineer.outgoing_handovers),
            bool(engineer.incoming_handovers),
            bool(engineer.chat_sessions)
        ])

        if has_linked_records:
            return jsonify({
                "success": False,
                "message": (
                    "This engineer has linked incident, handover, action, "
                    "or chat records. Permanent deletion is blocked. "
                    "Deactivate the account instead."
                )
            }), 409

        db.session.delete(engineer)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Engineer deleted successfully."
        }), 200

    except Exception:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": "Unable to delete engineer."
        }), 500
