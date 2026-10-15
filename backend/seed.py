r"""Create tables and demo data.   Usage (from the backend folder):
    ..\.venv\Scripts\python.exe seed.py            # add missing demo data (safe to repeat)
    ..\.venv\Scripts\python.exe seed.py --reset    # delete the database content and start fresh
"""
import sys

from app import models  # noqa: F401
from app.database import Base, SessionLocal, engine
from app.seed_data import seed_all

if __name__ == "__main__":
    if "--reset" in sys.argv:
        Base.metadata.drop_all(engine)
        print("Old data deleted.")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_all(db)
    print("Done: 12 demo hospitals and users (credentials configured in the project .env file).")
