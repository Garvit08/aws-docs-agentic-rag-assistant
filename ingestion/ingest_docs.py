
from __future__ import annotations

from pathlib import Path

import requests
import yaml

INGESTION_DIR = Path(__file__).resolve().parent
SOURCES_PATH = INGESTION_DIR / "aws_sources.yaml"
SNAPSHOTS_DIR = INGESTION_DIR / "snapshots"

REQUEST_TIMEOUT = 30  # seconds/request

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def load_sources(path: Path) -> list[dict]:
    """Load the corpus manifest and return the list of source entries."""
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    sources = (data or {}).get("sources") or []
    if not sources:
        raise ValueError(f"No sources found in {path}")
    return sources


def main() -> int:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    sources = load_sources(SOURCES_PATH)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    fetched: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []

    for source in sources:
        source_id = source["id"]
        url = source["url"]
        dest = SNAPSHOTS_DIR / f"{source_id}.html"

        if dest.exists():
            skipped.append(source_id)
            print(f"[skip]    {source_id}: snapshot exists ({dest.name})")
            continue

        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as exc:
            failed.append((source_id, str(exc)))
            print(f"[fail]    {source_id}: {exc}")
            continue

        dest.write_bytes(resp.content)
        fetched.append(source_id)
        print(
            f"[fetched] {source_id}: {resp.status_code} "
            f"{len(resp.content)} bytes -> {dest.name}"
        )

    print("\nSummary:")
    print(f"fetched: {len(fetched)}")
    print(f"skipped (already cached): {len(skipped)}")
    print(f"failed: {len(failed)}")
    for source_id, err in failed:
        print(f"    - {source_id}: {err}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
