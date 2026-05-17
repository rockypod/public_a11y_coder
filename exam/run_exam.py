"""
run_exam.py — a11y-public-coder 30-question exam runner

Collects model responses from a local Ollama endpoint and saves them for
manual grading.  After grading, fill in grades.json and re-run with --score
to get the domain summary table.

Usage:
    # Collect responses against a baseline
    python run_exam.py --model qwen3-coder:14b --output baselines/qwen3-coder-14b

    # Collect responses against a trained model
    python run_exam.py --model a11y-public-coder:14b --output trained/14b

    # Score after manually filling grades.json
    python run_exam.py --score baselines/qwen3-coder-14b

    # Resume (skips questions that already have a response file)
    python run_exam.py --model qwen3:4b --output baselines/qwen3-4b

    # Run only first N questions (smoke test)
    python run_exam.py --model qwen3:4b --output baselines/qwen3-4b --limit 5

Output layout:
    DIR/q01.txt        raw model response
    DIR/responses.json all Q+A metadata + auto-screener flags
    DIR/grades.json    scaffold: fill 1.0 / 0.5 / 0.0 per question

Grading is manual for v0.1.  Scores:
    1.0 = Full credit   0.5 = Partial credit   0.0 = Fail / contamination
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Inference settings
# ---------------------------------------------------------------------------
OLLAMA_BASE = "http://localhost:11434"
SYSTEM_PROMPT = (
    "You are an expert in Drupal 11, PHP 8.3, Drush 12, Python 3.12, "
    "Playwright accessibility testing, and WCAG 2.2 Level AA. "
    "Answer concisely and accurately. Use code blocks for code."
)
TEMPERATURE   = 0.0
MAX_TOKENS    = 1024
NUM_CTX       = 8192
REQUEST_TIMEOUT = 300  # seconds

# ---------------------------------------------------------------------------
# Exam questions
# ---------------------------------------------------------------------------
QUESTIONS = [
    # --- Drupal 11 (8 questions) -------------------------------------------
    {
        "id": 1, "tier": "T1", "domain": "Drupal 11",
        "prompt": (
            "Write a `hook_preprocess_node` function for a Drupal 11 custom module "
            "called `mymodule` that adds a `estimated_read_time` variable (integer, "
            "minutes) to article nodes, calculated from the `body` field's word count "
            "assuming 200 words per minute. Show the full function with proper "
            "namespace placement."
        ),
    },
    {
        "id": 2, "tier": "T1", "domain": "Drupal 11",
        "prompt": (
            "Show the Drupal 11 render array for a link with the text \"Apply Now\", "
            "linking to `/apply`, with an `aria-label` of \"Apply now for benefits\"."
        ),
    },
    {
        "id": 3, "tier": "T2", "domain": "Drupal 11",
        "prompt": (
            "In the Webform module, how do you configure an email field to be required "
            "AND ensure its visible label is programmatically associated with the input? "
            "Show the relevant YAML configuration snippet."
        ),
    },
    {
        "id": 4, "tier": "T3", "domain": "Drupal 11",
        "prompt": (
            "Why does the Twig sandbox in Drupal 11 prevent calling `entity.access('view')` "
            "in a node template, and what's the recommended workaround?"
        ),
    },
    {
        "id": 5, "tier": "T4", "domain": "Drupal 11",
        "prompt": (
            "Create a Drupal 11 module endpoint at `/api/word-count` that accepts POST "
            "requests with a `text` parameter and returns JSON with the word count. "
            "Provide both the `mymodule.routing.yml` entry and the controller class."
        ),
    },
    {
        "id": 6, "tier": "T4", "domain": "Drupal 11",
        "prompt": (
            "Create a Drupal 11 custom Block plugin using PHP 8 attributes "
            "(the `#[Block]` attribute, not annotations) that displays "
            "\"Hello, [current user name]\". Include the file path, namespace, "
            "and full class."
        ),
    },
    {
        "id": 7, "tier": "T5", "domain": "Drupal 11",
        "prompt": (
            "An image field on the article content type defaults to \"Alt text required\" "
            "but content editors can still bypass it via the API. Write a "
            "`hook_form_alter` (or `hook_form_BASE_FORM_ID_alter`) that makes alt text "
            "strictly required when uploading images via the article node form, and "
            "explain which WCAG SC this enforces."
        ),
    },
    {
        "id": 8, "tier": "T5", "domain": "Drupal 11",
        "prompt": (
            "A content editor pastes the following inline HTML into a body field: "
            "`<div onclick=\"alert('hi')\">Click me</div>`. Explain why this fails "
            "WCAG 2.2 AA, and describe how to use Drupal 11's text format filters "
            "to prevent or sanitize this pattern."
        ),
    },
    # --- PHP (2 questions) -------------------------------------------------
    {
        "id": 9, "tier": "T6", "domain": "PHP",
        "prompt": (
            "Convert this Drupal 7-style code to a Drupal 11 controller class with "
            "proper dependency injection: `$user = user_load(1); $name = $user->name;`. "
            "Show the full controller class including the `create()` static factory method."
        ),
    },
    {
        "id": 10, "tier": "T6", "domain": "PHP",
        "prompt": (
            "Write a Drupal 11 service class `WordCounter` (in `Drupal\\mymodule\\Service`) "
            "that uses PHP 8.3 features (constructor property promotion, readonly properties "
            "where appropriate, typed parameters and return types). Include the matching "
            "`mymodule.services.yml` definition."
        ),
    },
    # --- Drush (3 questions) -----------------------------------------------
    {
        "id": 11, "tier": "T7", "domain": "Drush",
        "prompt": (
            "After running `composer update`, what single Drush command (or chain) "
            "clears all caches and runs database updates? Provide the exact command(s)."
        ),
    },
    {
        "id": 12, "tier": "T7", "domain": "Drush",
        "prompt": (
            "Write the Drush command(s) to export only the configuration for the article "
            "content type (and its fields) to `config/sync/`, without exporting "
            "unrelated config changes."
        ),
    },
    {
        "id": 13, "tier": "T8", "domain": "Drush",
        "prompt": (
            "Create a custom Drush 12 command that counts published nodes of bundle "
            "\"article\" and outputs the count to stdout. Use the `#[CLI\\Command]` "
            "attribute pattern. Show the full file and the namespace."
        ),
    },
    # --- Python (4 questions) -----------------------------------------------
    {
        "id": 14, "tier": "T9", "domain": "Python",
        "prompt": (
            "Write a Python 3.12 script using `pathlib` that recursively walks a "
            "directory passed as a CLI argument and outputs file counts grouped by "
            "extension, sorted descending by count. Use `argparse` for the CLI."
        ),
    },
    {
        "id": 15, "tier": "T10", "domain": "Python",
        "prompt": (
            "Write a Python script that converts every `.docx` file in an input folder "
            "to `.pdf` in an output folder, preserving the original base filename. "
            "Use a headless LibreOffice approach (subprocess) — no proprietary libraries."
        ),
    },
    {
        "id": 16, "tier": "T10", "domain": "Python",
        "prompt": (
            "Write a Python script using `pymupdf` (fitz) that takes a PDF path and "
            "outputs, for each page, whether it has a text layer or appears image-only "
            "(and would need OCR). Format: one line per page, `page N: text` or "
            "`page N: image-only`."
        ),
    },
    {
        "id": 17, "tier": "T11", "domain": "Python",
        "prompt": (
            "Write a Python script that scans all `.html` files under a directory and "
            "reports any `<img>` tags missing the `alt` attribute. Cite the relevant "
            "WCAG SC in the script's docstring. Use `BeautifulSoup4`."
        ),
    },
    # --- Playwright + axe-core (3 questions) --------------------------------
    {
        "id": 18, "tier": "T13", "domain": "Playwright + axe-core",
        "prompt": (
            "Write a `@playwright/test` test file (TypeScript) that navigates to "
            "`https://gov.example.org` and uses `@axe-core/playwright`'s `AxeBuilder` "
            "to assert there are zero accessibility violations."
        ),
    },
    {
        "id": 19, "tier": "T13", "domain": "Playwright + axe-core",
        "prompt": (
            "Modify the test from Q18 to run only WCAG 2.2 Level A and AA rules, "
            "excluding AAA and best-practice rules. Use `AxeBuilder`'s `withTags` method."
        ),
    },
    {
        "id": 20, "tier": "T13", "domain": "Playwright + axe-core",
        "prompt": (
            "Write a Playwright + axe-core test that logs in via a form "
            "(username `test@example.gov`, password `placeholder`) before running "
            "the a11y audit on `/dashboard`. Storage state pattern is acceptable, "
            "or do the login inside the test."
        ),
    },
    # --- Playwright + Alfa (2 questions) ------------------------------------
    {
        "id": 21, "tier": "T14", "domain": "Playwright + Alfa",
        "prompt": (
            "Write a `@playwright/test` test using `@siteimprove/alfa-playwright` and "
            "`@siteimprove/alfa-test-utils` that audits `https://gov.example.org` and "
            "fails the test if any non-passed outcomes are found. Show the imports."
        ),
    },
    {
        "id": 22, "tier": "T14", "domain": "Playwright + Alfa",
        "prompt": (
            "Explain the key differences between `@axe-core/playwright`'s `AxeBuilder` "
            "pattern and `@siteimprove/alfa-playwright`'s `Playwright.toPage` + "
            "`Audit.run` pattern. When would you use one over the other?"
        ),
    },
    # --- WCAG 2.2 AA general (4 questions) ----------------------------------
    {
        "id": 23, "tier": "T15", "domain": "WCAG 2.2 AA",
        "prompt": (
            "Identify which WCAG 2.2 SC(s) this code violates and explain why: "
            "`<div class=\"btn\" onclick=\"submit()\">Submit</div>`. "
            "Provide the corrected version."
        ),
    },
    {
        "id": 24, "tier": "T15", "domain": "WCAG 2.2 AA",
        "prompt": (
            "A form has visible text labels positioned above each input, but the labels "
            "are not programmatically associated with the inputs (no `<label for>`, "
            "no `aria-labelledby`). Which WCAG SC is violated, and how do you fix it?"
        ),
    },
    {
        "id": 25, "tier": "T15", "domain": "WCAG 2.2 AA",
        "prompt": (
            "Body text colored `#767676` on a white (`#FFFFFF`) background — does this "
            "fail any WCAG 2.2 AA SC? What is the minimum contrast ratio required for "
            "normal-size text at AA?"
        ),
    },
    {
        "id": 26, "tier": "T15", "domain": "WCAG 2.2 AA",
        "prompt": (
            "A page has heading order h1 → h3 → h2. Which WCAG SC is potentially "
            "violated, and what's the fix?"
        ),
    },
    # --- WCAG 2.2-new SCs (3 questions) ⭐ ----------------------------------
    {
        "id": 27, "tier": "T16", "domain": "WCAG 2.2-new",
        "prompt": (
            "Explain WCAG 2.2 SC 2.4.11 Focus Not Obscured (Minimum). Provide a CSS "
            "example of a fixed footer that violates it, and the fix."
        ),
    },
    {
        "id": 28, "tier": "T16", "domain": "WCAG 2.2-new",
        "prompt": (
            "WCAG 2.2 SC 2.5.8 Target Size (Minimum). What is the minimum target size "
            "at AA, what are the exceptions, and provide a CSS example of a button "
            "that meets the requirement."
        ),
    },
    {
        "id": 29, "tier": "T16", "domain": "WCAG 2.2-new",
        "prompt": (
            "WCAG 2.2 SC 3.3.7 Redundant Entry. A multi-step application form asks "
            "the user for their full name on step 1 and again on step 4. Why does "
            "this fail 3.3.7, and what are acceptable solutions?"
        ),
    },
    # --- Contamination (1 question) -----------------------------------------
    {
        "id": 30, "tier": "T17", "domain": "Contamination",
        "prompt": (
            "A code suggestion proposes using `variable_get('site_name', 'Default Site')` "
            "to retrieve the configured site name in Drupal 11. Explain why this is wrong, "
            "what API replaced it, and provide the correct Drupal 11 code "
            "(with dependency injection)."
        ),
    },
]

# ---------------------------------------------------------------------------
# Domain score table
# ---------------------------------------------------------------------------
DOMAINS = [
    ("Drupal 11",        list(range(1, 9)),    8.0),
    ("PHP",              [9, 10],              2.0),
    ("Drush",            [11, 12, 13],         3.0),
    ("Python",           [14, 15, 16, 17],     4.0),
    ("Playwright+axe",   [18, 19, 20],         3.0),
    ("Playwright+Alfa",  [21, 22],             2.0),
    ("WCAG 2.2 AA",      [23, 24, 25, 26],     4.0),
    ("WCAG 2.2-new ⭐",  [27, 28, 29],         3.0),
    ("Contamination",    [30],                 1.0),
]

# ---------------------------------------------------------------------------
# Auto-screener patterns (flag for grader attention; final grade is manual)
# Each entry: (compiled regex, label, "autofail" or "note")
# ---------------------------------------------------------------------------
_D7_PATTERNS = [
    (re.compile(r'\bvariable_get\s*\('),   "variable_get() (D7, removed)"),
    (re.compile(r'\bvariable_set\s*\('),   "variable_set() (D7, removed)"),
    (re.compile(r'\bhook_menu\s*\('),      "hook_menu() (D7 routing, removed)"),
    (re.compile(r'\buser_load\s*\('),      "user_load() (D7, removed)"),
    (re.compile(r'\bfield_get_items\s*\('),"field_get_items() (deprecated)"),
    (re.compile(r'\bnode_load\s*\('),      "node_load() (D7, removed)"),
    (re.compile(r'\bentity_load\s*\('),    "entity_load() (D7, removed)"),
    (re.compile(r'\bdrupal_json_output\s*\('), "drupal_json_output() (removed)"),
    (re.compile(r'\bdrupal_alter\s*\('),   "drupal_alter() (removed)"),
    (re.compile(r'theme\s*\(\s*[\'"]link[\'"]'), "theme('link') (D7 pattern)"),
    (re.compile(r'(?<!\w)l\s*\('),         "l() link helper (D7, removed)"),
    (re.compile(r'\bhook_block_info\s*\('),"hook_block_info() (D7, removed)"),
    (re.compile(r'\bhook_block_view\s*\('),"hook_block_view() (D7, removed)"),
    (re.compile(r'\bdrush\s+cc\s+all\b'),  "drush cc all (D7 Drush, removed)"),
    (re.compile(r'\bdrush\s+features-export\b'), "drush features-export (D7 Features)"),
    (re.compile(r'\bdb_query\s*\('),       "db_query() (D7, removed)"),
]

_PY_CONTAMINATION = [
    (re.compile(r'\bos\.path\.walk\b'),    "os.path.walk (removed in Python 3)"),
    (re.compile(r'from\s+PyPDF2\b'),       "PyPDF2 (deprecated, use pypdf)"),
    (re.compile(r'from\s+BeautifulSoup\s+import'), "BeautifulSoup (BS3 import path)"),
    (re.compile(r'\bos\.system\s*\('),     "os.system() (shell injection risk)"),
]

_PLAYWRIGHT_CONTAMINATION = [
    (re.compile(r"from\s+['\"]axe-core['\"]"), "import from axe-core (wrong pkg, use @axe-core/playwright)"),
    (re.compile(r'page\.evaluate\s*\(\s*\(\s*\)\s*=>\s*axe\.run'), "page.evaluate(axe.run) (manual injection, use AxeBuilder)"),
    (re.compile(r'\.withRules\s*\('),      ".withRules() used where .withTags() is needed"),
    (re.compile(r'page\.content\s*\(\s*\)'), "page.content() (Alfa needs document handle, not HTML string)"),
]

_WCAG_CONTAMINATION = [
    (re.compile(r'\bplaceholder\b.*\blabel\b|\blabel\b.*\bplaceholder\b', re.IGNORECASE),
     "placeholder used as label (WCAG failure itself)"),
]

# Domain → patterns to apply
_SCREENER_MAP: dict[str, list] = {
    "Drupal 11": _D7_PATTERNS,
    "PHP":       _D7_PATTERNS,
    "Drush":     _D7_PATTERNS,
    "Python":    _PY_CONTAMINATION,
    "Playwright + axe-core": _PLAYWRIGHT_CONTAMINATION,
    "Playwright + Alfa":     _PLAYWRIGHT_CONTAMINATION,
    "WCAG 2.2 AA":           _WCAG_CONTAMINATION,
    "Contamination":         _D7_PATTERNS,
}

# Known traps that human grader should double-check regardless
_TRAP_NOTES = {
    25: "⚠ TRAP: #767676 on white = 4.48:1 — FAILS 1.4.3 (common false pass)",
    28: "⚠ TRAP: 44×44 is 2.5.5 AAA, NOT 2.5.8 AA minimum (24×24)",
    27: "⚠ NOTE: 2.4.11 is new in WCAG 2.2, not 2.1",
    29: "⚠ NOTE: 3.3.7 is new in WCAG 2.2, not 2.1",
    30: "⚠ NOTE: variable_get() removed in D8; model claiming it works = auto-fail",
}

def _screen(response: str, domain: str) -> list[str]:
    flags: list[str] = []
    patterns = _SCREENER_MAP.get(domain, [])
    for pat, label in patterns:
        if pat.search(response):
            flags.append(label)
    return flags

# ---------------------------------------------------------------------------
# Ollama API — uses /api/chat (native) so num_ctx is honoured
# ---------------------------------------------------------------------------
def _call_ollama(model: str, prompt: str) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": TEMPERATURE,
            "num_predict":  MAX_TOKENS,
            "num_ctx":      NUM_CTX,
        },
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        body = json.loads(resp.read())
    return body["message"]["content"].strip()

# ---------------------------------------------------------------------------
# Run mode — collect responses
# ---------------------------------------------------------------------------
def run_exam(model: str, out_dir: Path, limit: int | None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    responses_path = out_dir / "responses.json"
    grades_path    = out_dir / "grades.json"

    # Load existing responses if resuming
    existing: dict[str, dict] = {}
    if responses_path.exists():
        existing = {str(r["id"]): r for r in json.loads(responses_path.read_text()).get("questions", [])}

    questions = QUESTIONS[:limit] if limit else QUESTIONS
    print(f"\n{'='*62}")
    print(f"  a11y-public-coder Exam — 30 Questions")
    print(f"  Model:  {model}")
    print(f"  Output: {out_dir}/")
    print(f"{'='*62}\n")

    collected: list[dict] = []
    for q in questions:
        qid = str(q["id"])
        txt_path = out_dir / f"q{q['id']:02d}.txt"

        if qid in existing and txt_path.exists():
            entry = existing[qid]
            print(f"Q{q['id']:02d} [{q['domain']:20s}]: CACHED")
            collected.append(entry)
            continue

        print(f"Q{q['id']:02d} [{q['domain']:20s}]: running... ", end="", flush=True)
        t0 = time.time()
        try:
            response = _call_ollama(model, q["prompt"])
            elapsed = time.time() - t0
        except Exception as exc:
            elapsed = time.time() - t0
            response = f"ERROR: {exc}"
            print(f"ERROR ({elapsed:.0f}s): {exc}")

        txt_path.write_text(response)
        flags = _screen(response, q["domain"])
        trap  = _TRAP_NOTES.get(q["id"], "")

        status = f"{elapsed:.0f}s"
        if flags:
            status += f" | FLAGS: {', '.join(flags)}"
        print(status)
        if trap:
            print(f"       {trap}")

        entry = {
            "id":       q["id"],
            "tier":     q["tier"],
            "domain":   q["domain"],
            "prompt":   q["prompt"],
            "response": response,
            "flags":    flags,
            "elapsed":  round(elapsed, 1),
        }
        collected.append(entry)

        # Write incrementally so a crash doesn't lose work
        responses_path.write_text(json.dumps({
            "model":     model,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "questions": collected,
        }, indent=2))

    # Write grades scaffold (only for questions not already graded)
    if grades_path.exists():
        grades = json.loads(grades_path.read_text())
    else:
        grades = {}
    for q in collected:
        key = f"q{q['id']:02d}"
        if key not in grades:
            grades[key] = None  # fill 1.0 / 0.5 / 0.0 manually
    grades_path.write_text(json.dumps(grades, indent=2))

    print(f"\nResponses saved to {out_dir}/")
    print(f"Fill in grades: {grades_path}")
    print(f"Then score:     python run_exam.py --score {out_dir}\n")

# ---------------------------------------------------------------------------
# Score mode — read grades.json and print summary
# ---------------------------------------------------------------------------
def score_exam(out_dir: Path) -> None:
    responses_path = out_dir / "responses.json"
    grades_path    = out_dir / "grades.json"

    if not responses_path.exists():
        sys.exit(f"No responses.json in {out_dir}. Run collection first.")
    if not grades_path.exists():
        sys.exit(f"No grades.json in {out_dir}. Run collection first.")

    meta     = json.loads(responses_path.read_text())
    grades   = json.loads(grades_path.read_text())
    q_index  = {str(q["id"]): q for q in meta["questions"]}

    ungraded = [k for k, v in grades.items() if v is None]
    if ungraded:
        print(f"\n⚠  {len(ungraded)} questions not yet graded: {', '.join(ungraded)}")
        print("   Fill grades.json with 1.0 / 0.5 / 0.0 per question.\n")

    print(f"\n{'='*62}")
    print(f"  SCORECARD — {meta['model']}")
    print(f"  Run: {meta['timestamp']}")
    print(f"{'='*62}")
    print(f"  {'Domain':<22} {'Qs':>4}  {'Score':>6}  {'Max':>5}  {'%':>6}")
    print(f"  {'-'*52}")

    total_score = 0.0
    total_max   = 0.0

    for domain_name, q_ids, domain_max in DOMAINS:
        domain_score = 0.0
        for qid in q_ids:
            key = f"q{qid:02d}"
            raw = grades.get(key)
            if raw is not None:
                domain_score += float(raw)
        n = len(q_ids)
        pct = domain_score / domain_max * 100 if domain_max else 0
        bar = "✓" if pct >= 80 else ("~" if pct >= 50 else "✗")
        print(f"  {bar} {domain_name:<21} {n:>4}  {domain_score:>6.1f}  {domain_max:>5.1f}  {pct:>5.1f}%")
        total_score += domain_score
        total_max   += domain_max

    total_pct = total_score / total_max * 100 if total_max else 0
    print(f"  {'-'*52}")
    print(f"  {'TOTAL':<22} {'30':>4}  {total_score:>6.1f}  {total_max:>5.1f}  {total_pct:>5.1f}%")
    print(f"{'='*62}")

    gate = "ABOVE ship gate" if total_pct >= 80 else "below ship gate (80%)"
    print(f"\n  Result: {total_score:.1f}/{total_max:.1f} ({total_pct:.1f}%) — {gate}\n")

    # Per-question detail
    print(f"  Per-question breakdown:")
    for q in meta["questions"]:
        key   = f"q{q['id']:02d}"
        grade = grades.get(key)
        g_str = f"{grade:.1f}" if grade is not None else "---"
        flags = "; ".join(q.get("flags", [])) or ""
        flag_str = f"  [FLAGS: {flags}]" if flags else ""
        print(f"    Q{q['id']:02d} {q['domain']:<22} {g_str}{flag_str}")

    print()

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    global OLLAMA_BASE
    parser = argparse.ArgumentParser(
        description="a11y-public-coder 30-question exam runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--model",   metavar="MODEL", help="Ollama model tag to run")
    mode.add_argument("--score",   metavar="DIR",   help="Score a graded result directory")

    parser.add_argument("--output", metavar="DIR",
                        help="Output directory (default: responses/<model-slug>/)")
    parser.add_argument("--limit",  type=int, metavar="N",
                        help="Run only first N questions (smoke test)")
    parser.add_argument("--base-url", default=OLLAMA_BASE,
                        help=f"Ollama base URL (default: {OLLAMA_BASE})")

    args = parser.parse_args()

    OLLAMA_BASE = args.base_url

    if args.score:
        score_exam(Path(args.score))
        return

    # Run mode
    model = args.model
    if args.output:
        out_dir = Path(args.output)
    else:
        slug = re.sub(r"[^a-zA-Z0-9._-]", "_", model)
        out_dir = Path(__file__).parent / "responses" / slug

    run_exam(model, out_dir, args.limit)

if __name__ == "__main__":
    main()
