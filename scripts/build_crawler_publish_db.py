import json
import sqlite3
import sys
from pathlib import Path


PUBLISH_TABLES = ("candidates", "matches", "dujiao_candidates")


def build_publish_db(source: Path, target: Path) -> dict[str, int]:
    source = source.resolve()
    target = target.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"crawler database does not exist: {source}")
    if target.exists():
        raise FileExistsError(f"publish database already exists: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(target, uri=True)
    counts: dict[str, int] = {}
    try:
        source_uri = f"{source.as_uri()}?mode=ro"
        db.execute("ATTACH DATABASE ? AS source", (source_uri,))
        db.execute("BEGIN IMMEDIATE")
        for table in PUBLISH_TABLES:
            row = db.execute(
                "SELECT sql FROM source.sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if row is None or not row[0]:
                raise RuntimeError(f"crawler database is missing required table: {table}")
            db.execute(row[0])
            db.execute(f'INSERT INTO "{table}" SELECT * FROM source."{table}"')
            counts[table] = int(db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        db.commit()
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("compact crawler publish database validation failed")
    except Exception:
        db.rollback()
        db.close()
        target.unlink(missing_ok=True)
        raise
    db.close()
    return counts


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: build_crawler_publish_db.py SOURCE TARGET", file=sys.stderr)
        return 2
    counts = build_publish_db(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps(counts, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
