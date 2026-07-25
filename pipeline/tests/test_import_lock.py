from common import import_lock, session_for


def test_import_lock_allows_non_postgres_test_databases():
    db = session_for("sqlite://")
    try:
        with import_lock(db):
            assert db.get_bind().dialect.name == "sqlite"
    finally:
        db.close()
