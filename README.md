# IMAP REST API

A FastAPI-based REST API that provides convenient access to IMAP email servers. This service allows you to retrieve emails with various filtering options including date ranges, sender, and subject filters.

## Features

- Email retrieval with flexible filtering
- Support for multiple mailboxes
- Configurable via environment variables
- Docker support
- Detailed logging
- Health check endpoint
- Support for email attachments
- HTML and plain text content handling

## Quick Start

1. Clone the repository
```bash
git clone https://github.com/yourusername/imap-rest-api.git
cd imap-rest-api
```

2. Create and configure environment file
```bash
cp .env.example .env
```

Edit `.env` with your IMAP settings:
```ini
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USERNAME=your_email@gmail.com
IMAP_PASSWORD=your_app_password
SSL_VERIFY=true
LOG_LEVEL=INFO
```

3. Build and run with Docker
```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`.

## API Documentation

After starting the service, visit:
- OpenAPI documentation: `http://localhost:8000/docs`
- ReDoc documentation: `http://localhost:8000/redoc`

### Endpoints

#### GET /health
Health check endpoint

#### GET /emails/
Retrieve emails with optional filters:
- `start_date`: Filter emails after this date (DD-Mon-YYYY format)
- `end_date`: Filter emails before this date (DD-Mon-YYYY format)
- `sender`: Filter by sender email address
- `subject`: Filter by subject text (case-insensitive contains)
- `mailbox`: Mailbox to search in (defaults to "INBOX")
- `limit`: Maximum number of emails to return (defaults to 50)

## Example Requests

### Get Most Recent Email
```bash
curl -s "http://localhost:8000/emails/?limit=1" | jq '.'
```

### Get Emails from Date Range
```bash
# Get emails between October 30-31, 2024
curl -s "http://localhost:8000/emails/?limit=2&start_date=30-Oct-2024&end_date=31-Oct-2024" | jq '.'

# Get emails from yesterday (using date command)
curl -s "http://localhost:8000/emails/\
?limit=2\
&start_date=$(date -d "yesterday" '+%d-%b-%Y')\
&end_date=$(date '+%d-%b-%Y')" | jq '.'
```

### Filter by Sender
```bash
curl -s "http://localhost:8000/emails/?sender=example@domain.com&limit=5" | jq '.'
```

### Filter by Subject
```bash
curl -s "http://localhost:8000/emails/?subject=invoice&limit=5" | jq '.'
```

### Combined Filters
```bash
curl -s "http://localhost:8000/emails/\
?limit=5\
&start_date=30-Oct-2024\
&sender=example@domain.com\
&subject=report" | jq '.'
```

## Date Format

The API expects dates in the format: `DD-Mon-YYYY`

Examples:
- `31-Oct-2024`
- `01-Jan-2024`
- `15-Dec-2024`

Components:
- Day: 2 digits (01-31)
- Month: 3-letter abbreviation (Jan, Feb, Mar, etc.)
- Year: 4 digits
- Separators: hyphens (-)

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| IMAP_HOST | IMAP server hostname | imap.gmail.com |
| IMAP_PORT | IMAP server port | 993 |
| IMAP_USERNAME | IMAP account username | - |
| IMAP_PASSWORD | IMAP account password | - |
| SSL_VERIFY | Enable/disable SSL verification | true |
| LOG_LEVEL | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |
| ENABLE_HTML_CONTENT | Enable HTML content in responses | true |
| ENABLE_ATTACHMENTS | Enable attachment information in responses | true |

## Development

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- Git

### Local Development Setup
1. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Run development server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Running Tests
```bash
# TODO: Add testing instructions
```

## Security Notes

1. Use app-specific passwords when possible (especially for Gmail)
2. Store sensitive credentials securely
3. Consider implementing rate limiting for production use
4. Review your IMAP server's security settings

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- FastAPI for the excellent web framework
- Python's imaplib for IMAP functionality