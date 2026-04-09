"""
interview_engine.py  –  Groq API edition
Generates AI-powered interview questions and evaluates answers.
Falls back to a static question bank if Groq is unavailable.
Model: llama3-8b-8192
"""

import os
import json
from dotenv import load_dotenv

# Load .env from the same directory as this file (works regardless of cwd)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BASE_DIR, ".env"), override=True)

_client = None

def _get_client():
    """Return Groq client, or None if key not set (silent fallback)."""
    global _client
    if _client is not None:
        return _client
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    if not GROQ_API_KEY:
        return None
    try:
        from groq import Groq
        _client = Groq(api_key=GROQ_API_KEY)
        return _client
    except Exception as e:
        print(f"⚠️  Groq init failed: {e}")
        return None


def _call_groq(prompt, temperature=0.4):
    """Call Groq LLaMA and return text. Returns None on failure."""
    client = _get_client()
    if not client:
        return None
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user",   "content": prompt}
            ],
            temperature=temperature,
            max_tokens=1024,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️  Groq call failed: {e}")
        return None


def _parse_json(raw):
    """Strip markdown fences and parse JSON safely."""
    if not raw:
        return None
    if raw.startswith("```"):
        parts = raw.split("```")
        raw   = parts[1] if len(parts) > 1 else raw
        if raw.lower().startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw.strip())
    except Exception:
        return None


# ── Static fallback question bank ────────────────────────────────────────────
QUESTION_BANK = {
    "python": [
        "What is Python and what are its key features?",
        "Explain the difference between list, tuple, and set in Python.",
        "What is a dictionary in Python and when would you use it?",
        "Explain OOP concepts in Python with examples.",
        "What are decorators in Python and how do they work?",
    ],
    "flask": [
        "What is Flask and how does it differ from Django?",
        "Explain routing in Flask with an example.",
        "What is Jinja2 and how is it used in Flask?",
        "How do you handle forms and POST requests in Flask?",
        "What is Flask's application context and request context?",
    ],
    "django": [
        "What is Django and what is its MTV architecture?",
        "Explain Django ORM and how to write a query.",
        "What are Django migrations and why are they needed?",
        "Difference between ForeignKey and ManyToManyField.",
        "How does Django handle user authentication?",
    ],
    "sql": [
        "What is SQL and what are its main types of commands?",
        "Explain the different types of JOINs in SQL.",
        "What is the difference between WHERE and HAVING clauses?",
        "What is database normalization and why is it important?",
        "What is an index in a database and when should you use it?",
    ],
    "mysql": [
        "What is MySQL and how is it different from other databases?",
        "Explain ACID properties in MySQL.",
        "What are stored procedures in MySQL?",
        "How do you optimize a slow MySQL query?",
        "What is the difference between MyISAM and InnoDB engines?",
    ],
    "javascript": [
        "What is JavaScript and where is it used?",
        "Explain the difference between var, let, and const.",
        "What is a closure in JavaScript?",
        "Explain async/await and how it handles asynchronous code.",
        "What is the difference between == and === in JavaScript?",
    ],
    "react": [
        "What is React and what problem does it solve?",
        "Explain the virtual DOM and how React uses it.",
        "What are React hooks and give examples of commonly used ones.",
        "What is the difference between state and props in React?",
        "How does useEffect work and when would you use it?",
    ],
    "html": [
        "What is the difference between div and span elements?",
        "Explain semantic HTML and give examples of semantic tags.",
        "What are HTML5 new features compared to HTML4?",
        "What is the purpose of the DOCTYPE declaration?",
        "How do forms work in HTML?",
    ],
    "css": [
        "Explain the CSS box model.",
        "What is the difference between Flexbox and Grid?",
        "What is CSS specificity and how is it calculated?",
        "What are media queries and how do you use them?",
        "Explain CSS position: relative, absolute, fixed, sticky.",
    ],
    "java": [
        "What are the main principles of OOP in Java?",
        "What is the difference between an interface and an abstract class?",
        "Explain Java's garbage collection mechanism.",
        "What is the difference between ArrayList and LinkedList?",
        "What are Java generics and why are they useful?",
    ],
    "machine learning": [
        "What is the difference between supervised and unsupervised learning?",
        "Explain overfitting and how to prevent it.",
        "What is a confusion matrix and what metrics can you derive from it?",
        "Explain the bias-variance tradeoff.",
        "What is cross-validation and why is it used?",
    ],
    "ai": [
        "What is the difference between AI, ML, and deep learning?",
        "Explain neural networks and how they learn.",
        "What is transfer learning?",
        "What are the common challenges in building AI systems?",
        "What is natural language processing and what are its applications?",
    ],
    "node": [
        "What is Node.js and what makes it different from browser JavaScript?",
        "Explain the event loop in Node.js.",
        "What is npm and how do you use it?",
        "What is Express.js and how does it work with Node.js?",
        "How does Node.js handle asynchronous operations?",
    ],
    "git": [
        "What is the difference between git merge and git rebase?",
        "Explain the git branching strategy you follow.",
        "What is a pull request and how does the code review process work?",
        "How do you resolve merge conflicts in git?",
        "What is the difference between git fetch and git pull?",
    ],
    "docker": [
        "What is Docker and what problems does it solve?",
        "Explain the difference between a Docker image and a container.",
        "What is Docker Compose and when would you use it?",
        "How do you create a Dockerfile?",
        "What is the difference between CMD and ENTRYPOINT in Docker?",
    ],
    "aws": [
        "What are the core AWS services you have used?",
        "Explain the difference between EC2 and Lambda.",
        "What is S3 and what are common use cases for it?",
        "What is IAM in AWS and why is it important?",
        "Explain the difference between vertical and horizontal scaling in AWS.",
    ],
}

DEFAULT_QUESTIONS = [
    "Tell me about yourself and your technical background.",
    "What are your strongest technical skills and how have you applied them?",
    "Describe a challenging project you worked on and how you solved the problems.",
    "How do you approach debugging a difficult issue in your code?",
    "Where do you see yourself in 5 years technically?",
]


# ─────────────────────────────────────────────────────────────────────────────

def generate_questions(skills, max_questions=5):
    """
    Generate interview questions using Groq LLaMA.
    Falls back to static question bank if API unavailable.
    """
    # ── Groq AI path ──────────────────────────────────────────────────────────
    client = _get_client()
    if client:
        skills_str = ", ".join(skills) if skills else "general programming"
        prompt = f"""You are a senior technical interviewer conducting a job interview.

Generate exactly {max_questions} interview questions for a candidate whose skills include: {skills_str}

Requirements:
- Questions must directly test knowledge of the listed skills
- Mix conceptual questions (theory) with practical ones (how you'd use it)
- Make questions specific and meaningful, not generic
- Each question must be on its own line
- Do NOT number them, do NOT add bullets or dashes
- Do NOT add any intro text or explanation

Output only the {max_questions} questions, one per line."""

        raw = _call_groq(prompt, temperature=0.5)
        if raw:
            lines     = raw.strip().split("\n")
            questions = [
                line.strip().lstrip("0123456789.-•) ").strip()
                for line in lines if line.strip()
            ]
            questions = [q for q in questions if len(q) > 15 and "?" in q or len(q) > 20]
            questions = questions[:max_questions]
            if len(questions) >= 3:
                return questions

    # ── Static fallback ───────────────────────────────────────────────────────
    questions = []
    for skill in skills:
        skill_lower = skill.lower().strip()
        if skill_lower in QUESTION_BANK:
            questions.extend(QUESTION_BANK[skill_lower])
        else:
            # partial match
            for key in QUESTION_BANK:
                if key in skill_lower or skill_lower in key:
                    questions.extend(QUESTION_BANK[key])
                    break

    unique = list(dict.fromkeys(questions))
    return unique[:max_questions] if unique else DEFAULT_QUESTIONS[:max_questions]


def evaluate_answers(questions, answers):
    """
    Evaluate interview answers using Groq LLaMA.
    Returns: (score: int, weak_areas: list, readiness: str)
    Falls back to keyword scoring if API unavailable.
    """
    # ── Groq AI path ──────────────────────────────────────────────────────────
    client = _get_client()
    if client and questions and answers:
        qa_pairs = "\n\n".join(
            f"Q{i+1}: {q}\nA{i+1}: {a if a.strip() else '(no answer given)'}"
            for i, (q, a) in enumerate(zip(questions, answers))
        )
        prompt = f"""You are a senior technical interviewer evaluating a candidate's mock interview.

Below are the questions asked and the candidate's answers:

{qa_pairs}

Evaluate the candidate and respond with STRICT JSON only.
No markdown, no explanation, no extra text — just the JSON object:

{{
  "overall_score": 72,
  "weak_areas": ["database optimization", "async programming"],
  "readiness": "Ready"
}}

Rules:
- overall_score: integer from 0 to 100 based on accuracy, depth, and completeness of answers
- weak_areas: list of specific topic strings where the candidate answered poorly or incompletely. Empty list [] if all answers were good.
- readiness: exactly the string "Ready" if overall_score >= 60, otherwise exactly "Needs Improvement"
"""
        raw    = _call_groq(prompt, temperature=0.2)
        result = _parse_json(raw)
        if result and "overall_score" in result:
            score      = max(0, min(100, int(result.get("overall_score", 50))))
            weak_areas = result.get("weak_areas", [])
            readiness  = result.get("readiness", "Needs Improvement")
            if not isinstance(weak_areas, list):
                weak_areas = []
            return score, weak_areas, readiness

    # ── Keyword-based fallback ────────────────────────────────────────────────
    total_score = 0
    weak_areas  = []
    ignore      = {"what", "is", "the", "explain", "difference", "between", "and",
                   "a", "an", "how", "why", "when", "in", "of", "to", "you"}

    for q, a in zip(questions, answers):
        keywords  = [w.rstrip("?.") for w in q.lower().split() if w not in ignore and len(w) > 2]
        a_lower   = a.lower()
        relevance = sum(1 for kw in keywords if kw in a_lower)
        length    = len(a.strip())

        q_score = 0
        if relevance >= 3:   q_score += 15
        elif relevance >= 2: q_score += 10
        elif relevance == 1: q_score += 5

        if length >= 80:     q_score += 10
        elif length >= 40:   q_score += 7
        elif length >= 20:   q_score += 3

        if q_score < 10:
            # extract topic from question for weak_area label
            topic = " ".join(kw for kw in keywords[:3] if len(kw) > 3)
            if topic:
                weak_areas.append(topic)

        total_score += q_score

    max_score   = len(questions) * 25 if questions else 1
    final_score = min(100, int((total_score / max_score) * 100))
    readiness   = "Ready" if final_score >= 60 else "Needs Improvement"

    return final_score, weak_areas[:5], readiness
