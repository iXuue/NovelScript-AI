from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ConversationMessage(BaseModel):
    message_id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime

