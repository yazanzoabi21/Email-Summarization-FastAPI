from pydantic import BaseModel
from typing import Optional

class EmailSchema(BaseModel):
    to: str
    subject: str
    body: str
    cc: Optional[str] = None
    bcc: Optional[str] = None
