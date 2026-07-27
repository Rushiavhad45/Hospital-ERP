"""Wipe the SQLite database and uploads, then reseed demo data.

Usage:  python scripts/reset_db.py
"""
from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402


async def main() -> None:
    settings = get_settings()
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite"):
        db_path = Path(db_url.split("///", 1)[1])
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(db_path) + suffix)
            if p.exists():
                p.unlink()
                print(f"removed {p}")
    uploads = Path(settings.UPLOAD_DIR)
    if uploads.exists():
        shutil.rmtree(uploads)
        print(f"removed {uploads}/")

    from app.core.database import SessionLocal, init_db
    from app.utils.seeder import seed_if_empty

    await init_db()
    async with SessionLocal() as db:
        created = await seed_if_empty(db)
    print("Database reset — demo data reseeded." if created
          else "Database reset — seeder skipped (not empty?).")


if __name__ == "__main__":
    asyncio.run(main())
