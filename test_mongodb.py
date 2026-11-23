import os
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient


def main():
    load_dotenv(Path(__file__).resolve().parent / ".env")
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise SystemExit("MONGO_URI is not set. Configure it in .env first.")

    with MongoClient(mongo_uri, serverSelectionTimeoutMS=5000) as client:
        client.admin.command("ping")
    print("MongoDB connected successfully!")


if __name__ == "__main__":
    main()
