"""
generate_questions.py
Generates medium & hard questions for tech_mcq.json, tech_coding.json,
and aptitude_questions.json using Groq API, then saves them in-place.

Usage:
    python generate_questions.py
"""

import os, json, re, sys
from groq import Groq

# ── Load .env manually (no dotenv needed) ──────────────────────
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.getenv("GROQ_API_KEY", "")
if not API_KEY or API_KEY == "your_groq_api_key_here":
    print("❌  GROQ_API_KEY not set in your .env file.")
    print("    Get a free key at https://console.groq.com/keys")
    sys.exit(1)

client = Groq(api_key=API_KEY)
MODEL  = "llama-3.3-70b-versatile"

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# ── Helper: call Groq and parse JSON from response ─────────────
def ask_groq(prompt: str) -> list:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=4096,
    )
    raw = resp.choices[0].message.content.strip()
    # Extract JSON array from response
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON array found in response:\n{raw[:300]}")
    return json.loads(match.group())


# ══════════════════════════════════════════════════════════════
#  1. TECH MCQ  (medium & hard, 5 questions each)
# ══════════════════════════════════════════════════════════════
def generate_tech_mcq():
    path = os.path.join(DATA_DIR, "tech_mcq.json")
    with open(path) as f:
        data = json.load(f)

    for level, start_id, difficulty_desc in [
        ("medium", 101, "intermediate Python/web-dev topics like decorators, OOP, REST APIs, SQL joins, git"),
        ("hard",   201, "advanced topics like system design, concurrency, database indexing, algorithms, time complexity"),
    ]:
        if level in data:
            print(f"  ⚠️  tech_mcq '{level}' already exists — skipping")
            continue

        print(f"  🤖 Generating tech MCQ [{level}] ...")
        prompt = f"""Generate exactly 5 multiple-choice questions on {difficulty_desc} for a software engineering recruitment test.

Return ONLY a valid JSON array with this exact structure, no extra text:
[
  {{
    "id": {start_id},
    "question": "Question text here?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": "Option A"
  }}
]
IDs should be {start_id} through {start_id+4}.
The "answer" must exactly match one of the "options".
"""
        questions = ask_groq(prompt)
        # Ensure IDs are correct
        for i, q in enumerate(questions):
            q["id"] = start_id + i
        data[level] = questions
        print(f"  ✅ tech_mcq [{level}]: {len(questions)} questions")

    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  💾 Saved: {path}\n")


# ══════════════════════════════════════════════════════════════
#  2. TECH CODING  (medium & hard, 3 questions each)
# ══════════════════════════════════════════════════════════════
def generate_tech_coding():
    path = os.path.join(DATA_DIR, "tech_coding.json")
    with open(path) as f:
        data = json.load(f)

    for level, start_id, difficulty_desc in [
        ("medium", 101, "string manipulation, array operations, basic sorting/searching algorithms"),
        ("hard",   201, "dynamic programming, graph traversal, recursion, binary search, advanced data structures"),
    ]:
        if level in data:
            print(f"  ⚠️  tech_coding '{level}' already exists — skipping")
            continue

        print(f"  🤖 Generating tech coding [{level}] ...")
        prompt = f"""Generate exactly 3 coding problems about {difficulty_desc} for a software engineering recruitment test.

Each problem must have a Python function named `solution(n)` that accepts a single argument.

Return ONLY a valid JSON array with this exact structure, no extra text:
[
  {{
    "id": {start_id},
    "question": "Write a function `solution(n)` that ... (clear description)",
    "sample_input": 5,
    "expected_output": 25
  }}
]
IDs should be {start_id} through {start_id+2}.
sample_input must be a simple value (int, string, or list) that can be passed directly to solution().
expected_output must be the correct return value for that sample_input.
"""
        questions = ask_groq(prompt)
        for i, q in enumerate(questions):
            q["id"] = start_id + i
        data[level] = questions
        print(f"  ✅ tech_coding [{level}]: {len(questions)} questions")

    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  💾 Saved: {path}\n")


# ══════════════════════════════════════════════════════════════
#  3. APTITUDE  (medium & hard, 10 questions each)
# ══════════════════════════════════════════════════════════════
def generate_aptitude():
    path = os.path.join(DATA_DIR, "aptitude_questions.json")
    with open(path) as f:
        data = json.load(f)

    default = data.setdefault("default", {})

    for level, start_id, difficulty_desc in [
        ("medium", 101, "percentages, ratios, time & work, profit & loss, simple algebra, logical reasoning"),
        ("hard",   201, "advanced quantitative aptitude: permutations, probability, data interpretation, complex logical puzzles, number series"),
    ]:
        if level in default:
            print(f"  ⚠️  aptitude '{level}' already exists — skipping")
            continue

        print(f"  🤖 Generating aptitude [{level}] ...")
        prompt = f"""Generate exactly 10 aptitude questions on {difficulty_desc} for a job recruitment test.

Return ONLY a valid JSON array with this exact structure, no extra text:
[
  {{
    "id": {start_id},
    "question": "Question text here?",
    "options": ["A", "B", "C", "D"],
    "answer": "A"
  }}
]
IDs should be {start_id} through {start_id+9}.
The "answer" must exactly match one of the "options".
Keep options concise (numbers or short phrases).
"""
        questions = ask_groq(prompt)
        for i, q in enumerate(questions):
            q["id"] = start_id + i
        default[level] = questions
        print(f"  ✅ aptitude [{level}]: {len(questions)} questions")

    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  💾 Saved: {path}\n")


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 55)
    print("  AI Question Generator  –  Groq / LLaMA3-70B")
    print("=" * 55)

    print("\n📝 [1/3] Tech MCQ Questions")
    generate_tech_mcq()

    print("💻 [2/3] Tech Coding Questions")
    generate_tech_coding()

    print("🧮 [3/3] Aptitude Questions")
    generate_aptitude()

    print("=" * 55)
    print("✅  All questions generated successfully!")
    print("    Restart Flask (Ctrl+C then python app.py)")
    print("=" * 55)
