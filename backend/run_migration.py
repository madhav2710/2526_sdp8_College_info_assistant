#!/usr/bin/env python3
"""
Database migration runner for the unified single-project Supabase setup.

Default behavior:
1) Run unified schema bootstrap
2) Run unified schema check queries

Legacy migrations are intentionally moved to: migrations/legacy/
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse, urlunparse

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except Exception:  # pragma: no cover
    psycopg2 = None
    ISOLATION_LEVEL_AUTOCOMMIT = None

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


ROOT = Path(__file__).parent
MIGRATIONS_DIR = ROOT / "migrations"
LEGACY_MIGRATIONS_DIR = MIGRATIONS_DIR / "legacy"

CURRENT_MIGRATIONS = [
    "000_unified_single_project_schema.sql",
    "000_unified_single_project_schema_check.sql",
]

CURRENT_ALL_MIGRATIONS = [
    "000_unified_single_project_schema.sql",
    "000_unified_single_project_schema_check.sql",
    "001_repair_auth_foreign_keys.sql",
    "008_fix_notify_document_status_change_case.sql",
]

MIGRATION_PLANS = {
    "current": CURRENT_MIGRATIONS,
    "current-all": CURRENT_ALL_MIGRATIONS,
    "schema": ["000_unified_single_project_schema.sql"],
    "check": ["000_unified_single_project_schema_check.sql"],
    "repair-auth-fks": ["001_repair_auth_foreign_keys.sql"],
    "hotfix-notify-case": ["008_fix_notify_document_status_change_case.sql"],
}

logger = logging.getLogger("migration_runner")


@dataclass(frozen=True)
class ConnectionCandidate:
    label: str
    dsn: str


def configure_logging(debug: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if value and value.strip():
            return value.strip()
    return None


def load_env_vars(env_file: Path | None = None) -> Path | None:
    if env_file is not None:
        candidate_paths = [env_file]
    else:
        candidate_paths = [ROOT / ".env", ROOT / "_env"]

    for path in candidate_paths:
        if path.exists():
            if load_dotenv is not None:
                load_dotenv(dotenv_path=path, override=False)
            else:
                with open(path, encoding="utf-8") as handle:
                    for line in handle:
                        stripped = line.strip()
                        if not stripped or stripped.startswith("#") or "=" not in stripped:
                            continue
                        key, value = stripped.split("=", 1)
                        os.environ.setdefault(key, value.strip().strip("\"'"))
            logger.info("Loaded environment variables from %s", path)
            return path
    logger.warning("No .env/_env file found in %s; using shell environment only", ROOT)
    return None


def decode_jwt_payload(token: str | None) -> dict:
    if not token:
        return {}
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        return {}


def extract_project_ref_from_supabase_url(supabase_url: str | None) -> str | None:
    if not supabase_url:
        return None
    hostname = urlparse(supabase_url).hostname or ""
    if hostname.endswith(".supabase.co") and "." in hostname:
        return hostname.split(".", 1)[0]
    return None


def extract_project_ref_from_db_url(db_url: str | None) -> str | None:
    if not db_url:
        return None
    hostname = urlparse(db_url).hostname or ""
    if hostname.startswith("db.") and hostname.endswith(".supabase.co"):
        return hostname[len("db.") :].split(".", 1)[0]
    return None


def redact_dsn(dsn: str) -> str:
    parsed = urlparse(dsn)
    if parsed.password is None:
        return dsn
    masked_netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
    return urlunparse(parsed._replace(netloc=masked_netloc))


def ensure_sslmode(dsn: str) -> str:
    if "sslmode=" in dsn:
        return dsn
    separator = "&" if "?" in dsn else "?"
    return f"{dsn}{separator}sslmode=require"


def build_supabase_priority_candidates() -> list[ConnectionCandidate]:
    supabase_url = first_non_empty(os.getenv("SUPABASE_URL"), os.getenv("supabase_url"))
    supabase_key = first_non_empty(os.getenv("SUPABASE_KEY"), os.getenv("supabase_key"))

    project_ref = extract_project_ref_from_supabase_url(supabase_url)
    payload = decode_jwt_payload(supabase_key)
    key_ref = payload.get("ref")
    key_role = payload.get("role")

    logger.debug("SUPABASE_URL present: %s", bool(supabase_url))
    logger.debug("SUPABASE_KEY present: %s", bool(supabase_key))
    logger.debug("Parsed project_ref from SUPABASE_URL: %s", project_ref)
    if key_ref:
        logger.debug("Parsed project_ref from SUPABASE_KEY: %s (role=%s)", key_ref, key_role)

    if project_ref and key_ref and project_ref != key_ref:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY belong to different projects. "
            "Please align environment values for single-project mode."
        )

    candidates: list[ConnectionCandidate] = []

    db_password = first_non_empty(
        os.getenv("SUPABASE_DB_PASSWORD"),
        os.getenv("DB_PASSWORD"),
        os.getenv("SUPABASE_PASSWORD"),
    )
    db_user = first_non_empty(os.getenv("SUPABASE_DB_USER"), os.getenv("DB_USER"), "postgres")
    db_name = first_non_empty(os.getenv("SUPABASE_DB_NAME"), os.getenv("DB_NAME"), "postgres")
    db_port = first_non_empty(os.getenv("SUPABASE_DB_PORT"), os.getenv("DB_PORT"), "5432")

    if project_ref and db_password:
        derived = f"postgresql://{db_user}:{db_password}@db.{project_ref}.supabase.co:{db_port}/{db_name}"
        candidates.append(
            ConnectionCandidate(
                label="derived from SUPABASE_URL (+ DB password)",
                dsn=ensure_sslmode(derived),
            )
        )

    for label, env_var in (
        ("SUPABASE_DB_URL", "SUPABASE_DB_URL"),
        ("DATABASE_URL", "DATABASE_URL"),
    ):
        value = first_non_empty(os.getenv(env_var))
        if not value:
            continue
        candidate_ref = extract_project_ref_from_db_url(value)
        if project_ref and candidate_ref and candidate_ref != project_ref:
            logger.warning(
                "Skipping %s because it targets project '%s', expected '%s'",
                env_var,
                candidate_ref,
                project_ref,
            )
            continue
        candidates.append(ConnectionCandidate(label=label, dsn=ensure_sslmode(value)))

    host = first_non_empty(os.getenv("SUPABASE_DB_HOST"), os.getenv("DB_HOST"))
    if host and db_user and db_name and db_password:
        component_dsn = f"postgresql://{db_user}:{db_password}@{host}:{db_port}/{db_name}"
        candidate_ref = extract_project_ref_from_db_url(component_dsn)
        if not (project_ref and candidate_ref and candidate_ref != project_ref):
            candidates.append(
                ConnectionCandidate(label="DB_* components", dsn=ensure_sslmode(component_dsn))
            )
        else:
            logger.warning(
                "Skipping DB_* components because host targets project '%s', expected '%s'",
                candidate_ref,
                project_ref,
            )

    return candidates


def get_db_connection() -> psycopg2.extensions.connection:
    if psycopg2 is None:
        raise ImportError(
            "psycopg2 is not installed. Install backend dependencies before running migrations."
        )

    candidates = build_supabase_priority_candidates()
    if not candidates:
        raise ValueError(
            "No PostgreSQL connection candidate found. "
            "Set SUPABASE_DB_PASSWORD (preferred) or DATABASE_URL/SUPABASE_DB_URL."
        )

    errors: list[str] = []
    for candidate in candidates:
        redacted = redact_dsn(candidate.dsn)
        logger.info("Trying DB connection via %s: %s", candidate.label, redacted)
        try:
            conn = psycopg2.connect(candidate.dsn, connect_timeout=10)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            logger.info("Connected successfully using %s", candidate.label)
            return conn
        except Exception as exc:
            message = f"{candidate.label}: {exc}"
            errors.append(message)
            logger.warning("Connection attempt failed (%s)", message)

    combined = "\n  - ".join(errors)
    raise ConnectionError(f"Unable to connect to database. Attempts:\n  - {combined}")


def available_current_migrations() -> list[str]:
    return sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql") if path.is_file())


def available_legacy_migrations() -> list[str]:
    if not LEGACY_MIGRATIONS_DIR.exists():
        return []
    return sorted(path.name for path in LEGACY_MIGRATIONS_DIR.glob("*.sql") if path.is_file())


def resolve_migration_path(name: str) -> Path:
    raw = Path(name)
    if raw.exists() and raw.is_file():
        return raw

    current_candidate = MIGRATIONS_DIR / name
    if current_candidate.exists():
        return current_candidate

    legacy_candidate = LEGACY_MIGRATIONS_DIR / name
    if legacy_candidate.exists():
        raise FileNotFoundError(
            f"{name} is in migrations/legacy and is not part of current unified migration flow."
        )

    raise FileNotFoundError(f"Migration file not found: {name}")


def resolve_migration_list(args: argparse.Namespace) -> list[str]:
    if args.list:
        print("Current migrations:")
        for migration in available_current_migrations():
            print(f"  - {migration}")
        legacy = available_legacy_migrations()
        if legacy:
            print("\nLegacy migrations (not run by default):")
            for migration in legacy:
                print(f"  - legacy/{migration}")
        return []

    if args.migrations:
        return args.migrations

    if args.plan not in MIGRATION_PLANS:
        raise ValueError(f"Unknown migration plan: {args.plan}")
    return list(MIGRATION_PLANS[args.plan])


def run_single_migration(conn: psycopg2.extensions.connection, migration_file: str) -> None:
    migration_path = resolve_migration_path(migration_file)
    logger.info("Running migration: %s", migration_path.relative_to(ROOT))

    with open(migration_path, "r", encoding="utf-8") as handle:
        migration_sql = handle.read()

    started = time.time()
    with conn.cursor() as cursor:
        cursor.execute(migration_sql)
    elapsed = time.time() - started
    logger.info("Completed %s in %.2fs", migration_path.name, elapsed)


def run_migrations(migrations: Iterable[str], dry_run: bool = False) -> None:
    migrations = list(migrations)
    logger.info("Selected migrations (%d): %s", len(migrations), ", ".join(migrations))

    if dry_run:
        logger.info("Dry run mode: no SQL executed")
        return

    conn = get_db_connection()
    try:
        for migration in migrations:
            run_single_migration(conn, migration)
    finally:
        conn.close()
        logger.info("Database connection closed")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run SQL migrations for the unified single-project Supabase schema."
    )
    parser.add_argument(
        "migrations",
        nargs="*",
        help="Specific migration files to run (from backend/migrations).",
    )
    parser.add_argument(
        "--plan",
        default="current",
        choices=sorted(MIGRATION_PLANS.keys()),
        help="Predefined migration plan. Default: current",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional explicit env file path. Default: backend/.env then backend/_env",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print selected migrations and exit without executing SQL.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List current and legacy migration files.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(debug=args.debug)

    try:
        load_env_vars(args.env_file)
        migrations = resolve_migration_list(args)
        if not migrations:
            return 0
        run_migrations(migrations, dry_run=args.dry_run)
        logger.info("Migration run finished successfully")
        return 0
    except Exception as exc:
        logger.error("Migration run failed: %s", exc)
        if args.debug:
            logger.exception("Detailed traceback")
        return 1


if __name__ == "__main__":
    sys.exit(main())
