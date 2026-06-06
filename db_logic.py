"""
Versysmon - SQLite Database Interface

Handles all persistence for network bandwidth logs. Responsible for 
creating tables, committing daily/monthly traffic records, and fetching 
aggregated historical data for the dashboard UI.
"""
import sqlite3
from datetime import datetime

DB_NAME = "versysmon_data.db"

def init_db():
    """Creates the database and tables if they don't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
          
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_network_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT,
            bytes_used INTEGER,
            log_date DATE
        )
    ''')
    conn.commit()
    conn.close()

def log_app_usage(app_name, bytes_used):
    """Adds data to the database for today."""
    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT id, bytes_used FROM app_network_logs WHERE app_name=? AND log_date=?", (app_name, today))
    row = cursor.fetchone()

    if row:
        new_total = row[1] + bytes_used
        cursor.execute("UPDATE app_network_logs SET bytes_used=? WHERE id=?", (new_total, row[0]))
    else:
        cursor.execute("INSERT INTO app_network_logs (app_name, bytes_used, log_date) VALUES (?, ?, ?)", 
                       (app_name, bytes_used, today))

    conn.commit()
    conn.close()

init_db()