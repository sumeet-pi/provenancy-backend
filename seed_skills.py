import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from app.models import SkillMaster, Base
from app.database import engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def seed():
    Base.metadata.create_all(bind=engine)

    backend_dir = Path(__file__).parent

    # --- Read skills.xlsx ---
    xlsx_path = backend_dir / "skills.xlsx"
    print(f"Reading {xlsx_path}...")
    df_xlsx = pd.read_excel(xlsx_path)
    df_xlsx = df_xlsx[['Example']].dropna(subset=['Example'])
    df_xlsx = df_xlsx.rename(columns={'Example': 'name'})
    print(f"xlsx skills: {len(df_xlsx)}")

    # --- Read skills CSV ---
    csv_path = backend_dir / "skills.csv"
    print(f"Reading {csv_path}...")
    df_csv = pd.read_csv(csv_path, on_bad_lines='skip')
    df_csv = df_csv[['name:String']].dropna()
    df_csv = df_csv.rename(columns={'name:String': 'name'})
    print(f"CSV skills: {len(df_csv)}")

    # --- Combine both ---
    df_combined = pd.concat([df_xlsx, df_csv], ignore_index=True)

    # Clean — strip whitespace, title case, drop empty
    df_combined['name'] = df_combined['name'].astype(str).str.strip()
    df_combined = df_combined[df_combined['name'] != '']
    df_combined = df_combined[df_combined['name'].str.lower() != 'nan']

    # Deduplicate case-insensitively
    df_combined['name_lower'] = df_combined['name'].str.lower()
    df_combined = df_combined.drop_duplicates(subset=['name_lower'])
    df_combined = df_combined.drop(columns=['name_lower'])

    total = len(df_combined)
    print(f"\nTotal unique skills after combining: {total}")

    db = SessionLocal()
    inserted = 0
    batch = []

    try:
        print("Clearing old data...")
        db.execute(text("TRUNCATE TABLE skill_master"))
        db.commit()
        print("Cleared.")

        print("Inserting...")
        for _, row in df_combined.iterrows():
            skill_name = str(row['name']).strip()
            if not skill_name:
                continue

            batch.append(SkillMaster(name=skill_name))

            if len(batch) == 500:
                db.bulk_save_objects(batch)
                db.commit()
                inserted += len(batch)
                batch = []
                print(f"Inserted {inserted}/{total}...")

        if batch:
            db.bulk_save_objects(batch)
            db.commit()
            inserted += len(batch)

        print(f"\nDone! Seeded {inserted} skills successfully.")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        sys.exit(1)

    finally:
        db.close()

if __name__ == "__main__":
    seed()