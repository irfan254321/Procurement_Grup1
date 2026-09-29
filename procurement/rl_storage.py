# PANDUAN MAHASISWA: Lapisan SQLite untuk run MARL; transaksi menyimpan metadata dan semua event sehingga riwayat dapat diputar ulang.
"""Penyimpanan riwayat episode MARL ke SQLite."""
import json
import sqlite3
from pathlib import Path


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS marl_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            policy TEXT NOT NULL,
            seed INTEGER NOT NULL,
            scenario_json TEXT NOT NULL,
            status TEXT NOT NULL,
            total INTEGER NOT NULL,
            rounds INTEGER NOT NULL,
            report_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS marl_events (
            run_id INTEGER NOT NULL REFERENCES marl_runs(id),
            step INTEGER NOT NULL,
            round INTEGER NOT NULL,
            agent TEXT NOT NULL,
            detail_json TEXT NOT NULL,
            PRIMARY KEY(run_id, step)
        );
        CREATE TABLE IF NOT EXISTS vendor_settings (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            vendors_json TEXT NOT NULL
        );
    """)
    return db


def save_run(db, policy: str, seed: int, scenario: dict, result: dict, report: dict) -> int:
    """Simpan laporan dan seluruh aksi dalam satu transaksi."""
    # `with db` commit semua INSERT sekaligus; bila satu event gagal, rollback
    # mencegah run tanpa jejak langkah yang lengkap.
    with db:
        cur = db.execute("""INSERT INTO marl_runs(policy,seed,scenario_json,status,total,rounds,report_json)
                            VALUES(?,?,?,?,?,?,?)""",
                         (policy, seed, json.dumps(scenario), report["status"], result["total"],
                          result["rounds"], json.dumps(report, ensure_ascii=False)))
        run_id = cur.lastrowid
        for step, event in enumerate(result["log"], 1):
            db.execute("INSERT INTO marl_events VALUES(?,?,?,?,?)",
                       (run_id, step, event["round"], event["agent"],
                        json.dumps(event, ensure_ascii=False)))
    return run_id


def runs(db):
    return db.execute("SELECT id,created_at,policy,status,total,rounds FROM marl_runs ORDER BY id DESC").fetchall()


def load_run(db, run_id: int):
    row = db.execute("SELECT * FROM marl_runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        raise ValueError("Skenario tersimpan tidak ditemukan")
    return dict(row)


def load_events(db, run_id: int) -> list[dict]:
    rows = db.execute("SELECT detail_json FROM marl_events WHERE run_id=? ORDER BY step", (run_id,)).fetchall()
    return [json.loads(row[0]) for row in rows]


def load_vendor_settings(db) -> list[dict] | None:
    """Ambil konfigurasi A/B/C untuk skenario berikutnya; None berarti pakai BAB 6."""
    row = db.execute("SELECT vendors_json FROM vendor_settings WHERE id=1").fetchone()
    return json.loads(row[0]) if row else None


def save_vendor_settings(db, vendors: list[dict]) -> None:
    """Satu baris ini adalah konfigurasi aktif, bukan perubahan atas riwayat lama."""
    with db:
        db.execute("""INSERT INTO vendor_settings(id,updated_at,vendors_json)
                      VALUES(1,CURRENT_TIMESTAMP,?)
                      ON CONFLICT(id) DO UPDATE SET
                        updated_at=CURRENT_TIMESTAMP,
                        vendors_json=excluded.vendors_json""",
                   (json.dumps(vendors, ensure_ascii=False),))


def reset_vendor_settings(db) -> None:
    """Hapus konfigurasi khusus sehingga fixture BAB 6 kembali menjadi sumber data."""
    with db:
        db.execute("DELETE FROM vendor_settings WHERE id=1")
