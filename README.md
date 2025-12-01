# 🚀 Kognia Backend

A FastAPI backend that runs agentic analysis jobs and manages sessions, messages and reports. Key features:

- API endpoints for creating and polling analysis jobs, listing sessions, and fetching session messages.
- Supabase JWT authentication (Bearer tokens) with automatic Base64 decoding of the configured JWT secret.
- Async Postgres access via `asyncpg` with connection pooling and helpers to ensure user profiles for RLS.
- Integration with Google ADK / GenAI runner, memory and session services for agent execution.
- Background task orchestration to run agents and persist reports to the database.
- Designed for deployment on Render, Google Cloud Run (Cloud SQL), or Supabase-hosted Postgres.

**Public endpoint**: https://kognia-backend.onrender.com
---

### 1. The Problem: Data Overwhelm & Insight Famine
Modern Brand Strategists are drowning in data but starving for insight. They face a "Cognitive Bottleneck" defined by three critical pain points:
* **The Research Black Hole:** Strategists spend 80% of their time manually sifting through disparate tabs (SEO tools, news sites, competitors) and only 20% on actual strategy.
* **The "Blank Page" Paralysis:** Starting a brand narrative from scratch is daunting without a sounding board or data-backed creative sparks.
* **The Accuracy Gap:** Proving the "why" behind a strategy is difficult when data is scattered, leading to skeptical clients and weak positioning.

**The Opportunity:** By automating the *collection* and *synthesis* of intelligence, we can flip the 80/20 ratio, allowing strategists to focus entirely on high-value creative execution.

### 2. The Solution: A Virtual Strategy Team
Kognia AI is not just a chatbot; it is a **virtual strategy department**. It replaces linear prompting with a team of specialized agents that collaborate to:
1.  **Conduct Deep Research:** Autonomously scour the web for real-time market trends and competitor moves using grounded search tools.
2.  **Strategic Synthesis:** Transform raw data into structured SWOT analyses and executive reports without human intervention.
3.  **Synthetic Focus Groups:** Uniquely, Kognia AI can **simulate conversations** between specific user personas. This allows strategists to "test" a brand message against an AI-simulated audience before launching, directly solving the "Blank Page" problem by providing instant feedback.

### 3. Architecture & Agentic Workflow
Kognia AI utilizes a **Hierarchical Orchestration Pattern**. The system is modular, ensuring that no single agent is overloaded with context, which reduces hallucinations and improves output quality.



**The Orchestrator: `kognia_nexus_agent`**
Built using the `LlmAgent` class from Google ADK, this is the central "Project Manager." It does not perform analysis itself. Instead, it evaluates the user's intent (e.g., "I need a stress test of this brand") and routes the task to the correct specialist using strict delegation rules.

**The Specialist Team:**

* **🕵️ Market Intel Analyst (`market_intel_analyst_agent`)**
    * *Role:* The "Fact-Finder."
    * *Tools:* `Google Search` (grounding), `url_context` (deep scraping).
    * *Function:* Systematically collects and verifies real-world data to ensure all downstream agents operate on facts, not hallucinations.

* **⚖️ SWOT Evaluator (`strategic_swot_evaluator_agent`)**
    * *Role:* The "Critic."
    * *Function:* Takes raw intelligence from the Analyst and applies rigid strategic frameworks to categorize Strengths, Weaknesses, Opportunities, and Threats.

* **📝 Report Architect (`strategic_report_architect`)**
    * *Role:* The "Synthesizer."
    * *Function:* Merges the disparate outputs (Research + SWOT) into a cohesive, client-ready document.

* **⚡ Executive Briefer (`executive_briefer_agent`)**
    * *Role:* The "Bottom-Liner."
    * *Function:* Distills voluminous and complex reports into concise, high-impact summaries optimized for rapid decision-making by leadership.

* **👥 Simulation Expert (`conversation_simulator_agent`)**
    * *Role:* The "Tester."
    * *Function:* Uses the research data to roleplay as a target consumer or competitor. This allows the user to interview the data interactively.
---

## 📦 Requirements

- **Python**: 3.11.x (recommended)
- **pip**: >= 25.2
- **PostgreSQL**: any Postgres-compatible server (Supabase or Cloud SQL recommended)
- **Python packages** (from `requirements.txt`):
  - `fastapi>=0.110.0`
  - `uvicorn[standard]>=0.29.0`
  - `asyncpg>=0.29.0`
  - `pydantic>=1.10.13`
  - `google-adk>=1.18.0`
  - `psycopg[binary]>=3.2.13`
  - `PyJWT>=2.8.0`  # or latest stable
  - `cryptography`  # recommended for JWT support

- **Optional**: Rust toolchain (only needed if building certain packages from source)

---

## 🛠️ Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/Hou-dini/kognia_backend
cd kognia_backend

python -m venv .venv
# On Windows
.venv\Scripts\activate
# On macOS/Linux
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

# Running the app
uvicorn app.main:app --reload

# Reporducibility notes
## **Environment Variables**

- **`DATABASE_URL`**: Postgres connection URL used by `asyncpg`. Example:
  ```
  postgresql://username:password@host:5432/dbname
  ```
- **`SUPABASE_JWT_SECRET`**: Supabase project's JWT secret used to verify incoming bearer tokens. This may be base64-encoded; `main.py` will attempt Base64 decoding and fall back to the raw value if decoding fails.
- **`GOOGLE_APPLICATION_CREDENTIALS`**: (Optional) Path to Google service account JSON if using Google ADK or Google Cloud services.

Keep these variables in your environment or configure them in your deployment platform's environment settings.

## **Local Development & Setup**

- Create and activate a virtual environment and install dependencies:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

- Create a `.env` file (optional) or export environment variables for local testing. Example `.env` contents:

```
DATABASE_URL=postgresql://postgres:password@localhost:5432/kognia
SUPABASE_JWT_SECRET=your-supabase-jwt-secret-or-base64
GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json
```

- Run the application locally (the app's entrypoint is `main:app`):

```powershell
# Recommended for development
setx DATABASE_URL "postgresql://..." /M
setx SUPABASE_JWT_SECRET "..." /M
# Start uvicorn (reload useful during dev)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000` by default.

## **Database / Supabase Setup**

- This project expects a Postgres-compatible database. Supabase is the reference platform used by the code:
  - Create a new Supabase project and note the `DATABASE_URL` (connection string). Use this as `DATABASE_URL` in your environment.
  - In the Supabase dashboard go to `Settings -> API` and copy the `JWT Secret` to `SUPABASE_JWT_SECRET`.
  - Ensure the tables referenced by the code exist: `sessions`, `messages`, `jobs`, `reports`, and `user_profiles`. The application expects `jobs.status` to use a `public.job_status_enum` enum type.

Example minimal SQL for `jobs` and `reports` (adapt for your schema):

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
```

You may prefer to use Supabase's SQL editor to create these objects or run migrations from your local environment.

## **Google ADK / GenAI Integration**

- The project imports `google.adk` packages and the `google.genai` types. To use ADK features (runner, memory, sessions):
  - Install the ADK extra if required: `pip install google-adk[eval]` (the project may already include this in `requirements.txt`).
  - Create a Google Cloud service account with the necessary permissions for GenAI and any other Google APIs you plan to use. Download the JSON key and set `GOOGLE_APPLICATION_CREDENTIALS` to its path.
  - Enable the Google GenAI API and relevant Cloud APIs in your Google Cloud project.

Notes: ADK setup steps may change as the GenAI/ADK ecosystem evolves — consult the official Google ADK docs for the most accurate setup instructions.

## **Deployment Reproduction**

Below are reproduction steps for two cloud deployment flows referenced by files in this repository: `Render` (render.yaml is present) and `Google Cloud`.

**Render.com (recommended quick deploy)**

- This repo includes a `render.yaml` manifest. To reproduce deployment on Render:
  1. Create a new Web Service in Render and connect your GitHub/GitLab repo.
  2. Use the `render.yaml` manifest (Render will detect and apply it). If creating manually, set these build and start commands:

```text
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

  3. Add the environment variables to the service settings:
     - `DATABASE_URL` (from Supabase or Cloud SQL)
     - `SUPABASE_JWT_SECRET`
     - `GOOGLE_APPLICATION_CREDENTIALS` (if you need ADK; for Render consider using Render's secret storage and mounting, or use Google Secret Manager + application credentials)
  4. Deploy and monitor logs from the Render dashboard.

**Google Cloud (Cloud Run + Cloud SQL) - Reproducible Steps**

Below is an example Docker-based deployment to Google Cloud Run using a Cloud SQL Postgres instance. This reproduces a production-ready deployment similar to what the repository expects.

1) Create a Cloud SQL (Postgres) instance and a database. Note the connection details.

2) Create a Google Cloud service account, grant it the `Cloud SQL Client` role and any GenAI roles required, and download the JSON key.

3) Example `Dockerfile` (create at repository root):

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

4) Build and push the image (example using Cloud Build):

```bash
# Set project and image name
gcloud config set project YOUR_PROJECT_ID
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/kognia-backend:latest
```

5) Deploy to Cloud Run with Cloud SQL connection (replace placeholders):

```bash
gcloud run deploy kognia-backend \
  --image gcr.io/YOUR_PROJECT_ID/kognia-backend:latest \
  --region YOUR_REGION \
  --add-cloudsql-instances YOUR_PROJECT:REGION:INSTANCE_NAME \
  --set-env-vars DATABASE_URL="postgresql://USER:PASSWORD@/DBNAME?host=/cloudsql/YOUR_PROJECT:REGION:INSTANCE_NAME",SUPABASE_JWT_SECRET="your-jwt-secret" \
  --service-account YOUR_SERVICE_ACCOUNT@YOUR_PROJECT.iam.gserviceaccount.com \
  --platform managed
```

6) If your application needs the service account JSON at runtime (not recommended for Cloud Run), consider using Secret Manager and mounting secrets rather than embedding JSON on disk.

## **Troubleshooting & Notes**

- The project expects `jobs.status` to use enum values like `pending`, `processing`, `completed`, and `failed`. The code now sets `'failed'` instead of `'error'` to match that enum naming.
- If you use Supabase RLS policies, ensure `user_profiles` are created (the app calls `get_or_create_user_profile` during job creation).
- If you see asyncpg connection issues locally, verify your `DATABASE_URL` is reachable and Postgres accepts connections.

## **Where to look in the code**

- API entrypoint: `main.py` (FastAPI app, authentication, and worker orchestration).
- Agent code: `agents/` directory contains agent implementations and helpers used by the ADK runner.

---
