"""
Script to drop all existing tables so they can be recreated with new schema.
"""
from sqlalchemy import text
from app.database import engine, Base

# Drop all tables
with engine.connect() as conn:
    # Disable foreign key checks temporarily
    conn.execute(text("DROP TABLE IF EXISTS student_profiles CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS supervisor_profiles CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
    conn.commit()

print("All tables dropped successfully!")