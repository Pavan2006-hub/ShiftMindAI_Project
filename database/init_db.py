
from app import create_app
from database.db import db


def initialize_database():

    app = create_app()

    with app.app_context():

        print("Checking database connection...")

        db.session.execute(db.text("SELECT 1"))

        print("Database connection successful.")

        db.create_all()

        print("\nShiftMind AI database initialized successfully.")

        print("\nCreated tables:")

        for table_name in db.metadata.tables:
            print("-", table_name)


if __name__ == "__main__":
    initialize_database()
