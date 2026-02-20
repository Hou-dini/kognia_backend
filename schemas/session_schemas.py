from pydantic import BaseModel


class SessionSummary(BaseModel):
    id: str
    title: str
    updated_at: str

class MessageResponseItem(BaseModel):
    role: str
    content: str
    created_at: str
