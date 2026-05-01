#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "anthropic>=0.83.0",
#     "google-genai>=1.0.0",
#     "pillow>=10.0.0",
#     "requests>=2.31.0",
# ]
# ///
"""
ReadAloud Book Creator — end-to-end pipeline

Creates a complete storybook from scratch:
  1. story    — Claude writes the story text + colors → story.json
  2. prompts  — Claude writes illustration prompts → Illustration_Prompts.md
  3. images   — Gemini generates page images → page-01.webp … cover.jpg
  4. audio    — ElevenLabs generates page audio + timestamps → page-01.mp3 …
  5. words    — ElevenLabs generates per-word audio → words/{word}.mp3
  6. library  — Adds the book to library.json

Usage
-----
    uv run create_book.py --title "The Little Seed" \\
        --grade-level PreK --reading-level Pre-A \\
        --theme "A child plants a seed and watches it grow into a flower" \\
        --tags plants,nature,science --pages 10

    # Re-run only the image step for an existing book:
    uv run create_book.py --id the-little-seed --steps images

    # Skip steps already done:
    uv run create_book.py --title "The Little Seed" ... --skip-existing
"""

import argparse
import base64
import json
import os
import re
import sys
import time
from io import BytesIO
from pathlib import Path

# ─── API KEYS (from environment variables) ──────────────────────────────────

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "J6Bc5DFk5HsxIQlL1hmC")
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")

ELEVENLABS_MODEL   = "eleven_multilingual_v2"
ELEVENLABS_VOICE_SETTINGS = {
    "stability": 0.65,
    "similarity_boost": 0.80,
    "style": 0.45,
    "use_speaker_boost": True,
}

CLAUDE_MODEL       = "claude-sonnet-4-6"
GEMINI_MODEL_HIGH  = "gemini-3-pro-image-preview"   # Imagen 3 Pro  ~$0.04/image
GEMINI_MODEL_FAST  = "gemini-2.0-flash-preview-image-generation"  # Flash  ~$0.02/image
GEMINI_MODEL       = GEMINI_MODEL_HIGH  # default; overridden by --image-quality fast
GEMINI_RESOLUTION  = "1K"
GEMINI_ASPECT      = "16:9"

STORIES_DIR = Path(__file__).parent / "public" / "stories"
LIBRARY_JSON = Path(__file__).parent / "public" / "library.json"

ALL_STEPS = ["story", "prompts", "images", "audio", "words", "library"]


# ─── UTILITIES ────────────────────────────────────────────────────────────────

def slugify(title: str) -> str:
    s = title.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s.strip())
    return s


def word_count(pages: list[dict]) -> int:
    return sum(len(p["text"].split()) for p in pages)


def font_size_for_level(reading_level: str) -> int:
    if reading_level in ("Pre-A",): return 32
    if reading_level in ("F",): return 22
    return 28


def lexile_for_level(reading_level: str, wc: int) -> str:
    # Rough mapping — Claude will refine this
    table = {"Pre-A": "BR90L", "A": "BR120L", "B": "BR150L", "C": "200L", "D": "400L", "E": "550L", "F": "750L"}
    return table.get(reading_level, "BR120L")


# ─── STEP 1: STORY GENERATION ─────────────────────────────────────────────────

STORY_SYSTEM = """You are an expert children's book author writing for Hope Academy in the Dominican Republic.
You write warm, joyful English storybooks for students learning English across all grade levels.
Characters are Dominican unless the theme specifies otherwise (e.g., Biblical stories use ancient Middle Eastern settings).
For reading levels Pre-A through E: Each page has exactly ONE short sentence. Keep vocabulary simple and concrete.
For reading level F (5th grade): Each page has 2-4 sentences forming a complete paragraph. Use richer vocabulary and more complex sentence structures appropriate for 10-11 year olds."""

STORY_USER = """Write a {num_pages}-page children's storybook with these parameters:

Title: {title}
Grade level: {grade_level}
Reading level: {reading_level} (Pre-A = 6-10 words/page; A = 8-13 words/page; B = 10-15 words/page; C-E = 12-20 words/page; F = 35-50 words/page)
Theme / story idea: {theme}
Tags: {tags}

Rules:
- Pre-A through E: Each page has exactly one sentence, appropriate length for the reading level
- F (5th grade): Each page has 2-4 sentences forming a complete paragraph with richer vocabulary and complex sentence structures
- Content should flow naturally as a complete story with a beginning, middle, and end
- For F level: Use more sophisticated vocabulary, longer sentences, and multi-character interactions/dialogue
- Dominican/Caribbean setting and characters (warm brown skin, dark hair, colorful homes) unless the theme says otherwise
- Vary sentence structure across pages so it doesn't feel repetitive
- For each page also choose a warm child-friendly background color (bg) and a complementary accent color

Return ONLY a valid JSON object with this exact structure — no markdown fences, no commentary:
{{
  "title": "{title}",
  "gradeLevel": "{grade_level}",
  "readingLevel": "{reading_level}",
  "tags": {tags_json},
  "pages": [
    {{"text": "Sentence for page 1.", "bg": "#E8F5E9", "accent": "#43A047"}},
    ...
  ]
}}"""


def step_story(book_id: str, title: str, grade_level: str, reading_level: str,
               theme: str, tags: list[str], num_pages: int,
               skip_existing: bool) -> dict:
    """Generate story content via Claude and write story.json."""
    story_dir = STORIES_DIR / book_id
    json_path = story_dir / "story.json"

    if skip_existing and json_path.exists():
        print("  [story] Already exists — loading.")
        return json.loads(json_path.read_text())

    print(f"  [story] Calling Claude ({CLAUDE_MODEL}) to write the story...")
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    tags_json = json.dumps(tags)
    prompt = STORY_USER.format(
        title=title, num_pages=num_pages, grade_level=grade_level,
        reading_level=reading_level, theme=theme,
        tags=", ".join(tags), tags_json=tags_json,
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=STORY_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown fences if Claude wrapped it anyway
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    story_data = json.loads(raw)

    # Build full story.json
    wc = word_count(story_data["pages"])
    fs = font_size_for_level(reading_level)
    full = {
        "schemaVersion": 1,
        "id": book_id,
        "title": story_data["title"],
        "author": "Hope Academy",
        "narrator": "Kirk",
        "cover": "cover.jpg",
        "gradeLevel": story_data.get("gradeLevel", grade_level),
        "readingLevel": story_data.get("readingLevel", reading_level),
        "lexile": story_data.get("lexile", lexile_for_level(reading_level, wc)),
        "wordCount": wc,
        "highlightMode": "word",
        "celebrationStyle": "confetti",
        "display": {
            "fontSize": fs,
            "fontFamily": "Andika",
            "lineHeight": 1.75,
            "wordSpacing": "0.15em",
            "letterSpacing": "0.03em",
        },
        "pages": [
            {
                "text": p["text"],
                "image": f"page-{i+1:02d}.webp",
                "bg": p.get("bg", "#FFF8E1"),
                "accent": p.get("accent", "#F9A825"),
                "audio": f"page-{i+1:02d}.mp3",
                "timestamps": [],
            }
            for i, p in enumerate(story_data["pages"])
        ],
    }

    story_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(full, indent=2, ensure_ascii=False))
    print(f"  [story] Wrote {len(full['pages'])} pages → {json_path}")
    for i, p in enumerate(full["pages"]):
        print(f"    p{i+1:02d}: {p['text']}")
    return full


# ─── STEP 2: ILLUSTRATION PROMPTS ─────────────────────────────────────────────

PROMPTS_SYSTEM = """You are an expert art director creating image generation prompts for a children's storybook.
You write vivid, specific Gemini image generation prompts that produce warm, vibrant, child-friendly illustrations.
Every prompt must specify: characters (with physical description), setting, action, mood, and art style."""

PROMPTS_USER = """Create illustration prompts for this {num_pages}-page children's storybook:

Title: {title}
Theme: {theme}
Setting context: {setting_context}

Story pages:
{pages_list}

Write ONE master style prompt (used as a prefix for every page) and ONE specific scene prompt per page.

Rules for master style:
- "Vibrant, warm children's book illustration in soft digital painting style. Clean outlines with rich saturated colors."
- Describe the main character(s) with specific physical details (age, skin tone, hair, clothing) — be consistent
- Describe the setting (Caribbean/Dominican yard/home/beach/etc. OR Biblical landscape as appropriate)
- End with "16:9 landscape format."

Rules for page prompts:
- Describe exactly what is happening on that page based on the text
- Include the character(s) with their visual anchors (same description every time)
- Specify the specific action, expression, and mood
- End each prompt with "Children's book illustration, 16:9 landscape."
- 3-6 sentences per prompt

Return ONLY a valid JSON object — no markdown, no commentary:
{{
  "master_style": "MASTER STYLE: ...",
  "page_prompts": [
    "Page 1 scene description. ... Children's book illustration, 16:9 landscape.",
    "Page 2 scene description. ...",
    ...
  ]
}}"""


def step_prompts(book_id: str, story: dict, theme: str, skip_existing: bool) -> dict:
    """Generate illustration prompts via Claude."""
    story_dir = STORIES_DIR / book_id
    prompts_path = story_dir / "Illustration_Prompts.json"
    md_path = story_dir / "Illustration_Prompts.md"

    if skip_existing and prompts_path.exists():
        print("  [prompts] Already exists — loading.")
        return json.loads(prompts_path.read_text())

    print(f"  [prompts] Calling Claude ({CLAUDE_MODEL}) to write illustration prompts...")
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    pages_list = "\n".join(
        f"  Page {i+1}: \"{p['text']}\"" for i, p in enumerate(story["pages"])
    )

    # Determine setting context from grade/theme
    theme_lower = theme.lower()
    if any(w in theme_lower for w in ["jesus", "bible", "biblical", "disciples", "god", "miracle"]):
        setting_context = "Ancient Middle Eastern Biblical setting — stone houses, sandy landscape, robes. Jesus: tall, kind, olive skin, white robes."
    else:
        setting_context = "Dominican Republic / Caribbean — colorful homes, tropical plants, warm brown-skinned Dominican family."

    prompt = PROMPTS_USER.format(
        title=story["title"], num_pages=len(story["pages"]),
        theme=theme, setting_context=setting_context,
        pages_list=pages_list,
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8192,
        system=PROMPTS_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)

    # Save JSON version for reuse
    prompts_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    # Also save human-readable Markdown guide
    md_lines = [
        f"# Illustration Prompt Guide: {story['title']}",
        "",
        "## Master Style",
        "",
        data["master_style"],
        "",
        "## Page Prompts",
        "",
    ]
    for i, p in enumerate(data["page_prompts"]):
        md_lines += [
            f"### Page {i+1} — `page-{i+1:02d}.webp`",
            f"> {story['pages'][i]['text']}",
            "",
            p,
            "",
        ]
    md_path.write_text("\n".join(md_lines))
    print(f"  [prompts] Wrote {len(data['page_prompts'])} prompts → {prompts_path.name}")
    return data


# ─── STEP 3: IMAGE GENERATION ─────────────────────────────────────────────────

REAL_IMAGE_MIN_BYTES = 20_000  # anything smaller is a placeholder, not a real illustration


def generate_one_image(client, prompt: str, output_path: Path,
                       retries: int = 3, fast: bool = False) -> bool:
    import signal
    from google.genai import types
    from PIL import Image as PILImage

    model   = GEMINI_MODEL_FAST if fast else GEMINI_MODEL_HIGH
    quality = 72 if fast else 85

    def _timeout_handler(signum, frame):
        raise TimeoutError("Gemini API call timed out")

    for attempt in range(retries):
        try:
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(90)  # 90-second hard timeout per attempt
            try:
                # Fast (Flash) model doesn't support image_config size/aspect params
                if fast:
                    config = types.GenerateContentConfig(
                        response_modalities=["TEXT", "IMAGE"],
                    )
                else:
                    config = types.GenerateContentConfig(
                        response_modalities=["TEXT", "IMAGE"],
                        image_config=types.ImageConfig(
                            image_size=GEMINI_RESOLUTION,
                            aspect_ratio=GEMINI_ASPECT,
                        ),
                    )
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
            finally:
                signal.alarm(0)

            for part in response.parts:
                if part.inline_data is not None:
                    image_data = part.inline_data.data
                    if isinstance(image_data, str):
                        image_data = base64.b64decode(image_data)
                    img = PILImage.open(BytesIO(image_data))
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    # Flash model outputs square images — crop to 16:9
                    if fast:
                        w, h = img.size
                        target_h = int(w * 9 / 16)
                        if target_h < h:
                            top = (h - target_h) // 2
                            img = img.crop((0, top, w, top + target_h))
                        elif target_h > h:
                            target_w = int(h * 16 / 9)
                            left = (w - target_w) // 2
                            img = img.crop((left, 0, left + target_w, h))
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    img.save(str(output_path), "WEBP", quality=quality)
                    return True
            print(f"    Warning: no image in response (attempt {attempt+1})")
        except Exception as e:
            print(f"    Error attempt {attempt+1}: {e}")
            if attempt < retries - 1:
                wait = 15 * (attempt + 1)
                print(f"    Waiting {wait}s...")
                time.sleep(wait)
    return False


def step_images(book_id: str, story: dict, prompts: dict,
                skip_existing: bool, fast: bool = False) -> None:
    """Generate WebP images via Gemini and create cover.jpg."""
    from google import genai
    from PIL import Image as PILImage

    story_dir = STORIES_DIR / book_id
    client = genai.Client(api_key=GEMINI_API_KEY)
    master = prompts["master_style"]
    page_prompts = prompts["page_prompts"]
    n = len(story["pages"])
    model_name = GEMINI_MODEL_FAST if fast else GEMINI_MODEL_HIGH

    print(f"  [images] Generating {n} images via Gemini ({model_name})...")
    ok = fail = 0

    for i in range(n):
        filename = f"page-{i+1:02d}.webp"
        out = story_dir / filename

        if skip_existing and out.exists() and out.stat().st_size > REAL_IMAGE_MIN_BYTES:
            print(f"    page {i+1:02d}: skip (exists, {out.stat().st_size//1024}KB)")
            ok += 1
            continue

        full_prompt = f"{master}\n\n{page_prompts[i]}"
        print(f"    page {i+1:02d}/{n}...", end=" ", flush=True)
        success = generate_one_image(client, full_prompt, out, fast=fast)
        if success:
            print("done")
            ok += 1
        else:
            print("FAILED")
            fail += 1

        if i < n - 1:
            time.sleep(3)

    # Create cover.jpg from page-01.webp
    cover_src = story_dir / "page-01.webp"
    cover_dst = story_dir / "cover.jpg"
    if cover_src.exists() and (not skip_existing or not cover_dst.exists()):
        img = PILImage.open(str(cover_src))
        img.save(str(cover_dst), "JPEG", quality=90)
        print(f"  [images] Created cover.jpg")

    print(f"  [images] {ok} generated, {fail} failed")


# ─── STEP 4: PAGE AUDIO ───────────────────────────────────────────────────────

def char_alignment_to_words(alignment: dict) -> list[dict]:
    chars  = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends   = alignment["character_end_times_seconds"]
    words, buf, word_start, word_end = [], [], None, None
    for ch, s, e in zip(chars, starts, ends):
        if ch in (" ", "\n", "\t", ""):
            if buf:
                words.append({"word": "".join(buf), "start": round(word_start, 3), "end": round(word_end, 3)})
                buf, word_start, word_end = [], None, None
        else:
            if word_start is None:
                word_start = s
            word_end = e
            buf.append(ch)
    if buf:
        words.append({"word": "".join(buf), "start": round(word_start, 3), "end": round(word_end, 3)})
    return words


def step_audio(book_id: str, story: dict, skip_existing: bool) -> dict:
    """Generate page MP3s + timestamps via ElevenLabs. Returns updated story."""
    import requests as req

    story_dir = STORIES_DIR / book_id
    json_path = story_dir / "story.json"
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/with-timestamps"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    print(f"  [audio] Generating {len(story['pages'])} page audio files...")
    updated = False

    for i, page in enumerate(story["pages"]):
        filename = f"page-{i+1:02d}.mp3"
        mp3_path = story_dir / filename

        if skip_existing and mp3_path.exists() and page.get("timestamps"):
            print(f"    page {i+1:02d}: skip (exists)")
            continue

        print(f"    page {i+1:02d}/{len(story['pages'])}...", end=" ", flush=True)
        payload = {
            "text": page["text"],
            "model_id": ELEVENLABS_MODEL,
            "voice_settings": ELEVENLABS_VOICE_SETTINGS,
        }

        try:
            resp = req.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            audio_bytes = base64.b64decode(data["audio_base64"])
            alignment = data.get("normalized_alignment") or data["alignment"]
            timestamps = char_alignment_to_words(alignment)

            mp3_path.write_bytes(audio_bytes)
            story["pages"][i]["audio"] = filename
            story["pages"][i]["timestamps"] = timestamps
            updated = True
            print(f"done ({len(timestamps)} words, {len(audio_bytes)//1024}KB)")
        except Exception as e:
            print(f"FAILED: {e}")

        time.sleep(0.5)

    if updated:
        story["wordCount"] = word_count(story["pages"])
        json_path.write_text(json.dumps(story, indent=2, ensure_ascii=False))
        print(f"  [audio] Updated story.json with timestamps")

    return story


# ─── STEP 5: WORD AUDIO ───────────────────────────────────────────────────────

def step_words(book_id: str, story: dict, skip_existing: bool) -> None:
    """Generate per-word MP3s via ElevenLabs."""
    import requests as req

    story_dir = STORIES_DIR / book_id
    words_dir = story_dir / "words"
    words_dir.mkdir(exist_ok=True)

    url_tpl = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    word_settings = {
        "stability": 0.75,
        "similarity_boost": 0.80,
        "style": 0.10,
        "use_speaker_boost": True,
    }

    # Collect unique words
    seen: dict[str, str] = {}
    for page in story["pages"]:
        for raw in page["text"].split():
            stem = re.sub(r"[^a-z0-9]", "", raw.strip(".,!?;:\"'()[]{}—–-").lower())
            spoken = raw.strip(".,!?;:\"()[]{}—–-")
            if stem and stem not in seen:
                seen[stem] = spoken

    words = sorted(seen.items())
    print(f"  [words] {len(words)} unique words to generate...")
    gen = skip = fail = 0

    for stem, spoken in words:
        mp3_path = words_dir / f"{stem}.mp3"
        if skip_existing and mp3_path.exists():
            skip += 1
            continue

        try:
            resp = req.post(
                url_tpl.format(voice_id=ELEVENLABS_VOICE_ID),
                headers=headers,
                json={"text": spoken, "model_id": ELEVENLABS_MODEL, "voice_settings": word_settings},
                timeout=30,
            )
            resp.raise_for_status()
            mp3_path.write_bytes(resp.content)
            gen += 1
        except Exception as e:
            print(f"    word '{spoken}': {e}")
            fail += 1

        time.sleep(0.3)

    print(f"  [words] {gen} generated, {skip} skipped, {fail} failed")


# ─── STEP 6: LIBRARY ──────────────────────────────────────────────────────────

def step_library(book_id: str, story: dict, tags: list[str], featured: bool) -> None:
    """Add or update the book entry in library.json."""
    lib = json.loads(LIBRARY_JSON.read_text()) if LIBRARY_JSON.exists() else {"stories": []}

    entry = {
        "id": book_id,
        "title": story["title"],
        "author": story.get("author", "Hope Academy"),
        "cover": f"stories/{book_id}/cover.jpg",
        "pages": len(story["pages"]),
        "featured": featured,
        "gradeLevel": story["gradeLevel"],
        "readingLevel": story["readingLevel"],
        "lexile": story.get("lexile", "BR120L"),
        "tags": tags,
        "narrator": story.get("narrator", "Kirk"),
    }

    existing = [s for s in lib["stories"] if s["id"] != book_id]
    lib["stories"] = existing + [entry]
    LIBRARY_JSON.write_text(json.dumps(lib, indent=2, ensure_ascii=False))
    print(f"  [library] Added/updated '{story['title']}' in library.json")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ReadAloud end-to-end book creator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--title",          help="Book title (required for new books)")
    parser.add_argument("--id",             help="Book ID slug (auto-derived from title if omitted)")
    parser.add_argument("--grade-level",    default="PreK", choices=["PreK", "K", "1st", "2nd", "3rd", "5th"],
                        help="Grade level (default: PreK)")
    parser.add_argument("--reading-level",  default="A", choices=["Pre-A", "A", "B", "C", "D", "E", "F"],
                        help="Reading level (default: A)")
    parser.add_argument("--theme",          help="Story theme / description (required for new books)")
    parser.add_argument("--tags",           default="",
                        help="Comma-separated tags, e.g. nature,family,animals")
    parser.add_argument("--pages",          type=int, default=12,
                        help="Number of pages (default: 12)")
    parser.add_argument("--featured",       action="store_true",
                        help="Mark as featured in the library")
    parser.add_argument("--steps",          default=",".join(ALL_STEPS),
                        help=f"Comma-separated steps to run (default: all). Options: {', '.join(ALL_STEPS)}")
    parser.add_argument("--skip-existing",  action="store_true",
                        help="Skip steps/files that already exist (safe to re-run)")
    parser.add_argument("--image-quality", default="high", choices=["high", "fast"],
                        help="'high' = Imagen 3 Pro ~$0.04/img (default); 'fast' = Flash ~$0.02/img, quality=72")

    args = parser.parse_args()

    steps = [s.strip() for s in args.steps.split(",")]
    invalid = [s for s in steps if s not in ALL_STEPS]
    if invalid:
        sys.exit(f"Unknown steps: {invalid}. Valid: {ALL_STEPS}")

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    # Resolve book ID
    if args.id:
        book_id = args.id
    elif args.title:
        book_id = slugify(args.title)
    else:
        sys.exit("Error: provide --title or --id")

    title = args.title or book_id.replace("-", " ").title()

    print(f"\n{'='*60}")
    print(f"ReadAloud Book Creator")
    print(f"Book:  {title} ({book_id})")
    print(f"Steps: {', '.join(steps)}")
    print(f"{'='*60}\n")

    story = None
    prompts = None

    # Load existing story.json if not regenerating
    story_json_path = STORIES_DIR / book_id / "story.json"
    if "story" not in steps and story_json_path.exists():
        story = json.loads(story_json_path.read_text())

    # ── Step 1: Story
    if "story" in steps:
        if not args.theme:
            sys.exit("Error: --theme is required for the 'story' step")
        story = step_story(
            book_id=book_id, title=title,
            grade_level=args.grade_level, reading_level=args.reading_level,
            theme=args.theme, tags=tags, num_pages=args.pages,
            skip_existing=args.skip_existing,
        )

    if story is None:
        sys.exit(f"Error: no story.json found for '{book_id}'. Run with --steps story first.")

    # ── Step 2: Illustration Prompts
    if "prompts" in steps:
        theme = args.theme or "children's storybook"
        prompts = step_prompts(book_id=book_id, story=story,
                               theme=theme, skip_existing=args.skip_existing)

    # Load existing prompts if not regenerating
    prompts_path = STORIES_DIR / book_id / "Illustration_Prompts.json"
    if prompts is None and prompts_path.exists():
        prompts = json.loads(prompts_path.read_text())

    # ── Step 3: Images
    if "images" in steps:
        if prompts is None:
            sys.exit("Error: no prompts found. Run with --steps prompts first (or include 'prompts' in --steps).")
        step_images(book_id=book_id, story=story, prompts=prompts,
                    skip_existing=args.skip_existing,
                    fast=(args.image_quality == "fast"))

    # ── Step 4: Page Audio
    if "audio" in steps:
        story = step_audio(book_id=book_id, story=story,
                           skip_existing=args.skip_existing)

    # ── Step 5: Word Audio
    if "words" in steps:
        step_words(book_id=book_id, story=story,
                   skip_existing=args.skip_existing)

    # ── Step 6: Library
    if "library" in steps:
        step_library(book_id=book_id, story=story, tags=tags,
                     featured=args.featured)

    print(f"\n{'='*60}")
    print(f"Done! Book '{title}' is ready at:")
    print(f"  {STORIES_DIR / book_id}/")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
