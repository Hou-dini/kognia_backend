# 🚀 Kognia Backend

Kognia Backend is a FastAPI service that executes agent-led analysis jobs, manages chat sessions and messages, and stores generated reports. It integrates with Supabase-compatible Postgres databases and Google ADK/GenAI for agent orchestration.

**Highlights**

- Job creation and polling endpoints
- Session and message management
- Supabase JWT verification for authentication
- Async DB access via `asyncpg` with pooling
- Google ADK integration for agent execution, sessions and memory
- Designed for deployment on Render, Google Cloud Run (Cloud SQL), or similar platforms

---

## Project background

Public endpoint: https://kognia-backend.onrender.com

### The problem

Modern Brand Strategists are drowning in data but starving for insight. They face a "Cognitive Bottleneck" defined by three critical pain points:

- The Research Black Hole: Strategists spend most of their time manually sifting through disparate sources (SEO tools, news sites, competitors) and only a small fraction on strategy.
- The "Blank Page" Paralysis: Starting a brand narrative from scratch is daunting without a structured, data-backed sounding board.
- The Accuracy Gap: Proving the "why" behind strategic recommendations is difficult when data is scattered and unverified.

The opportunity is to automate the collection and synthesis of intelligence so strategists can focus on high-value creative and decision-making tasks.

### The solution

Kognia AI functions as a virtual strategy team rather than a simple chatbot. It replaces linear prompting with a coordinated set of specialized agents that collaborate to:

1. Conduct deep research: autonomously gather real-world evidence and context using grounded search and scraping tools.
2. Perform strategic synthesis: convert raw findings into structured outputs such as SWOT analyses and executive reports.
3. Simulate audiences: roleplay target personas to stress-test messaging and uncover weaknesses before launch.

### Architecture & agentic workflow

Kognia AI uses a hierarchical orchestration pattern. Agents are specialized and lightweight, reducing hallucination risk and improving reliability. The orchestrator delegates tasks to specialists, which then return structured outputs for synthesis and reporting.

![Kognia AI Architecture diagram](assets/architecture.png)
> Visual representation of the Kognia AI architecture

**The orchestrator — `kognia_nexus_agent`**

Built with Google ADK primitives, the orchestrator evaluates user intent and assigns work to specialist agents. It enforces delegation rules and compacts events for downstream processing.

**Specialist agents (examples)**

- Market Intel Analyst (`market_intel_analyst_agent`) — collects and verifies factual data using grounded search and URL/context scraping.
- SWOT Evaluator (`strategic_swot_evaluator_agent`) — applies strategic frameworks to categorize strengths, weaknesses, opportunities and threats.
- Report Architect (`strategic_report_architect`) — merges research and analysis into client-ready reports.
- Executive Briefer (`executive_briefer_agent`) — distills long reports into concise executive summaries.
- Conversation Simulator (`conversation_simulator_agent`) — roleplays audience personas to test messaging and surface issues.

---

---

## Table of contents

- [Requirements](#requirements)
- [Quickstart](#quickstart)
- [Configuration](#configuration)
- [Database schema notes](#database-schema-notes)
- [Google ADK / GenAI integration](#google-adk--genai-integration)
- [Deployment (Render, Cloud Run)](#deployment-render-cloud-run)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Requirements

- Python 3.11.x (recommended)
- pip >= 25.2
- Postgres-compatible database (Supabase / Cloud SQL recommended)

Key Python dependencies (see `requirements.txt`):

- `fastapi>=0.110.0`
- `uvicorn[standard]>=0.29.0`
- `asyncpg>=0.29.0`
- `pydantic>=1.10.13`
- `google-adk>=1.18.0`
- `psycopg[binary]>=3.2.13`
- `PyJWT>=2.8.0` (or latest stable)
- `cryptography` (recommended for JWT support)

Optional: Rust toolchain (only if building some packages from source).

---

## Quickstart

1. Clone the repository and create a virtual environment:

```powershell
git clone https://github.com/Hou-dini/kognia_backend.git
cd kognia_backend
python -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate # macOS / Linux
pip install --upgrade pip
pip install -r requirements.txt
```

2. Configure environment variables (see next section).

3. Start the application for local development:

```powershell
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API docs are available at `http://localhost:8000/docs`.

---

## Configuration

Environment variables required or commonly used by the project:

- `DATABASE_URL` — Postgres connection string, e.g. `postgresql://user:pass@host:5432/dbname`
- `SUPABASE_JWT_SECRET` — Supabase project's JWT secret (may be Base64 encoded; the app will attempt to decode)
- `GOOGLE_APPLICATION_CREDENTIALS` — Optional path to Google service account JSON for ADK/GenAI

Use your host's secret manager (Render secrets, GCP Secret Manager, etc.) to store these securely.

---

## Database schema notes

Minimal required tables (examples):

```sql
CREATE TYPE public.job_status_enum AS ENUM ('pending','processing','completed','failed');

CREATE TABLE jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  session_id uuid NOT NULL,
  prompt text,
  status public.job_status_enum DEFAULT 'pending',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id uuid REFERENCES jobs(id),
  user_id uuid,
  content text
);

CREATE TABLE sessions (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL,
  title text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid REFERENCES sessions(id),
  user_id uuid,
  role text,
  content text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE user_profiles (
  id uuid PRIMARY KEY,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
```

If you use Supabase RLS, ensure `user_profiles` entries exist for authenticated users; the app includes a helper to create them when missing.

---

## Google ADK / GenAI integration

To use agent orchestration with Google ADK & GenAI:

1. (Optional) Install ADK extras: `pip install google-adk[eval]`.
2. Create a Google Cloud service account, enable GenAI APIs, and set `GOOGLE_APPLICATION_CREDENTIALS` to the credentials file.

Consult the Google ADK documentation for authentication, usage quotas, and best practices.

---

## Deployment (Render, Cloud Run)

Render

- Use the provided `render.yaml` or create a new Web Service. Set environment variables (`DATABASE_URL`, `SUPABASE_JWT_SECRET`, and optionally `GOOGLE_APPLICATION_CREDENTIALS`).
- Build: `pip install -r requirements.txt`.
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`.

Google Cloud Run (Cloud SQL)

- Example Dockerfile (root):

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- Build and push the image, then deploy to Cloud Run. For Cloud SQL, use `--add-cloudsql-instances` and set `DATABASE_URL` accordingly or use the Cloud SQL proxy.

---

## Troubleshooting

- DB connection errors: check `DATABASE_URL`, networking, and that the DB accepts connections.
- JWT errors: verify `SUPABASE_JWT_SECRET` and token signing algorithm (HS256 expected).
- Static analyzer warnings about `db_pool` being possibly `None` can be addressed by adding explicit type hints or runtime guards; the runtime uses `ensure_db_pool()` checks.

---

## Contributing

Please open issues for bugs or feature requests. Submit pull requests against `main`.

---

## License

Apache 2.0 — see `LICENSE`.

---

Designed and developed by Elikplim Kudowor.

