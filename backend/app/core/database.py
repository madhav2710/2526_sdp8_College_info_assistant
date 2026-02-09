import os
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path
import httpx

# Load environment variables from env file in the backend directory.
# Prefer `.env` but fall back to `_env` (your project currently uses `_env`).
backend_root = Path(__file__).resolve().parent.parent.parent
env_path = backend_root / '.env'
if not env_path.exists():
    alt_env_path = backend_root / '_env'
    if alt_env_path.exists():
        env_path = alt_env_path

load_dotenv(dotenv_path=env_path)

def _read_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _resolve_env(primary_name: str, *alias_names: str) -> str | None:
    primary_value = _read_env(primary_name)
    alias_values = {alias_name: _read_env(alias_name) for alias_name in alias_names}

    if primary_value:
        for alias_name, alias_value in alias_values.items():
            if alias_value and alias_value != primary_value:
                raise ValueError(
                    f"Conflicting Supabase env values: {primary_name} and {alias_name} differ. "
                    "Use one unified Supabase project for all data."
                )
        return primary_value

    non_empty_aliases = {name: value for name, value in alias_values.items() if value}
    distinct_values = set(non_empty_aliases.values())
    if len(distinct_values) > 1:
        conflict_names = ", ".join(sorted(non_empty_aliases.keys()))
        raise ValueError(
            f"Conflicting Supabase env values across aliases ({conflict_names}). "
            "Use one unified Supabase project for all data."
        )

    return next(iter(distinct_values)) if distinct_values else None


def _ensure_secondary_alias_matches(primary_value: str | None, secondary_name: str) -> None:
    secondary_value = _read_env(secondary_name)
    if secondary_value and primary_value and secondary_value != primary_value:
        raise ValueError(
            f"{secondary_name} points to a different Supabase project. "
            "This app is configured for a single unified Supabase project."
        )


url: str = _resolve_env("SUPABASE_URL", "supabase_url")
key: str = _resolve_env("SUPABASE_KEY", "supabase_key")
service_key: str = _resolve_env("SUPABASE_SERVICE_ROLE_KEY", "SERVICE_ROLE_KEY", "supabase_service_role_key")

for legacy_url_var in ("RAG_SUPABASE_URL", "SUPABASE_RAG_URL", "VECTOR_SUPABASE_URL"):
    _ensure_secondary_alias_matches(url, legacy_url_var)

for legacy_key_var in ("RAG_SUPABASE_KEY", "SUPABASE_RAG_KEY", "VECTOR_SUPABASE_KEY"):
    _ensure_secondary_alias_matches(key, legacy_key_var)

for legacy_service_var in (
    "RAG_SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_RAG_SERVICE_ROLE_KEY",
    "VECTOR_SUPABASE_SERVICE_ROLE_KEY",
):
    _ensure_secondary_alias_matches(service_key, legacy_service_var)

if not url or not key:
    raise ValueError(
        "Supabase credentials not found in environment. "
        "Expected SUPABASE_URL and SUPABASE_KEY for the unified project."
    )

# Set a longer timeout for large file uploads
timeout = httpx.Timeout(60.0, connect=10.0)

# Initialize Supabase client without deprecated ClientOptions
supabase: Client = create_client(url, key) if url and key else None

def get_service_client() -> Client:
    if url and service_key:
        return create_client(url, service_key)
    return supabase
