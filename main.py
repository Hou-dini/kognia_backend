import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.memory import InMemoryMemoryService
from google.adk.plugins.logging_plugin import LoggingPlugin
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from agents.agent import root_agent
from api.endpoints import jobs, sessions
from services.db_service import close_db_pool, init_db_pool

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

if not GOOGLE_API_KEY:
    print("FATAL: GOOGLE_API_KEY environment variable not set.")
    exit(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    print("FastAPI app starting up...")
    print("Connecting to database...")
    try:
        await init_db_pool()
        print("Database connection successful.")
    except Exception as e:
        print(f"FATAL: Could not connect to database: {e}")

    print("Initializing ADK Agent Runner and Services...")
    try:
        memory_service = InMemoryMemoryService()
        session_service = InMemorySessionService() 
        
        adk_app = App(
            name="agents",
            root_agent=root_agent,
            events_compaction_config=EventsCompactionConfig(
                compaction_interval=5,
                overlap_size=2,
            ),
            plugins=[LoggingPlugin()]
        )
        runner_instance = Runner(
            app=adk_app,
            memory_service=memory_service,
            session_service=session_service
        )
        app.state.runner = runner_instance
        print("ADK Agent Runner initialized.") 
    except Exception as e:
        print(f"FATAL: Could not initialize ADK Agent Runner: {e}")
        app.state.runner = None

    yield

    # --- Shutdown ---
    print("FastAPI app shutting down...")
    await close_db_pool()
    print("Database pool closed.")

app = FastAPI(
    title="Kognia API (Modular)",
    description="A modularized FastAPI backend for agentic analysis jobs.",
    version="0.7.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Update to a specific origin later for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Routers ---
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)  # nosec B104
