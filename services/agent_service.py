import uuid

from google.genai import types

from services import db_service


async def update_job_status(job_id: str, status: str):
    """
    Updates the status of a job in the database.
    """
    try:
        db_service.ensure_db_pool()
        assert db_service.db_pool is not None
        async with db_service.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE jobs SET status = $1::public.job_status_enum, updated_at = NOW() WHERE id = $2",
                status,
                uuid.UUID(job_id)
            )
        print(f"[Job {job_id}]: Status updated to '{status}'.")
    except Exception as e:
        print(f"[Job {job_id}]: Error updating status to '{status}': {e}")

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
            # Join all parts to ensure we don't miss anything if the response is multi-part
            final_text = "".join([p.text for p in event.content.parts if p.text])
            print("[Agent] Final response received.")

    return final_text

async def run_agent_task(runner, job_id: str, prompt: str, user_id: uuid.UUID, session_id: str):
    """
    Runs the agent for a given job in the background.
    Updates the job status and stores the report in the database.
    """
    print(f"[Job {job_id}]: Starting background agent task...")

    if not runner:
        print(f"[Job {job_id}]: FATAL- Runner not initialized.")
        await update_job_status(job_id, "failed")
        return
    
    try:
        await update_job_status(job_id, "processing")

        print(f"[Job {job_id}]: Creating ADK session: {session_id} for user: {user_id}...")
        try:
            await runner.session_service.create_session(app_name="agents", user_id=str(user_id), session_id=session_id)
            print(f"[Job {job_id}]: ADK Session created successfully.")
        except Exception as e:
            print(f"[Job {job_id}]: ADK Session creation warning (might already exist): {e}")


        # Log user's message to the DB
        db_service.ensure_db_pool()
        assert db_service.db_pool is not None
        async with db_service.db_pool.acquire() as conn:
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
            session_obj = await runner.session_service.get_session(
                app_name="agents", user_id=str(user_id), session_id=session_id
            )
            if session_obj:
                await runner.memory_service.add_session_to_memory(session_obj)
                print(f"[Job {job_id}]: Session archived successfully.")
            else:
                print(f"[Job {job_id}]: WARNING- Session object not found for archiving.")
        except Exception as mem_e:
            print(f"[Job {job_id}]: WARNING- Failed to save memory: {mem_e}")

        # Log agent's report to the DB
        async with db_service.db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO messages (session_id, user_id, role, content, created_at) VALUES($1, $2, $3, $4, NOW())",
                uuid.UUID(session_id), user_id, "agent", report_content
            )

        # 4. Save Report and Complete Job
        async with db_service.db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO reports (job_id, user_id, content) VALUES($1, $2, $3)",
                uuid.UUID(job_id), user_id, report_content
            )

            await update_job_status(job_id, "completed")
        print(f"[Job {job_id}]: Success Report Saved.")

    except Exception as e:
        print(f"[Job {job_id}]: FATAL- Error: {e}")
        await update_job_status(job_id, "failed")
