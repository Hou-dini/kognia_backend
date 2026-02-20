import os

import asyncpg
from asyncpg.pool import Pool

# This will hold our database connection pool
db_pool: Pool | None = None


def ensure_db_pool() -> None:
    """
    Raises RuntimeError if the database pool is not initialized.
    """
    if db_pool is None:
        raise RuntimeError("Database pool is not initialized")


async def init_db_pool():
    global db_pool
    database_url = os.environ.get("DATABASE_URL", "")
    db_pool = await asyncpg.create_pool(
        database_url,
        min_size=1,
        max_size=10,
        statement_cache_size=0
    )
    return db_pool


async def close_db_pool():
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None


async def get_or_create_user_profile(conn, user_id):
    """
    Ensures an entry exists in the public.user_profiles table for a given user_id.
    """
    existing_profile_id = await conn.fetchval("SELECT id FROM user_profiles WHERE id = $1", user_id)
    if existing_profile_id:
        return user_id

    try:
        await conn.execute(
            "INSERT INTO user_profiles (id, created_at, updated_at) VALUES ($1, NOW(), NOW())",
            user_id
        )
        print(f"Created new user_profile entry for auth.uid(): {user_id}")
    except Exception:
        existing_profile_id = await conn.fetchval("SELECT id FROM user_profiles WHERE id = $1", user_id)
        if existing_profile_id:
            return user_id
        raise
    return user_id
