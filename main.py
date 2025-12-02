import binascii
import datetime
import uvicorn
import asyncpg
import uuid
import os
from typing import Optional
from asyncpg.pool import Pool
import hashlib

from fastapi import FastAPI, HTTPException, Body, BackgroundTasks, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

import jwt as pyjwt
from jwt import PyJWTError, ExpiredSignatureError, InvalidSignatureError, DecodeError


from google.genai import types
from google.adk.runners import Runner
from google.adk.memory import InMemoryMemoryService
from google.adk.sessions import InMemorySessionService 
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.plugins.logging_plugin import LoggingPlugin

from agents.agent import root_agent

# --- Configuration ---
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres.nmqruitpbhkjcuucqkgn:Kognia_reloaded@aws-1-eu-north-1.pooler.supabase.com:5432/postgres")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET","o/rAeML82YdqtjbstQR/Ir/O0EGvgwKD5USFWm/gE7DoDOeRUtFic/tBPZRy2xbVxWYHVrsWIuKTaV02m1me0w==")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY","AIzaSyBPQQL3w1UQB7eHNLra_5Xm3N9aV9t37qs")

if not DATABASE_URL:
    print("FATAL: DATABASE_URL environment variable not set.")
    exit(1)
if not SUPABASE_JWT_SECRET:
    print("FATAL: SUPABASE_JWT_SECRET environment variable not set.")
    exit(1)
if not GOOGLE_API_KEY:
    print("FATAL: GOOGLE_API_KEY environment variable not set.")
    exit(1)

# This will hold our database connection pool
db_pool: Optional[Pool] = None


def ensure_db_pool() -> None:
    """
    Raises RuntimeError if the database pool is not initialized.
    Used to make usage sites explicit for static analysis and runtime checks.
    """
    if db_pool is None:
        raise RuntimeError("Database pool is not initialized")

# --- Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    print("FastAPI app starting up...")
    print("Connecting to Supabase (Postgres)...")
    try:
        global db_pool
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            statement_cache_size=0
        )
        ensure_db_pool()
        async with db_pool.acquire() as connection:
            test_query = await connection.fetchval("SELECT 1")
            if test_query == 1:
                print("Supabase connection successful!")
            else:
                raise Exception("Failed to verify Supabase connection.")
        print("Database pool created.")
    except Exception as e:
        print(f"FATAL: Could not connect to database: {e}")
        db_pool = None

    print("Initializing ADK Agent Runner and Services...")
    try:
        # --- REMOVED DatabaseSessionService and its DB_URL setup ---
        # because there were errors involving ADK creating its sessions table in Supabase
        # --- Using InMemorySessionService instead ---
        memory_service = InMemoryMemoryService()
        session_service = InMemorySessionService() 
        
        app_with_compaction = App(
            name="agents",
            root_agent=root_agent,
            events_compaction_config=EventsCompactionConfig(
                compaction_interval=5,
                overlap_size=2,
            ),
            plugins=[LoggingPlugin()]
        )
        runner_instance = Runner(
            app=app_with_compaction,
            memory_service=memory_service,
            session_service=session_service
        )
        print("ADK Agent Runner initialized with InMemorySessionService.") 
        app.state.runner = runner_instance
    except Exception as e:
        print(f"FATAL: Could not initialize ADK Agent Runner: {e}")
        app.state.runner = None

    yield

    # --- Shutdown ---
    print("FastAPI app shutting down...")
    if db_pool:
        await db_pool.close()
        print("Database pool closed.")

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Kognia API (Unified)",
    description="A FastAPI backend that runs agentic analysis jobs and manages sessions, messages and reports.",
    version="0.6.0",
    lifespan=lifespan
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Supabase JWT Authentication Dependency ---
security = HTTPBearer()

async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> uuid.UUID:
    """
    Decodes and verifies the Supabase JWT from the Authorization header
    and returns the user_id (UUID).
    """
    token = credentials.credentials # This is the JWT string

    if not SUPABASE_JWT_SECRET:
        print("FATAL: SUPABASE_JWT_SECRET environment variable not set or is empty.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: JWT secret not set."
        )

    # SUPABASE_JWT_SECRET holds a 64 byte key that results in `Signature verification failed` error when
    # used to verify the token.  The token was signed with `HS256`, which requires a 32-byte key.
    # Attempting to verify a 32-byte (HS256) signature with a 64-byte key (derived from Base64 decoding)
    # caused the `Signature verification failed` error.
    try:
        # So we convert it to 32 bytes by:
        # 1. Encoding it to its UTF-8 byte representation (88 bytes).
        # 2. Applying `hashlib.sha256()` to this 88-byte string, which produces the required 32-byte (256-bit) digest.
        jwt_secret_bytes = hashlib.sha256(SUPABASE_JWT_SECRET.encode('utf-8')).digest()
        print(f"DEBUG: Calculated JWT Secret successfully. Length of bytes: {len(jwt_secret_bytes)}")
        print(f"DEBUG: Calculated Secret Hex: {binascii.hexlify(jwt_secret_bytes).decode('ascii')}")
    except Exception as e:
        print(f"FATAL: Error hashing SUPABASE_JWT_SECRET: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: Invalid JWT secret processing."
        )
    
    print(f"DEBUG: Raw token received (first 60 chars): {token[:60]}...")
    print(f"DEBUG: Token length: {len(token)}")
    print(f"DEBUG: Server current UTC time: {datetime.datetime.now(datetime.timezone.utc).isoformat()}")

    user_id = None

    try:
        payload = pyjwt.decode(
            token,
            key=jwt_secret_bytes,
            algorithms=["HS256"],
            options={
                "verify_aud": False,
                "verify_iss": False,
            }
        )

        print("DEBUG: JWT DECODE SUCCESS (PyJWT)!")
        user_id = payload.get("sub")

        if not user_id:
            print("DEBUG: JWT payload missing 'sub' claim.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials: Missing user ID in token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        parsed_user_id = uuid.UUID(user_id)
        print(f"DEBUG: Authenticated user_id: {parsed_user_id}")
        return parsed_user_id
        
    except ExpiredSignatureError:
        print("DEBUG: Token has expired (PyJWT).")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidSignatureError as e:
        print(f"DEBUG: JWT signature verification failed (PyJWT): {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: Invalid signature. ({e})",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except DecodeError as e:
        print(f"DEBUG: JWT decode error (PyJWT): {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: Invalid token format or algorithm. ({e})",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except PyJWTError as e:
        print(f"DEBUG: Generic PyJWT error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ValueError as e:
        print(f"DEBUG: Invalid UUID format for user_id in token: {user_id}. Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials: Invalid user ID format in token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        print(f"DEBUG: Unexpected error during JWT authentication: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authentication.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# --- Pydantic Models ---
class JobRequest(BaseModel):
    prompt: str = Field(..., min_length=2, description="The user's prompt for analysis.")
    session_id: str = Field(..., description="UUID generated by the frontend for this chat session.")

class JobStatus(BaseModel):
    job_id: str
    status: str

class ReportResponse(BaseModel):
    job_id: str
    status: str
    report: str | None = None

class SessionSummary(BaseModel):
    id: str
    title: str
    updated_at: str

class MessageResponseItem(BaseModel):
    role: str
    content: str
    created_at: str


# --- Agent Logic (To be run in background) ---

async def run_agent_task(job_id: str, prompt: str, user_id: uuid.UUID, session_id: str):
    """
    Runs the agent for a given job in the background.
    Updates the job status and stores the report in the database.
    """
    print(f"[Job {job_id}]: Starting background agent task...")

    runner = app.state.runner
    if not runner:
        print(f"[Job {job_id}]: FATAL- Runner not initialized.")
        await update_job_status(job_id, "failed")
        return
    
    try:
        await update_job_status(job_id, "processing")

        print(f"[Job {job_id}]: Creating ADK session: {session_id} for user: {user_id}...")
        try:
            # ADK's session service has its own session management.
            # Make sure this `user_id` is passed correctly to ADK's `create_session`
            # For InMemorySessionService, this just creates an in-memory session.
            await runner.session_service.create_session(app_name="agents", user_id=str(user_id), session_id=session_id)
            print(f"[Job {job_id}]: ADK Session created successfully.")
        except Exception as e:
            # This might happen if ADK session already exists, which is fine.
            # With InMemorySessionService, this is less likely to error on creation.
            print(f"[Job {job_id}]: ADK Session creation warning (might already exist): {e}")


        # Log user's message to the DB
        ensure_db_pool()
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO messages (session_id, user_id, role, content, created_at) VALUES($1, $2, $3, $4, NOW())",
                uuid.UUID(session_id), user_id, "user", prompt
            )

        report_content = await get_agent_response(runner, prompt, str(user_id), session_id)

        if not report_content:
            print(f"[Job {job_id}]: FATAL- No report content received from agent.")
            await update_job_status(job_id, "failed")
            return
        
        print(f"[Job {job_id}]: Archiving session to Long-Term Memory...")
        try:
            # InMemorySessionService does not persist, but InMemoryMemoryService will still work
            # within the current process lifetime.
            session_obj = await runner.session_service.get_session(
                app_name="agents", user_id=str(user_id), session_id=session_id
            )
            if session_obj:
                await runner.memory_service.add_session_to_memory(session_obj)
                print(f"[Job {job_id}]: Session archived successfully (to in-memory memory service).")
            else:
                print(f"[Job {job_id}]: WARNING- Session object not found for archiving.")
        except Exception as mem_e:
            print(f"[Job {job_id}]: WARNING- Failed to save memory: {mem_e}")

        # Log agent's report to the DB
        ensure_db_pool()
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO messages (session_id, user_id, role, content, created_at) VALUES($1, $2, $3, $4, NOW())",
                uuid.UUID(session_id), user_id, "agent", report_content
            )

        # 4. Save Report and Complete Job
        ensure_db_pool()
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO reports (job_id, user_id, content) VALUES($1, $2, $3)",
                uuid.UUID(job_id), user_id, report_content
            )

            await update_job_status(job_id, "completed")
        print(f"[Job {job_id}]: Success Report Saved.")

    except Exception as e:
        print(f"[Job {job_id}]: FATAL- Error: {e}")
        await update_job_status(job_id, "failed")


async def get_agent_response(runner, prompt: str, user_id: str, session_id: str) -> str:
    """
    Runs the agent and extracts the final text response for the database.
    """
    user_input = types.Content(
        role="user",
        parts=[types.Part(text=prompt)]
    )

    final_text = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_input,
    ):
        if event.is_final_response and event.content and event.content.parts:
            final_text = event.content.parts[0].text
            print(f"[Agent] Final response received.")

    return final_text

async def update_job_status(job_id: str, status: str):
    """
    Updates the status of a job in the database.
    """
    try:
        ensure_db_pool()
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE jobs SET status = $1::public.job_status_enum, updated_at = NOW() WHERE id = $2",
                status,
                uuid.UUID(job_id)
            )
        print(f"[Job {job_id}]: Status updated to '{status}'.")
    except Exception as e:
        print(f"[Job {job_id}]: Error updating status to '{status}': {e}")


# --- Function to ensure user_profile entry exists ---
async def get_or_create_user_profile(conn, user_id: uuid.UUID):
    """
    Ensures an entry exists in the public.user_profiles table for a given user_id.
    This is called once the user's Supabase auth.uid() is known.
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
    except Exception as e:
        existing_profile_id = await conn.fetchval("SELECT id FROM user_profiles WHERE id = $1", user_id)
        if existing_profile_id:
            return user_id
        raise e
    return user_id


# --- API Endpoints ---

@app.post("/api/v1/jobs", response_model=JobStatus)
async def create_job(
    background_tasks: BackgroundTasks,
    job_request: JobRequest = Body(...),
    current_user_id: uuid.UUID = Depends(get_current_user_id)
):
    """
    Create a new analysis job.
    This runs instantly, creates the job, and schedules the agent
    to run in the background.
    """
    authenticated_user_id = current_user_id
    client_session_id = job_request.session_id
    print(f"Received new job request from {authenticated_user_id} with prompt: {job_request.prompt}")
    
    if db_pool is None:
        raise HTTPException(
            status_code=503, 
            detail="Database connection is not available. Check server logs."
        )

    try:
        async with db_pool.acquire() as conn:
            # 1a. Ensure user_profile exists for RLS
            await get_or_create_user_profile(conn, authenticated_user_id)
            print(f"Ensured user_profile exists for user_id: {authenticated_user_id}")

            # 1b. Create session in DB first (if not exists)
            existing_session_owner = await conn.fetchval(
                "SELECT user_id FROM sessions WHERE id = $1",
                uuid.UUID(client_session_id)
            )

            if existing_session_owner is None:
                await conn.execute(
                    "INSERT INTO sessions (id, user_id, title, created_at, updated_at) VALUES ($1, $2, $3, NOW(), NOW())",
                    uuid.UUID(client_session_id), authenticated_user_id, job_request.prompt[:50]
                )
                print(f"Session {client_session_id} created in DB for user {authenticated_user_id}.")
            elif existing_session_owner != authenticated_user_id:
                 raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Session ID belongs to another user."
                )
            else:
                print(f"Session {client_session_id} already exists in DB for user {authenticated_user_id}.")
                await conn.execute(
                    "UPDATE sessions SET title = $1, updated_at = NOW() WHERE id = $2",
                    job_request.prompt[:50], uuid.UUID(client_session_id)
                )
            
            # 2. Insert the new job into the 'jobs' table
            new_job_id = await conn.fetchval(
                "INSERT INTO jobs (user_id, session_id, prompt, status, created_at, updated_at) VALUES ($1, $2, $3, $4::public.job_status_enum, NOW(), NOW()) RETURNING id",
                authenticated_user_id, uuid.UUID(client_session_id), job_request.prompt, 'pending'
            )
            
            if not new_job_id:
                raise HTTPException(status_code=500, detail="Failed to create job in database.")

            # 3. Add the REAL agent task to the background queue
            background_tasks.add_task(
                run_agent_task, str(new_job_id), job_request.prompt, 
                authenticated_user_id,
                client_session_id,
            )
            
            print(f"Job {new_job_id} created and background task scheduled.")
            
            return JobStatus(job_id=str(new_job_id), status="pending")
    
    except Exception as e:
        print(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@app.get("/api/v1/jobs/{job_id}", response_model=ReportResponse)
async def get_job_status(job_id: str, current_user_id: uuid.UUID = Depends(get_current_user_id)):
    """
    Get the status of a job.
    The frontend will poll this endpoint.
    """
    print(f"Polling for job ID: {job_id}")
    
    if db_pool is None:
        raise HTTPException(
            status_code=503, 
            detail="Database connection is not available."
        )
        
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format. Must be a UUID.")

    try:
        ensure_db_pool()
        async with db_pool.acquire() as conn:
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
        print(f"Error fetching job status: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
    

@app.get("/api/v1/sessions", response_model=list[SessionSummary])
async def get_all_sessions(current_user_id: uuid.UUID = Depends(get_current_user_id)):
    """
    Retrieves all chat sessions for the authenticated user.
    """
    if db_pool is None:
        raise HTTPException(
            status_code=503,
            detail="Database connection is not available."
        )

    try:
        authenticated_user_id = current_user_id

        ensure_db_pool()
        async with db_pool.acquire() as conn:
            sessions = await conn.fetch(
                "SELECT id, title, updated_at FROM sessions WHERE user_id = $1 ORDER BY updated_at DESC",
                authenticated_user_id
            )
            return [
                SessionSummary(
                    id=str(s['id']),
                    title=s['title'],
                    updated_at=s['updated_at'].isoformat()
                ) for s in sessions
            ]
    except Exception as e:
        print(f"Error fetching all sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
    
@app.get("/api/v1/sessions/{session_id}/messages", response_model=list[MessageResponseItem])
async def get_session_messages(
    session_id: str,
    current_user_id: uuid.UUID = Depends(get_current_user_id)
):
    """
    Retrieves all messages for a specific chat session, verifying user ownership.
    """
    if db_pool is None:
        raise HTTPException(
            status_code=503,
            detail="Database connection is not available."
        )

    try:
        session_uuid = uuid.UUID(session_id)
        authenticated_user_id = current_user_id

        ensure_db_pool()
        async with db_pool.acquire() as conn:
            session_owner_id = await conn.fetchval(
                "SELECT user_id FROM sessions WHERE id = $1",
                session_uuid
            )
            if not session_owner_id or session_owner_id != authenticated_user_id:
                raise HTTPException(status_code=403, detail="Forbidden: You do not own this session or it does not exist.")

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
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format. Must be a UUID.")
    except Exception as e:
        print(f"Error fetching messages for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


# --- Main Entry Point ---
if __name__ == "__main__":
    print("Starting Uvicorn server in reload mode...")
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)