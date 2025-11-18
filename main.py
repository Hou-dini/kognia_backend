import uvicorn
import asyncpg
import time
import uuid
from fastapi import FastAPI, HTTPException, Body, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager


# --- Configuration ---
# CRITICAL: Get your Supabase Postgres connection string
# Go to Supabase -> Project Settings -> Database -> Connection string -> URI
# Paste it into an environment variable or right here (for dev).
# Make sure to replace [YOUR-PASSWORD]
# Example: "postgres://postgres:[YOUR-PASSWORD]@db.xxxxxx.supabase.co:5432/postgres"

DATABASE_URL = " "

# This will hold our database connection pool
db_pool = None

# --- Lifespan Management ---
# This function runs on app startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    print("FastAPI app starting up...")
    print("Connecting to Supabase (Postgres)...")
    try:
        global db_pool
        # Create a connection pool
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10
        )
        # Test the connection
        async with db_pool.acquire() as connection:
            test_query = await connection.fetchval("SELECT 1")
            if test_query == 1:
                print("Supabase connection successful!")
            else:
                raise Exception("Failed to verify Supabase connection.")
        print("Database pool created.")
    except Exception as e:
        print(f"FATAL: Could not connect to database: {e}")
        # In a real app, you might want to prevent startup
        # For our sprint, we log and continue, but it will fail on requests.
        db_pool = None # Ensure it's None if setup failed

    yield # This is where the app runs

    # --- Shutdown ---
    print("FastAPI app shutting down...")
    if db_pool:
        await db_pool.close()
        print("Database pool closed.")

# --- FastAPI App Initialization ---

app = FastAPI(
    title="BrandSpark API (Unified)",
    description="API to manage agentic brand analysis jobs. Runs agents as background tasks.",
    version="0.2.0",
    lifespan=lifespan # Use our startup/shutdown manager
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for our sprint
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class JobRequest(BaseModel):
    prompt: str = Field(..., min_length=10, description="The user's prompt for analysis.")

class JobStatus(BaseModel):
    job_id: str
    status: str

class ReportResponse(BaseModel):
    job_id: str
    status: str
    report: str | None = None

# --- Agent Logic (To be run in background) ---

async def run_agent_task(job_id: str, prompt: str):
    """
    This is the "agentic core" logic.
    It runs in the background *after* the /api/v1/jobs request has returned.
    """
    print(f"[Agent Task {job_id}]: Starting for prompt: {prompt}")
    
    try:
        # 1. Acquire a connection from the pool
        async with db_pool.acquire() as conn:
            # 2. Update job status to 'running'
            print(f"[Agent Task {job_id}]: Setting status to 'running'")
            await conn.execute(
                "UPDATE jobs SET status = 'running' WHERE id = $1",
                job_id
            )

            # 3. --- STUBBED AGENT WORK ---
            # This is where we will call the ADK and agents (Day 4-6)
            # For now, we simulate a 10-second task
            print(f"[Agent Task {job_id}]: Simulating 10s of agentic work...")
            time.sleep(10) # Using time.sleep() for simplicity in this stub
            
            # This is the fake report our "Synthesizer Agent" would create
            stub_report_content = (
                f"# Analysis Report\n\n"
                f"## Prompt: {prompt}\n\n"
                f"- This is a **simulated report** for job_id: `{job_id}`.\n"
                f"- The real agent swarm will generate a full market analysis here.\n"
                f"- For example, we'd analyze competitors and summarize findings."
            )
            print(f"[Agent Task {job_id}]: Work complete. Generating report.")

            # 4. Save the report to the 'reports' table
            # We use a transaction to be safe
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO reports (job_id, content) VALUES ($1, $2)",
                    job_id, stub_report_content
                )
                
                # 5. Update job status to 'complete'
                await conn.execute(
                    "UPDATE jobs SET status = 'complete' WHERE id = $1",
                    job_id
                )
            
            print(f"[Agent Task {job_id}]: Finished successfully. Report saved.")

    except Exception as e:
        print(f"[Agent Task {job_id}]: FAILED with error: {e}")
        # If anything fails, mark the job as 'error'
        try:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE jobs SET status = 'error' WHERE id = $1",
                    job_id
                )
        except Exception as db_e:
            print(f"[Agent Task {job_id}]: FAILED TO EVEN MARK AS ERROR: {db_e}")

# --- API Endpoints ---

@app.post("/api/v1/jobs", response_model=JobStatus)
async def create_job(
    background_tasks: BackgroundTasks, # FastAPI injects this
    job_request: JobRequest = Body(...)
):
    """
    Create a new analysis job.
    This runs instantly, creates the job, and schedules the agent
    to run in the background.
    """
    print(f"Received new job request with prompt: {job_request.prompt}")
    
    if db_pool is None:
        raise HTTPException(
            status_code=503, 
            detail="Database connection is not available. Check server logs."
        )

    try:
        # 1. Acquire a connection from the pool
        async with db_pool.acquire() as conn:
            
            # 2. Insert the new job into the 'jobs' table
            new_job_id = await conn.fetchval(
                "INSERT INTO jobs (prompt, status) VALUES ($1, $2) RETURNING id",
                job_request.prompt, 'pending'
            )
            
            if not new_job_id:
                raise HTTPException(status_code=500, detail="Failed to create job in database.")

            # 3. Add the REAL agent task to the background queue
            background_tasks.add_task(run_agent_task, new_job_id, job_request.prompt)
            
            print(f"Job {new_job_id} created and background task scheduled.")
            
            # 4. Return the new job ID and 'pending' status immediately
            return JobStatus(job_id=str(new_job_id), status="pending")
    
    except Exception as e:
        print(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@app.get("/api/v1/jobs/{job_id}", response_model=ReportResponse)
async def get_job_status(job_id: str):
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
        job_uuid = uuid.UUID(job_id) # Validate UUID format
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format. Must be a UUID.")

    try:
        async with db_pool.acquire() as conn:
            # Check the job status first
            job_record = await conn.fetchrow("SELECT status FROM jobs WHERE id = $1", job_uuid)
            
            if not job_record:
                raise HTTPException(status_code=404, detail="Job not found")

            status = job_record['status']

            if status == "complete":
                # If complete, fetch the report content
                report_content = await conn.fetchval(
                    "SELECT content FROM reports WHERE job_id = $1",
                    job_uuid
                )
                return ReportResponse(job_id=job_id, status="complete", report=report_content)
            
            else:
                # If 'pending', 'running', or 'error', just return the status
                return ReportResponse(job_id=job_id, status=status, report=None)

    except Exception as e:
        print(f"Error fetching job status: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


# --- Main Entry Point ---
if __name__ == "__main__":
    # Note: Uvicorn's 'reload=True' is great for dev but can be tricky
    # with lifespan events. For production, run with gunicorn or similar.
    print("Starting Uvicorn server in reload mode...")
    
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)