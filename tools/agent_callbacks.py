



async def auto_save_to_memory(callback_context):
    """ Auto-save all interactions to memory after each agent turn"""
    await callback_context.invocation_context.memory_service.add_session_to_memory(
        callback_context.invocation_context.session
    )