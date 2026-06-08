from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings, get_settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(settings: Settings | None = None, database_path: Path | None = None) -> sqlite3.Connection:
    settings = settings or get_settings()
    path = database_path or settings.database_path
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          input_path TEXT NOT NULL,
          output_path TEXT,
          status TEXT NOT NULL DEFAULT 'queued',
          created_at TEXT NOT NULL,
          started_at TEXT,
          finished_at TEXT,
          updated_at TEXT NOT NULL,
          source_width INTEGER,
          source_height INTEGER,
          source_fps REAL,
          source_frame_count INTEGER,
          source_duration_seconds REAL,
          target_width INTEGER,
          target_height INTEGER,
          preset TEXT,
          seedvr2_model TEXT,
          seedvr2_precision TEXT,
          batch_size INTEGER,
          temporal_overlap INTEGER,
          encoder TEXT,
          crf REAL,
          gpu_name TEXT,
          cuda_version TEXT,
          driver_version TEXT,
          total_elapsed_seconds REAL,
          estimated_total_seconds_initial REAL,
          estimated_total_seconds_final REAL,
          eta_confidence_initial TEXT,
          error_message TEXT,
          current_stage TEXT,
          frames_total INTEGER NOT NULL DEFAULT 0,
          frames_processed INTEGER NOT NULL DEFAULT 0,
          progress REAL NOT NULL DEFAULT 0,
          options_json TEXT NOT NULL DEFAULT '{}',
          cancel_requested INTEGER NOT NULL DEFAULT 0,
          log_path TEXT
        );

        CREATE TABLE IF NOT EXISTS job_stage_stats (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
          stage_name TEXT NOT NULL,
          status TEXT NOT NULL,
          started_at TEXT,
          finished_at TEXT,
          elapsed_seconds REAL,
          frames_total INTEGER,
          frames_processed INTEGER,
          effective_fps REAL,
          input_width INTEGER,
          input_height INTEGER,
          output_width INTEGER,
          output_height INTEGER,
          options_json TEXT NOT NULL DEFAULT '{}',
          peak_vram_mb REAL,
          average_gpu_utilisation REAL,
          average_vram_mb REAL,
          completed_sample INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS performance_profiles (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          stage_name TEXT NOT NULL,
          source_type TEXT,
          preset TEXT,
          source_width INTEGER,
          source_height INTEGER,
          target_width INTEGER,
          target_height INTEGER,
          model TEXT,
          precision TEXT,
          batch_size INTEGER,
          temporal_overlap INTEGER,
          encoder TEXT,
          gpu_name TEXT,
          sample_count INTEGER NOT NULL,
          mean_fps REAL NOT NULL,
          median_fps REAL NOT NULL,
          p20_fps REAL NOT NULL,
          p80_fps REAL NOT NULL,
          mean_seconds_per_frame REAL NOT NULL,
          last_updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_stage_stats_job ON job_stage_stats(job_id);
        CREATE INDEX IF NOT EXISTS idx_stage_stats_stage ON job_stage_stats(stage_name);
        CREATE INDEX IF NOT EXISTS idx_profiles_stage ON performance_profiles(stage_name);
        """
    )
    conn.commit()

