# Kognia Backend - Gemini Context Management

## Project Overview
Kognia Backend is a FastAPI service orchestrating a multi-agent system (MAS) using Google ADK and Gemini 2.5-Flash. It manages market research, competitor intelligence, and strategic analysis jobs.

## Architecture
- **Orchestrator**: `kognia_nexus_agent` (Kognia Nexus)
- **Specialists**:
    - `MarketIntel Analyst`: Web research & data collection.
    - `Executive Briefer`: Summarization for decision-makers.
    - `StrategicSWOT Evaluator`: SWOT framework application.
    - `StrategicReport Architect`: Synthesis of research & SWOT into reports.
    - `Conversation Simulator`: Persona-based audience simulation.
- **Tech Stack**: FastAPI, asyncpg (Postgres/Supabase), Google ADK, PyJWT (RS256 JWKS).

## Recent Changes
- **CI/CD Initialization**:
    - Added `pytest`, `ruff`, and `httpx` to `requirements.txt`.
    - Created `tests/` directory with `test_main.py` for core app validation.
    - Added `.github/workflows/ci.yml` for automated linting and testing on GitHub.

## Environment & Development
- **Local Test Command**: `$env:PYTHONPATH = '.'; .venv\Scripts\pytest.exe`
- **Session Service**: Currently using `InMemorySessionService` to avoid Supabase schema conflicts with ADK internal tables.

## Development Memories
- User: Eli (Applied AI Engineer based in Ghana).
- Project is being prepared for robust deployment with automated quality checks.
