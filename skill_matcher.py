# skill_matcher.py

SKILL_KEYWORDS = {
    "python": ["python"],
    "flask": ["flask"],
    "django": ["django"],
    "sql": ["sql", "mysql", "postgres"],
    "html": ["html"],
    "css": ["css"],
    "javascript": ["javascript", "js"],
    "machine learning": ["machine learning", "ml"],
    "ai": ["artificial intelligence", "ai"]
}

def extract_skills_from_resume(resume_text):
    resume_text = resume_text.lower()
    found_skills = []

    for skill, keywords in SKILL_KEYWORDS.items():
        for k in keywords:
            if k in resume_text:
                found_skills.append(skill)
                break

    return list(set(found_skills))


def calculate_match_score(resume_text, job_skills):
    resume_skills = extract_skills_from_resume(resume_text)

    if not job_skills:
        return 0, []

    matched = set(resume_skills).intersection(set(job_skills))
    score = int((len(matched) / len(job_skills)) * 100)

    return score, list(matched)