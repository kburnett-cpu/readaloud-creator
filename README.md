# ReadAloud Creator

A web-based book creation tool for teachers at Hope Academy. Teachers fill out a simple form (story topic, student names, grade level) and the system automatically generates a complete ReadAloud book with story, illustrations, and metadata.

## Project Structure

```
readaloud-creator/
├── src/
│   ├── components/
│   │   └── BookCreator.jsx       # Main teacher form component
│   ├── App.jsx                   # Root app with PIN auth
│   └── main.jsx                  # Entry point
├── netlify/functions/
│   ├── create-book.js            # Netlify function: POST /api/create-book
│   └── book-status.js            # Netlify function: GET /api/book-status
├── api/
│   ├── server.py                 # Flask backend (runs on Railway)
│   ├── requirements.txt           # Python dependencies
│   └── Procfile                  # Railway deployment config
├── index.html                    # HTML entry point
├── package.json                  # Node.js dependencies & scripts
├── vite.config.js                # Frontend build config
├── netlify.toml                  # Netlify deployment config
├── .env.example                  # Template for environment variables
├── README.md                     # This file
└── DEPLOYMENT.md                 # Step-by-step deployment guide
```

## Key Components

### Frontend (Netlify)
- **React + Vite** - Fast, modern web app
- **src/App.jsx** - PIN-protected entry (teachers enter a 4-digit code)
- **src/components/BookCreator.jsx** - Form with:
  - Grade level selector
  - Story topic textarea
  - Student name input
  - Featured checkbox
  - Progress screen with status polling
  - Success/error screens

### Backend (Railway)
- **api/server.py** - Flask app running on Railway
- Endpoints:
  - `POST /create-book` - Start a book creation job
  - `GET /status/:jobId` - Poll job status
  - `GET /health` - Health check
- Handles the full pipeline: story → images → library → git push
- Pushes to GitHub to trigger Netlify rebuild

### Netlify Functions (Serverless)
- **create-book.js** - Proxies form submission to Railway backend
- **book-status.js** - Proxies status checks to Railway backend
- Keeps Railway URL and shared secret hidden from the browser

## Local Development

### Prerequisites
- Node.js 18+ (for frontend)
- Python 3.10+ (for backend testing)
- The main `readaloud` project in `/home/kabur/readaloud`

### Frontend Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev
# Opens http://localhost:5173

# Build for production
npm run build
```

**File-by-file editing guide:**

- **App.jsx** - PIN screen and app layout. Edit to change PIN, header text, styling
- **BookCreator.jsx** - The form. Edit to add/remove fields, change labels, adjust styling
- **netlify/functions/*.js** - API proxies. Edit to change how data is sent to Railway

### Backend Development (Local Testing)

```bash
# Create a Python virtual environment
cd api
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run locally
PIPELINE_SECRET=dev-secret READALOUD_REPO_PATH=/home/kabur/readaloud python server.py
# Server runs on http://localhost:5000

# Test endpoints
curl http://localhost:5000/health
```

**File-by-file editing guide:**

- **server.py** - The Flask app. Main areas to edit:
  - `create_book_pipeline()` - The book creation steps (story, images, etc.)
  - `generate_book_title()` - How titles are created from topic
  - `build_theme_from_topic()` - The theme prompt sent to Claude
  - Endpoints - Add new routes or modify existing ones
- **requirements.txt** - Python dependencies. Add packages here if needed
- **Procfile** - Deployment config for Railway. Usually don't need to change

### Configuration

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
# Edit .env with your actual values
```

**Do NOT commit `.env` to Git** — it contains secrets!

For development, you can use dummy values:
```
VITE_TEACHER_PIN=1234
RAILWAY_API_URL=http://localhost:5000
PIPELINE_SECRET=dev-secret
```

## How It Works

### User Flow (From Teacher's Perspective)

1. Teacher opens the creator app
2. Enters PIN (default: 1234)
3. Fills form: grade, story idea, student names
4. Clicks "Create Book"
5. Sees progress: "Writing story... Creating images... Deploying..."
6. ~15-20 minutes later: "✅ Book ready! Open book"
7. Book appears in the main ReadAloud library

### Technical Flow (Behind the Scenes)

1. **Frontend** sends form data to Netlify function `/api/create-book`
2. **Netlify function** validates & forwards to Railway backend
3. **Railway backend** receives request, creates a job, returns `jobId` immediately
4. **Backend runs pipeline in background:**
   - Runs `create_book.py` from the main readaloud project
   - Steps: story → images → library.json
   - Commits & pushes results to GitHub
5. **Frontend polls** `/api/book-status` every 3 seconds for job status
6. **GitHub webhook** detects the new commit
7. **Netlify (main readaloud site)** auto-rebuilds & deploys
8. **Book appears** in the library

### Status States

- **idle** - Waiting for input
- **validating** - Checking form fields
- **submitting** - Sending to backend
- **running** - Pipeline is executing
- **story**, **images**, **library**, **deploying** - Current step
- **done** - Success! Book is ready
- **error** - Something went wrong

## Modifying the System

### Change the Teacher PIN

Edit `src/App.jsx`:
```jsx
const CONFIG = {
  TEACHER_PIN: import.meta.env.VITE_TEACHER_PIN || '5678',
}
```

Or set `VITE_TEACHER_PIN` in Netlify environment variables.

### Add a New Form Field

1. Add to `formData` state in `BookCreator.jsx`
2. Add input element in the form (around line 250)
3. Update submission data (around line 195)
4. Pass to Netlify function
5. Handle in `api/server.py` `create_book_pipeline()` function

Example: Add a "Book Length" field

```jsx
// In formData state
const [formData, setFormData] = useState({
  // ... existing fields ...
  pages: 12,  // Add this
})

// In the form JSX
<div style={styles.formGroup}>
  <label style={styles.label}>Number of Pages</label>
  <input
    type="number"
    name="pages"
    min="8"
    max="20"
    value={formData.pages}
    onChange={handleInputChange}
    style={styles.input}
  />
</div>

// In handleSubmit
body: JSON.stringify({
  // ... existing fields ...
  pages: formData.pages,  // Add this
})

// In api/server.py, create_book_pipeline()
pages = data.get('pages', 16)  # Add this
cmd.extend(['--pages', str(pages)])  # Add this
```

### Change What Steps Run

In `api/server.py`, around line 70:

```python
# Current: story + images + library (skip audio for speed)
cmd.extend(['--steps', 'story,prompts,images,library'])

# With audio (slower but complete):
cmd.extend(['--steps', 'story,prompts,images,audio,words,library'])

# Story only (fastest, for testing):
cmd.extend(['--steps', 'story,library'])
```

### Change the Book Title Generation

In `api/server.py`, modify `generate_book_title()`:

```python
def generate_book_title(topic, names):
    # Current simple approach:
    title = topic.strip()
    
    # Could be smarter: use student names
    # title = f"{names[0]}'s {topic}"
    
    return title
```

### Change the Story Prompt

In `api/server.py`, modify `build_theme_from_topic()`:

```python
def build_theme_from_topic(topic, names):
    names_str = ', '.join(names)
    return f"""
Create a story for students named {names_str}.

Teacher's story idea / topic: {topic}

Guidelines:
- Make it warm, joyful, and age-appropriate
- Include all {len(names)} students as characters where possible
- Set in a Caribbean/Dominican context unless the topic specifies otherwise
- The story should have a clear beginning, middle, and end
- [Add any other guidelines you want]
    """.strip()
```

## Deployment

See **DEPLOYMENT.md** for complete step-by-step instructions for deploying to:
- **Railway** (Python backend)
- **Netlify** (Frontend + Functions)
- **GitHub** (Integration)

Quick summary:
1. Create GitHub PAT with `repo` scope
2. Create Railway project from GitHub
3. Set Railway env vars (GitHub token, API keys, repo path)
4. Create Netlify site from GitHub
5. Set Netlify env vars (PIN, Railway URL, shared secret)
6. Test the form and watch it create a book

## API Reference

### POST /api/create-book

Creates a new book. Called by the frontend form.

**Request:**
```json
{
  "topic": "A turtle learning to swim",
  "names": ["Ashley", "Marcos", "Axel"],
  "gradeLevel": "3rd",
  "readingLevel": "D",
  "featured": false
}
```

**Response:**
```json
{
  "jobId": "550e8400-e29b-41d4-a716-446655440000"
}
```

### GET /api/book-status?jobId=...

Checks the status of a book creation job. Called repeatedly by the frontend.

**Query params:**
- `jobId` - UUID from the create-book response

**Response:**
```json
{
  "status": "running",
  "step": "images",
  "progress": 8,
  "total": 16,
  "bookId": "the-turtle-adventure",
  "bookTitle": "The Turtle Adventure"
}
```

Status values:
- `running` - Pipeline is executing
- `done` - Complete, book ready
- `error` - Failed, check `error` field

---

## Tips for Improvement

- **Auto-generate titles:** Use Claude to create titles from topics
- **Preview story:** Let teachers see the generated story before images start
- **Iterate on failures:** If a book fails, let teachers modify and retry without starting from scratch
- **Email notifications:** Send teachers an email when their book is ready
- **Image-only generation:** Let teachers regenerate images for a book without recreating the story
- **Admin dashboard:** See all books created, their status, timestamps
- **Bulk book creation:** Teachers can create multiple books in a queue

## Questions or Issues?

Refer to the DEPLOYMENT.md troubleshooting section.
