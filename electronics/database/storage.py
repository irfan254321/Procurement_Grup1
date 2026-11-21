from contextlib import closing
import json
import sqlite3


def connect(path):
    return closing(sqlite3.connect(path, timeout=10))


def create_schema(db):
    db.execute("CREATE TABLE IF NOT EXISTS world (id INTEGER PRIMARY KEY CHECK(id=1), state TEXT)")
    db.execute("""CREATE TABLE IF NOT EXISTS agent_memory (
        role TEXT, tick INTEGER, day INTEGER, subject TEXT, facts TEXT, decision TEXT, reason TEXT,
        PRIMARY KEY (role, tick))""")
    db.execute("""CREATE TABLE IF NOT EXISTS epcis_events (
        epc_id TEXT, tick INTEGER, biz_step TEXT, disposition TEXT, payload TEXT,
        PRIMARY KEY (epc_id, tick, biz_step))""")
    db.execute("""CREATE TABLE IF NOT EXISTS negotiation_logs (
        company TEXT, tick INTEGER, cycle TEXT, kind TEXT, payload TEXT,
        PRIMARY KEY (company, tick, kind))""")
    db.execute("""CREATE TABLE IF NOT EXISTS delivery_schedules (
        company TEXT, cycle TEXT, order_key TEXT, payload TEXT,
        PRIMARY KEY (company, cycle, order_key))""")
    db.execute("""CREATE TABLE IF NOT EXISTS negotiation_schedules (
        company TEXT, cycle TEXT, partner TEXT, payload TEXT,
        PRIMARY KEY (company, cycle, partner))""")
    db.execute("CREATE TABLE IF NOT EXISTS procurement_cycles (cycle TEXT PRIMARY KEY, tick INTEGER, payload TEXT)")
    db.execute("""CREATE TABLE IF NOT EXISTS anomaly_alerts (
        tick INTEGER, code TEXT, subject TEXT, score REAL, severity TEXT, payload TEXT,
        PRIMARY KEY (tick, code, subject))""")
    db.execute("""CREATE TABLE IF NOT EXISTS company_passwords (
        slug TEXT PRIMARY KEY, salt BLOB, digest BLOB, failures INTEGER DEFAULT 0, retry_after INTEGER DEFAULT 0)""")
    db.execute("""CREATE TABLE IF NOT EXISTS company_sessions (
        token_hash BLOB PRIMARY KEY, slug TEXT, expires INTEGER)""")
    db.execute("CREATE INDEX IF NOT EXISTS agent_memory_by_tick ON agent_memory(tick DESC, role)")


def clear_scenario(db):
    for table in ("agent_memory", "epcis_events", "negotiation_logs", "delivery_schedules", "negotiation_schedules",
                  "procurement_cycles", "anomaly_alerts", "company_sessions"):
        db.execute(f"DELETE FROM {table}")


def read_world(db):
    return json.loads(db.execute("SELECT state FROM world WHERE id=1").fetchone()[0])


def save_world(db, world):
    db.execute("INSERT OR REPLACE INTO world (id,state) VALUES (1,?)", (json.dumps(world),))
