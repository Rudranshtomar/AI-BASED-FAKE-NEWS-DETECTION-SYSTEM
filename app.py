"""Flask application for TruthLens AI - Explainable AI Fake News Detection System.

Includes secure session-based authentication, user dashboards, administrative controls,
and REST API endpoints with MongoDB Atlas integration.
"""

from collections import defaultdict
import csv
from datetime import datetime, timedelta, timezone
from functools import wraps
import io
import ipaddress
import os
from pathlib import Path
import pickle
import re
import secrets
import socket
from urllib.parse import urlparse

from bson import ObjectId
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import requests
from werkzeug.security import check_password_hash, generate_password_hash

# Set base directory first before loading any relative resources
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024
app.secret_key = os.getenv("SECRET_KEY", "dev_secret_key_truthlens_2026_fallback")

# Secure session cookies
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
)


def load_artifact(filename):
    with (BASE_DIR / "model" / filename).open("rb") as artifact_file:
        return pickle.load(artifact_file)


# Load model, vectorizer, and evaluation metrics safely
model = load_artifact("model.pkl")
vectorizer = load_artifact("vectorizer.pkl")
FEATURE_NAMES = vectorizer.get_feature_names_out()

accuracy_path = BASE_DIR / "model" / "accuracy.txt"
if accuracy_path.exists():
    MODEL_ACCURACY = accuracy_path.read_text(encoding="utf-8").strip()
else:
    MODEL_ACCURACY = "N/A"

metrics_path = BASE_DIR / "model" / "evaluation_metrics.pkl"
if metrics_path.exists():
    with open(metrics_path, "rb") as file:
        metrics = pickle.load(file)
else:
    metrics = {
        "accuracy": MODEL_ACCURACY,
        "precision": "N/A",
        "recall": "N/A",
        "f1_score": "N/A",
        "class_labels": ["FAKE", "REAL"],
        "confusion_matrix": [[0, 0], [0, 0]],
    }

# Initialize MongoDB Atlas
mongo_uri = os.getenv("MONGO_URI")
try:
    mongo_client = (
        MongoClient(mongo_uri, serverSelectionTimeoutMS=2000) if mongo_uri else None
    )
    if mongo_client:
        db = mongo_client["fake_news_detector"]
        collection = db["predictions"]
        feedback_collection = db["feedback"]
        users_collection = db["users"]
        # Ensure indexes safely
        try:
            users_collection.create_index("email", unique=True)
            collection.create_index([("created_at", -1)])
            collection.create_index([("user_email", 1)])
        except PyMongoError:
            pass
    else:
        db = None
        collection = None
        feedback_collection = None
        users_collection = None
except PyMongoError:
    app.logger.warning("MongoDB URI could not be initialized; database features degraded.")
    mongo_client = None
    db = None
    collection = None
    feedback_collection = None
    users_collection = None


# =====================================================================
# Security & CSRF Utilities
# =====================================================================

def generate_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


@app.context_processor
def inject_global_template_vars():
    return {
        "csrf_token": generate_csrf_token(),
        "now_year": datetime.now(timezone.utc).year,
    }


@app.before_request
def verify_csrf():
    # Bypass during automated pytest execution or non-state-changing verbs
    if app.config.get("TESTING") or os.getenv("PYTEST_CURRENT_TEST"):
        return
    if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
        return
    # Exempt REST APIs (which may use token/key auth or automated calls)
    if request.path.startswith("/api/") or request.path == "/feedback":
        return

    submitted_token = (
        request.form.get("csrf_token")
        or request.headers.get("X-CSRF-Token")
        or (request.get_json(silent=True) or {}).get("csrf_token")
    )
    session_token = session.get("csrf_token")

    if not session_token or not submitted_token or not secrets.compare_digest(session_token, submitted_token):
        app.logger.warning("CSRF validation failure on %s", request.path)
        abort(400, description="CSRF validation failed. Please refresh the page and try again.")


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in to access your dashboard.", "info")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            flash("Administrator login required.", "error")
            return redirect(url_for("login", next=request.path))
        if session.get("user_role") != "admin":
            abort(403, description="Access Forbidden: Administrator privileges required.")
        return f(*args, **kwargs)
    return decorated_function


def validate_email_address(email: str) -> bool:
    regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(regex, email))


def validate_password_strength(password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must include at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must include at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must include at least one number."
    return True, ""


# =====================================================================
# Database Helpers & Aggregate Statistics
# =====================================================================

def empty_stats():
    return {
        "history": [],
        "total_predictions": 0,
        "fake_count": 0,
        "real_count": 0,
        "average_confidence": 0,
    }


def get_stats():
    """Return recent history and aggregates; keep classification usable without MongoDB."""
    stats = empty_stats()
    if collection is None:
        stats["storage_unavailable"] = True
        return stats

    try:
        stats["history"] = list(
            collection.find({}, {"_id": 0}).sort("created_at", -1).limit(5)
        )
        stats["total_predictions"] = collection.count_documents({})
        stats["fake_count"] = collection.count_documents({"prediction": "FAKE"})
        stats["real_count"] = collection.count_documents({"prediction": "REAL"})
        result = list(
            collection.aggregate([
                {"$group": {"_id": None, "average": {"$avg": "$confidence"}}}
            ])
        )
        if result and result[0].get("average") is not None:
            stats["average_confidence"] = round(result[0]["average"], 2)
    except PyMongoError:
        app.logger.warning("MongoDB is unavailable; showing empty prediction history.")
        stats = empty_stats()
        stats["storage_unavailable"] = True
    return stats


def render_page(**context):
    stats = get_stats()

    page_context = {
        "model_accuracy": MODEL_ACCURACY,
        "model_metrics": metrics,
        **stats,
        **context,
    }

    page_context["storage_unavailable"] = (
        stats.get("storage_unavailable", False)
        or context.get("storage_unavailable", False)
    )

    return render_template("index.html", **page_context)


def explain_prediction(news, top_k=5):
    """Identify top words contributing to REAL vs FAKE classification."""
    if not news or not news.strip():
        return {"fake_signals": [], "real_signals": []}

    features = vectorizer.transform([news])
    non_zero_indices = features.nonzero()[1]
    if len(non_zero_indices) == 0:
        return {"fake_signals": [], "real_signals": []}

    coef = model.coef_[0]
    contributions = []
    for idx in non_zero_indices:
        word = FEATURE_NAMES[idx]
        val = features[0, idx]
        weight = coef[idx]
        score = float(val * weight)
        contributions.append((word, score))

    real_words = sorted([c for c in contributions if c[1] > 0], key=lambda x: x[1], reverse=True)[:top_k]
    fake_words = sorted([c for c in contributions if c[1] < 0], key=lambda x: x[1])[:top_k]

    return {
        "real_signals": [{"word": w, "weight": round(s, 3)} for w, s in real_words],
        "fake_signals": [{"word": w, "weight": round(abs(s), 3)} for w, s in fake_words],
    }


def classify(news):
    """Predict label, confidence score, and word-level explainability signals."""
    features = vectorizer.transform([news])
    prediction = str(model.predict(features)[0])
    confidence = round(float(max(model.predict_proba(features)[0])) * 100, 2)
    explainability = explain_prediction(news, top_k=5)
    return prediction, confidence, explainability


def save_prediction(record):
    if collection is None:
        return False
    try:
        # Link prediction with logged-in user if active session exists
        if session.get("user_id"):
            record["user_id"] = session.get("user_id")
            record["user_email"] = session.get("user_email")
            record["user_name"] = session.get("user_name")
        else:
            record["user_id"] = None
            record["user_email"] = None

        collection.insert_one(record)
        return True
    except PyMongoError:
        app.logger.warning("Could not save prediction because MongoDB is unavailable.")
        return False


def is_safe_url(url: str) -> bool:
    """Validate that the URL is public and prevent Server-Side Request Forgery (SSRF)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            return False
        return True
    except Exception:
        return False


def extract_news_from_url(url):
    """Fetch an article once and return its title and text, guarding against SSRF."""
    if not is_safe_url(url):
        app.logger.info("Rejected unsafe or internal URL: %s", url)
        return None, None

    try:
        response = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (compatible; TruthLensAI/1.0)"
            },
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else "Unknown Title"

        for element in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            element.decompose()

        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        body_text = " ".join(text for text in paragraphs if text).strip()

        if not body_text or len(body_text) < 40:
            meta_desc = (
                soup.find("meta", attrs={"name": "description"})
                or soup.find("meta", attrs={"property": "og:description"})
            )
            if meta_desc and meta_desc.get("content"):
                body_text = meta_desc["content"].strip()

        return title, body_text if body_text else None
    except (requests.RequestException, ValueError) as exc:
        app.logger.info("Article extraction failed: %s", exc)
        return None, None


# =====================================================================
# Core Web Routes
# =====================================================================

@app.get("/")
def home():
    return render_page()


@app.post("/predict")
def predict():
    news = request.form.get("news", "").strip()
    if not news:
        return render_page(error="Enter an article before checking it."), 400

    prediction, confidence, explainability = classify(news)
    saved = save_prediction({
        "news": news,
        "prediction": prediction,
        "confidence": confidence,
        "created_at": datetime.now(timezone.utc),
    })
    return render_page(
        prediction=prediction,
        confidence=confidence,
        explainability=explainability,
        news=news,
        storage_unavailable=not saved,
    )


@app.post("/predict-url")
def predict_url():
    url = request.form.get("url", "").strip()
    if not url:
        return render_page(error="Enter a URL before analyzing it."), 400

    title, news = extract_news_from_url(url)
    if not news or not news.strip():
        return render_page(
            error="Could not extract article text from this URL. Try pasting the article instead."
        ), 400

    prediction, confidence, explainability = classify(news)
    saved = save_prediction({
        "title": title,
        "news": news,
        "url": url,
        "prediction": prediction,
        "confidence": confidence,
        "created_at": datetime.now(timezone.utc),
    })
    return render_page(
        prediction=prediction,
        confidence=confidence,
        explainability=explainability,
        news=news,
        title=title,
        url=url,
        storage_unavailable=not saved,
    )


# =====================================================================
# Authentication & User Management Routes
# =====================================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("user_dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password:
            return render_template("register.html", error="All fields are required.", name=name, email=email)

        if not validate_email_address(email):
            return render_template("register.html", error="Please enter a valid email address.", name=name, email=email)

        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match.", name=name, email=email)

        valid_pw, pw_err = validate_password_strength(password)
        if not valid_pw:
            return render_template("register.html", error=pw_err, name=name, email=email)

        if users_collection is None:
            return render_template(
                "register.html",
                error="Account registration is temporarily unavailable because the database is offline.",
                name=name,
                email=email,
            )

        try:
            existing_user = users_collection.find_one({"email": email})
            if existing_user:
                return render_template(
                    "register.html",
                    error="An account with this email address already exists. Please log in.",
                    name=name,
                    email=email,
                )

            # Public registration NEVER grants admin privileges automatically
            role = "user"
            # If the email matches the explicitly designated ADMIN_EMAIL from env, allow admin assignment
            admin_email_env = os.getenv("ADMIN_EMAIL", "").strip().lower()
            if admin_email_env and email == admin_email_env:
                role = "admin"

            try:
                hashed_pw = generate_password_hash(password, method="scrypt")
            except Exception:
                hashed_pw = generate_password_hash(password, method="pbkdf2:sha256")

            user_doc = {
                "name": name,
                "email": email,
                "password_hash": hashed_pw,
                "role": role,
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
                "last_login": datetime.now(timezone.utc),
            }

            result = users_collection.insert_one(user_doc)

            # Establish session immediately
            session.clear()
            generate_csrf_token()
            session["user_id"] = str(result.inserted_id)
            session["user_name"] = name
            session["user_email"] = email
            session["user_role"] = role

            flash(f"Welcome to TruthLens AI, {name}! Your account has been created.", "success")
            return redirect(url_for("user_dashboard"))

        except PyMongoError as exc:
            app.logger.error("Registration database error: %s", exc)
            return render_template(
                "register.html",
                error="Failed to create account due to a database error. Please try again later.",
                name=name,
                email=email,
            )

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("user_dashboard"))

    next_url = request.args.get("next") or request.form.get("next") or ""

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember", "").lower() in ("true", "on", "1")

        if not email or not password:
            return render_template("login.html", error="Email and password are required.", email=email)

        if users_collection is None:
            return render_template(
                "login.html",
                error="Authentication is temporarily unavailable because the database is offline.",
                email=email,
            )

        try:
            user = users_collection.find_one({"email": email})
            if not user or not check_password_hash(user.get("password_hash", ""), password):
                return render_template("login.html", error="Invalid email address or password.", email=email)

            if not user.get("is_active", True):
                return render_template(
                    "login.html",
                    error="Your account has been suspended by an administrator. Please contact support.",
                    email=email,
                )

            # Establish session securely
            session.clear()
            generate_csrf_token()
            session["user_id"] = str(user["_id"])
            session["user_name"] = user.get("name", "User")
            session["user_email"] = user.get("email", email)
            session["user_role"] = user.get("role", "user")

            if remember:
                session.permanent = True

            users_collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"last_login": datetime.now(timezone.utc)}}
            )

            flash(f"Welcome back, {user.get('name')}!", "success")

            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            if user.get("role") == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("user_dashboard"))

        except PyMongoError as exc:
            app.logger.error("Login database error: %s", exc)
            return render_template("login.html", error="A database error occurred. Please try again.", email=email)

    return render_template("login.html", next=next_url)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    flash("You have successfully signed out.", "info")
    return redirect(url_for("login"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email or not validate_email_address(email):
            return render_template("forgot_password.html", error="Please enter a valid email address.")

        # In production this emails a secure token; for this project it safely instructs the user
        return render_template(
            "forgot_password.html",
            success=f"If an account is associated with {email}, password recovery instructions have been dispatched. Contact the administrator at {os.getenv('ADMIN_EMAIL', 'admin@truthlens.ai')} for direct credential resets.",
        )

    return render_template("forgot_password.html")


# =====================================================================
# User Dashboard Routes
# =====================================================================

@app.get("/dashboard")
@login_required
def user_dashboard():
    user_email = session.get("user_email")
    query = request.args.get("q", "").strip()
    filter_verdict = request.args.get("filter", "all").strip().upper()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    per_page = 10

    # User profile data
    user_profile = {"name": session.get("user_name"), "email": user_email, "role": session.get("user_role")}
    if users_collection is not None:
        try:
            db_user = users_collection.find_one({"email": user_email})
            if db_user:
                user_profile["created_at"] = db_user.get("created_at")
        except PyMongoError:
            pass

    user_stats = {
        "user_total": 0,
        "user_fake": 0,
        "user_real": 0,
        "user_avg_conf": 0,
        "history": [],
        "total_pages": 1,
        "current_page": page,
        "total_count": 0,
    }

    if collection is not None:
        try:
            base_filter = {"user_email": user_email}
            user_stats["user_total"] = collection.count_documents(base_filter)
            user_stats["user_fake"] = collection.count_documents({**base_filter, "prediction": "FAKE"})
            user_stats["user_real"] = collection.count_documents({**base_filter, "prediction": "REAL"})

            avg_res = list(
                collection.aggregate([
                    {"$match": base_filter},
                    {"$group": {"_id": None, "avg": {"$avg": "$confidence"}}}
                ])
            )
            if avg_res and avg_res[0].get("avg") is not None:
                user_stats["user_avg_conf"] = round(avg_res[0]["avg"], 2)

            search_filter = {"user_email": user_email}
            if filter_verdict in ("FAKE", "REAL"):
                search_filter["prediction"] = filter_verdict
            if query:
                search_filter["$or"] = [
                    {"news": {"$regex": re.escape(query), "$options": "i"}},
                    {"title": {"$regex": re.escape(query), "$options": "i"}},
                ]

            total_matches = collection.count_documents(search_filter)
            user_stats["total_count"] = total_matches
            user_stats["total_pages"] = max(1, (total_matches + per_page - 1) // per_page)

            records = list(
                collection.find(search_filter)
                .sort("created_at", -1)
                .skip((page - 1) * per_page)
                .limit(per_page)
            )
            user_stats["history"] = records

        except PyMongoError as exc:
            app.logger.warning("Failed to fetch user prediction history: %s", exc)

    return render_template(
        "dashboard.html",
        user=user_profile,
        query=query,
        current_filter=filter_verdict,
        **user_stats,
    )


@app.post("/dashboard/prediction/<pred_id>/delete")
@login_required
def user_delete_prediction(pred_id):
    if collection is None:
        flash("Database offline. Could not delete record.", "error")
        return redirect(url_for("user_dashboard"))

    try:
        obj_id = ObjectId(pred_id)
        # Enforce that users can ONLY delete records they own
        result = collection.delete_one({"_id": obj_id, "user_email": session.get("user_email")})
        if result.deleted_count > 0:
            flash("Prediction record removed from your history.", "success")
        else:
            flash("Record not found or unauthorized.", "error")
    except Exception as exc:
        app.logger.error("Error deleting prediction: %s", exc)
        flash("Invalid record ID.", "error")

    return redirect(url_for("user_dashboard"))


@app.post("/dashboard/clear-history")
@login_required
def user_clear_history():
    if collection is None:
        flash("Database offline.", "error")
        return redirect(url_for("user_dashboard"))

    try:
        collection.delete_many({"user_email": session.get("user_email")})
        flash("Your personal prediction history has been cleared.", "success")
    except PyMongoError:
        flash("Could not clear history.", "error")

    return redirect(url_for("user_dashboard"))


# =====================================================================
# Admin Dashboard & Management Routes
# =====================================================================

@app.get("/admin")
@admin_required
def admin_dashboard():
    user_query = request.args.get("user_q", "").strip()
    pred_query = request.args.get("pred_q", "").strip()
    pred_filter = request.args.get("pred_filter", "all").strip().upper()
    try:
        pred_page = max(1, int(request.args.get("p_page", 1)))
    except ValueError:
        pred_page = 1
    per_page = 15

    admin_data = {
        "total_users": 0,
        "total_predictions": 0,
        "fake_count": 0,
        "real_count": 0,
        "recent_activity": [],
        "users_list": [],
        "user_pred_counts": {},
        "all_predictions": [],
        "pred_page": pred_page,
        "pred_total_pages": 1,
        "user_query": user_query,
        "pred_query": pred_query,
        "pred_filter": pred_filter,
        "model_metrics": metrics,
    }

    if collection is not None:
        try:
            admin_data["total_predictions"] = collection.count_documents({})
            admin_data["fake_count"] = collection.count_documents({"prediction": "FAKE"})
            admin_data["real_count"] = collection.count_documents({"prediction": "REAL"})
            admin_data["recent_activity"] = list(
                collection.find({}).sort("created_at", -1).limit(6)
            )

            # Global prediction query with filter & pagination
            p_filter = {}
            if pred_filter in ("FAKE", "REAL"):
                p_filter["prediction"] = pred_filter
            if pred_query:
                p_filter["$or"] = [
                    {"news": {"$regex": re.escape(pred_query), "$options": "i"}},
                    {"title": {"$regex": re.escape(pred_query), "$options": "i"}},
                    {"user_email": {"$regex": re.escape(pred_query), "$options": "i"}},
                ]

            total_preds = collection.count_documents(p_filter)
            admin_data["pred_total_pages"] = max(1, (total_preds + per_page - 1) // per_page)
            admin_data["all_predictions"] = list(
                collection.find(p_filter)
                .sort("created_at", -1)
                .skip((pred_page - 1) * per_page)
                .limit(per_page)
            )

            # Aggregate predictions per user email
            user_counts = list(
                collection.aggregate([
                    {"$match": {"user_email": {"$ne": None}}},
                    {"$group": {"_id": "$user_email", "count": {"$sum": 1}}}
                ])
            )
            admin_data["user_pred_counts"] = {c["_id"]: c["count"] for c in user_counts}

        except PyMongoError as exc:
            app.logger.warning("Admin prediction aggregation error: %s", exc)

    if users_collection is not None:
        try:
            admin_data["total_users"] = users_collection.count_documents({})
            u_filter = {}
            if user_query:
                u_filter["$or"] = [
                    {"name": {"$regex": re.escape(user_query), "$options": "i"}},
                    {"email": {"$regex": re.escape(user_query), "$options": "i"}},
                ]
            admin_data["users_list"] = list(
                users_collection.find(u_filter).sort("created_at", -1)
            )
        except PyMongoError as exc:
            app.logger.warning("Admin user query error: %s", exc)

    return render_template("admin.html", **admin_data)


@app.post("/admin/user/<user_id>/toggle-status")
@admin_required
def admin_toggle_user_status(user_id):
    if users_collection is None:
        flash("Database offline.", "error")
        return redirect(url_for("admin_dashboard"))

    try:
        obj_id = ObjectId(user_id)
        target = users_collection.find_one({"_id": obj_id})
        if not target:
            flash("User not found.", "error")
            return redirect(url_for("admin_dashboard") + "#users")

        if target.get("email") == session.get("user_email"):
            flash("You cannot suspend your own administrative account.", "error")
            return redirect(url_for("admin_dashboard") + "#users")

        new_status = not target.get("is_active", True)
        users_collection.update_one({"_id": obj_id}, {"$set": {"is_active": new_status}})
        flash(f"Account for {target.get('email')} {'activated' if new_status else 'suspended'}.", "success")
    except Exception as exc:
        flash(f"Action failed: {exc}", "error")

    return redirect(url_for("admin_dashboard") + "#users")


@app.post("/admin/user/<user_id>/toggle-role")
@admin_required
def admin_toggle_user_role(user_id):
    if users_collection is None:
        flash("Database offline.", "error")
        return redirect(url_for("admin_dashboard"))

    try:
        obj_id = ObjectId(user_id)
        target = users_collection.find_one({"_id": obj_id})
        if not target:
            flash("User not found.", "error")
            return redirect(url_for("admin_dashboard") + "#users")

        if target.get("email") == session.get("user_email"):
            flash("You cannot demote yourself from administrator status.", "error")
            return redirect(url_for("admin_dashboard") + "#users")

        new_role = "user" if target.get("role") == "admin" else "admin"
        users_collection.update_one({"_id": obj_id}, {"$set": {"role": new_role}})
        flash(f"Role for {target.get('email')} updated to {new_role.upper()}.", "success")
    except Exception as exc:
        flash(f"Action failed: {exc}", "error")

    return redirect(url_for("admin_dashboard") + "#users")


@app.post("/admin/user/<user_id>/delete")
@admin_required
def admin_delete_user(user_id):
    if users_collection is None:
        flash("Database offline.", "error")
        return redirect(url_for("admin_dashboard"))

    try:
        obj_id = ObjectId(user_id)
        target = users_collection.find_one({"_id": obj_id})
        if not target:
            flash("User not found.", "error")
            return redirect(url_for("admin_dashboard") + "#users")

        if target.get("email") == session.get("user_email"):
            flash("You cannot delete your own account.", "error")
            return redirect(url_for("admin_dashboard") + "#users")

        users_collection.delete_one({"_id": obj_id})
        # Clean up user's prediction history if requested
        if collection is not None:
            collection.delete_many({"user_email": target.get("email")})

        flash(f"User account {target.get('email')} permanently deleted.", "success")
    except Exception as exc:
        flash(f"Action failed: {exc}", "error")

    return redirect(url_for("admin_dashboard") + "#users")


@app.post("/admin/prediction/<pred_id>/delete")
@admin_required
def admin_delete_prediction(pred_id):
    if collection is None:
        flash("Database offline.", "error")
        return redirect(url_for("admin_dashboard"))

    try:
        collection.delete_one({"_id": ObjectId(pred_id)})
        flash("Prediction record removed by administrator.", "success")
    except Exception as exc:
        flash(f"Failed to delete record: {exc}", "error")

    return redirect(url_for("admin_dashboard") + "#predictions")


@app.post("/admin/clear-all-history")
@admin_required
def admin_clear_all_history():
    if collection is None:
        flash("Database offline.", "error")
        return redirect(url_for("admin_dashboard"))

    try:
        collection.delete_many({})
        flash("All prediction records have been purged from the system.", "success")
    except PyMongoError:
        flash("Failed to purge records.", "error")

    return redirect(url_for("admin_dashboard") + "#predictions")


# =====================================================================
# REST API Endpoints
# =====================================================================

@app.get("/api/health")
def api_health():
    """Health check endpoint for monitoring, Docker, and status."""
    is_db_connected = False
    if mongo_client:
        try:
            mongo_client.admin.command("ping")
            is_db_connected = True
        except PyMongoError:
            is_db_connected = False

    return jsonify({
        "status": "healthy",
        "model_loaded": model is not None,
        "vectorizer_loaded": vectorizer is not None,
        "database_connected": is_db_connected,
        "accuracy": MODEL_ACCURACY,
    }), 200


@app.post("/api/predict")
def api_predict():
    """Programmatic JSON API for classifying news text or public URLs."""
    data = request.get_json(silent=True) or {}
    news = data.get("news", "").strip()
    url = data.get("url", "").strip()
    title = None

    if url and not news:
        extracted_title, extracted_news = extract_news_from_url(url)
        if not extracted_news:
            return jsonify({
                "status": "error",
                "error": "Could not extract article text from the provided URL.",
            }), 400
        title = extracted_title
        news = extracted_news

    if not news:
        return jsonify({
            "status": "error",
            "error": "Please provide either 'news' (article text) or a valid 'url'.",
        }), 400

    prediction, confidence, explainability = classify(news)

    record = {
        "news": news[:5000],
        "prediction": prediction,
        "confidence": confidence,
        "created_at": datetime.now(timezone.utc),
    }
    if url:
        record["url"] = url
    if title:
        record["title"] = title
    save_prediction(record)

    response_payload = {
        "status": "success",
        "prediction": prediction,
        "confidence": confidence,
        "explainability": explainability,
    }
    if title:
        response_payload["title"] = title
    if url:
        response_payload["url"] = url

    return jsonify(response_payload), 200


@app.post("/feedback")
def submit_feedback():
    """Record user feedback on prediction accuracy."""
    data = request.get_json(silent=True) or request.form.to_dict()
    prediction = data.get("prediction")
    is_correct = data.get("is_correct")
    news_snippet = data.get("news", "")[:300]

    if is_correct is not None and isinstance(is_correct, str):
        is_correct = is_correct.lower() in ("true", "1", "yes")

    if feedback_collection is not None:
        try:
            feedback_collection.insert_one({
                "prediction": prediction,
                "is_correct": is_correct,
                "news_snippet": news_snippet,
                "created_at": datetime.now(timezone.utc),
            })
            return jsonify({"status": "success", "message": "Feedback recorded. Thank you!"}), 200
        except PyMongoError:
            pass

    return jsonify({"status": "received", "message": "Feedback noted."}), 200


@app.get("/export-history")
def export_history():
    """Export prediction history as a downloadable CSV."""
    if collection is None:
        return Response("Prediction history unavailable without MongoDB.", status=503, mimetype="text/plain")

    try:
        records = list(collection.find({}, {"_id": 0}).sort("created_at", -1))
    except PyMongoError:
        return Response("Failed to fetch history from MongoDB.", status=503, mimetype="text/plain")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Created At (UTC)", "User", "Prediction", "Confidence (%)", "Title", "URL", "News Snippet"])

    for item in records:
        created_at_str = (
            item["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(item.get("created_at"), datetime)
            else "N/A"
        )
        writer.writerow([
            created_at_str,
            item.get("user_email", "Anonymous"),
            item.get("prediction", "N/A"),
            item.get("confidence", "N/A"),
            item.get("title", ""),
            item.get("url", ""),
            (item.get("news", "") or "")[:200].replace("\n", " "),
        ])

    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=truthlens_fake_news_predictions.csv"},
    )


@app.post("/clear-history")
def clear_history():
    if collection is None:
        return render_page(
            error="Prediction history is unavailable because MongoDB is not configured."
        ), 503
    try:
        collection.delete_many({})
    except PyMongoError:
        app.logger.warning("Could not clear history because MongoDB is unavailable.")
        return render_page(
            error="Could not clear history because MongoDB is unavailable."
        ), 503
    return render_page()


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
