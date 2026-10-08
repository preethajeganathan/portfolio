import os
import html
import logging
from pathlib import Path

from dotenv import load_dotenv
import resend
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__, static_folder=None)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Required environment variables:
# RESEND_API_KEY=re_xxxxxxxxxxxxxxxxx
# RESEND_FROM_EMAIL=Portfolio <noreply@your-verified-domain.com>
# CONTACT_TO_EMAIL=your-email@example.com

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL")
CONTACT_TO_EMAIL = os.getenv("CONTACT_TO_EMAIL")

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


@app.get("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.post("/api/contact")
def contact():
    # Keep the API key on the server. Never put it in index.html.
    if not RESEND_API_KEY:
        logger.error("RESEND_API_KEY is not configured.")
        return jsonify({
            "success": False,
            "message": "Email service is not configured on the server."
        }), 500

    if not RESEND_FROM_EMAIL or not CONTACT_TO_EMAIL:
        logger.error("RESEND_FROM_EMAIL or CONTACT_TO_EMAIL is not configured.")
        return jsonify({
            "success": False,
            "message": "Email configuration is incomplete."
        }), 500

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip()
    subject = str(data.get("subject", "")).strip()
    message = str(data.get("message", "")).strip()

    # Match the frontend limits and reject incomplete requests.
    if not name or not email or not subject or not message:
        return jsonify({
            "success": False,
            "message": "All fields are required."
        }), 400

    if len(name) > 80:
        return jsonify({"success": False, "message": "Name is too long."}), 400

    if len(email) > 120:
        return jsonify({"success": False, "message": "Email is too long."}), 400

    if len(subject) > 120:
        return jsonify({"success": False, "message": "Subject is too long."}), 400

    if len(message) > 2000:
        return jsonify({"success": False, "message": "Message is too long."}), 400

    # Basic email validation. The browser already uses type="email",
    # but backend validation is still required.
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return jsonify({
            "success": False,
            "message": "Please provide a valid email address."
        }), 400

    safe_name = html.escape(name)
    safe_email = html.escape(email)
    safe_subject = html.escape(subject)
    safe_message = html.escape(message).replace("\n", "<br>")

    email_html = f"""
    <!doctype html>
    <html>
      <body style="font-family:Arial,sans-serif;line-height:1.6;color:#222;">
        <h2>New Portfolio Contact Message</h2>
        <p><strong>Name:</strong> {safe_name}</p>
        <p><strong>Email:</strong> {safe_email}</p>
        <p><strong>Subject:</strong> {safe_subject}</p>
        <hr>
        <p><strong>Message:</strong></p>
        <p>{safe_message}</p>
      </body>
    </html>
    """

    try:
        params = {
            "from": RESEND_FROM_EMAIL,
            "to": [CONTACT_TO_EMAIL],
            "reply_to": [email],
            "subject": f"Portfolio Contact: {subject}",
            "html": email_html,
        }

        result = resend.Emails.send(params)
        logger.info("Contact email sent successfully: %s", result)

        return jsonify({
            "success": True,
            "message": "Your message has been sent."
        }), 200

    except Exception:
        logger.exception("Failed to send contact email through Resend.")
        return jsonify({
            "success": False,
            "message": "Could not send the message right now."
        }), 500


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
