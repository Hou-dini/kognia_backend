import uuid

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_current_user_id
from schemas.session_schemas import MessageResponseItem, SessionSummary
from services.db_service import db_pool

router = APIRouter()

@router.get("", response_model=list[SessionSummary])
async def get_all_sessions(current_user_id: uuid.UUID = Depends(get_current_user_id)):  # noqa: B008
    """
    Retrieves all chat sessions for the authenticated user.
    """
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database connection is not available.")

    try:
        async with db_pool.acquire() as conn:
            sessions = await conn.fetch(
                "SELECT id, title, updated_at FROM sessions WHERE user_id = $1 ORDER BY updated_at DESC",
                current_user_id
            )
            return [
                SessionSummary(
                    id=str(s['id']),
                    title=s['title'],
                    updated_at=s['updated_at'].isoformat()
                ) for s in sessions
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") from e
    
@router.get("/{session_id}/messages", response_model=list[MessageResponseItem])
async def get_session_messages(
    session_id: str,
    current_user_id: uuid.UUID = Depends(get_current_user_id)  # noqa: B008
):
    """
    Retrieves all messages for a specific chat session.
    """
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database connection is not available.")

    try:
        session_uuid = uuid.UUID(session_id)
        async with db_pool.acquire() as conn:
            session_owner_id = await conn.fetchval(
                "SELECT user_id FROM sessions WHERE id = $1",
                session_uuid
            )
            if not session_owner_id or session_owner_id != current_user_id:
                raise HTTPException(status_code=403, detail="Forbidden: You do not own this session.")

            messages = await conn.fetch(
                "SELECT role, content, created_at FROM messages WHERE session_id = $1 ORDER BY created_at ASC",
                session_uuid
            )
            return [
                MessageResponseItem(
                    role=m['role'],
                    content=m['content'],
                    created_at=m['created_at'].isoformat()
                ) for m in messages
            ]
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid session ID format.") from e
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") from e
