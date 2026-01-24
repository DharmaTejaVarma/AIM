import os
from supabase import create_client, Client

_supabase: Client | None = None

def get_supabase() -> Client:
    global _supabase

    if _supabase is not None:
        return _supabase

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY. "
            "Check docker-compose.yml or .env file."
        )

    _supabase = create_client(url, key)
    return _supabase
