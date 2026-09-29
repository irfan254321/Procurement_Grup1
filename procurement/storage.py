# PANDUAN MAHASISWA: Penyimpanan SQLite untuk simulator aturan lama; tabelnya terpisah dari marl_runs/marl_events.
"""Penyimpanan SQLite: setiap langkah adalah transaksi yang dapat dibaca kembali."""
import json
import sqlite3
from pathlib import Path


def connect(path: str | Path) -> sqlite3.Connection:
    """Buat tabel otomatis saat aplikasi pertama kali dijalankan."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'berjalan',
            step INTEGER NOT NULL DEFAULT 0,
            scenario_json TEXT NOT NULL,
            seed INTEGER NOT NULL,
            volatility REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES runs(id),
            step INTEGER NOT NULL,
            stage TEXT NOT NULL,
            agent TEXT NOT NULL,
            explanation TEXT NOT NULL,
            data_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(run_id, step)
        );
        CREATE TABLE IF NOT EXISTS vendor_snapshots (
            run_id INTEGER NOT NULL REFERENCES runs(id),
            round INTEGER NOT NULL,
            vendor TEXT NOT NULL,
            price INTEGER NOT NULL,
            capacity INTEGER NOT NULL,
            lead_days INTEGER NOT NULL,
            PRIMARY KEY(run_id, round, vendor)
        );
        CREATE TABLE IF NOT EXISTS reports (
            run_id INTEGER PRIMARY KEY REFERENCES runs(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            summary_json TEXT NOT NULL
        );
    """)
    return db


def create_run(db: sqlite3.Connection, scenario: dict, seed: int, volatility: float) -> int:
    with db:
        cursor = db.execute("INSERT INTO runs(scenario_json, seed, volatility) VALUES (?, ?, ?)",
                            (json.dumps(scenario), seed, volatility))
    return cursor.lastrowid


def get_run(db: sqlite3.Connection, run_id: int):
    return db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()


def list_runs(db: sqlite3.Connection):
    return db.execute("SELECT id, created_at, status, step FROM runs ORDER BY id DESC").fetchall()


def events(db: sqlite3.Connection, run_id: int):
    return db.execute("SELECT * FROM events WHERE run_id = ? ORDER BY step", (run_id,)).fetchall()


def snapshots(db: sqlite3.Connection, run_id: int):
    return db.execute("SELECT * FROM vendor_snapshots WHERE run_id = ? ORDER BY round, vendor", (run_id,)).fetchall()


def get_report(db: sqlite3.Connection, run_id: int):
    """Laporan ringkas yang otomatis dibuat pada tahap konsensus."""
    row = db.execute("SELECT summary_json FROM reports WHERE run_id = ?", (run_id,)).fetchone()
    return json.loads(row[0]) if row else None
