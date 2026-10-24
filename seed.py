import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.database import engine, Base, SessionLocal
from app.seed_data import seed_database

def main():
    print("Initializing AICTE database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("Seeding synthetic realistic data and demo scenarios...")
        seed_database(db)
        print("Seed complete! Database ready for Smart India Hackathon demo.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
