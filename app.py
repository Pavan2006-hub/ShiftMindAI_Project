
import os
from pathlib import Path
from datetime import datetime

from flask import (
    Flask,
    jsonify,
    redirect,
    request,
    url_for,
    render_template,
    session
)

from flask_wtf.csrf import CSRFError

from config import get_config
from database.db import db, migrate
from utils.logger import configure_logging
from extensions import bcrypt, login_manager, csrf


def create_app(config_object=None):

    app = Flask(
        __name__,
        template_folder="frontend/templates",
        static_folder="frontend/static",
        static_url_path="/static",
        instance_relative_config=True
    )

    # -------------------------------------------------
    # LOAD CONFIGURATION
    # -------------------------------------------------

    app.config.from_object(config_object or get_config())

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------
    # GMAIL SMTP CONFIGURATION
    # -------------------------------------------------

    app.config["MAIL_SERVER"] = (
        app.config.get("MAIL_SERVER")
        or os.getenv("MAIL_SERVER", "smtp.gmail.com")
    )

    app.config["MAIL_PORT"] = int(
        app.config.get("MAIL_PORT")
        or os.getenv("MAIL_PORT", "587")
    )

    app.config["MAIL_USE_TLS"] = (
        str(
            app.config.get("MAIL_USE_TLS", os.getenv("MAIL_USE_TLS", "true"))
        ).lower() == "true"
    )

    app.config["MAIL_USERNAME"] = (
        app.config.get("MAIL_USERNAME")
        or os.getenv("MAIL_USERNAME", "")
    )

    app.config["MAIL_PASSWORD"] = (
        app.config.get("MAIL_PASSWORD")
        or os.getenv("MAIL_PASSWORD", "")
    )

    app.config["MAIL_DEFAULT_SENDER"] = (
        app.config.get("MAIL_DEFAULT_SENDER")
        or os.getenv(
            "MAIL_DEFAULT_SENDER",
            app.config["MAIL_USERNAME"]
        )
    )

    # -------------------------------------------------
    # OTP CONFIGURATION
    # -------------------------------------------------

    app.config["OTP_EXPIRY_MINUTES"] = int(
        app.config.get("OTP_EXPIRY_MINUTES", 5)
    )

    app.config["OTP_MAX_ATTEMPTS"] = int(
        app.config.get("OTP_MAX_ATTEMPTS", 5)
    )

    app.config["OTP_RESEND_SECONDS"] = int(
        app.config.get("OTP_RESEND_SECONDS", 60)
    )

    app.config["OTP_MAX_RESENDS"] = int(
        app.config.get("OTP_MAX_RESENDS", 5)
    )

    # -------------------------------------------------
    # LOGGING
    # -------------------------------------------------

    configure_logging(app)

    # -------------------------------------------------
    # DATABASE AND MIGRATIONS
    # -------------------------------------------------

    db.init_app(app)
    migrate.init_app(app, db)

    # -------------------------------------------------
    # AUTHENTICATION EXTENSIONS
    # -------------------------------------------------

    bcrypt.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.session_protection = "strong"
    login_manager.login_view = "web.login_page"

    # -------------------------------------------------
    # IMPORT MODELS
    # -------------------------------------------------

    import models  # noqa: F401

    from models.user import User
    from models.email_otp import EmailOTP

    # -------------------------------------------------
    # FLASK-LOGIN USER LOADER
    # -------------------------------------------------

    @login_manager.user_loader
    def load_user(user_id):

        try:
            return db.session.get(User, int(user_id))

        except (ValueError, TypeError):
            return None

    # -------------------------------------------------
    # UNAUTHORIZED HANDLER
    # -------------------------------------------------

    @login_manager.unauthorized_handler
    def unauthorized():

        if request.path.startswith("/api/"):

            return jsonify({
                "success": False,
                "message": "Authentication required."
            }), 401

        return redirect(url_for("web.login_page"))

    # -------------------------------------------------
    # REGISTER AUTHENTICATION API
    # -------------------------------------------------

    from routes.auth_routes import auth_bp

    app.register_blueprint(
        auth_bp,
        url_prefix="/api/auth"
    )

    # -------------------------------------------------
    # REGISTER INCIDENT API
    # -------------------------------------------------

    from routes.incident_routes import incident_bp

    app.register_blueprint(
        incident_bp,
        url_prefix="/api/incidents"
    )

    # -------------------------------------------------
    # REGISTER AI API
    # -------------------------------------------------

    from routes.ai_routes import ai_bp, memory_bp

    app.register_blueprint(
        ai_bp,
        url_prefix="/api/ai"
    )

    app.register_blueprint(
        memory_bp,
        url_prefix="/api/memory"
    )

    # -------------------------------------------------
    # REGISTER HANDOVER API
    # -------------------------------------------------

    from routes.handover_routes import handover_bp

    app.register_blueprint(
        handover_bp,
        url_prefix="/api/handovers"
    )

    # -------------------------------------------------
    # REGISTER FRONTEND PAGES
    # -------------------------------------------------

    from routes.web_routes import web_bp

    app.register_blueprint(web_bp)

    # -------------------------------------------------
    # OTP VERIFICATION PAGE
    # -------------------------------------------------

    @app.get("/verify-otp")
    def verify_otp_page():

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

    # -------------------------------------------------
    # HOME
    # -------------------------------------------------

    @app.route("/", methods=["GET"])
    def home():

        return redirect(url_for("web.dashboard"))

    # -------------------------------------------------
    # HEALTH ENDPOINTS
    # -------------------------------------------------

    def health_payload():

        return jsonify({
            "success": True,
            "message": "ShiftMind AI backend is running",
            "data": {
                "status": "healthy",
                "phase": 5
            }
        }), 200

    app.add_url_rule(
        "/health",
        "health",
        health_payload,
        methods=["GET"]
    )

    app.add_url_rule(
        "/api/health",
        "api_health",
        health_payload,
        methods=["GET"]
    )

    # -------------------------------------------------
    # CSRF ERROR HANDLER
    # -------------------------------------------------

    @app.errorhandler(CSRFError)
    def csrf_error(error):

        return jsonify({
            "success": False,
            "message": (
                "Security token missing or expired. "
                "Refresh the page and try again."
            ),
            "error": error.description
        }), 400

    # -------------------------------------------------
    # 404 ERROR
    # -------------------------------------------------

    @app.errorhandler(404)
    def not_found(error):

        return jsonify({
            "success": False,
            "message": "Resource not found",
            "error": "The requested endpoint does not exist"
        }), 404

    # -------------------------------------------------
    # 405 ERROR
    # -------------------------------------------------

    @app.errorhandler(405)
    def method_not_allowed(error):

        return jsonify({
            "success": False,
            "message": "Method not allowed",
            "error": "This endpoint does not support that HTTP method"
        }), 405

    # -------------------------------------------------
    # 413 ERROR
    # -------------------------------------------------

    @app.errorhandler(413)
    def too_large(error):

        return jsonify({
            "success": False,
            "message": "Request is too large",
            "error": "Reduce the size of the submitted data"
        }), 413

    # -------------------------------------------------
    # 500 ERROR
    # -------------------------------------------------

    @app.errorhandler(500)
    def internal_error(error):

        db.session.rollback()

        app.logger.exception(
            "Unhandled server error"
        )

        return jsonify({
            "success": False,
            "message": "An internal server error occurred",
            "error": "Please try again later"
        }), 500

    return app


# -----------------------------------------------------
# APPLICATION ENTRY POINT
# -----------------------------------------------------

if __name__ == "__main__":

    application = create_app()

    application.run(
        host=application.config.get("HOST", "127.0.0.1"),
        port=application.config.get("PORT", 5000),
        debug=application.config.get("DEBUG", False)
    )
