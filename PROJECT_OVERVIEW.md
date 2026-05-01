# ReadAloud Creator — Project Overview

Welcome! This project enables teachers to create ReadAloud books through a web form instead of requiring a developer to run `create_book.py` manually.

## What You Have

A complete, production-ready system split into **three parts**:

### 1. **Frontend** (Netlify)
- React app with Vite build system
- Teacher PIN login
- Book creation form
- Status polling UI
- Serverless functions (Netlify Functions)

### 2. **Backend** (Railway)
- Python Flask server
- Receives book requests
- Runs the full `create_book.py` pipeline
- Manages job status
- Pushes changes to GitHub

### 3. **Integration** (GitHub)
- Your main ReadAloud repository
- Automatically rebuilds on Netlify when new books are pushed
- Teachers never see Git—it's automatic

## Files You'll Work With

### Configuration (Setup Once)
- **`.env.example`** → Copy to `.env` and fill in your secrets
- **`netlify.toml`** → Already configured
- **`api/Procfile`** → Already configured for Railway
- **`package.json`** → Already configured

### Code to Customize (Based on Teacher Feedback)
- **`src/components/BookCreator.jsx`** — Teacher form
  - Change fields (topic, names, grade, etc.)
  - Update form labels and descriptions
  - Adjust styling
  
- **`api/server.py`** — Book creation logic
  - Customize how book titles are generated
  - Modify the story prompt sent to Claude
  - Change which pipeline steps run (story, images, audio, etc.)
  - Add new API endpoints

- **`src/App.jsx`** — PIN login screen
  - Change the teacher PIN
  - Update welcome message
  - Customize styling

### Documentation (Reference)
- **`README.md`** — Technical overview and how to modify
- **`DEPLOYMENT.md`** — ⭐ **Start here for going live** — Step-by-step instructions
- **`QUICKSTART.md`** — Quick local setup guide

## The Journey

### Phase 1: Test Locally
```bash
npm install
npm run dev
# Opens http://localhost:5173 with the form
# (Backend features require local Flask setup)
```

**See:** QUICKSTART.md

### Phase 2: Deploy to Production
1. Push code to GitHub
2. Connect to Railway (backend)
3. Connect to Netlify (frontend)
4. Set environment variables
5. Done!

**See:** DEPLOYMENT.md ← **Most important document**

### Phase 3: Teachers Create Books
1. Visit the form URL
2. Enter PIN (e.g., 1234)
3. Fill in: topic, names, grade
4. Click "Create Book"
5. Wait 15-20 minutes
6. Book appears in ReadAloud library

### Phase 4: Iterate & Improve
1. Gather feedback from teachers
2. Modify the form / backend
3. Deploy changes
4. Repeat

## Key Design Decisions

### Why This Architecture?

- **Netlify Frontend** → Good for static UI, functions are fast for proxies
- **Railway Backend** → Can run long Python processes (15+ minutes)
- **GitHub Integration** → Automatic rebuilds, teachers don't see Git
- **Environment Variables** → Secrets never hardcoded, easily changed
- **Threading/Background Jobs** → Form responds instantly, pipeline runs in background

### Why Modular Code?

Every function is designed to be **easily changeable without breaking things**:

- `generate_book_title()` → Change how titles are created
- `build_theme_from_topic()` → Change the prompt sent to Claude
- Form fields → Add/remove without touching other code
- API endpoints → Add new ones without modifying existing ones

## Important URLs (After Deployment)

```
Frontend (Teachers use this):
https://readaloud-creator.netlify.app  (or your custom domain)

Backend (Never accessed directly):
https://your-app.railway.app  (internal only)

Main ReadAloud App (Where books appear):
https://readaloud.burnettgroupusa.com  (or your URL)
```

## What Happens When a Teacher Creates a Book

```
1. Teacher submits form
   ↓
2. Frontend POSTs to Netlify function (create-book.js)
   ↓
3. Function forwards to Railway backend
   ↓
4. Backend creates job, returns jobId
   ↓
5. Frontend polls status every 3 seconds
   ↓
6. Backend runs pipeline in background:
   - Claude generates story
   - Gemini generates images
   - Updates library.json
   ↓
7. Backend pushes to GitHub
   ↓
8. GitHub webhook triggers Netlify rebuild
   ↓
9. Main ReadAloud site deploys
   ↓
10. Book appears in library (1-2 min after pipeline finishes)
```

Total time: **15-20 minutes** (most of that is Gemini image generation)

## First Time Deployment Checklist

- [ ] Read **DEPLOYMENT.md** carefully (all the way through first)
- [ ] Create GitHub Personal Access Token
- [ ] Push readaloud-creator to GitHub
- [ ] Create Railway project
- [ ] Set Railway environment variables
- [ ] Create Netlify project
- [ ] Set Netlify environment variables
- [ ] Trigger Netlify rebuild
- [ ] Test: Visit form → enter PIN → submit form
- [ ] Watch logs: Check Railway logs, GitHub commits, Netlify rebuilds
- [ ] Verify: Check that book appears in main ReadAloud app

## Common Modifications

### Change Teacher PIN
Edit `src/App.jsx` or Netlify env vars → redeploy

### Add a New Form Field
1. Add to `formData` in `BookCreator.jsx`
2. Add input element
3. Pass to backend in form submission
4. Handle in `api/server.py`

### Change Pipeline Steps
Edit `api/server.py` line 70 — change which steps run

### Auto-Generate Book Titles
Modify `generate_book_title()` in `api/server.py`

### Change the Story Prompt
Modify `build_theme_from_topic()` in `api/server.py`

## Support & Debugging

1. **Local issues?** → See QUICKSTART.md
2. **Deployment issues?** → See DEPLOYMENT.md Troubleshooting section
3. **Book creation fails?** → Check Railway logs + GitHub token
4. **Form not submitting?** → Check Netlify functions + browser console
5. **Book doesn't appear?** → Check library.json in GitHub + Netlify deploy status

## Version Control & Deployment

```bash
# Make changes locally
edit src/components/BookCreator.jsx

# Test locally
npm run dev

# Commit and push
git add .
git commit -m "Update form fields"
git push origin main

# Netlify auto-rebuilds immediately
# Railway auto-redeploys if api/* changed
# Changes live in ~2 minutes
```

## Next Steps

1. **Read DEPLOYMENT.md** — Follow every step carefully
2. **Test locally** — Run `npm run dev`
3. **Deploy to Railway** — Follow DEPLOYMENT.md Phase 2
4. **Deploy to Netlify** — Follow DEPLOYMENT.md Phase 3
5. **Test end-to-end** — Create a test book
6. **Share with teachers** — Give them the form URL + PIN

## Questions to Ask Yourself (Plan for Future)

After the first teacher creates a book:

- Did they understand what to fill in?
- Was the 15-20 minute wait acceptable?
- Did they want to see a preview of the story?
- Did they want to customize the title?
- Did they want to iterate (retry without restarting)?
- Should audio be included automatically or optional?
- Should there be an admin dashboard?

These answers drive the next version of improvements.

---

## File-by-File Guide

| File | Purpose | Modify? |
|------|---------|---------|
| `package.json` | Node dependencies | Rarely |
| `vite.config.js` | Frontend build | No |
| `netlify.toml` | Netlify config | No |
| `index.html` | HTML entry | No |
| `src/App.jsx` | PIN login | Yes (PIN, text) |
| `src/App.css` | Styling | Yes (colors, fonts) |
| `src/main.jsx` | React entry | No |
| `src/components/BookCreator.jsx` | Teacher form | **Yes** (main customization) |
| `netlify/functions/create-book.js` | POST handler | Rarely |
| `netlify/functions/book-status.js` | Status handler | Rarely |
| `api/server.py` | Pipeline orchestration | **Yes** (book creation logic) |
| `api/requirements.txt` | Python deps | Rarely |
| `api/Procfile` | Railway config | No |
| `.env.example` | Secrets template | No (reference only) |
| `.gitignore` | Git ignore | No |
| `README.md` | Technical guide | Reference |
| `DEPLOYMENT.md` | Deploy guide | Reference |
| `QUICKSTART.md` | Local setup | Reference |

---

## Success Criteria

After deployment, you'll have succeeded when:

✅ Teachers can access the form with a PIN
✅ Teachers can fill out and submit the form
✅ The frontend shows progress (status polling works)
✅ After ~15 minutes, the book appears in the library
✅ The book has story, images, and metadata
✅ Teachers can create multiple books
✅ You can easily modify the form/pipeline based on feedback

## You're Ready!

Everything is built and documented. Start with **DEPLOYMENT.md** and follow the steps exactly.

Good luck! 📚✨
