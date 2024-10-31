# app/services.py
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import List, Optional, Dict, Tuple
import logging
from datetime import datetime
import re
from .models import EmailResponse, EmailAttachment, MailboxResponse
from .config import Settings

class ImapService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.setup_logging()

    def setup_logging(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(self.settings.LOG_LEVEL)
        # Add formatter for more detailed logs
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def decode_header_value(self, value: Optional[str]) -> str:
        """Decode email header value safely"""
        if not value:
            return ""
        try:
            self.logger.debug(f"Decoding header value: {value[:100]}...")
            decoded_header = decode_header(value)
            parts = []
            for part, charset in decoded_header:
                if isinstance(part, bytes):
                    try:
                        if charset:
                            self.logger.debug(f"Decoding with charset: {charset}")
                            parts.append(part.decode(charset))
                        else:
                            parts.append(part.decode('utf-8', errors='replace'))
                    except:
                        self.logger.debug("Fallback to ASCII decoding")
                        parts.append(part.decode('ascii', errors='replace'))
                else:
                    parts.append(str(part))
            result = " ".join(parts)
            self.logger.debug(f"Decoded result: {result[:100]}...")
            return result
        except Exception as e:
            self.logger.warning(f"Error decoding header: {str(e)}")
            return str(value)

    def create_imap_connection(self) -> imaplib.IMAP4:
        """Create and return an IMAP connection"""
        self.logger.info(f"Connecting to IMAP server {self.settings.IMAP_HOST}:{self.settings.IMAP_PORT}")
        try:
            if self.settings.SSL_VERIFY:
                self.logger.debug("Using SSL connection")
                connection = imaplib.IMAP4_SSL(
                    host=self.settings.IMAP_HOST,
                    port=self.settings.IMAP_PORT
                )
            else:
                self.logger.debug("Using non-SSL connection")
                connection = imaplib.IMAP4(
                    host=self.settings.IMAP_HOST,
                    port=self.settings.IMAP_PORT
                )
            
            self.logger.debug("Attempting login...")
            connection.login(self.settings.IMAP_USERNAME, self.settings.IMAP_PASSWORD)
            self.logger.info("Successfully logged in to IMAP server")
            return connection
        except Exception as e:
            self.logger.error(f"Failed to connect to IMAP server: {str(e)}")
            raise

    def get_content_parts(self, msg: email.message.Message) -> Tuple[Optional[str], Optional[str], List[EmailAttachment]]:
        """Extract text, HTML content and attachments from email message"""
        self.logger.debug("Processing message parts")
        text_content = None
        html_content = None
        attachments = []

        for part in msg.walk():
            content_type = part.get_content_type()
            self.logger.debug(f"Processing part with content type: {content_type}")
            
            try:
                if part.get_content_maintype() == 'multipart':
                    self.logger.debug("Skipping multipart")
                    continue
                    
                if content_type == 'text/plain' and not text_content:
                    self.logger.debug("Extracting plain text content")
                    text_content = part.get_payload(decode=True).decode('utf-8', errors='replace')
                    
                elif content_type == 'text/html' and not html_content:
                    self.logger.debug("Extracting HTML content")
                    html_content = part.get_payload(decode=True).decode('utf-8', errors='replace')
                    
                elif part.get('Content-Disposition') and 'attachment' in part['Content-Disposition']:
                    filename = part.get_filename('')
                    self.logger.debug(f"Processing attachment: {filename}")
                    attachments.append(EmailAttachment(
                        filename=self.decode_header_value(filename),
                        content_type=content_type,
                        size=len(part.get_payload()),
                        content_id=part.get("Content-ID")
                    ))
            except Exception as e:
                self.logger.error(f"Error processing message part: {str(e)}")
                continue

        self.logger.debug(f"Found {len(attachments)} attachments")
        return text_content, html_content, attachments

    async def get_emails(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sender: Optional[str] = None,
        subject: Optional[str] = None,
        mailbox: str = "INBOX",
        limit: int = 1  # Changed default to 1
    ) -> List[EmailResponse]:
        """Retrieve emails with optional filtering"""
        self.logger.info(f"Starting email retrieval from mailbox: {mailbox}")
        self.logger.debug(f"Service method received limit={limit}")  # Debug log for limit
        
        connection = self.create_imap_connection()
        try:
            status, messages = connection.select(mailbox)
            if status != 'OK':
                raise Exception(f"Failed to select mailbox: {messages}")

            total_messages = int(messages[0].decode())
            self.logger.info(f"Mailbox contains {total_messages} messages")
            
            # Build search criteria
            search_criteria = []
            if start_date:
                search_criteria.append(f'SINCE {start_date}')
            if end_date:
                search_criteria.append(f'BEFORE {end_date}')
            if sender:
                search_criteria.append(f'FROM "{sender}"')
            
            search_string = ' '.join(search_criteria) if search_criteria else 'ALL'
            self.logger.info(f"Search criteria: {search_string}")
            
            _, message_numbers = connection.search(None, search_string)
            all_msgs = message_numbers[0].split()
            all_msgs.reverse()  # Newest first
            
            self.logger.debug(f"Found {len(all_msgs)} messages, will process max {limit}")
            
            emails = []
            for msg_num in all_msgs:
                if len(emails) >= limit:  # Check before processing
                    self.logger.debug(f"Stopping at {len(emails)} emails (limit: {limit})")
                    break
                    
                try:
                    self.logger.debug(f"Processing message {len(emails) + 1}/{limit} (ID: {msg_num})")
                    _, msg_data = connection.fetch(msg_num, '(RFC822 FLAGS)')
                    if not msg_data or not msg_data[0]:
                        continue
                        
                    email_body = msg_data[0][1]
                    flags = [f.decode() for f in imaplib.ParseFlags(msg_data[1])]
                    msg = email.message_from_bytes(email_body)
                    
                    parsed_email = self.parse_email_message(msg, mailbox, flags)
                    
                    if subject and subject.lower() not in parsed_email.subject.lower():
                        self.logger.debug("Skipping - subject filter mismatch")
                        continue
                    
                    emails.append(parsed_email)
                    self.logger.debug(f"Added email {len(emails)}/{limit}: {parsed_email.subject}")
                    
                except Exception as e:
                    self.logger.error(f"Error processing email {msg_num}: {str(e)}")
                    continue

            self.logger.info(f"Successfully retrieved {len(emails)} emails (requested limit: {limit})")
            return emails

        finally:
            try:
                connection.logout()
            except Exception as e:
                self.logger.error(f"Error during logout: {str(e)}")
                
    def parse_email_message(self, msg: email.message.Message, mailbox: str, flags: List[str]) -> EmailResponse:
        """Parse email message into EmailResponse model"""
        try:
            self.logger.debug("Starting email parsing")
            
            # Parse date
            date_str = msg["date"]
            try:
                date = parsedate_to_datetime(date_str)
                self.logger.debug(f"Parsed date: {date}")
            except:
                self.logger.warning("Failed to parse date, using current time")
                date = datetime.now()

            # Get content and attachments
            self.logger.debug("Extracting content and attachments")
            text_content, html_content, attachments = self.get_content_parts(msg)

            email_response = EmailResponse(
                message_id=msg["message-id"] or "",
                subject=self.decode_header_value(msg["subject"]),
                sender=self.decode_header_value(msg["from"]),
                recipients=self.get_email_addresses(msg["to"]),
                date=date,
                mailbox=mailbox,
                flags=flags,
                text_content=text_content,
                html_content=html_content,
                size=len(str(msg).encode('utf-8')),
                attachments=attachments,
                headers={k: self.decode_header_value(v) for k, v in msg.items()}
            )
            
            self.logger.debug(f"Successfully parsed email: {email_response.subject}")
            return email_response
            
        except Exception as e:
            self.logger.error(f"Error parsing email: {str(e)}", exc_info=True)
            return EmailResponse(
                message_id=msg["message-id"] or "",
                subject="[Error: Could not parse email]",
                sender="",
                date=datetime.now(),
                mailbox=mailbox,
                flags=flags,
                size=0
            )
        
    def get_email_addresses(self, header_value: Optional[str]) -> List[str]:
        """Extract email addresses from header value"""
        if not header_value:
            return []
        
        self.logger.debug(f"Extracting email addresses from: {header_value[:100]}...")
        
        # Handle both standard email format and encoded headers
        decoded_header = self.decode_header_value(header_value)
        
        # Match email addresses pattern
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        addresses = re.findall(email_pattern, decoded_header)
        
        self.logger.debug(f"Found email addresses: {addresses}")
        return addresses