"""Script to initialize or promote an administrator account for TruthLens AI."""

import argparse
from datetime import datetime, timezone
import getpass
import os
from pathlib import Path
import re
import sys

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def validate_email(email: str) -> bool:
    regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(regex, email))


def validate_password(password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    return True, ""


def main():
    parser = argparse.ArgumentParser(description="Create or promote an administrator in TruthLens AI.")
    parser.add_argument("--name", help="Full name of administrator")
    parser.add_argument("--email", help="Administrator email address")
    parser.add_argument("--password", help="Administrator password")
    args = parser.parse_args()

    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        print("ERROR: MONGO_URI is not set in environment or .env file.")
        sys.exit(1)

    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=4000)
        db = client["fake_news_detector"]
        users_col = db["users"]
        # Ensure unique index on email
        users_col.create_index("email", unique=True)
    except PyMongoError as exc:
        print(f"ERROR: Could not connect to MongoDB: {exc}")
        sys.exit(1)

    name = args.name or input("Admin Full Name [System Admin]: ").strip() or "System Admin"
    default_email = os.getenv("ADMIN_EMAIL", "admin@truthlens.ai")
    email = args.email or input(f"Admin Email [{default_email}]: ").strip() or default_email
    email = email.lower().strip()

    if not validate_email(email):
        print(f"ERROR: '{email}' is not a valid email address.")
        sys.exit(1)

    existing = users_col.find_one({"email": email})
    if existing:
        print(f"Found existing account for '{email}'. Current role: '{existing.get('role', 'user')}'")
        if existing.get("role") == "admin":
            print("User is already an administrator.")
            sys.exit(0)
        users_col.update_one(
            {"_id": existing["_id"]},
            {"$set": {"role": "admin", "updated_at": datetime.now(timezone.utc)}}
        )
        print(f"SUCCESS: Promoted existing account '{email}' to administrator.")
        sys.exit(0)

    password = args.password
    if not password:
        password = getpass.getpass("Enter Administrator Password (min 8 chars, mixed case & numbers): ")
        confirm_password = getpass.getpass("Confirm Administrator Password: ")
        if password != confirm_password:
            print("ERROR: Passwords do not match.")
            sys.exit(1)

    valid, err_msg = validate_password(password)
    if not valid:
        print(f"ERROR: {err_msg}")
        sys.exit(1)

    try:
        pw_hash = generate_password_hash(password, method="scrypt")
    except Exception:
        pw_hash = generate_password_hash(password, method="pbkdf2:sha256")

    admin_doc = {
        "name": name,
        "email": email,
        "password_hash": pw_hash,
        "role": "admin",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "last_login": None,
    }

    try:
        users_col.insert_one(admin_doc)
        print(f"SUCCESS: Created new administrator account for '{email}'.")
    except PyMongoError as exc:
        print(f"ERROR: Failed to save admin user: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
