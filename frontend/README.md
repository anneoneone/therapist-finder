# Frontend

A modern, simple frontend for Therapist Finder built with vanilla JavaScript and CSS.

## Features

- **File Upload**: Drag & drop or click to upload PDF/text files
- **User Info Form**: Collect user information for email personalization
- **Results Table**: Display parsed therapists with status indicators
- **Downloads**: Export CSV table and AppleScript file

## Structure

```
frontend/
├── index.html          # Main HTML file
├── css/
│   └── styles.css      # Modern CSS with variables
├── js/
│   ├── app.js          # Main application logic
│   └── api.js          # API client for backend
└── package.json        # Dev server configuration
```

## Development

### Quick Start (Python)

```bash
cd frontend
python -m http.server 3000
```

### With npm

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:3000

## API Integration

The frontend expects these API endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/therapists/parse` | Upload file, returns parsed therapists |
| `POST` | `/api/emails/generate` | Generate emails, returns drafts + AppleScript |
| `GET` | `/api/health` | Health check |

### Request: Parse File

```javascript
// POST /api/therapists/parse
// Content-Type: multipart/form-data
FormData { file: File }

// Response
{
  "therapists": [
    {
      "name": "Dr. Maria Schmidt",
      "email": "m.schmidt@example.com",
      "phone": "030-1234567",
      "address": "Hauptstr. 1, 10115 Berlin"
    }
  ]
}
```

### Request: Generate Emails

```javascript
// POST /api/emails/generate
// Content-Type: application/json
{
  "therapists": [...],
  "user_info": {
    "first_name": "Max",
    "last_name": "Mustermann",
    "birth_date": "01.01.1990",
    "insurance": "TK",
    "email": "max@example.com",
    "phone": "0170-1234567"
  }
}

// Response
{
  "drafts": [
    {
      "to": "m.schmidt@example.com",
      "subject": "Anfrage Psychotherapie",
      "body": "..."
    }
  ],
  "applescript": "tell application \"Mail\"..."
}
```

## Browser Support

Modern browsers with ES6+ module support:
- Chrome 61+
- Firefox 60+
- Safari 11+
- Edge 79+
