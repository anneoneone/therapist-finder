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

## Free Hosting (GitHub Pages)

The `frontend/` directory is deployed to GitHub Pages automatically on every
push to `main` via `.github/workflows/pages.yml`.

### One-time setup

1. Push this branch and merge it to `main`.
2. In the GitHub repo: **Settings → Pages → Build and deployment → Source**:
   select **GitHub Actions**.
3. The `Deploy Frontend to GitHub Pages` workflow will publish the site to
   `https://<user>.github.io/<repo>/`.

### Backend on Render

GitHub Pages serves static files only. The FastAPI backend is deployed
separately to Render using the `render.yaml` blueprint at the repo root.

1. Sign in at [render.com](https://render.com) and click **New → Blueprint**.
2. Point it at this GitHub repo; Render reads `render.yaml` and creates the
   `therapist-finder-api` web service on the free plan.
3. Set the `CORS_ORIGINS` env var to your Pages URL, e.g.
   `https://anneoneone.github.io`.
4. After the first deploy Render prints the public URL, e.g.
   `https://therapist-finder-api.onrender.com`.
5. Point the frontend at that URL by adding a script tag to `index.html`
   **before** the `app.js` import:

   ```html
   <script>window.API_BASE = 'https://therapist-finder-api.onrender.com/api';</script>
   ```

Note: Render's free web services sleep after ~15 min of inactivity and take a
few seconds to wake on the first request.

## Browser Support

Modern browsers with ES6+ module support:
- Chrome 61+
- Firefox 60+
- Safari 11+
- Edge 79+
