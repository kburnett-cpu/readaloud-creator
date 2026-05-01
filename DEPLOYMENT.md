# ReadAloud Creator — Deployment Guide

This guide walks you through deploying the ReadAloud Creator system to production. It assumes you have the main ReadAloud project already deployed on Netlify.

## Architecture Overview

```
Your Computer (git push)
    ↓
GitHub (repository)
    ↙               ↘
Railway            Netlify
(Python backend)   (Frontend + Functions)
    ↓
create_book.py runs
    ↓
Pushes back to GitHub
    ↓
Netlify auto-deploys
    ↓
Books appear in library
```

## Prerequisites

- GitHub account with your ReadAloud repository
- Netlify account (with ReadAloud already deployed)
- Railway.com account (free tier available)
- The `readaloud-creator` project in your local machine

## Step-by-Step Deployment

### Phase 1: GitHub Setup

#### 1.1 Create a GitHub Personal Access Token (PAT)

Railway needs this to push commits on your behalf.

1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a name: `ReadAloud Creator`
4. Select scopes: **`repo`** (all suboptions), **`workflow`** (optional)
5. Click "Generate token"
6. **Copy the token immediately** — you won't see it again

Store this somewhere safe; you'll need it in the next section.

#### 1.2 Initialize Git in readaloud-creator (if not already done)

```bash
cd /home/kabur/readaloud-creator
git init
git add .
git commit -m "Initial commit: ReadAloud Creator project"
```

#### 1.3 Create a GitHub Repository for readaloud-creator

1. Go to https://github.com/new
2. Name: `readaloud-creator` (or your preferred name)
3. **Do NOT initialize with README** (you already have files)
4. Click "Create repository"
5. Follow the instructions to push your local code:

```bash
git remote add origin https://github.com/YOUR_USERNAME/readaloud-creator.git
git branch -M main
git push -u origin main
```

---

### Phase 2: Railway Backend Setup

Railway hosts the Python Flask app that runs `create_book.py`.

#### 2.1 Sign Up / Log In to Railway

1. Go to https://railway.app
2. Sign up or log in with GitHub (recommended)

#### 2.2 Create a New Railway Project

1. Click "New Project"
2. Select "Deploy from GitHub repo"
3. Authorize Railway to access your GitHub account
4. Select your `readaloud-creator` repository
5. Railway will auto-detect the Python app (from `api/requirements.txt`)
6. Click "Deploy"

This deploys the Procfile automatically. The app will start but will fail initially (missing env vars — that's ok).

#### 2.3 Configure Environment Variables on Railway

1. In the Railway dashboard, click on your project
2. Click the "Variables" tab
3. Add each variable below. **Do not commit `.env` to Git** — Railway provides them:

```
PIPELINE_SECRET = (same value you'll use for Netlify — choose something random)
GITHUB_TOKEN = (your GitHub PAT from step 1.1)
GITHUB_REPO = your-username/readaloud (the MAIN readaloud repo, not readaloud-creator)
READALOUD_REPO_PATH = /app/readaloud
FLASK_ENV = production
ANTHROPIC_API_KEY = (from your main project)
GEMINI_API_KEY = (from your main project)
ELEVENLABS_API_KEY = (from your main project)
```

**Important:** 
- `GITHUB_REPO` should point to your main **readaloud** project (where books are stored), not readaloud-creator
- `PIPELINE_SECRET` must match what you set on Netlify (step 3.2)

#### 2.4 Deploy the Backend

1. Save the variables (Railway auto-saves)
2. Go to the "Deployments" tab
3. If it shows a failed deployment, manually trigger a redeploy:
   - Click "Trigger Deploy" or push a commit to readaloud-creator

Once deployed, you should see:
- A green checkmark next to the latest deployment
- A public URL (e.g., `https://readaloud-creator-production.up.railway.app`)
- **Copy this URL** — you'll need it for Netlify

Test it by visiting: `https://your-railway-url/health` — should return `{"status": "ok"}`

---

### Phase 3: Netlify Frontend Setup

Netlify hosts the web form and serverless functions that talk to Railway.

#### 3.1 Prepare the Frontend for Deployment

1. Update the book link in `src/components/BookCreator.jsx` (around line 235):

```jsx
href={`https://readaloud.burnettgroupusa.com/?bookId=${newBookId}`}
```

Replace `readaloud.burnettgroupusa.com` with your actual ReadAloud domain.

#### 3.2 Create a New Netlify Site from GitHub

1. Go to https://app.netlify.com
2. Click "Add new site" → "Import an existing project"
3. Select GitHub, then choose `readaloud-creator`
4. **Build settings:**
   - Build command: `npm run build`
   - Publish directory: `dist`
5. Click "Deploy site"

**Wait for the build to complete** (it will fail initially — missing env vars, that's ok).

#### 3.3 Configure Netlify Environment Variables

1. In the Netlify site dashboard, go to **Site settings** → **Build & deploy** → **Environment**
2. Add these variables:

```
VITE_TEACHER_PIN = 1234 (or your 4-digit code)
RAILWAY_API_URL = https://your-railway-url (from step 2.4)
PIPELINE_SECRET = (same value you set on Railway)
```

#### 3.4 Trigger a Rebuild

1. In Netlify, go to **Deploys**
2. Click **Trigger deploy** → **Deploy site**
3. Wait for the build to complete (should take ~2 minutes)

Once complete, you'll see a deploy URL (e.g., `https://readaloud-creator.netlify.app`).

#### 3.5 Set Up a Custom Domain (Optional but Recommended)

1. In Netlify site dashboard, go to **Site settings** → **Domain management**
2. Click "Add domain"
3. Point your domain to Netlify (follow their instructions)

---

### Phase 4: Integration Testing

#### 4.1 Test the Form

1. Open your Netlify site (or custom domain)
2. Enter the teacher PIN (default: `1234`)
3. Fill out the form:
   - Grade: 3rd
   - Topic: "A cat who finds a toy"
   - Names: Add 2-3 student names
   - Click "Create Book"
4. **You should see a progress screen** updating every few seconds

#### 4.2 Watch the Pipeline

1. Check the Railway logs:
   - Go to Railway dashboard
   - Click your project → **Deployments** → Click the latest deployment
   - Scroll to "Logs" tab — you should see messages like `[job-id] Starting pipeline...`

2. Monitor GitHub commits:
   - After ~10 minutes, check https://github.com/your-username/readaloud/commits
   - A new commit should appear: `Add book: ...` (teacher-created)

3. Check Netlify rebuild:
   - In the main readaloud Netlify dashboard, go to **Deploys**
   - A new deploy should be triggered automatically
   - Once complete, the book appears in the ReadAloud library

#### 4.3 Verify the Book

1. Open your main ReadAloud app (https://readaloud.burnettgroupusa.com or localhost:5173)
2. Scroll the library — your new book should appear within 1-2 minutes of the deploy completing
3. Click the book to read it

If you don't see it:
- Check that `library.json` was updated: look for your book in the GitHub commit
- Refresh the ReadAloud page (sometimes it takes a moment to load)
- Check Netlify logs for deploy errors

---

## Configuration & Customization

### Changing the Teacher PIN

1. On Netlify site dashboard, go to **Site settings** → **Build & deploy** → **Environment**
2. Edit `VITE_TEACHER_PIN` to a new 4-digit code
3. Trigger a redeploy

### Changing the Book Link Destination

If teachers should see a different link after book creation (not your main Readaloud domain):

1. Edit `src/components/BookCreator.jsx` line ~235
2. Update the `href` URL
3. Commit and push to GitHub — Netlify will auto-rebuild

### Changing the Pipeline Behavior

Want to customize which steps run, or add audio generation?

1. Edit `api/server.py` function `create_book_pipeline()` around line 70
2. Modify the `cmd` list to include/exclude steps
3. Push to GitHub (`readaloud-creator` repo) — Railway will auto-redeploy

Example: To include audio generation, change:

```python
cmd.extend(['--steps', 'story,prompts,images,library'])
```

to:

```python
cmd.extend(['--steps', 'story,prompts,images,audio,words,library'])
```

---

## Troubleshooting

### "Failed to start book creation"

1. **Check the Netlify function logs:**
   - Netlify dashboard → Functions → Click the function → Logs
   - Look for errors in the `/api/create-book` function

2. **Check Railway is running:**
   - Go to Railway dashboard
   - Verify the deployment is marked as "Running" (green status)
   - Check the backend URL in Netlify env vars matches Railway URL

3. **Check the shared secret:**
   - `PIPELINE_SECRET` on Netlify must **exactly match** the value on Railway
   - Case-sensitive!

### Book creation never completes

1. **Check Railway logs:**
   - Railway dashboard → Deployments → Logs tab
   - Look for errors in the `create_book.py` execution

2. **Check GitHub PAT:**
   - `GITHUB_TOKEN` on Railway should be a valid GitHub Personal Access Token
   - Token needs `repo` scope
   - Token expires after 1 year (by default)

3. **Check create_book.py itself:**
   - The pipeline relies on your main `readaloud/create_book.py`
   - Make sure it's up-to-date and working locally
   - API keys (Anthropic, Gemini, ElevenLabs) must be correct on Railway

### Book created but didn't push to GitHub

1. **Check git configuration on Railway:**
   - Verify `GITHUB_REPO` format is exactly `username/repo`
   - Verify `GITHUB_TOKEN` is valid and hasn't expired
   - Check Railway logs for `git push` errors

2. **Check main readaloud permissions:**
   - Make sure your GitHub account has write access to the main readaloud repo
   - The PAT should have `repo` scope

### Status polling never finishes

1. **Check if Railway is still running:**
   - If Railway crashed, the job status is lost
   - You may need to restart the Railway deployment

2. **Check Netlify function timeout:**
   - The `book-status` function has a 26-second timeout
   - If Railway isn't responding, you'll hit this timeout
   - Check both services' uptime/logs

---

## Next Steps & Improvements

### For You (Admin)

1. **Monitor book quality:** Periodically check books created by teachers for glitches
2. **Gather feedback:** Ask teachers what improvements they'd like
3. **Update the pipeline:** Modify `api/server.py` to add new features

### For Teachers

1. **Create books for their classes**
2. **Provide feedback:** What worked? What was confusing?

### Future Enhancements

- [ ] Auto-generate book title from topic using Claude
- [ ] Let teachers customize book length (pages)
- [ ] Preview generated story before creating images
- [ ] Add audio generation as a separate step (teachers can trigger it later)
- [ ] Email teachers when their book is ready
- [ ] Admin dashboard to see all created books and metadata
- [ ] Let teachers edit/iterate on failed books without starting over

---

## Getting Help

If something breaks:

1. **Check the logs:**
   - Netlify function logs (step 1)
   - Railway deployment logs (step 2)
   - Browser console (step 3)

2. **Check the configuration:**
   - Verify all environment variables are set correctly
   - Verify the shared secret matches between services
   - Verify GitHub PAT is valid

3. **Test locally (if possible):**
   ```bash
   # Test the Flask backend locally
   cd api
   python server.py  # Should listen on http://localhost:5000
   
   # Test the frontend locally
   cd ..
   npm install
   npm run dev  # Should open http://localhost:5173
   ```

4. **Reset and redeploy:**
   - Push a small change to readaloud-creator → Railway redeploys
   - Or manually trigger Netlify rebuild

---

## Summary

You now have:
- ✅ A teacher-facing form on Netlify
- ✅ A Python backend on Railway running `create_book.py`
- ✅ Automatic GitHub integration for easy library updates
- ✅ A status screen showing teachers what's happening

Teachers can now create books by filling out a simple form. The system handles the rest automatically.

Good luck, and happy book creating! 📚✨
