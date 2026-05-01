#!/usr/bin/env python3
"""
ReadAloud Creator Backend

Flask server that runs the book creation pipeline. Receives form data from the
Netlify frontend, orchestrates the create_book.py pipeline, and provides status updates.

This server is deployed to Railway.com for long-running book generation tasks.

Environment variables:
- FLASK_ENV: development or production
- PORT: Server port (default 5000)
- PIPELINE_SECRET: Shared secret for Netlify Functions authentication
- GITHUB_TOKEN: GitHub PAT for pushing commits
- GITHUB_REPO: GitHub repo in format "username/repo"
- ANTHROPIC_API_KEY: Claude API key
- GEMINI_API_KEY: Google Gemini API key
- ELEVENLABS_API_KEY: ElevenLabs API key
"""

import os
import json
import uuid
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify
from functools import wraps

app = Flask(__name__)

# Configuration
PIPELINE_SECRET = os.environ.get('PIPELINE_SECRET', 'dev-secret')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO = os.environ.get('GITHUB_REPO', '')
READALOUD_REPO_PATH = os.environ.get('READALOUD_REPO_PATH', '/app/readaloud')

# In-memory job storage (sufficient for one teacher creating books at a time)
# Structure: { jobId: { status: 'running'|'done'|'error', step: 'images', progress: 8, total: 16, bookId, error } }
jobs = {}

def ensure_readaloud_repo():
    """Clone the main readaloud repo if it doesn't exist, or pull latest if it does."""
    repo_path = Path(READALOUD_REPO_PATH)
    clone_url = f'https://x-access-token:{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git'

    if not repo_path.exists():
        print(f'Cloning {GITHUB_REPO} into {READALOUD_REPO_PATH}...')
        subprocess.run(['git', 'clone', clone_url, str(repo_path)], check=True)
        print('Clone complete.')
    else:
        print(f'Pulling latest from {GITHUB_REPO}...')
        subprocess.run(['git', '-C', str(repo_path), 'pull'], check=True)
        print('Pull complete.')

# Clone/pull the readaloud repo on startup
if GITHUB_TOKEN and GITHUB_REPO:
    try:
        ensure_readaloud_repo()
    except Exception as e:
        print(f'Warning: Could not clone/pull readaloud repo on startup: {e}')

# ═══════════════════════════════════════════════════════════════════════════════
# Authentication Middleware
# ═══════════════════════════════════════════════════════════════════════════════

def require_auth(f):
    """Decorator to require X-Api-Key header authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-Api-Key')
        if api_key != PIPELINE_SECRET:
            return jsonify({ 'error': 'Unauthorized' }), 401
        return f(*args, **kwargs)
    return decorated_function

# ═══════════════════════════════════════════════════════════════════════════════
# Book Creation Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def create_book_pipeline(job_id, topic, names, grade_level, reading_level, featured):
    """
    Main book creation pipeline. Runs in a background thread.

    Steps:
    1. Generate story
    2. Generate image prompts
    3. Generate images
    4. Update library.json
    5. Git push to trigger Netlify deploy
    """
    try:
        # Update job status
        jobs[job_id]['status'] = 'running'

        # Pull latest readaloud repo before creating a book
        ensure_readaloud_repo()

        # Generate book title from topic
        book_title = generate_book_title(topic, names)
        book_id = slugify(book_title)

        # Build the create_book.py command
        cmd = [
            'uv', 'run', 'create_book.py',
            '--title', book_title,
            '--grade-level', grade_level,
            '--reading-level', reading_level,
            '--theme', build_theme_from_topic(topic, names),
            '--pages', '16',
            '--tags', 'teacher-created,story',
        ]

        if featured:
            cmd.append('--featured')

        # Steps to run (skip audio for now to speed up)
        cmd.extend(['--steps', 'story,prompts,images,library'])

        # Run create_book.py in the readaloud directory
        print(f'[{job_id}] Starting pipeline with command: {" ".join(cmd)}')
        jobs[job_id]['step'] = 'story'

        result = subprocess.run(
            cmd,
            cwd=READALOUD_REPO_PATH,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )

        if result.returncode != 0:
            print(f'[{job_id}] Pipeline failed:')
            print(f'STDOUT: {result.stdout}')
            print(f'STDERR: {result.stderr}')
            jobs[job_id]['status'] = 'error'
            jobs[job_id]['error'] = 'Book creation pipeline failed. Check server logs.'
            return

        print(f'[{job_id}] create_book.py completed successfully')

        # Push to GitHub to trigger Netlify deploy
        jobs[job_id]['step'] = 'deploying'
        jobs[job_id]['progress'] = 0
        jobs[job_id]['total'] = 1

        push_to_github(job_id, book_title)

        # Success!
        jobs[job_id]['status'] = 'done'
        jobs[job_id]['bookId'] = book_id
        jobs[job_id]['bookTitle'] = book_title
        jobs[job_id]['step'] = 'done'

        print(f'[{job_id}] Book creation complete: {book_title} ({book_id})')

    except subprocess.TimeoutExpired:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['error'] = 'Pipeline timed out after 30 minutes'
        print(f'[{job_id}] Pipeline timeout')
    except Exception as e:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['error'] = str(e)
        print(f'[{job_id}] Pipeline error: {e}')

def generate_book_title(topic, names):
    """Generate a book title from topic and names"""
    # Simple strategy: use topic as title, may refine later
    # Could be improved to use LLM or smarter heuristics
    title = topic.strip()
    if not title.endswith(('!', '?', '.')):
        title += ''
    # Truncate to reasonable length
    if len(title) > 50:
        title = title[:47] + '...'
    return title

def build_theme_from_topic(topic, names):
    """Build a detailed theme/story prompt from teacher input"""
    names_str = ', '.join(names)
    return f"""
Create a story for students named {names_str}.

Teacher's story idea / topic: {topic}

Guidelines:
- Make it warm, joyful, and age-appropriate
- Include all {len(names)} students as characters where possible
- Set in a Caribbean/Dominican context unless the topic specifies otherwise
- The story should have a clear beginning, middle, and end
- Include positive messages about friendship, learning, and community
    """.strip()

def slugify(text):
    """Convert text to a URL-safe slug"""
    s = text.lower()
    s = ''.join(c if c.isalnum() or c in ('-', ' ') else '' for c in s)
    s = '-'.join(s.split())
    return s

def push_to_github(job_id, book_title):
    """Push changes to GitHub to trigger Netlify rebuild"""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print(f'[{job_id}] Skipping GitHub push (credentials not configured)')
        return

    try:
        os.chdir(READALOUD_REPO_PATH)

        # Configure git (needed in CI/CD environments)
        subprocess.run(['git', 'config', 'user.name', 'ReadAloud Creator'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'creator@readaloud.local'], check=True, capture_output=True)

        # Add changes
        subprocess.run(['git', 'add', 'public/stories/', 'public/library.json'], check=True, capture_output=True)

        # Commit
        commit_msg = f'Add book: {book_title} (teacher-created)'
        subprocess.run(['git', 'commit', '-m', commit_msg], check=True, capture_output=True)

        # Push (use token for auth)
        push_url = f'https://x-access-token:{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git'
        subprocess.run(['git', 'push', push_url, 'HEAD:main'], check=True, capture_output=True)

        print(f'[{job_id}] Pushed to GitHub successfully')
    except subprocess.CalledProcessError as e:
        print(f'[{job_id}] GitHub push failed: {e}')
        raise

# ═══════════════════════════════════════════════════════════════════════════════
# API Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({ 'status': 'ok', 'timestamp': datetime.utcnow().isoformat() })

@app.route('/create-book', methods=['POST'])
@require_auth
def create_book():
    """
    POST /create-book

    Receives book creation form data and starts the pipeline in a background thread.
    Returns immediately with a jobId for polling.

    Request body:
    {
      "topic": "A turtle learning to swim",
      "names": ["Ashley", "Marcos"],
      "gradeLevel": "3rd",
      "readingLevel": "D",
      "featured": false
    }

    Response:
    {
      "jobId": "uuid-here"
    }
    """
    try:
        data = request.get_json()

        topic = data.get('topic', '').strip()
        names = data.get('names', [])
        grade_level = data.get('gradeLevel', '3rd')
        reading_level = data.get('readingLevel', 'D')
        featured = data.get('featured', False)

        # Validation
        if not topic:
            return jsonify({ 'error': 'topic is required' }), 400
        if not names or len(names) == 0:
            return jsonify({ 'error': 'at least one name is required' }), 400

        # Create job
        job_id = str(uuid.uuid4())
        jobs[job_id] = {
            'status': 'initializing',
            'step': 'starting',
            'progress': 0,
            'total': 16,
            'createdAt': datetime.utcnow().isoformat(),
        }

        print(f'[{job_id}] New book creation job: {topic} ({", ".join(names)})')

        # Start pipeline in background thread
        thread = threading.Thread(
            target=create_book_pipeline,
            args=(job_id, topic, names, grade_level, reading_level, featured),
            daemon=True,
        )
        thread.start()

        return jsonify({ 'jobId': job_id }), 202

    except Exception as e:
        print(f'Error in create-book endpoint: {e}')
        return jsonify({ 'error': 'Server error' }), 500

@app.route('/status/<job_id>', methods=['GET'])
@require_auth
def status(job_id):
    """
    GET /status/<jobId>

    Returns the current status of a book creation job.

    Response:
    {
      "status": "running" | "done" | "error",
      "step": "story" | "images" | "library" | "deploying",
      "progress": 8,
      "total": 16,
      "bookId": "the-book-slug",
      "bookTitle": "The Book Title",
      "error": "error message if status is error"
    }
    """
    if job_id not in jobs:
        return jsonify({ 'error': 'Job not found' }), 404

    job = jobs[job_id]
    response = {
        'status': job.get('status'),
        'step': job.get('step'),
        'progress': job.get('progress', 0),
        'total': job.get('total', 16),
    }

    if job.get('bookId'):
        response['bookId'] = job['bookId']
    if job.get('bookTitle'):
        response['bookTitle'] = job['bookTitle']
    if job.get('error'):
        response['error'] = job['error']

    return jsonify(response), 200

@app.route('/', methods=['GET'])
def root():
    """Root endpoint with API info"""
    return jsonify({
        'service': 'ReadAloud Creator Backend',
        'version': '0.1.0',
        'endpoints': {
            'POST /create-book': 'Start a book creation job',
            'GET /status/:jobId': 'Check job status',
            'GET /health': 'Health check',
        },
    }), 200

# ═══════════════════════════════════════════════════════════════════════════════
# Error Handlers
# ═══════════════════════════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    return jsonify({ 'error': 'Not found' }), 404

@app.errorhandler(500)
def server_error(e):
    print(f'Server error: {e}')
    return jsonify({ 'error': 'Server error' }), 500

# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
