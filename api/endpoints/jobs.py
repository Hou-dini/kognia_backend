import uuid

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request, status

from api.dependencies import get_current_user_id
from schemas.job_schemas import JobRequest, JobStatus, ReportResponse
from services import db_service
from services.agent_service import run_agent_task

router = APIRouter()

@router.post("", response_model=JobStatus)
async def create_job(
    request: Request,
    background_tasks: BackgroundTasks,
    job_request: JobRequest = Body(...),  # noqa: B008
    current_user_id: uuid.UUID = Depends(get_current_user_id)  # noqa: B008
):
    """
    Create a new analysis job.
    """
    authenticated_user_id = current_user_id
    client_session_id = job_request.session_id
    
    if db_service.db_pool is None:
        raise HTTPException(
            status_code=503, 
            detail="Database connection is not available."
        )

    try:
        async with db_service.db_pool.acquire() as conn:
            await db_service.get_or_create_user_profile(conn, authenticated_user_id)

            existing_session_owner = await conn.fetchval(
                "SELECT user_id FROM sessions WHERE id = $1",
                uuid.UUID(client_session_id)
            )

            if existing_session_owner is None:
                await conn.execute(
                    "INSERT INTO sessions (id, user_id, title, created_at, updated_at) VALUES ($1, $2, $3, NOW(), NOW())",
                    uuid.UUID(client_session_id), authenticated_user_id, job_request.prompt[:50]
                )
            elif existing_session_owner != authenticated_user_id:
                 raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Session ID belongs to another user."
                )
            else:
                await conn.execute(
                    "UPDATE sessions SET title = $1, updated_at = NOW() WHERE id = $2",
                    job_request.prompt[:50], uuid.UUID(client_session_id)
                )
            
            new_job_id = await conn.fetchval(
                "INSERT INTO jobs (user_id, session_id, prompt, status, created_at, updated_at) VALUES ($1, $2, $3, $4::public.job_status_enum, NOW(), NOW()) RETURNING id",
                authenticated_user_id, uuid.UUID(client_session_id), job_request.prompt, 'pending'
            )
            
            if not new_job_id:
                raise HTTPException(status_code=500, detail="Failed to create job in database.")

            background_tasks.add_task(
                run_agent_task, 
                request.app.state.runner,
                str(new_job_id), 
                job_request.prompt, 
                authenticated_user_id,
                client_session_id,
            )
            
            return JobStatus(job_id=str(new_job_id), status="pending")
    
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") from e


@router.get("/{job_id}", response_model=ReportResponse)
async def get_job_status(job_id: str, current_user_id: uuid.UUID = Depends(get_current_user_id)):  # noqa: B008
    """
    Get the status of a job.
    """
    if db_service.db_pool is None:
        raise HTTPException(status_code=503, detail="Database connection is not available.")
        
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format. Must be a UUID.") from None

    try:
        async with db_service.db_pool.acquire() as conn:
            job_record = await conn.fetchrow(
                "SELECT status FROM jobs WHERE id = $1 AND user_id = $2",
                job_uuid, current_user_id
            )
            
            if not job_record:
                raise HTTPException(status_code=404, detail="Job not found or not accessible.")

            status_val = job_record['status']

            if status_val == "completed":
                report_content = await conn.fetchval(
                    "SELECT content FROM reports WHERE job_id = $1 AND user_id = $2",
                    job_uuid, current_user_id
                )
                return ReportResponse(job_id=job_id, status="completed", report=report_content)
            
            else:
                return ReportResponse(job_id=job_id, status=status_val, report=None)

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") from e
