from pathlib import Path

from flask import Flask, jsonify, redirect, request, url_for
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

    # Load configuration
    app.config.from_object(config_object or get_config())

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # Configure logging
    configure_logging(app)

    # Initialize database and migrations
    db.init_app(app)
    migrate.init_app(app, db)

    # Initialize authentication extensions
    bcrypt.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.session_protection = "strong"

    # Import every model so SQLAlchemy and Flask-Migrate know all tables
    import models  # noqa: F401
    from models.user import User

    # Flask-Login user loader
    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None

    # Unauthorized: JSON for API calls, redirect to login for pages
    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return jsonify({
                "success": False,
                "message": "Authentication required."
            }), 401
        return redirect(url_for("web.login_page"))

    # Register APIs
    from routes.auth_routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    from routes.incident_routes import incident_bp
    app.register_blueprint(incident_bp, url_prefix="/api/incidents")

    from routes.ai_routes import ai_bp, memory_bp
    app.register_blueprint(ai_bp, url_prefix="/api/ai")
    app.register_blueprint(memory_bp, url_prefix="/api/memory")

    from routes.handover_routes import handover_bp
    app.register_blueprint(handover_bp, url_prefix="/api/handovers")

    # Register frontend pages
    from routes.web_routes import web_bp
    app.register_blueprint(web_bp)

    # Home: send people to the app
    @app.route("/", methods=["GET"])
    def home():
        return redirect(url_for("web.dashboard"))

    # Health endpoints
    def health_payload():
        return jsonify({
            "success": True,
            "message": "ShiftMind AI backend is running",
            "data": {"status": "healthy", "phase": 5}
        }), 200

    app.add_url_rule("/health", "health", health_payload, methods=["GET"])
    app.add_url_rule("/api/health", "api_health", health_payload, methods=["GET"])

    # Error handlers
    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return jsonify({
            "success": False,
            "message": "Security token missing or expired. Refresh the page and try again.",
            "error": error.description
        }), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "success": False,
            "message": "Resource not found",
            "error": "The requested endpoint does not exist"
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            "success": False,
            "message": "Method not allowed",
            "error": "This endpoint does not support that HTTP method"
        }), 405

    @app.errorhandler(413)
    def too_large(error):
        return jsonify({
            "success": False,
            "message": "Request is too large",
            "error": "Reduce the size of the submitted data"
        }), 413

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.exception("Unhandled server error")

        return jsonify({
            "success": False,
            "message": "An internal server error occurred",
            "error": "Please try again later"
        }), 500

    return app


if __name__ == "__main__":

    application = create_app()

    application.run(
        host=application.config.get("HOST", "127.0.0.1"),
        port=application.config.get("PORT", 5000),
        debug=application.config.get("DEBUG", False)
    )
