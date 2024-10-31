# IMAP REST API

A FastAPI-based REST API that provides access to IMAP email servers.

## Features

- Email retrieval with filtering capabilities
- Support for multiple mailboxes
- Configurable via environment variables
- Docker support
- Health check endpoint

## Setup

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in your IMAP credentials
3. Build and run with Docker:

```bash
docker-compose up --build
```

## API Endpoints

### GET /health
Health check endpoint

### GET /emails/
Retrieve emails with optional filters:
- start_date: Filter emails after this date (YYYY-MM-DD format)
- end_date: Filter emails before this date (YYYY-MM-DD format)
- sender: Filter by sender email address
- subject: Filter by subject text (case-insensitive contains)
- mailbox: Mailbox to search in (defaults to "INBOX")

## Environment Variables

- IMAP_HOST: IMAP server hostname (default: imap.gmail.com)
- IMAP_PORT: IMAP server port (default: 993)
- IMAP_USERNAME: IMAP account username
- IMAP_PASSWORD: IMAP account password
- SSL_VERIFY: Enable/disable SSL verification (default: true)
- LOG_LEVEL: Logging level (default: INFO)

## Security Notes

- Use app-specific passwords when possible
- Store sensitive credentials securely
- Consider implementing rate limiting for production use
