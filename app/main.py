"""
CareCloud Voice Agent — Flask Application
"""
import logging
import os
from flask import Flask, jsonify
from app.models import init_db
from app.routes import patients_bp
from app.vapi_handler import vapi_bp

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),                      # stdout
        logging.FileHandler("carecloud.log"),         # file
    ]
)
log = logging.getLogger("carecloud")


def create_app():
    app = Flask(__name__)

    # ── Blueprints ────────────────────────────────────────────────────────
    app.register_blueprint(patients_bp)
    app.register_blueprint(vapi_bp)

    # ── Health Check ──────────────────────────────────────────────────────
    @app.route("/", methods=["GET"])
    def health():
        return jsonify({"message": "CareCloud Voice Agent is Online"})

    # ── Global Error Handlers ─────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"data": None, "error": {"message": "Endpoint not found."}}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"data": None, "error": {"message": "Method not allowed."}}), 405

    @app.errorhandler(500)
    def internal_error(e):
        log.exception("Unhandled 500 error: %s", e)
        return jsonify({"data": None, "error": {"message": "Internal server error."}}), 500

    # ── Init DB ───────────────────────────────────────────────────────────
    with app.app_context():
        init_db()
        log.info("Database initialized.")

    return app
