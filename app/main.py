# app/main.py
from fastapi import FastAPI, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging

from .models import EmailResponse
from .services import ImapService
from .config import Settings

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to see all parameter values
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="IMAP REST API")

def get_settings():
    return Settings()

@app.get("/emails/", response_model=List[EmailResponse])
async def get_emails(
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    sender: Optional[str] = Query(None, description="Sender email address"),
    subject: Optional[str] = Query(None, description="Subject contains text"),
    mailbox: str = Query("INBOX", description="Mailbox to search in"),
    limit: int = Query(1, description="Maximum number of emails to return", gt=0),  # Changed default to 1
    settings: Settings = Depends(get_settings)
):
    """Retrieve emails with optional filtering"""
    logger.debug(f"API received request with limit={limit}")  # Add debug log
    try:
        imap_service = ImapService(settings)
        return await imap_service.get_emails(
            start_date=start_date,
            end_date=end_date,
            sender=sender,
            subject=subject,
            mailbox=mailbox,
            limit=limit  # Explicitly pass limit
        )
    except Exception as e:
        logger.error(f"Failed to retrieve emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))