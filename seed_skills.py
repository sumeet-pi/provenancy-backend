import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend/ folder
load_dotenv(Path(__file__).parent / ".env")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Build DATABASE_URL from individual env vars
USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")
DATABASE_URL = f"postgresql+psycopg://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"

# Import models after env is loaded
from app.models import SkillMaster, Base
from app.database import engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed():
    # Create table if not exists
    Base.metadata.create_all(bind=engine)

    # Read xlsx
    import pandas as pd
    xlsx_path = Path(__file__).parent / "skills.xlsx"

    print(f"Reading {xlsx_path}...")
    df = pd.read_excel(xlsx_path, header=None)

    # Try column 0 first, if empty try column 1
    skills_col = None
    if df.shape[0] > 0 and not df.iloc[:, 0].isna().all():
        skills_col = df.iloc[:, 0]
    elif df.shape[1] > 1 and not df.iloc[:, 1].isna().all():
        skills_col = df.iloc[:, 1]
    else:
        print("Error: Could not find skills in the Excel file.")
        return

    # Filter and clean skills
    skills = []
    for val in skills_col:
        if pd.isna(val):
            continue
        name = str(val).strip()
        if name == "" or name.lower() == "nan":
            continue
        skills.append(name)

    total = len(skills)
    print(f"Found {total} skills in Excel file.")

    # Batch insert in chunks of 500
    batch_size = 500
    db = SessionLocal()
    inserted = 0
    existing = set()

    try:
        # Pre-load existing skill names to skip duplicates
        existing = {s[0] for s in db.query(SkillMaster.name).all()}
        print(f"Found {len(existing)} existing skills in database.")

        for i in range(0, total, batch_size):
            batch = skills[i:i + batch_size]
            for name in batch:
                if name in existing:
                    continue
                skill = SkillMaster(name=name)
                db.add(skill)
                existing.add(name)
                inserted += 1

            db.commit()
            progress = min(i + batch_size, total)
            print(f"Inserted {progress}/{total}...")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
    finally:
        db.close()

    print(f"Done! Seeded {inserted} skills.")


if __name__ == "__main__":
    seed()
