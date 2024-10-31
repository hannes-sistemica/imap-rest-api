# app/services.py
import imaplib
import email
import mimetypes
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

    def get_email_addresses(self, header_value: Optional[str]) -> List[str]:
        """Extract email addresses from header value"""
        if not header_value:
            return []
        
        self.logger.debug(f"Extracting email addresses from: {header_value[:100]}...")
        decoded_header = self.decode_header_value(header_value)
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        addresses = re.findall(email_pattern, decoded_header)
        self.logger.debug(f"Found email addresses: {addresses}")
        return addresses

    # app/services.py - Updated get_emails method

    async def get_emails(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sender: Optional[str] = None,
        subject: Optional[str] = None,
        mailbox: str = "INBOX",
        limit: int = 1
    ) -> List[EmailResponse]:
        """Retrieve emails with optional filtering"""
        self.logger.info(f"Starting email retrieval from mailbox: {mailbox} with limit {limit}")
        
        connection = self.create_imap_connection()
        try:
            connection.select(mailbox)
            self.logger.info(f"Selected mailbox: {mailbox}")

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
            message_nums = message_numbers[0].split()
            message_nums.reverse()  # Newest first
            message_nums = message_nums[:limit]  # Apply limit

            emails = []
            for num in message_nums:
                try:
                    # First fetch structure and basic info
                    _, response = connection.fetch(num, '(BODYSTRUCTURE FLAGS)')
                    if response[0]:
                        self.logger.debug(f"Message structure: {response[0]}")

                    # Then fetch the full message
                    _, msg_data = connection.fetch(num, '(RFC822)')
                    email_body = msg_data[0][1]
                    msg = email.message_from_bytes(email_body)

                    # Log the complete message structure
                    self.logger.debug(f"""
                    Processing Message:
                    Subject: {msg['subject']}
                    Content-Type: {msg.get_content_type()}
                    Has Payload: {msg.is_multipart()}
                    Parts: {len(msg.get_payload()) if msg.is_multipart() else 1}
                    """)

                    text_content = None
                    html_content = None
                    attachments = []

                    # Process all parts
                    for part in msg.walk():
                        self.logger.debug(f"""
                        Part Info:
                        Content-Type: {part.get_content_type()}
                        Content-Disposition: {part.get('Content-Disposition')}
                        Filename: {part.get_filename()}
                        Is Multipart: {part.is_multipart()}
                        """)

                        if part.is_multipart():
                            continue

                        filename = part.get_filename()
                        content_type = part.get_content_type()

                        # Check for attachment using multiple methods
                        if filename or \
                        part.get('Content-Disposition', '').startswith('attachment') or \
                        content_type.startswith(('application/', 'image/', 'video/', 'audio/')):
                            
                            if not filename:
                                ext = mimetypes.guess_extension(content_type) or ''
                                filename = f"attachment{ext}"

                            self.logger.info(f"Found attachment: {filename} ({content_type})")
                            
                            # Get the payload
                            payload = part.get_payload(decode=True)
                            if payload is None:
                                payload = part.get_payload().encode('utf-8')

                            attachments.append(EmailAttachment(
                                filename=filename,
                                content_type=content_type,
                                size=len(payload),
                                content_id=part.get('Content-ID')
                            ))
                        elif content_type == 'text/plain':
                            text_content = part.get_payload(decode=True).decode('utf-8', errors='replace')
                        elif content_type == 'text/html':
                            html_content = part.get_payload(decode=True).decode('utf-8', errors='replace')

                    # Create EmailResponse
                    email_response = EmailResponse(
                        message_id=msg['message-id'] or "",
                        subject=self.decode_header_value(msg['subject']),
                        sender=self.decode_header_value(msg['from']),
                        recipients=self.get_email_addresses(msg['to']),
                        date=parsedate_to_datetime(msg['date']) if msg['date'] else datetime.now(),
                        mailbox=mailbox,
                        flags=[],
                        text_content=text_content,
                        html_content=html_content,
                        size=len(email_body),
                        attachments=attachments,
                        headers={k: self.decode_header_value(v) for k, v in msg.items()}
                    )

                    if subject and subject.lower() not in email_response.subject.lower():
                        continue

                    emails.append(email_response)
                    
                    if len(emails) >= limit:
                        break

                except Exception as e:
                    self.logger.error(f"Error processing email {num}: {str(e)}", exc_info=True)
                    continue

            return emails

        finally:
            connection.logout()

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

    async def get_attachment(
        self,
        message_id: str,
        attachment_filename: str,
        mailbox: str = "INBOX"
    ) -> Optional[Tuple[bytes, str, str]]:
        """Retrieve a specific attachment from an email"""
        connection = self.create_imap_connection()
        try:
            status, messages = connection.select(mailbox)
            if status != 'OK':
                raise Exception(f"Failed to select mailbox: {messages}")

            # Search for the specific email
            _, message_numbers = connection.search(None, f'HEADER "Message-ID" "{message_id}"')
            message_nums = message_numbers[0].split()
            
            if not message_nums:
                return None

            # Get the email
            _, msg_data = connection.fetch(message_nums[0], '(RFC822)')
            email_body = msg_data[0][1]
            msg = email.message_from_bytes(email_body)

            # Look for the attachment
            for part in msg.walk():
                try:
                    if part.is_multipart():
                        continue

                    filename = part.get_filename()
                    if filename:
                        filename = self.decode_header_value(filename)
                        
                        if filename == attachment_filename:
                            content_type = part.get_content_type()
                            payload = part.get_payload(decode=True)
                            return payload, filename, content_type
                            
                except Exception as e:
                    self.logger.error(f"Error processing attachment: {str(e)}")
                    continue

            return None

        finally:
            connection.logout()




    # Add this helper function to ImapService class
    def debug_message_structure(self, msg: email.message.Message, prefix: str = '') -> None:
        """Debug helper to print complete message structure"""
        self.logger.info(f"""{prefix}Message Part:
        Type: {msg.get_content_type()}
        Filename: {msg.get_filename()}
        Content-Disposition: {msg.get('Content-Disposition')}
        Is Multipart: {msg.is_multipart()}
        Headers: {dict(msg.items())}
        """)
        
        if msg.is_multipart():
            for idx, part in enumerate(msg.get_payload()):
                self.logger.info(f"{prefix}Part {idx}:")
                self.debug_message_structure(part, prefix + '    ')


    def get_content_parts(self, msg: email.message.Message) -> Tuple[Optional[str], Optional[str], List[EmailAttachment]]:
        """Extract text, HTML content and attachments from email message"""
        text_content = None
        html_content = None
        attachments = []

        def dump_structure(part, level=0):
            """Debug helper to dump complete structure"""
            indent = "  " * level
            self.logger.info(f"""{indent}Part:
    {indent}  Type: {part.get_content_type()}
    {indent}  Filename: {part.get_filename()}
    {indent}  Disposition: {part.get('Content-Disposition')}
    {indent}  Headers: {dict(part.items())}
    {indent}  Is Multipart: {part.is_multipart()}""")
            
            if part.is_multipart():
                for subpart in part.get_payload():
                    dump_structure(subpart, level + 1)
            else:
                payload_type = type(part.get_payload())
                payload_length = len(part.get_payload(decode=True) or b'') if payload_type != str else len(part.get_payload())
                self.logger.info(f"{indent}  Payload Type: {payload_type}, Length: {payload_length}")

        # First dump complete structure
        self.logger.info("=== Full Message Structure ===")
        dump_structure(msg)
        self.logger.info("=============================")

        def process_part(part):
            """Process individual message part"""
            nonlocal text_content, html_content

            if part.is_multipart():
                for subpart in part.get_payload():
                    process_part(subpart)
                return

            content_type = part.get_content_type()
            content_disp = str(part.get('Content-Disposition', '')).lower()
            filename = part.get_filename()
            maintype = part.get_content_maintype()
            subtype = part.get_content_subtype()

            self.logger.info(f"""
    Processing Part:
    Content-Type: {content_type}
    Content-Disposition: {content_disp}
    Filename: {filename}
    Main/Sub Type: {maintype}/{subtype}
    Headers: {dict(part.items())}
            """)

            # Check if this is an attachment
            is_attachment = False
            if content_disp and ('attachment' in content_disp or 'inline' in content_disp):
                is_attachment = True
                self.logger.info(f"Detected attachment via disposition: {content_disp}")
            elif filename:
                is_attachment = True
                self.logger.info(f"Detected attachment via filename: {filename}")
            elif maintype not in ['text', 'multipart']:
                is_attachment = True
                self.logger.info(f"Detected attachment via content type: {content_type}")

            if is_attachment:
                try:
                    if not filename:
                        ext = mimetypes.guess_extension(content_type) or ''
                        filename = f"attachment{ext}"

                    payload = part.get_payload(decode=True)
                    if payload is None:
                        payload = part.get_payload().encode('utf-8')

                    size = len(payload)
                    self.logger.info(f"Adding attachment: {filename} ({content_type}, {size} bytes)")

                    attachments.append(EmailAttachment(
                        filename=filename,
                        content_type=content_type,
                        size=size,
                        content_id=part.get('Content-ID')
                    ))
                except Exception as e:
                    self.logger.error(f"Error processing attachment {filename}: {str(e)}", exc_info=True)
                return

            # Handle text content
            try:
                if content_type == 'text/plain' and not text_content:
                    payload = part.get_payload(decode=True)
                    if payload:
                        text_content = payload.decode('utf-8', errors='replace')
                        self.logger.info("Extracted text/plain content")
                elif content_type == 'text/html' and not html_content:
                    payload = part.get_payload(decode=True)
                    if payload:
                        html_content = payload.decode('utf-8', errors='replace')
                        self.logger.info("Extracted text/html content")
            except Exception as e:
                self.logger.error(f"Error processing {content_type} content: {str(e)}")

        # Process the message
        try:
            if msg.is_multipart():
                self.logger.info("Processing multipart message")
                for part in msg.get_payload():
                    process_part(part)
            else:
                self.logger.info("Processing non-multipart message")
                process_part(msg)
        except Exception as e:
            self.logger.error(f"Error in content processing: {str(e)}", exc_info=True)

        # Log results
        self.logger.info(f"""
    Content Processing Results:
    - Attachments Found: {len(attachments)}
    - Attachment Details: {[(a.filename, a.content_type, a.size) for a in attachments]}
    - Has Text Content: {bool(text_content)}
    - Has HTML Content: {bool(html_content)}
        """)

        return text_content, html_content, attachments