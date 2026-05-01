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

API_DIR = Path(__file__).parent
PUBLIC_DIR = API_DIR / 'public'

# In-memory job storage (sufficient for one teacher creating books at a time)
# Structure: { jobId: { status: 'running'|'done'|'error', step: 'images', progress: 8, total: 16, bookId, error } }
jobs = {}

def download_library_json():
    """Fetch current library.json from GitHub before each run so library step can append to it."""
    from github import Github
    import base64 as _b64

    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)
    local = PUBLIC_DIR / 'library.json'
    local.parent.mkdir(parents=True, exist_ok=True)

    try:
        contents = repo.get_contents('public/library.json')
        local.write_text(_b64.b64decode(contents.content).decode('utf-8'))
        print('Downloaded library.json from GitHub')
    except Exception as e:
        print(f'library.json not found on GitHub ({e}), starting fresh')
        local.write_text('{"stories":[]}')

def push_to_github_api(job_id, book_title, book_id):
    """Push generated files to GitHub using Git Trees API — no git binary required."""
    from github import Github, InputGitTreeElement
    import base64 as _b64

    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)

    ref = repo.get_git_ref('heads/main')
    base_commit = repo.get_git_commit(ref.object.sha)
    base_tree = base_commit.tree

    elements = []

    # library.json
    lib_path = PUBLIC_DIR / 'library.json'
    if lib_path.exists():
        blob = repo.create_git_blob(lib_path.read_text('utf-8'), 'utf-8')
        elements.append(InputGitTreeElement('public/library.json', '100644', 'blob', sha=blob.sha))

    # All story files for this book
    story_dir = PUBLIC_DIR / 'stories' / book_id
    if story_dir.exists():
        for f in sorted(story_dir.rglob('*')):
            if not f.is_file():
                continue
            github_path = 'public/stories/' + book_id + '/' + str(f.relative_to(story_dir))
            if f.suffix in ('.webp', '.jpg', '.mp3'):
                blob = repo.create_git_blob(_b64.b64encode(f.read_bytes()).decode(), 'base64')
            else:
                blob = repo.create_git_blob(f.read_text('utf-8'), 'utf-8')
            elements.append(InputGitTreeElement(github_path, '100644', 'blob', sha=blob.sha))

    if not elements:
        print(f'[{job_id}] No files to push')
        return

    new_tree = repo.create_git_tree(elements, base_tree)
    new_commit = repo.create_git_commit(
        f'Add book: {book_title} (teacher-created)', new_tree, [base_commit]
    )
    ref.edit(new_commit.sha)
    print(f'[{job_id}] Pushed {len(elements)} files to GitHub via API')

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

        # Download library.json before creating a book
        download_library_json()

        # Generate book title from topic
        book_title = generate_book_title(topic, names)
        book_id = slugify(book_title)

        # Build the create_book.py command
        cmd = [
            'python', 'create_book.py',
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

        # Run create_book.py in the api directory
        print(f'[{job_id}] Starting pipeline with command: {" ".join(cmd)}')
        jobs[job_id]['step'] = 'story'

        result = subprocess.run(
            cmd,
            cwd=str(API_DIR),
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

        push_to_github_api(job_id, book_title, book_id)

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
