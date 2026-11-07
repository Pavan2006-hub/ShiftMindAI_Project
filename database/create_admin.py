
import getpass

from app import create_app
from database.db import db
from extensions import bcrypt
from models.user import User


def create_admin():

    app = create_app()

    with app.app_context():

        print("\nSHIFT MIND AI - CREATE ADMIN")

        name = input("Admin name: ").strip()

        email = input("Admin email: ").strip().lower()

        if not name or not email:
            print("Name and email are required.")
            return

        existing = User.query.filter_by(email=email).first()

        if existing:
            print("An account with this email already exists.")
            return

        password = getpass.getpass("Admin password: ")

        confirm_password = getpass.getpass(
            "Confirm admin password: "
        )

        if password != confirm_password:
            print("Passwords do not match.")
            return

        if len(password) < 8 or len(password) > 72:
            print("Password must contain 8 to 72 characters.")
            return

        password_hash = bcrypt.generate_password_hash(
            password
        ).decode("utf-8")

        admin = User(
            name=name,
            email=email,
            password_hash=password_hash,
            role="admin",
            is_active=True
        )

        try:
            db.session.add(admin)
            db.session.commit()

            print("\nAdministrator created successfully.")

        except Exception:
            db.session.rollback()
            print("Unable to create administrator.")
            raise


if __name__ == "__main__":
    create_admin()
