
import re

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_user, logout_user, login_required, current_user

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

    if current_user.is_authenticated:
        logout_user()

    login_user(user, remember=False, fresh=True)

    return jsonify({
        "success": True,
        "message": "Login successful.",
        "user": user_response(user)
    }), 200


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
