"""Isolated, session-scoped SQLite and upload operations for CloudForenX (demo only).

No authentication, cryptographic audit signatures, or reliable durable storage is claimed.
"""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone

MAX_BYTES = 12 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_session_store() -> str:
    root = tempfile.mkdtemp(prefix="cloudforenx_demo_")
    Path(root, "uploads").mkdir(exist_ok=True)
    with connect(root) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS evidence (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          case_id TEXT NOT NULL,
          evidence_name TEXT NOT NULL,
          evidence_type TEXT NOT NULL,
          collected_by TEXT NOT NULL,
          original_filename TEXT NOT NULL,
          stored_filename TEXT NOT NULL UNIQUE,
          sha256 TEXT NOT NULL,
          size_bytes INTEGER NOT NULL,
          created_utc TEXT NOT NULL,
          last_verified TEXT
        );
        CREATE TABLE IF NOT EXISTS custody (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          timestamp_utc TEXT NOT NULL,
          evidence_id INTEGER NOT NULL,
          case_id TEXT NOT NULL,
          collector TEXT NOT NULL,
          action TEXT NOT NULL,
          status TEXT NOT NULL,
          hash_value TEXT NOT NULL,
          notes TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(evidence_id) REFERENCES evidence(id)
        );
        """)
    return root


def connect(root: str) -> sqlite3.Connection:
    db = sqlite3.connect(str(Path(root, "cloudforenx.db")), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def get_records(root: str) -> list[dict]:
    with connect(root) as db:
        return [dict(x) for x in db.execute("SELECT * FROM evidence ORDER BY id DESC")]


def get_record(root: str, rid: int) -> dict | None:
    with connect(root) as db:
        item = db.execute("SELECT * FROM evidence WHERE id = ?", (rid,)).fetchone()
        return dict(item) if item else None


def log_event(root: str, item: dict, actor: str, action: str, status: str, hash_value: str, notes: str = "") -> None:
    with connect(root) as db:
        db.execute("""INSERT INTO custody
            (timestamp_utc,evidence_id,case_id,collector,action,status,hash_value,notes)
            VALUES(?,?,?,?,?,?,?,?)""",
            (utc_now(), item["id"], item["case_id"], actor, action, status, hash_value, notes[:1000]))


def save_evidence(root: str, *, case_id: str, evidence_name: str, evidence_type: str,
                  collected_by: str, filename: str, data: bytes) -> dict:
    fields = [case_id, evidence_name, evidence_type, collected_by, filename]
    if any(not x or not x.strip() for x in fields):
        raise ValueError("Complete all evidence details and choose a file.")
    if len(data) > MAX_BYTES:
        raise ValueError("Choose a sample file smaller than 12 MB.")
    if not data:
        raise ValueError("The selected sample file is empty.")
    digest = hash_bytes(data)
    safe_filename = f"{uuid.uuid4().hex}.bin"
    target = Path(root, "uploads", safe_filename)
    target.write_bytes(data)
    try:
        with connect(root) as db:
            cur = db.execute("""INSERT INTO evidence
              (case_id,evidence_name,evidence_type,collected_by,original_filename,stored_filename,
               sha256,size_bytes,created_utc,last_verified)
              VALUES(?,?,?,?,?,?,?,?,?,?)""",
              (case_id.strip(),evidence_name.strip(),evidence_type,collected_by.strip(),
               Path(filename).name,safe_filename,digest,len(data),utc_now(),"Not checked"))
            rid = cur.lastrowid
        item = get_record(root, rid)
        log_event(root, item, collected_by.strip(), "Evidence uploaded", "Saved", digest,
                  f"Original filename: {Path(filename).name}")
        return item
    except Exception:
        target.unlink(missing_ok=True)
        raise


def verify_evidence(root: str, rid: int, data: bytes, actor: str) -> tuple[bool, str, str]:
    if not actor.strip():
        raise ValueError("Please provide your name for the custody log.")
    if len(data) > MAX_BYTES:
        raise ValueError("Comparison files must be smaller than 12 MB.")
    item = get_record(root, rid)
    if item is None:
        raise ValueError("This evidence record no longer exists.")
    new_hash = hash_bytes(data)
    matches = new_hash == item["sha256"]
    status = "Verified" if matches else "Not verified"
    with connect(root) as db:
        db.execute("UPDATE evidence SET last_verified = ? WHERE id = ?", (status, rid))
    log_event(root, item, actor.strip(), "Integrity verification", status, new_hash,
              "Hash matches saved reference" if matches else "Hash mismatch (content differs)")
    return matches, item["sha256"], new_hash


def add_custody_note(root: str, rid: int, actor: str, action: str, notes: str) -> None:
    item = get_record(root, rid)
    if item is None:
        raise ValueError("Evidence not found.")
    if not actor.strip():
        raise ValueError("Provide the person recording the action.")
    log_event(root, item, actor.strip(), action, "Recorded (demo)", item["sha256"], notes)


def get_custody(root: str) -> list[dict]:
    with connect(root) as db:
        return [dict(x) for x in db.execute("SELECT * FROM custody ORDER BY id DESC")]


def file_path(root: str, record: dict) -> Path:
    # Stored filename is server-generated and never supplied by the user.
    return Path(root, "uploads", record["stored_filename"])
