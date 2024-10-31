# app/models.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict
from datetime import datetime

class EmailAttachment(BaseModel):
    filename: str
    content_type: str
    size: int
    content_id: Optional[str] = None

class EmailResponse(BaseModel):
    message_id: str
    subject: str
    sender: str
    recipients: List[str] = Field(default_factory=list)
    date: datetime
    mailbox: str
    flags: List[str] = Field(default_factory=list)
    
    # Content
    text_content: Optional[str] = None
    html_content: Optional[str] = None
    
    # Metadata
    size: int = Field(default=0)
    attachments: List[EmailAttachment] = Field(default_factory=list)
    headers: Dict[str, str] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class MailboxResponse(BaseModel):
    name: str
    flags: List[str] = Field(default_factory=list)
    delimiter: Optional[str] = None
    message_count: Optional[int] = None