#!/usr/bin/env python3
"""Create, verify, compress, and rotate consistent TechNexus SQLite backups."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_database(path: Path) -> None:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {result}")
    finally:
        connection.close()


def create_backup(source: Path, backup_dir: Path, retention_days: int) -> dict:
    if not source.is_file():
        raise FileNotFoundError(f"Database not found: {source}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        backup_dir.chmod(0o700)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    final_path = backup_dir / f"technexus-{timestamp}.db.gz"

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="technexus-backup-", suffix=".db", dir=backup_dir, delete=False) as handle:
            temporary_path = Path(handle.name)
        source_connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        target_connection = sqlite3.connect(temporary_path)
        try:
            source_connection.backup(target_connection)
        finally:
            target_connection.close()
            source_connection.close()

        verify_database(temporary_path)
        with temporary_path.open("rb") as raw, gzip.open(final_path, "wb", compresslevel=6) as compressed:
            shutil.copyfileobj(raw, compressed, length=1024 * 1024)
        checksum = sha256_file(final_path)
        checksum_path = final_path.with_suffix(final_path.suffix + ".sha256")
        checksum_path.write_text(f"{checksum}  {final_path.name}\n", encoding="ascii")
        if os.name != "nt":
            final_path.chmod(0o600)
            checksum_path.chmod(0o600)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()

    cutoff = datetime.now(timezone.utc).timestamp() - max(1, retention_days) * 86400
    removed = 0
    for candidate in backup_dir.glob("technexus-*.db.gz"):
        if candidate.stat().st_mtime >= cutoff:
            continue
        checksum_path = candidate.with_suffix(candidate.suffix + ".sha256")
        candidate.unlink()
        if checksum_path.exists():
            checksum_path.unlink()
        removed += 1

    return {
        "ok": True,
        "source": str(source),
        "backup": str(final_path),
        "bytes": final_path.stat().st_size,
        "sha256": checksum,
        "integrity_check": "ok",
        "retention_days": retention_days,
        "removed_old_backups": removed,
    }


def main() -> int:
    project_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Back up the TechNexus production SQLite database")
    parser.add_argument("--source", type=Path, default=project_dir / "technexus_data" / "technexus.db")
    parser.add_argument("--backup-dir", type=Path, default=project_dir / "technexus_data" / "backups")
    parser.add_argument("--retention-days", type=int, default=30)
    args = parser.parse_args()
    result = create_backup(args.source.resolve(), args.backup_dir.resolve(), args.retention_days)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
