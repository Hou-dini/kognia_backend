import uvicorn
import asyncpg
import uuid
import os
import json # Added for JWT parsing

from fastapi import FastAPI, HTTPException, Body, BackgroundTasks, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials # Added for auth
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

# For JWT verification
from jose import jwt, jwk # Added for JWT
from jose.utils import base64url_decode # Added for JWT

from google.genai import types
from google.adk.runners import Runner
from google.adk.memory import InMemoryMemoryService
from google.adk.sessions import DatabaseSessionService
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.plugins.logging_plugin import LoggingPlugin

from agents.agent import root_agent

# --- Configuration ---
DATABASE_URL = os.environ.get("DATABASE_URL", "")
# --- NEW: Supabase JWT Secret ---
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET","")

if not DATABASE_URL:
    print("FATAL: DATABASE_URL environment variable not set.")
    exit(1)
if not SUPABASE_JWT_SECRET:
    print("FATAL: SUPABASE_JWT_SECRET environment variable not set.")
    exit(1)


# This will hold our database connection pool
db_pool = None

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
            max_size=10
        )
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
        base_db_url = DATABASE_URL
        if base_db_url.startswith("postgresql://"):
            adk_db_url_base = "postgresql+psycopg://" + base_db_url[len("postgresql://"):]
        else:
            print(f"WARNING: Unexpected DATABASE_URL format: {base_db_url}. Using as is.")
            adk_db_url_base = base_db_url

        # Using a separate schema for ADK tables to avoid clashes
        adk_db_url_with_schema = f"{adk_db_url_base}?options=-csearch_path%3Dadk_schema"
        
        memory_service = InMemoryMemoryService()
        session_service = DatabaseSessionService(db_url=adk_db_url_with_schema)
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
        print("ADK Agent Runner initialized.")
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
    title="Flux API (Unified)",
    description="API to manage agentic brand and competitor analysis jobs. Runs agents as background tasks.",
    version="0.5.0",
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

# --- NEW: Supabase JWT Authentication Dependency ---
security = HTTPBearer()

async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> uuid.UUID:
    """
    Decodes and verifies the Supabase JWT from the Authorization header
    and returns the user_id (UUID).
    """
    token = credentials.credentials # This is the JWT string
    
    try:
        # Supabase JWTs are generally HS256 signed with the project's JWT secret
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub") # 'sub' claim is the user ID in Supabase JWTs

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials: Missing user ID in token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Ensure the user_id is a valid UUID
        return uuid.UUID(user_id)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials: Invalid token signature or format.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ValueError: # If user_id is not a valid UUID string
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials: Invalid user ID format in token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# --- Pydantic Models ---
class JobRequest(BaseModel):
    prompt: str = Field(..., min_length=10, description="The user's prompt for analysis.")
    session_id: str = Field(..., description="UUID generated by the frontend for this chat session.")
    # Removed auth_token from here, it will come via header

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
    created_at: str # Renamed timestamp to created_at


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
        await update_job_status(job_id, "error")
        return
    
    try:
        await update_job_status(job_id, "running")

        print(f"[Job {job_id}]: Creating ADK session: {session_id} for user: {user_id}...")
        try:
            # ADK's session service has its own session management.
            # Make sure this `user_id` is passed correctly to ADK's `create_session`
            await runner.session_service.create_session(app_name="agents", user_id=str(user_id), session_id=session_id)
            print(f"[Job {job_id}]: ADK Session created successfully.")
        except Exception as e:
            # This might happen if ADK session already exists, which is fine.
            print(f"[Job {job_id}]: ADK Session creation warning (might already exist): {e}")


        # Log user's message to the DB
        async with db_pool.acquire() as conn:
            # --- MODIFIED: Added user_id to INSERT ---
            await conn.execute(
                "INSERT INTO messages (session_id, user_id, role, content, created_at) VALUES($1, $2, $3, $4, NOW())",
                uuid.UUID(session_id), user_id, "user", prompt
            )

        report_content = await get_agent_response(runner, prompt, str(user_id), session_id) # ADK expects string for user_id

        if not report_content:
            print(f"[Job {job_id}]: FATAL- No report content received from agent.")
            await update_job_status(job_id, "error")
            return
        
        print(f"[Job {job_id}]: Archiving session to Long-Term Memory...")
        try:
            session_obj = await runner.session_service.get_session(
                app_name="agents", user_id=str(user_id), session_id=session_id # ADK expects string for user_id
            )
            if session_obj:
                await runner.memory_service.add_session_to_memory(session_obj)
                print(f"[Job {job_id}]: Session archived successfully.")
            else:
                print(f"[Job {job_id}]: WARNING- Session object not found for archiving.")
        except Exception as mem_e:
            print(f"[Job {job_id}]: WARNING- Failed to save memory: {mem_e}")

        # Log agent's report to the DB
        async with db_pool.acquire() as conn:
            # --- MODIFIED: Added user_id to INSERT ---
            await conn.execute(
                "INSERT INTO messages (session_id, user_id, role, content, created_at) VALUES($1, $2, $3, $4, NOW())",
                uuid.UUID(session_id), user_id, "agent", report_content
            )

        # 4. Save Report and Complete Job
        async with db_pool.acquire() as conn:
            # --- MODIFIED: Added user_id to INSERT ---
            await conn.execute(
                "INSERT INTO reports (job_id, user_id, content) VALUES($1, $2, $3)",
                uuid.UUID(job_id), user_id, report_content
            )

            await update_job_status(job_id, "complete")
        print(f"[Job {job_id}]: Success Report Saved.")

    except Exception as e:
        print(f"[Job {job_id}]: FATAL- Error: {e}")
        await update_job_status(job_id, "error")


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
        async with db_pool.acquire() as conn:
            # --- MODIFIED: Now using public.job_status_enum ---
            await conn.execute(
                "UPDATE jobs SET status = $1::public.job_status_enum, updated_at = NOW() WHERE id = $2",
                status,
                uuid.UUID(job_id)
            )
        print(f"[Job {job_id}]: Status updated to '{status}'.")
    except Exception as e:
        print(f"[Job {job_id}]: Error updating status to '{status}': {e}")


# --- NEW: Function to ensure user_profile entry exists ---
async def get_or_create_user_profile(conn, user_id: uuid.UUID):
    """
    Ensures an entry exists in the public.user_profiles table for a given user_id.
    This is called once the user's Supabase auth.uid() is known.
    """
    # Check if user profile already exists
    existing_profile_id = await conn.fetchval("SELECT id FROM user_profiles WHERE id = $1", user_id)
    if existing_profile_id:
        return user_id

    # User profile doesn't exist, create one with minimal data
    try:
        await conn.execute(
            "INSERT INTO user_profiles (id, created_at, updated_at) VALUES ($1, NOW(), NOW())",
            user_id
        )
        print(f"Created new user_profile entry for auth.uid(): {user_id}")
    except Exception as e:
        # A race condition might occur where another request creates the profile
        # Try to fetch again, if still fails, re-raise.
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
    current_user_id: uuid.UUID = Depends(get_current_user_id) # NEW: Use auth dependency
):
    """
    Create a new analysis job.
    This runs instantly, creates the job, and schedules the agent
    to run in the background.
    """
    authenticated_user_id = current_user_id # Renamed for clarity
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

            if existing_session_owner is None: # Session doesn't exist
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
                # Optionally update title/updated_at if session already exists
                await conn.execute(
                    "UPDATE sessions SET title = $1, updated_at = NOW() WHERE id = $2",
                    job_request.prompt[:50], uuid.UUID(client_session_id)
                )
            
            # 2. Insert the new job into the 'jobs' table
            new_job_id = await conn.fetchval(
                # --- MODIFIED: Added user_id to INSERT ---
                "INSERT INTO jobs (user_id, session_id, prompt, status, created_at, updated_at) VALUES ($1, $2, $3, $4::public.job_status_enum, NOW(), NOW()) RETURNING id",
                authenticated_user_id, uuid.UUID(client_session_id), job_request.prompt, 'pending'
            )
            
            if not new_job_id:
                raise HTTPException(status_code=500, detail="Failed to create job in database.")

            # 3. Add the REAL agent task to the background queue
            background_tasks.add_task(
                run_agent_task, str(new_job_id), job_request.prompt, 
                authenticated_user_id, # Pass the UUID object
                client_session_id,
            )
            
            print(f"Job {new_job_id} created and background task scheduled.")
            
            return JobStatus(job_id=str(new_job_id), status="pending")
    
    except Exception as e:
        print(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@app.get("/api/v1/jobs/{job_id}", response_model=ReportResponse)
async def get_job_status(job_id: str, current_user_id: uuid.UUID = Depends(get_current_user_id)): # NEW: Add auth dependency
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
        async with db_pool.acquire() as conn:
            # --- MODIFIED: Added user_id to SELECT for RLS compatibility ---
            job_record = await conn.fetchrow(
                "SELECT status FROM jobs WHERE id = $1 AND user_id = $2",
                job_uuid, current_user_id
            )
            
            if not job_record:
                # IMPORTANT: Return 404 if not found OR not owned by user (RLS handles this too but explicit is clearer)
                raise HTTPException(status_code=404, detail="Job not found or not accessible.")

            status = job_record['status']

            if status == "complete":
                # --- MODIFIED: Added user_id to SELECT for RLS compatibility ---
                report_content = await conn.fetchval(
                    "SELECT content FROM reports WHERE job_id = $1 AND user_id = $2",
                    job_uuid, current_user_id
                )
                return ReportResponse(job_id=job_id, status="complete", report=report_content)
            
            else:
                return ReportResponse(job_id=job_id, status=status, report=None)

    except Exception as e:
        print(f"Error fetching job status: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
    

@app.get("/api/v1/sessions", response_model=list[SessionSummary])
async def get_all_sessions(current_user_id: uuid.UUID = Depends(get_current_user_id)): # NEW: Use auth dependency
    """
    Retrieves all chat sessions for the authenticated user.
    """
    if db_pool is None:
        raise HTTPException(
            status_code=503,
            detail="Database connection is not available."
        )

    try:
        authenticated_user_id = current_user_id # Using the ID from the JWT
        
        async with db_pool.acquire() as conn:
            # This query is already good, RLS will also filter by user_id
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
    
# --- REMOVED: is_valid_uuid helper as it's not needed with UUID type hints and JWT verification ---

@app.get("/api/v1/sessions/{session_id}/messages", response_model=list[MessageResponseItem])
async def get_session_messages(
    session_id: str,
    current_user_id: uuid.UUID = Depends(get_current_user_id) # NEW: Use auth dependency
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
        authenticated_user_id = current_user_id # Using the ID from the JWT

        async with db_pool.acquire() as conn:
            # First, verify that the session belongs to the authenticated user
            # RLS will also prevent fetching, but explicit check is good practice here.
            session_owner_id = await conn.fetchval(
                "SELECT user_id FROM sessions WHERE id = $1",
                session_uuid
            )
            if not session_owner_id or session_owner_id != authenticated_user_id:
                raise HTTPException(status_code=403, detail="Forbidden: You do not own this session or it does not exist.")

            # If authorized, fetch messages
            messages = await conn.fetch(
                # --- MODIFIED: Renamed timestamp to created_at ---
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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) # Changed host to 0.0.0.0 for external access