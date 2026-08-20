from flask import Flask, request, render_template, redirect, flash, url_for, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import time
import secrets
import hashlib
import smtplib

from email.message import EmailMessage

app = Flask(__name__)
app.secret_key = "secret123"

csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app)

DATABASE = "users.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(429)
def ratelimit_handler(e):
    return render_template("429.html"), 429


@app.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if not username or not email or not password:
            flash("All fields are required", "danger")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO users (username, email, password, created_at) VALUES (?, ?, ?, ?)",
                (username, email, hashed_password, int(time.time())),
            )
            conn.commit()
            flash("Account successfully created", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username or email already exists", "danger")
        finally:
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("Invalid username or password", "danger")
            return redirect(url_for("login"))

        conn = get_db()
        user = conn.execute(
            "SELECT id, password FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            flash("Login successful", "success")
            return redirect("https://youtube.com")
        else:
            flash("Invalid username or password", "danger")

    return render_template("login.html")


def send_reset_email(to_email, token):
    reset_link = f"http://127.0.0.1:5000/reset-password?token={token}"

    msg = EmailMessage()
    msg["Subject"] = "Password Reset Request"
    msg["From"] = "unitbaggy3@gmail.com"
    msg["To"] = to_email
    msg.set_content(
        f"""You requested a password reset.

Click the link below to reset your password:
{reset_link}

This link expires in 15 minutes.
"""
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(
            "unitbaggy3@gmail.com",
            "pdzy fphw zjkg zxoh",
        )
        server.send_message(msg)


@app.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgot_password():
    if request.method == "GET":
        return render_template("forgot-password.html")

    email = request.form.get("email")

    if not email:
        return jsonify({"message": "Invalid request"}), 400

    conn = get_db()
    user = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        (email,),
    ).fetchone()

    if user:
        token = secrets.token_urlsafe(32)
        hashed_token = hashlib.sha256(token.encode()).hexdigest()
        expiry = int(time.time()) + 900

        conn.execute(
            "UPDATE users SET reset_token = ?, reset_token_expiry = ? WHERE id = ?",
            (hashed_token, expiry, user["id"]),
        )
        conn.commit()
        send_reset_email(email, token)

    conn.close()

    return jsonify({"message": "If the email exists, a reset link has been sent."})


@app.route("/reset-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def reset_password():
    if request.method == "GET":
        token = request.args.get("token")
        if not token:
            return jsonify({"message": "Invalid request"}), 400
        return render_template("reset-password.html", token=token)

    token = request.form.get("token")
    new_password = request.form.get("new_password")

    if not token or not new_password:
        return jsonify({"message": "Invalid request"}), 400

    hashed_token = hashlib.sha256(token.encode()).hexdigest()

    conn = get_db()
    user = conn.execute(
        "SELECT id FROM users WHERE reset_token = ? AND reset_token_expiry > ?",
        (hashed_token, int(time.time())),
    ).fetchone()

    if not user:
        conn.close()
        return jsonify({"message": "Invalid or expired token"}), 400

    new_hashed_password = generate_password_hash(new_password)

    conn.execute(
        "UPDATE users SET password = ?, reset_token = NULL, reset_token_expiry = NULL WHERE id = ?",
        (new_hashed_password, user["id"]),
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "Password successfully reset"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)