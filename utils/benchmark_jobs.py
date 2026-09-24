"""Shared PostgreSQL or local SQLite research queue."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')


def database_url():
    return os.environ.get('BENCHMARK_DATABASE_URL', '').strip()


def external_worker():
    return os.environ.get('BENCHMARK_WORKER_MODE', 'external' if database_url() else 'local') == 'external'


class Database:
    def __init__(self, connection, postgres):
        self.connection, self.postgres = connection, postgres

    def execute(self, sql, params=()):
        return self.connection.execute(sql.replace('?', '%s') if self.postgres else sql, params)


@contextmanager
def connect():
    if database_url():
        import psycopg
        from psycopg.rows import dict_row
        connection = psycopg.connect(database_url(), row_factory=dict_row, connect_timeout=10)
    else:
        connection = local_connection()
    db = Database(connection, bool(database_url()))
    try:
        if db.postgres:
            db.execute('CREATE SCHEMA IF NOT EXISTS benchmark_private')
            db.execute('SET search_path TO benchmark_private')
        db.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, brief TEXT NOT NULL, prompt TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Taslak', progress TEXT NOT NULL DEFAULT '{}',
            result TEXT NOT NULL DEFAULT '[]', created_at TEXT, updated_at TEXT,
            worker_token TEXT, lease_until DOUBLE PRECISION)""")
        if db.postgres:
            db.execute('ALTER TABLE jobs ADD COLUMN IF NOT EXISTS worker_token TEXT')
            db.execute('ALTER TABLE jobs ADD COLUMN IF NOT EXISTS lease_until DOUBLE PRECISION')
        else:
            columns = {row['name'] for row in db.execute('PRAGMA table_info(jobs)').fetchall()}
            for name, kind in [('worker_token', 'TEXT'), ('lease_until', 'REAL')]:
                if name not in columns:
                    db.execute(f'ALTER TABLE jobs ADD COLUMN {name} {kind}')
        yield db
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def local_connection():
    path = Path(os.environ.get("BENCHMARK_DB_PATH", str(ROOT / "data/benchmark_jobs/jobs.sqlite3")))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    return db


def now():
    return datetime.now(timezone.utc).isoformat()


def create(brief, prompt):
    job_id = str(uuid4())
    with connect() as db:
        db.execute("INSERT INTO jobs(id, brief, prompt, created_at, updated_at) VALUES (?,?,?,?,?)", (job_id, json.dumps(brief, ensure_ascii=False), prompt, now(), now()))
    return job_id


def list_jobs():
    with connect() as db:
        rows = db.execute("SELECT * FROM jobs ORDER BY created_at DESC, id DESC LIMIT 50").fetchall()
    return [{**dict(row), **{key: json.loads(row[key]) for key in ('brief', 'progress', 'result')}} for row in rows]


def get(job_id):
    with connect() as db:
        row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        raise ValueError("Araştırma bulunamadı")
    return {**dict(row), **{key: json.loads(row[key]) for key in ('brief', 'progress', 'result')}}


def update(job_id, status, progress, result, token=None):
    with connect() as db:
        sql = "UPDATE jobs SET status=?, progress=?, result=?, updated_at=? WHERE id=? AND status NOT IN ('İptal edildi','Kesildi')"
        params = (status, json.dumps(progress, ensure_ascii=False), json.dumps(result, ensure_ascii=False), now(), job_id)
        if token:
            sql += ' AND worker_token=?'
            params += (token,)
        db.execute(sql, params)


def claim(job_id):
    token = str(uuid4())
    with connect() as db:
        claimed = db.execute("UPDATE jobs SET status='Araştırılıyor', worker_token=?, lease_until=?, updated_at=? WHERE id=? AND status='Sırada'", (token, time.time() + 180, now(), job_id)).rowcount
    return token if claimed else None


def heartbeat(job_id, token):
    with connect() as db:
        return db.execute("UPDATE jobs SET lease_until=? WHERE id=? AND worker_token=? AND status='Araştırılıyor'", (time.time() + 180, job_id, token)).rowcount == 1


def recover_interrupted():
    with connect() as db:
        return db.execute("UPDATE jobs SET status='Kesildi', updated_at=? WHERE status='Araştırılıyor' AND lease_until IS NOT NULL AND lease_until < ?", (now(), time.time())).rowcount


def next_queued():
    with connect() as db:
        row = db.execute("SELECT id FROM jobs WHERE status='Sırada' ORDER BY created_at, id LIMIT 1").fetchone()
    return row['id'] if row else None


def cancel(job_id):
    with connect() as db:
        db.execute("UPDATE jobs SET status='İptal edildi', updated_at=? WHERE id=? AND status IN ('Sırada','Araştırılıyor')", (now(), job_id))


def launch(job_id, api_key=None):
    with connect() as db:
        claimed = db.execute("UPDATE jobs SET status='Sırada', updated_at=? WHERE id=? AND status='Taslak'", (now(), job_id)).rowcount
    if not claimed:
        return
    if external_worker():
        return
    env = os.environ.copy()
    if api_key:
        env['ANTHROPIC_API_KEY'] = api_key
    try:
        subprocess.Popen([sys.executable, '-m', 'pipeline.run_custom_benchmark', job_id], cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        update(job_id, 'Hata', {'message': 'Araştırma çalışanı başlatılamadı.'}, [])
