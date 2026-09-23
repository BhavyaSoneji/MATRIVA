"""Ingestion pipeline entrypoint.

Usage:
    python -m pipelines.run --source ../knowledge/ayurveda

Phase 1 will implement parse -> chunk -> metadata -> embed -> write.
This stub only validates the CLI contract described in README.md.
"""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="MATRIVA knowledge ingestion pipeline")
    parser.add_argument("--source", required=True, help="Path to a knowledge/<domain> directory")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        raise SystemExit(f"Source path does not exist: {source}")

    print(f"[ingestion] would process source directory: {source.resolve()}")
    print("[ingestion] pipeline not yet implemented (see Phase 1 of the MVP build plan)")


if __name__ == "__main__":
    main()
