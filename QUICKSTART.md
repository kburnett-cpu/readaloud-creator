# Quick Start Guide

Get the ReadAloud Creator running locally for development.

## 5-Minute Setup

### 1. Install Dependencies

```bash
cd /home/kabur/readaloud-creator
npm install
```

### 2. Create Local .env

```bash
cp .env.example .env
```

Edit `.env` and set:
```
VITE_TEACHER_PIN=1234
```

(Other values are only needed if testing the full pipeline)

### 3. Start Frontend

```bash
npm run dev
```

Opens http://localhost:5173

**You can now:**
- See the PIN screen (enter `1234`)
- See the book creation form
- (Form submission won't work without a running backend)

---

## Full Local Setup (With Backend)

If you want to test the complete pipeline locally:

### Backend Setup

```bash
# In a new terminal, from the project root:
cd api
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set environment variables
export READALOUD_REPO_PATH=/home/kabur/readaloud
export PIPELINE_SECRET=dev-secret
export ANTHROPIC_API_KEY=your-key
export GEMINI_API_KEY=your-key

# Start the server
python server.py
```

Verify it's running: `curl http://localhost:5000/health`

### Frontend Setup (Different Terminal)

```bash
# Make sure RAILWAY_API_URL points to localhost
export RAILWAY_API_URL=http://localhost:5000
export PIPELINE_SECRET=dev-secret

# Start dev server
npm run dev
```

### Test the Full Flow

1. Open http://localhost:5173
2. Enter PIN: `1234`
3. Fill form and submit
4. Watch the backend terminal for output
5. Polls should show progress

---

## Production Deployment

See **DEPLOYMENT.md** for full instructions.

TL;DR:
1. Push to GitHub
2. Connect to Railway
3. Connect to Netlify
4. Set environment variables
5. Done!

---

## Common Commands

```bash
# Frontend
npm run dev          # Start dev server
npm run build        # Build for production
npm run preview      # Preview production build locally

# Backend
python server.py     # Run Flask app
python server.py --help  # See options (if implemented)

# Git
git status
git add .
git commit -m "message"
git push
```

---

## File Structure Quick Reference

```
src/
├── App.jsx           ← Main app with PIN auth
├── main.jsx          ← Entry point
└── components/
    └── BookCreator.jsx  ← The teacher form

netlify/functions/
├── create-book.js    ← Receives form → sends to Railway
└── book-status.js    ← Polls job status from Railway

api/
├── server.py         ← Flask backend (runs on Railway)
└── requirements.txt  ← Python packages
```

---

## Making Changes

### Change the Form

Edit `src/components/BookCreator.jsx`:
- Add/remove fields
- Change labels
- Update styling

Then refresh http://localhost:5173

### Change the Backend Logic

Edit `api/server.py`:
- Modify the pipeline steps
- Change how books are created
- Add new API endpoints

Then restart the Python server

### Add a New API Endpoint

In `api/server.py`, add:

```python
@app.route('/my-endpoint', methods=['GET', 'POST'])
@require_auth
def my_endpoint():
    return jsonify({ 'result': 'success' }), 200
```

Then call from frontend:
```javascript
const response = await fetch('/api/my-endpoint', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ data: 'value' })
})
```

---

## Debugging

### Backend not responding?

```bash
# Check if server is running
curl http://localhost:5000/health

# Check logs in terminal where you ran `python server.py`
# Look for error messages
```

### Frontend not loading?

```bash
# Check if Vite is running
# Open browser console (F12) and check for errors
# Verify http://localhost:5173 is accessible
```

### Form submission fails?

1. Check browser console for errors
2. Check Netlify function logs (or Flask logs if running locally)
3. Verify PIPELINE_SECRET matches on both frontend and backend
4. Verify RAILWAY_API_URL is correct

---

## Next Steps

1. **Try the form locally** - Understand the user flow
2. **Modify the form** - Add/remove fields based on teacher feedback
3. **Deploy to production** - Follow DEPLOYMENT.md
4. **Get feedback from teachers** - Iterate on improvements
