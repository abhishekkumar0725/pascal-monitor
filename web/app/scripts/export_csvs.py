"""Export all legacy CSVs to CSV_EXPORT_DIR.

Usage:
    cd web
    source .venv/bin/activate
    python -m app.scripts.export_csvs

Or via make:
    make sync-csvs
"""
from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.db import async_session_factory
from app.services.csv_export import write_all_csvs_to_dir

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def export_all() -> None:
    """Export all CSVs to the configured export directory."""
    output_dir = settings.csv_export_path
    logger.info("Exporting CSVs to: %s", output_dir)

    async with async_session_factory() as session:
        files = await write_all_csvs_to_dir(session, output_dir)

    for name, path in files.items():
        logger.info("Wrote %s -> %s", name, path)

    logger.info("Export complete.")


def main() -> None:
    """Entry point for the export script."""
    asyncio.run(export_all())


if __name__ == "__main__":
    main()
