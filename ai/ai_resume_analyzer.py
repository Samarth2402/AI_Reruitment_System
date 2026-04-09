"""
ai_resume_analyzer.py  –  Groq API edition
Model: llama-3.1-8b-instant (fast)
Install: pip install groq
"""

import os
import json
from dotenv import load_dotenv

# Load .env from the same directory as this file (works regardless of cwd)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BASE_DIR, ".env"), override=True)

# Lazy client – only created when first used (no crash on import)
_client = None


def _prepare_resume_excerpt(resume_text, max_chars=6000):
    """Create a representative excerpt using head, middle, and tail sections."""
    text = (resume_text or "").replace("\r", " ")
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text

    part = max_chars // 3
    mid_start = max((len(text) // 2) - (part // 2), 0)
    mid_end = mid_start + part
    return "\n\n".join([
        text[:part],
        text[mid_start:mid_end],
        text[-part:],
    ])


def _heuristic_resume_score(resume_text):
    """Rule-based scoring with strong penalties for non-resume documents."""
    import re

    text = (resume_text or "")
    lower = text.lower()
    score = 20

    # Basic length quality
    length = len(text)
    if length >= 1200:
        score += 15
    elif length >= 700:
        score += 10
    elif length >= 350:
        score += 5

    # Section coverage
    section_patterns = {
        "contact": r"(email|phone|mobile|linkedin|github)",
        "summary": r"(summary|profile|objective)",
        "experience": r"(experience|employment|work history)",
        "skills": r"\bskills?\b",
        "education": r"\beducation\b",
        "projects": r"\bprojects?\b",
    }
    section_hits = 0
    for pat in section_patterns.values():
        if re.search(pat, lower):
            section_hits += 1
    score += section_hits * 7

    # Bullet readability
    bullet_count = text.count("\n-") + text.count("\n*") + text.count("•")
    if bullet_count >= 8:
        score += 8
    elif bullet_count >= 4:
        score += 5
    elif bullet_count >= 1:
        score += 2

    # Skills diversity
    tech_keywords = {
        "python", "java", "javascript", "typescript", "react", "node", "flask", "django",
        "sql", "mysql", "postgres", "mongodb", "aws", "azure", "gcp", "docker", "kubernetes",
        "git", "linux", "html", "css", "pandas", "numpy", "tensorflow", "pytorch"
    }
    found = sum(1 for k in tech_keywords if re.search(rf"\b{k}\b", lower))
    if found >= 8:
        score += 12
    elif found >= 5:
        score += 8
    elif found >= 2:
        score += 4

    # Penalize company-profile/brochure style text that is not a personal resume.
    brochure_terms = [
        "our services", "our vision", "our mission", "our clients", "why us",
        "agency", "branding", "headquartered", "founded", "we offer", "we are",
        "creative partner", "social media marketing", "brochure", "bill board",
    ]
    brochure_hits = sum(1 for t in brochure_terms if t in lower)

    # Personal resume indicators.
    personal_indicators = [
        "curriculum vitae", "resume", "work experience", "professional experience",
        "education", "skills", "certification", "github.com/", "linkedin.com/in/",
    ]
    personal_hits = sum(1 for t in personal_indicators if t in lower)

    # Personal pronouns are usually present in candidate summaries.
    first_person_hits = len(re.findall(r"\b(i|my|me)\b", lower))

    looks_like_brochure = brochure_hits >= 3 and personal_hits <= 2 and first_person_hits == 0
    if looks_like_brochure:
        score = min(score, 35)
        score -= 10

    # Missing core resume identity details should lower marks.
    has_email = bool(re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text))
    has_phone = bool(re.search(r"(?:\+?\d[\d\s\-]{7,}\d)", text))
    if not has_email:
        score -= 10
    if not has_phone:
        score -= 8

    score = max(0, min(100, int(score)))
    if score >= 75:
        quality = "good"
    elif score >= 50:
        quality = "medium"
    else:
        quality = "bad"
    return {
        "score": score,
        "quality": quality,
        "looks_like_brochure": looks_like_brochure,
    }

def _get_client():
    global _client
    if _client is not None:
        return _client
    # Read key lazily so it picks up the value AFTER load_dotenv runs
    GROQ_API_KEY = (os.getenv("GROQ_API_KEY", "") or "").strip()
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set.\n"
            "Add  GROQ_API_KEY=your_key  to your .env file.\n"
            "Get your key from: https://console.groq.com/keys"
        )
    from groq import Groq
    _client = Groq(api_key=GROQ_API_KEY)
    return _client


def _call_groq(prompt, model="llama-3.1-8b-instant", temperature=0.2, max_tokens=1024):
    """Helper: call Groq and return raw text response."""
    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a precise assistant that responds only with valid JSON when asked."},
                {"role": "user",   "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[WARN] Groq API call failed: {e}")
        raise


def _parse_json(raw):
    """Robustly extract and parse JSON from any Groq response.
    Handles: markdown fences, leading/trailing text, truncated responses."""
    import re

    # 1. Strip markdown code fences
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = raw.replace("```", "").strip()

    # 2. Try parsing as-is first (happy path)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 3. Extract the first {...} block from the text
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        candidate = match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # 4. Try to fix truncated JSON by closing open brackets
    candidate = raw
    open_braces   = candidate.count("{") - candidate.count("}")
    open_brackets = candidate.count("[") - candidate.count("]")
    if open_braces > 0 or open_brackets > 0:
        candidate += "]" * max(open_brackets, 0)
        candidate += "}" * max(open_braces, 0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # 5. Nothing worked
    raise ValueError(f"Could not parse JSON from Groq response: {raw[:200]}")


def analyze_resume(resume_text):
    """
    Analyze a resume using Groq LLaMA.
    Returns: { "skills": [...], "projects": [...], "experience_level": "..." }
    Falls back to empty values if the API call fails.
    """
    excerpt = _prepare_resume_excerpt(resume_text, max_chars=5000)
    prompt = f"""
You are an AI recruitment assistant.

From the resume text below, extract:
1. Technical skills (programming languages, frameworks, tools)
2. Projects with technologies used
3. Experience level: Beginner (0-1 yr) / Intermediate (2-4 yrs) / Advanced (5+ yrs)

Respond with STRICT JSON only – no markdown, no explanation, no extra text:
{{
  "skills": ["Python", "Flask", "MySQL"],
  "projects": [
    {{
      "title": "Project Name",
      "technologies": ["Python", "Django"]
    }}
  ],
  "experience_level": "Intermediate"
}}

Resume Text:
\"\"\"
{excerpt}
\"\"\"
"""
    try:
        raw    = _call_groq(prompt)
        result = _parse_json(raw)
        return result
    except Exception as e:
        print(f"[WARN] analyze_resume failed: {e}")
        return {"skills": [], "projects": [], "experience_level": "Unknown"}


def check_resume_quality(resume_text):
    """
    Check resume quality and provide detailed feedback.
    Returns: {"quality": "good|medium|bad", "score": 0-100,
              "feedback": {...}, "suggestions": [...]}
    """
    excerpt = _prepare_resume_excerpt(resume_text, max_chars=6000)
    prompt = f"""You are a resume reviewer. Analyze the resume below and return ONLY a JSON object.
No markdown, no explanation, no extra text — just the raw JSON object.

Return exactly this structure:
{{
  "quality": "good",
  "score": 75,
  "feedback": {{
    "contact": "one sentence about contact info",
    "summary": "one sentence about professional summary",
    "experience": "one sentence about work experience",
    "skills": "one sentence about skills section",
    "education": "one sentence about education",
    "projects": "one sentence about projects",
    "format": "one sentence about formatting",
    "keywords": "one sentence about keywords"
  }},
  "suggestions": ["Tip 1", "Tip 2", "Tip 3"]
}}

Rules:
- quality must be exactly one of: "good", "medium", "bad"
- score must be a number between 0 and 100
- feedback values must be short strings (under 60 chars each)
- suggestions must be a list of 2-4 short strings
- Base the score on concrete evidence from the resume text.
- If a section is present, do not claim it is missing.

Resume to analyze:
{excerpt}"""
    heuristic = _heuristic_resume_score(resume_text)
    heuristic_score = heuristic["score"]
    heuristic_quality = heuristic["quality"]
    looks_like_brochure = heuristic["looks_like_brochure"]
    try:
        raw = _call_groq(prompt, temperature=0.1, max_tokens=900)
        print(f"[DEBUG] Raw Groq response (first 300 chars): {raw[:300]}")
        result = _parse_json(raw)
        # Validate required keys exist
        if "quality" not in result:
            result["quality"] = "medium"
        if "score" not in result:
            result["score"] = 50
        if "feedback" not in result or not isinstance(result["feedback"], dict):
            result["feedback"] = {"general": "Analysis complete"}
        if "suggestions" not in result or not isinstance(result["suggestions"], list):
            result["suggestions"] = ["Review your resume for completeness"]

        # Blend AI score with deterministic score so output reflects actual text.
        ai_score = int(result.get("score", 0))
        final_score = int(round((0.6 * ai_score) + (0.4 * heuristic_score)))
        final_score = max(0, min(100, final_score))

        # Hard cap if content appears to be a company profile/brochure.
        if looks_like_brochure:
            final_score = min(final_score, 35)
            result.setdefault("suggestions", [])
            result["suggestions"] = [
                "Uploaded file looks like a company profile, not a personal resume.",
                "Add candidate details: name, role, email, phone, LinkedIn/GitHub.",
                "Include personal experience, projects, education, and achievements."
            ]
            if not isinstance(result.get("feedback"), dict):
                result["feedback"] = {}
            result["feedback"]["format"] = "Document appears brochure-style, not resume-style."

        result["score"] = final_score
        if final_score >= 75:
            result["quality"] = "good"
        elif final_score >= 50:
            result["quality"] = "medium"
        else:
            result["quality"] = "bad"
        return result
    except Exception as e:
        print(f"[WARN] check_resume_quality failed: {e}")
        return {
            "quality": heuristic_quality,
            "score": heuristic_score,
            "feedback": {
                "general": "AI service issue. Showing rule-based analysis.",
                "format": "Use clear sections and bullet points.",
            },
            "suggestions": [
                "Add measurable achievements in experience.",
                "List core skills in a separate section.",
                "Include links for contact and portfolio."
            ]
        }