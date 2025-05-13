from pydantic import BaseModel
from typing import Optional

class EmailSchema(BaseModel):
    recipient: str
    subject: str
    body: str
    cc: Optional[str] = None
    bcc: Optional[str] = None
    # is_read: bool

class ReplyEmailSchema(BaseModel):
    recipient: str
    subject: str
    body: str
    thread_id: str
    message_id: str

class EmailReadStatus(BaseModel):
    is_read: bool

class EmailStarStatus(BaseModel):
    is_starred: bool