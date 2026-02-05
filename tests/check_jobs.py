
import sqlite3
import os

db_path = 'data/srme.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT id, status, total_faculty, processed_faculty, university FROM ingestion_jobs')
    jobs = c.fetchall()
    print("--- INGESTION JOBS ---")
    for j in jobs:
        print(f"Job: {j[0]} | Status: {j[1]} | Progress: {j[3]}/{j[2]} | Uni: {j[4]}")
    conn.close()
