from app import create_app
from database.db import db
from extensions import bcrypt
from models.user import User


app = create_app()

with app.app_context():

    print("\nSHIFT MIND AI - ADMIN ACCOUNT SETUP\n")

    name = input("Admin name: ").strip()
    email = input("Admin Gmail: ").strip().lower()

    # Password will be visible while typing
    password = input("Admin login password: ")
    confirm_password = input("Confirm password: ")

    if not name or not email:
        print("Name and email are required.")
        raise SystemExit(1)

    if len(password) < 8:
        print("Password must contain at least 8 characters.")
        raise SystemExit(1)

    if password != confirm_password:
        print("Passwords do not match.")
        raise SystemExit(1)

    admin = User.query.filter_by(email=email).first()

    password_hash = bcrypt.generate_password_hash(
        password
    ).decode("utf-8")

    if admin:
        admin.name = name
        admin.password_hash = password_hash
        admin.role = "admin"
        admin.is_active = True

        print("\nExisting account updated as admin.")

    else:
        admin = User(
            name=name,
            email=email,
            password_hash=password_hash,
            role="admin",
            is_active=True
        )

        db.session.add(admin)

        print("\nNew admin account created.")

    db.session.commit()

    print("\nAdmin account setup completed successfully!")
    print("Admin Email:", email)
    print("Admin Role:", admin.role)