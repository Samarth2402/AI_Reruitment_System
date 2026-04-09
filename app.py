
from flask import (Flask, render_template, request, redirect,
                   session, send_from_directory, jsonify)
import os, random, json, uuid, smtplib, threading, time
from email.mime.text import MIMEText
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# Load .env from the project directory (works regardless of cwd)
from dotenv import load_dotenv
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BASE_DIR, ".env"), override=True)

from db import fetchall, fetchone, execute, get_conn
from resume_parser import extract_text_from_pdf
from interview_engine import generate_questions, evaluate_answers
from skill_matcher import extract_skills_from_resume
from ai_resume_analyzer import analyze_resume, check_resume_quality

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "secret_ai_recruit_2025")

# Fixed admin credentials (separate from users table).
ADMIN_ID = "samarthsolanki1902@gmail.com"
ADMIN_PASSWORD = "Samarth@1902"

RESUME_FOLDER = "resumes"

# ═══════════════════════════════════════════════════════════════
#  AI QUESTION GENERATOR  (Groq / LLaMA)
#  - Generates fresh questions via Groq API
#  - Caches results in-memory for 24 hours per level
#  - HR custom questions from MySQL always override defaults
#  - Hardcoded fallback guarantees questions always show

# ═══════════════════════════════════════════════════════════════
import re as _re
_ai_question_cache = {}   # key: "tech_mcq:easy" → {"questions": [...], "ts": time()}
_CACHE_TTL = 86400        # refresh every 24 hours

# ── Hardcoded fallback — used ONLY when Groq API fails ──────────
_FALLBACK_MCQ = {
    "easy": [
        {"id":"fb_e1","question":"Which keyword defines a function in Python?","options":["func","def","define","function"],"answer":"def"},
        {"id":"fb_e2","question":"Which is a mutable data type in Python?","options":["tuple","string","list","int"],"answer":"list"},
        {"id":"fb_e3","question":"Which SQL command fetches data from a table?","options":["GET","FETCH","SELECT","RETRIEVE"],"answer":"SELECT"},
        {"id":"fb_e4","question":"What does HTML stand for?","options":["Hyper Text Markup Language","High Text Machine Language","Hyper Transfer Markup Language","None"],"answer":"Hyper Text Markup Language"},
        {"id":"fb_e5","question":"Which method adds an item to the end of a Python list?","options":["add()","insert()","append()","extend()"],"answer":"append()"},
        {"id":"fb_e6","question":"What is the correct Python file extension?","options":[".pt",".py",".pyt",".python"],"answer":".py"},
        {"id":"fb_e7","question":"What does CSS stand for?","options":["Cascading Style Sheets","Computer Style Sheets","Creative Style Sheets","Colorful Style Sheets"],"answer":"Cascading Style Sheets"},
        {"id":"fb_e8","question":"Which tag creates a hyperlink in HTML?","options":["<link>","<href>","<a>","<url>"],"answer":"<a>"},
    ],
    "medium": [
        {"id":"fb_m1","question":"What is the time complexity of binary search?","options":["O(n)","O(log n)","O(n²)","O(1)"],"answer":"O(log n)"},
        {"id":"fb_m2","question":"Which HTTP method updates a resource in REST?","options":["GET","POST","PUT","DELETE"],"answer":"PUT"},
        {"id":"fb_m3","question":"What does __init__ do in a Python class?","options":["Destroys object","Initializes object","Imports module","None"],"answer":"Initializes object"},
        {"id":"fb_m4","question":"Which Python library is used for data analysis?","options":["NumPy","Flask","Pandas","Django"],"answer":"Pandas"},
        {"id":"fb_m5","question":"Which data structure follows LIFO?","options":["Queue","Stack","Linked List","Tree"],"answer":"Stack"},
        {"id":"fb_m6","question":"In Flask, which decorator defines a route?","options":["@app.url()","@app.path()","@app.route()","@app.endpoint()"],"answer":"@app.route()"},
        {"id":"fb_m7","question":"What is a foreign key in SQL?","options":["Unique key","References primary key of another table","Duplicate key","NULL key"],"answer":"References primary key of another table"},
        {"id":"fb_m8","question":"What does API stand for?","options":["Application Programming Interface","Automated Program Integration","Application Process Integration","None"],"answer":"Application Programming Interface"},
    ],
    "hard": [
        {"id":"fb_h1","question":"What is the average time complexity for hash table insertion?","options":["O(n)","O(log n)","O(1)","O(n log n)"],"answer":"O(1)"},
        {"id":"fb_h2","question":"Which SQL clause filters GROUP BY results?","options":["WHERE","FILTER","HAVING","BETWEEN"],"answer":"HAVING"},
        {"id":"fb_h3","question":"What does the yield keyword do in Python?","options":["Returns value and ends function","Pauses and returns generator value","Raises exception","Imports module"],"answer":"Pauses and returns generator value"},
        {"id":"fb_h4","question":"Which normal form removes transitive dependencies?","options":["1NF","2NF","3NF","BCNF"],"answer":"3NF"},
        {"id":"fb_h5","question":"In REST, which status code means Not Found?","options":["200","301","403","404"],"answer":"404"},
        {"id":"fb_h6","question":"What is a Python decorator?","options":["Inherits from another class","Wraps and extends a function","Module import statement","Special comment"],"answer":"Wraps and extends a function"},
        {"id":"fb_h7","question":"What is deepcopy vs copy in Python?","options":["No difference","deepcopy recursively copies nested objects","copy copies nested objects","deepcopy is faster"],"answer":"deepcopy recursively copies nested objects"},
        {"id":"fb_h8","question":"What does __str__ return in Python?","options":["Object bytes","String representation","Deletes object","Compares objects"],"answer":"String representation"},
    ],
}
_FALLBACK_CODING = {
    "easy": [
        {"id":"fb_ce1","question":"Write a function solution(n) that returns the factorial of n. Example: solution(5) = 120","input_format":"Integer n (0-10)","expected_output":"solution(5) = 120"},
        {"id":"fb_ce2","question":"Write a function solution(lst) that returns the sum of all elements. Example: solution([1,2,3]) = 6","input_format":"List of integers","expected_output":"solution([1,2,3]) = 6"},
        {"id":"fb_ce3","question":"Write a function solution(s) that reverses a string. Example: solution('hello') = 'olleh'","input_format":"String","expected_output":"solution('hello') = 'olleh'"},
    ],
    "medium": [
        {"id":"fb_cm1","question":"Write a function solution(s) that checks if a string is a palindrome. Example: solution('racecar') = True","input_format":"String","expected_output":"solution('racecar') = True"},
        {"id":"fb_cm2","question":"Write a function solution(lst) that removes duplicates preserving order. Example: solution([1,2,2,3]) = [1,2,3]","input_format":"List of integers","expected_output":"solution([1,2,2,3]) = [1,2,3]"},
        {"id":"fb_cm3","question":"Write a function solution(n) that returns all prime numbers up to n. Example: solution(10) = [2,3,5,7]","input_format":"Integer n","expected_output":"solution(10) = [2,3,5,7]"},
    ],
    "hard": [
        {"id":"fb_ch1","question":"Write a function solution(lst) that returns the length of the longest increasing subsequence. Example: solution([10,9,2,5,3,7]) = 3","input_format":"List of integers","expected_output":"solution([10,9,2,5,3,7]) = 3"},
        {"id":"fb_ch2","question":"Write a function solution(n) that returns the nth Fibonacci number using dynamic programming. Example: solution(10) = 55","input_format":"Integer n (1-30)","expected_output":"solution(10) = 55"},
        {"id":"fb_ch3","question":"Write a function solution(s) that finds the longest substring without repeating characters. Example: solution('abcabcbb') = 3","input_format":"String","expected_output":"solution('abcabcbb') = 3"},
    ],
}
_FALLBACK_APTITUDE = {
    "easy": [
        {"id":"fb_ae1","question":"If a train travels 60 km in 1 hour, how far in 2.5 hours?","options":["120 km","150 km","180 km","200 km"],"answer":"150 km"},
        {"id":"fb_ae2","question":"What is 15% of 200?","options":["25","30","35","40"],"answer":"30"},
        {"id":"fb_ae3","question":"A shopkeeper buys for ₹100, sells for ₹120. Profit %?","options":["10%","15%","20%","25%"],"answer":"20%"},
        {"id":"fb_ae4","question":"6 workers finish a job in 10 days. How many days for 10 workers?","options":["4","6","8","12"],"answer":"6"},
        {"id":"fb_ae5","question":"Next in series: 2, 4, 8, 16, ___?","options":["24","28","32","36"],"answer":"32"},
        {"id":"fb_ae6","question":"A car covers 300 km at 60 km/h. Time taken?","options":["3 hrs","4 hrs","5 hrs","6 hrs"],"answer":"5 hrs"},
        {"id":"fb_ae7","question":"LCM of 4 and 6?","options":["8","10","12","24"],"answer":"12"},
        {"id":"fb_ae8","question":"If today is Monday, day after 15 days?","options":["Monday","Tuesday","Wednesday","Thursday"],"answer":"Tuesday"},
        {"id":"fb_ae9","question":"Average of 1,2,3,4,5?","options":["2","3","4","5"],"answer":"3"},
        {"id":"fb_ae10","question":"A rectangle is 8m × 5m. Its area?","options":["26 m²","30 m²","40 m²","45 m²"],"answer":"40 m²"},
    ],
    "medium": [
        {"id":"fb_am1","question":"Two numbers in ratio 3:5, sum is 80. Larger number?","options":["30","40","50","60"],"answer":"50"},
        {"id":"fb_am2","question":"₹5000 at 10% compound interest for 2 years?","options":["₹5950","₹6000","₹6050","₹6100"],"answer":"₹6050"},
        {"id":"fb_am3","question":"A can do work in 10 days, B in 15. Together?","options":["5 days","6 days","7 days","8 days"],"answer":"6 days"},
        {"id":"fb_am4","question":"Pipe fills tank in 6 hrs, another empties in 8 hrs. Together?","options":["20","24","28","32"],"answer":"24"},
        {"id":"fb_am5","question":"In class of 40, 60% passed Maths, 50% Science, 10% failed both. Passed both?","options":["4","6","8","10"],"answer":"8"},
        {"id":"fb_am6","question":"Boat goes 15 km upstream in 3 hrs, downstream in 1.5 hrs. Stream speed?","options":["1.5","2.5","3.5","4.5"],"answer":"2.5"},
        {"id":"fb_am7","question":"Find missing: 1, 4, 9, 16, 25, ___","options":["30","36","40","49"],"answer":"36"},
        {"id":"fb_am8","question":"Simple interest on ₹2000 at 5% for 3 years?","options":["₹200","₹250","₹300","₹350"],"answer":"₹300"},
        {"id":"fb_am9","question":"A train 200m passes pole in 10 sec. Speed?","options":["15 m/s","20 m/s","25 m/s","30 m/s"],"answer":"20 m/s"},
        {"id":"fb_am10","question":"Average of 11 results is 50. First 6 avg 49, last 6 avg 52. 6th result?","options":["48","50","56","58"],"answer":"56"},
    ],
    "hard": [
        {"id":"fb_ah1","question":"Three pipes fill tank in 6, 9, 12 hrs. C also leaks. All open, fills in 8 hrs. Leak time?","options":["18","24","36","48"],"answer":"24"},
        {"id":"fb_ah2","question":"In how many ways can letters of LEADER be arranged?","options":["360","480","520","720"],"answer":"360"},
        {"id":"fb_ah3","question":"Ages A:B = 3:5. After 10 yrs = 5:7. A's current age?","options":["10","15","20","25"],"answer":"15"},
        {"id":"fb_ah4","question":"Mixture of 40L, milk:water = 7:1. Water to make 3:1?","options":["4","6","8","10"],"answer":"4"},
        {"id":"fb_ah5","question":"A train 200m, platform 300m, passes in 25 sec. Speed?","options":["18","20","22","24"],"answer":"20"},
        {"id":"fb_ah6","question":"Man invests 1/3 at 7%, 1/4 at 8%, rest at 10%. Annual income ₹561. Capital?","options":["₹5000","₹5400","₹5800","₹6000"],"answer":"₹5400"},
        {"id":"fb_ah7","question":"If 12 men build wall in 20 days, 8 men take?","options":["24 days","28 days","30 days","36 days"],"answer":"30 days"},
        {"id":"fb_ah8","question":"P can do work in 12 days, Q in 16. P works 4 days, Q finishes. Q works?","options":["10 days","12 days","15 days","18 days"],"answer":"12 days"},
        {"id":"fb_ah9","question":"Probability of 2 heads in 3 coin tosses?","options":["1/4","3/8","1/2","5/8"],"answer":"3/8"},
        {"id":"fb_ah10","question":"A sum triples in 5 years at SI. Rate %?","options":["30%","35%","40%","45%"],"answer":"40%"},
    ],
}

def _call_groq(prompt: str) -> str:
    from groq import Groq as _Groq
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set in .env")
    _client = _Groq(api_key=api_key)
    resp = _client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=3000,
    )
    return resp.choices[0].message.content.strip()

def _parse_json_array(raw: str) -> list:
    # Strip markdown code fences like ```json ... ``` or ``` ... ```
    raw = _re.sub(r"```(?:json)?", "", raw).strip()
    # Find the JSON array — handles nested brackets correctly
    start = raw.find("[")
    if start == -1:
        raise ValueError("No JSON array found in response")
    depth, end = 0, -1
    for i, ch in enumerate(raw[start:], start):
        if ch == "[": depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        raise ValueError("Unclosed JSON array in response")
    return json.loads(raw[start:end+1])

def get_ai_tech_mcq(level: str, count: int = 8) -> list:
    """Return AI-generated tech MCQ questions for the given level. Cached 24h."""
    cache_key = f"tech_mcq:{level}"
    cached = _ai_question_cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return cached["questions"]

    difficulty = {
        "easy":   "basic Python syntax, HTML/CSS, simple SQL SELECT queries, basic web concepts",
        "medium": "Python OOP and decorators, REST APIs, SQL joins and aggregation, Flask routing, data structures like stack and queue",
        "hard":   "Python generators and context managers, system design, database indexing and normalization, time/space complexity, advanced OOP patterns",
    }.get(level, "Python and web development")

    prompt = f"""Generate exactly {count} multiple-choice questions on {difficulty} for a software engineering job recruitment test.

Return ONLY a valid JSON array — no explanation, no markdown, no extra text:
[
  {{
    "id": "ai_mcq_{level}_1",
    "question": "Question text here?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": "Option A"
  }}
]
Rules:
- IDs must be unique: ai_mcq_{level}_1 through ai_mcq_{level}_{count}
- "answer" must exactly match one of the 4 "options"
- Questions must be clear, unambiguous, and technically accurate
- Each question must be different — no repeats
"""
    try:
        raw = _call_groq(prompt)
        questions = _parse_json_array(raw)
        for i, q in enumerate(questions, 1):
            q["id"] = f"ai_mcq_{level}_{i}"
        _ai_question_cache[cache_key] = {"questions": questions, "ts": time.time()}
        print(f"[AI] Generated {len(questions)} tech MCQ [{level}] from Groq ✓")
        return questions
    except Exception as e:
        print(f"[AI] Groq tech MCQ [{level}] failed: {e} — using fallback")
        return _FALLBACK_MCQ.get(level, _FALLBACK_MCQ["easy"])

def get_ai_tech_coding(level: str, count: int = 3) -> list:
    """Return AI-generated coding problems for the given level. Cached 24h."""
    cache_key = f"tech_coding:{level}"
    cached = _ai_question_cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return cached["questions"]

    difficulty = {
        "easy":   "basic loops, string operations, simple math functions",
        "medium": "array manipulation, string algorithms, basic sorting and searching",
        "hard":   "dynamic programming, recursion, graph traversal, advanced data structures",
    }.get(level, "Python algorithms")

    prompt = f"""Generate exactly {count} coding problems on {difficulty} for a Python developer recruitment test.

Each solution function MUST be named `solution` and accept a single argument.

Return ONLY a valid JSON array — no explanation, no markdown, no extra text:
[
  {{
    "id": "ai_code_{level}_1",
    "question": "Write a function solution(n) that ... (clear problem statement with example)",
    "input_format": "Description of input type",
    "expected_output": "solution(example_input) = expected_result"
  }}
]
Rules:
- IDs must be: ai_code_{level}_1 through ai_code_{level}_{count}
- Function must always be named exactly `solution`
- Problem must be solvable in under 20 lines of Python
- Include one concrete example in the question text
"""
    try:
        raw = _call_groq(prompt)
        questions = _parse_json_array(raw)
        for i, q in enumerate(questions, 1):
            q["id"] = f"ai_code_{level}_{i}"
        _ai_question_cache[cache_key] = {"questions": questions, "ts": time.time()}
        print(f"[AI] Generated {len(questions)} tech coding [{level}] from Groq ✓")
        return questions
    except Exception as e:
        print(f"[AI] Groq tech coding [{level}] failed: {e} — using fallback")
        return _FALLBACK_CODING.get(level, _FALLBACK_CODING["easy"])

def get_ai_aptitude(level: str, count: int = 10) -> list:
    """Return AI-generated aptitude questions for the given level. Cached 24h."""
    cache_key = f"aptitude:{level}"
    cached = _ai_question_cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return cached["questions"]

    difficulty = {
        "easy":   "basic arithmetic, percentages, simple ratios, time and distance, profit and loss",
        "medium": "time and work, pipes and cisterns, mixtures, simple and compound interest, logical reasoning, number series",
        "hard":   "permutations and combinations, probability, data interpretation, complex puzzles, advanced number series, syllogisms",
    }.get(level, "quantitative aptitude")

    prompt = f"""Generate exactly {count} aptitude questions on {difficulty} for a job recruitment test.

Return ONLY a valid JSON array — no explanation, no markdown, no extra text:
[
  {{
    "id": "ai_apt_{level}_1",
    "question": "Question text with a clear problem statement?",
    "options": ["A", "B", "C", "D"],
    "answer": "A"
  }}
]
Rules:
- IDs must be: ai_apt_{level}_1 through ai_apt_{level}_{count}
- "answer" must exactly match one of the 4 "options"
- Options should be concise (numbers or short phrases, not sentences)
- All questions must be mathematically correct and unambiguous
- Each question must be unique — no repeats
"""
    try:
        raw = _call_groq(prompt)
        questions = _parse_json_array(raw)
        for i, q in enumerate(questions, 1):
            q["id"] = f"ai_apt_{level}_{i}"
        _ai_question_cache[cache_key] = {"questions": questions, "ts": time.time()}
        print(f"[AI] Generated {len(questions)} aptitude [{level}] from Groq ✓")
        return questions
    except Exception as e:
        print(f"[AI] Groq aptitude [{level}] failed: {e} — using fallback")
        return _FALLBACK_APTITUDE.get(level, _FALLBACK_APTITUDE["easy"])

def refresh_ai_questions(category: str = "all", level: str = "all"):
    """Clear cache for a category/level so fresh questions are generated next request.
       Called by HR when they want to refresh default questions.
       category: 'tech_mcq' | 'tech_coding' | 'aptitude' | 'all'
       level: 'easy' | 'medium' | 'hard' | 'all'
    """
    categories = ["tech_mcq", "tech_coding", "aptitude"] if category == "all" else [category]
    levels     = ["easy", "medium", "hard"]               if level == "all"     else [level]
    cleared = []
    for cat in categories:
        for lvl in levels:
            key = f"{cat}:{lvl}"
            if key in _ai_question_cache:
                del _ai_question_cache[key]
                cleared.append(key)
    print(f"[AI] Cache cleared: {cleared}")

os.makedirs(RESUME_FOLDER, exist_ok=True)
os.makedirs("data", exist_ok=True)

SMTP_EMAIL    = os.getenv("SMTP_EMAIL",    "ss9879086402@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "pvzj jkat dmmx hlvi")

# ─── Email ───────────────────────────────────────────────────

def send_email(to, subject, body):
    """Send email via Gmail SMTP. Raises exception on failure."""
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"]    = SMTP_EMAIL
    msg["To"]      = to
    s = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
    s.ehlo()
    s.starttls()
    s.ehlo()
    s.login(SMTP_EMAIL, SMTP_PASSWORD)
    s.sendmail(SMTP_EMAIL, to, msg.as_string())
    s.quit()
    print(f"✅ Email sent → {to}")


def _safe_send(to, subject, body):
    """Send email, log errors but don't crash the caller."""
    try:
        send_email(to, subject, body)
    except Exception as e:
        print(f"❌ Email failed to {to}: {e}")


def _format_dt(value):
    if not value:
        return "N/A"
    if hasattr(value, "strftime"):
        return value.strftime("%d %b %Y %I:%M %p")
    return str(value)


def _execute_rowcount(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            conn.commit()
            return cur.rowcount
    finally:
        conn.close()


def _annotate_job_state(job):
    job_date = job.get("deadline")
    if hasattr(job_date, "date"):
        job_date = job_date.date()
    today = datetime.now().date()
    job["is_closed"] = job.get("status") == "closed"
    job["is_closing_today"] = bool(job_date and job.get("status") == "open" and job_date == today)
    if job["is_closed"]:
        job["state_label"] = "Closed"
        job["state_icon"] = "fa-lock"
        job["state_class"] = "badge-pending"
    elif job["is_closing_today"]:
        job["state_label"] = "Closing Today"
        job["state_icon"] = "fa-hourglass-half"
        job["state_class"] = "badge-warning"
    else:
        job["state_label"] = "Open"
        job["state_icon"] = "fa-circle"
        job["state_class"] = "badge-open"
    return job

def send_account_blocked_email(email, name):
    _safe_send(email, "Account Blocked",
               f"Hi {name},\n\nYour account was blocked after 3 failed login attempts.\n\nSecurity Team")

def send_hr_decision_email(email, name, decision, job_title):
    _safe_send(email, f"Application Update – {job_title}",
               f"Hi {name},\n\nStatus for {job_title}: {decision.upper()}\n\nThank you.\nHR Team")

def send_tech_round_email(email, name):
    _safe_send(email, "Selected for Technical Round",
               f"Hi {name},\n\nYou are shortlisted for the Technical Round. Log in to your dashboard.\n\nAI Recruitment Team")

def send_aptitude_invite_email(email, name, job_title):
    _safe_send(email, "Aptitude Test Invitation",
               f"Hi {name},\n\nPlease complete the Aptitude Test for: {job_title}.\n\nAI Recruitment Team")

def send_schedule_email(email, name, job_title, date, time_str):
    _safe_send(email, "HR Interview Scheduled",
               f"Dear {name},\n\nHR interview for {job_title}:\nDate: {date}\nTime: {time_str}\n\nAI Recruitment Team")

# ─── HR Notification Emails ──────────────────────────────────

def send_hr_new_application_email(hr_email, hr_name, candidate_name, job_title, candidate_email):
    _safe_send(hr_email, f"New Application – {job_title}",
               f"Hi {hr_name},\n\nNew application received:\n\nCandidate: {candidate_name}\nEmail: {candidate_email}\nJob: {job_title}\n\nPlease review in your dashboard.\n\nAI Recruitment Team")

def send_hr_job_posted_email(hr_email, hr_name, job_title, company_name, posted_on, deadline=None):
    deadline_text = deadline if deadline else "Open until filled"
    _safe_send(hr_email, f"Job Posted – {job_title}",
               f"Hi {hr_name},\n\nYour job has been posted successfully.\n\nJob: {job_title}\nCompany: {company_name}\nPosted On: {posted_on}\nDeadline: {deadline_text}\n\nAI Recruitment Team")

def send_hr_job_closed_email(hr_email, hr_name, job_title, company_name, posted_on, closed_on):
    _safe_send(hr_email, f"Hiring Closed – {job_title}",
               f"Hi {hr_name},\n\nThe hiring process for this job is now closed.\n\nJob: {job_title}\nCompany: {company_name}\nPosted On: {posted_on}\nClosed On: {closed_on}\n\nAI Recruitment Team")

def send_hr_job_ending_soon_email(hr_email, hr_name, job_title, company_name, posted_on, deadline):
    _safe_send(hr_email, f"Job Ending Tomorrow – {job_title}",
               f"Hi {hr_name},\n\nThis is a reminder that your job will end tomorrow.\n\nJob: {job_title}\nCompany: {company_name}\nPosted On: {posted_on}\nDeadline: {deadline}\n\nAI Recruitment Team")

def send_hr_aptitude_completed_email(hr_email, hr_name, candidate_name, job_title, score, total, percentage):
    _safe_send(hr_email, f"Aptitude Test Completed – {job_title}",
               f"Hi {hr_name},\n\nAptitude test completed:\n\nCandidate: {candidate_name}\nJob: {job_title}\nScore: {score}/{total} ({percentage}%)\n\nPlease review in your dashboard.\n\nAI Recruitment Team")

def send_hr_tech_completed_email(hr_email, hr_name, candidate_name, job_title, score):
    _safe_send(hr_email, f"Technical Round Completed – {job_title}",
               f"Hi {hr_name},\n\nTechnical round completed:\n\nCandidate: {candidate_name}\nJob: {job_title}\nScore: {score}/100\n\nPlease review in your dashboard.\n\nAI Recruitment Team")

def send_candidate_aptitude_completed_email(email, name, score, total, percentage):
    _safe_send(email, "Aptitude Test Submitted",
               f"Hi {name},\n\nYour aptitude test has been submitted.\n\nScore: {score}/{total} ({percentage}%)\n\nYou will hear from the HR team soon.\n\nAI Recruitment Team")

# ─── Utility ────────────────────────────────────────────────

def _exp_to_level(exp):
    try: exp = float(exp)
    except: exp = 0
    if exp <= 1:  return "easy"
    if exp <= 3:  return "medium"
    return "hard"


def auto_close_expired_jobs():
    overdue_jobs = fetchall(
        """
        SELECT j.id, j.hr_id, j.title, j.created_at, j.deadline, u.email AS hr_email, u.name AS hr_name,
               u.company_name
        FROM jobs j
        JOIN users u ON u.id = j.hr_id
        WHERE j.status='open'
          AND j.deadline IS NOT NULL
                    AND j.deadline <= CURRENT_DATE
        ORDER BY j.deadline ASC, j.created_at ASC
        """
    )

    for job in overdue_jobs:
        updated = _execute_rowcount(
            "UPDATE jobs SET status='closed', closed_at=NOW() WHERE id=%s AND status='open'",
            (job["id"],)
        )
        if not updated:
            continue
        company_name = job.get("company_name") or "Your company"
        posted_on = _format_dt(job.get("created_at"))
        closed_on = _format_dt(datetime.now())
        threading.Thread(
            target=send_hr_job_closed_email,
            args=(job["hr_email"], job["hr_name"], job["title"], company_name, posted_on, closed_on),
            daemon=True,
        ).start()


def auto_send_job_end_reminders():
    reminder_jobs = fetchall(
        """
        SELECT j.id, j.hr_id, j.title, j.created_at, j.deadline, u.email AS hr_email, u.name AS hr_name,
               u.company_name
        FROM jobs j
        JOIN users u ON u.id = j.hr_id
        WHERE j.status='open'
          AND j.deadline IS NOT NULL
          AND j.deadline = CURRENT_DATE + INTERVAL '1 day'
          AND j.reminder_sent_at IS NULL
        ORDER BY j.deadline ASC, j.created_at ASC
        """
    )

    for job in reminder_jobs:
        updated = _execute_rowcount(
            "UPDATE jobs SET reminder_sent_at=NOW() WHERE id=%s AND reminder_sent_at IS NULL AND status='open'",
            (job["id"],)
        )
        if not updated:
            continue
        company_name = job.get("company_name") or "Your company"
        posted_on = _format_dt(job.get("created_at"))
        deadline = _format_dt(job.get("deadline"))
        threading.Thread(
            target=send_hr_job_ending_soon_email,
            args=(job["hr_email"], job["hr_name"], job["title"], company_name, posted_on, deadline),
            daemon=True,
        ).start()


def _ensure_job_columns():
    try:
        execute("ALTER TABLE jobs ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'open'")
    except Exception:
        pass
    try:
        execute("ALTER TABLE jobs ADD COLUMN closed_at DATETIME DEFAULT NULL")
    except Exception:
        pass
    try:
        execute("ALTER TABLE jobs ADD COLUMN reminder_sent_at DATETIME DEFAULT NULL")
    except Exception:
        pass


_ensure_job_columns()


@app.before_request
def _auto_close_jobs_before_request():
    if request.endpoint and request.endpoint != "static":
        auto_send_job_end_reminders()
        auto_close_expired_jobs()


def _start_background_scheduler():
    """Start APScheduler to run job reminders and closure checks daily."""
    scheduler = BackgroundScheduler()
    # Run reminder + closure checks daily at 8 AM
    scheduler.add_job(
        func=lambda: [
            auto_send_job_end_reminders(),
            auto_close_expired_jobs()
        ],
        trigger="cron",
        hour=8,
        minute=0,
        id="job_lifecycle_check",
        name="Daily job reminders and closures",
        replace_existing=True
    )
    if not scheduler.running:
        scheduler.start()
        print("[✓] Background scheduler started for job reminders")


_start_background_scheduler()

# ═══════════════════════════════════════════════════════════════
#  AUTH
# ═══════════════════════════════════════════════════════════════

def _is_admin_logged_in():
    return bool(session.get("is_admin"))


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if _is_admin_logged_in():
        return redirect("/admin/panel")
    return redirect("/")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    session.pop("admin_id", None)
    return redirect("/")


@app.route("/admin/panel")
def admin_panel():
    if not _is_admin_logged_in():
        return redirect("/admin")

    users = fetchall("SELECT id, name, email, role, blocked, created_at FROM users ORDER BY created_at DESC")
    jobs = fetchall("""
        SELECT j.id, j.title, j.status, j.created_at, u.name AS hr_name, u.email AS hr_email
        FROM jobs j
        LEFT JOIN users u ON u.id = j.hr_id
        ORDER BY j.created_at DESC
    """)
    applications = fetchall("""
        SELECT a.id, a.status, a.applied_at, a.user_id, a.job_id,
               u.name AS candidate_name, u.email AS candidate_email,
               j.title AS job_title
        FROM applications a
        LEFT JOIN users u ON u.id = a.user_id
        LEFT JOIN jobs j ON j.id = a.job_id
        ORDER BY a.applied_at DESC
    """)

    stats = {
        "users": len(users),
        "jobs": len(jobs),
        "applications": len(applications),
        "blocked_users": sum(1 for u in users if u.get("blocked")),
    }
    return render_template(
        "admin_panel.html",
        stats=stats,
        users=users,
        jobs=jobs,
        applications=applications,
        admin_id=session.get("admin_id", ADMIN_ID),
    )


@app.route("/admin/user/<int:user_id>/toggle_block", methods=["POST"])
def admin_toggle_user_block(user_id):
    if not _is_admin_logged_in():
        return redirect("/admin")

    user = fetchone("SELECT id, blocked FROM users WHERE id=%s", (user_id,))
    if not user:
        return "User not found", 404

    new_blocked = 0 if user.get("blocked") else 1
    execute("UPDATE users SET blocked=%s WHERE id=%s", (new_blocked, user_id))
    return redirect("/admin/panel")


@app.route("/admin/user/<int:user_id>/delete", methods=["POST"])
def admin_delete_user(user_id):
    if not _is_admin_logged_in():
        return redirect("/admin")

    execute("DELETE FROM users WHERE id=%s", (user_id,))
    return redirect("/admin/panel")


@app.route("/admin/job/<int:job_id>/delete", methods=["POST"])
def admin_delete_job(job_id):
    if not _is_admin_logged_in():
        return redirect("/admin")

    execute("DELETE FROM jobs WHERE id=%s", (job_id,))
    return redirect("/admin/panel")


@app.route("/admin/application/<app_id>/delete", methods=["POST"])
def admin_delete_application(app_id):
    if not _is_admin_logged_in():
        return redirect("/admin")

    execute("DELETE FROM applications WHERE id=%s", (app_id,))
    return redirect("/admin/panel")

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip().lower()
        password = request.form.get("password", "")

        if identifier == ADMIN_ID.lower() and password == ADMIN_PASSWORD:
            session.clear()
            session["is_admin"] = True
            session["admin_id"] = ADMIN_ID
            return redirect("/admin/panel")

        u = fetchone("SELECT * FROM users WHERE email=%s", (identifier,))
        if not u:
            return render_template("login.html", error="Email not found.")
        if u["blocked"]:
            return render_template("login.html", error="Account blocked. Check your email.")
        if u["password"] == password:
            session.clear()
            execute("UPDATE users SET login_attempts=0 WHERE id=%s", (u["id"],))
            session["user"] = dict(u)
            return redirect("/dashboard")
        attempts = u["login_attempts"] + 1
        if attempts >= 3:
            execute("UPDATE users SET login_attempts=%s, blocked=1 WHERE id=%s", (attempts, u["id"]))
            send_account_blocked_email(u["email"], u["name"])
            return render_template("login.html", error="Account blocked after 3 failed attempts.")
        execute("UPDATE users SET login_attempts=%s WHERE id=%s", (attempts, u["id"]))
        return render_template("login.html", error=f"Wrong password. {3-attempts} attempt(s) left.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    if request.is_json:
        d            = request.get_json()
        name         = d.get("name", "").strip()
        email        = d.get("email", "").strip().lower()
        password     = d.get("password", "")
        role         = d.get("role", "candidate")
        company_name = d.get("company_name", "")
        if not all([name, email, password, role]):
            return jsonify({"success": False, "message": "Missing fields"}), 400
        if role == "hr" and not company_name:
            return jsonify({"success": False, "message": "Company name required for HR"}), 400
        if fetchone("SELECT id FROM users WHERE email=%s", (email,)):
            return jsonify({"success": False, "message": "Email already registered"}), 400
        execute("INSERT INTO users (name,email,password,role,company_name) VALUES (%s,%s,%s,%s,%s)",
                (name, email, password, role, company_name if role == "hr" else None))
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Invalid request"}), 400


@app.route("/send_otp", methods=["POST"])
def send_otp():
    data  = request.get_json()
    email = data.get("email", "").strip().lower()

    if not email:
        return jsonify({"success": False, "message": "Email is required"}), 400

    otp = str(random.randint(100000, 999999))
    session["otp"]          = otp
    session["otp_email"]    = email
    session["otp_verified"] = False

    # Send OTP via Gmail SMTP
    try:
        send_email(
            email,
            "Your OTP - HireAI Registration",
            f"Hi,\n\nYour OTP for HireAI registration is:\n\n  {otp}\n\nValid for 5 minutes. Do not share it.\n\nHireAI Team"
        )
        return jsonify({"success": True})
    except Exception as e:
        print(f"OTP email failed: {e}")
        return jsonify({"success": False, "message": f"Could not send OTP. Check SMTP settings. ({str(e)})"}), 500


@app.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    if "otp" not in session:
        if request.is_json:
            return jsonify({"success": False, "message": "OTP expired"}), 400
        return redirect("/forgot-password")
    if request.method == "POST":
        if request.is_json:
            if request.get_json().get("otp") != session.get("otp"):
                return jsonify({"success": False, "message": "Invalid OTP"}), 400
            session["otp_verified"] = True
            return jsonify({"success": True})
        if request.form.get("otp") != session.get("otp"):
            return render_template("verify_otp.html", message="Invalid OTP")
        session["otp_verified"] = True
        return redirect("/reset_password")
    return render_template("verify_otp.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not fetchone("SELECT id FROM users WHERE email=%s", (email,)):
            return render_template("forgot_password.html", error="Email not found")
        otp = str(random.randint(100000, 999999))
        session["otp"]          = otp
        session["otp_email"]    = email
        session["otp_verified"] = False
        send_email(email, "Password Reset OTP", f"Your OTP: {otp}\nValid for 5 minutes.")
        return redirect("/verify_otp")
    return render_template("forgot_password.html")


@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if not session.get("otp_verified"):
        return redirect("/forgot-password")
    if request.method == "POST":
        execute("UPDATE users SET password=%s WHERE email=%s",
                (request.form["password"], session.get("otp_email")))
        session.pop("otp", None); session.pop("otp_verified", None); session.pop("otp_email", None)
        return redirect("/")
    return render_template("reset_password.html")

# ═══════════════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════════════

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    user = session["user"]
    applied_jobs = []
    if user["role"] == "candidate":
        rows = fetchall("""
            SELECT a.*, j.title AS job_title
            FROM applications a JOIN jobs j ON j.id=a.job_id
            WHERE a.user_id=%s ORDER BY a.applied_at DESC
        """, (user["id"],))
        for row in rows:
            row = dict(row)
            row["aptitude_allowed"] = (row.get("aptitude_required") and row.get("aptitude_status") == "pending" and row.get("status") != "rejected")
            row["aptitude_done"]    = row.get("aptitude_status") == "completed"
            row["tech_allowed"]     = (row.get("tech_round") and not row.get("tech_completed") and row.get("tech_status") == "pending")
            row["waiting_hr"]       = row.get("tech_completed") and row.get("status") not in ["rejected","hr_scheduled"]
            applied_jobs.append(row)
    return render_template("dashboard.html", user=user, applied_jobs=applied_jobs)

@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if "user" not in session:
        return redirect("/")
    user = session["user"]
    success = None
    error = None

    if request.method == "POST":
        name         = request.form.get("name", "").strip()
        email        = request.form.get("email", "").strip().lower()
        new_password = request.form.get("new_password", "").strip()
        confirm_pwd  = request.form.get("confirm_password", "").strip()
        company_name = request.form.get("company_name", "").strip()

        if not name or not email:
            error = "Name and email are required."
        elif new_password and new_password != confirm_pwd:
            error = "Passwords do not match."
        elif new_password and len(new_password) < 6:
            error = "Password must be at least 6 characters."
        else:
            # Check email unique (ignore own)
            existing = fetchone("SELECT id FROM users WHERE email=%s AND id != %s", (email, user["id"]))
            if existing:
                error = "That email is already in use by another account."
            else:
                if new_password:
                    execute("UPDATE users SET name=%s, email=%s, password=%s, company_name=%s WHERE id=%s",
                            (name, email, new_password, company_name or None, user["id"]))
                else:
                    execute("UPDATE users SET name=%s, email=%s, company_name=%s WHERE id=%s",
                            (name, email, company_name or None, user["id"]))
                # Refresh session
                updated = fetchone("SELECT * FROM users WHERE id=%s", (user["id"],))
                session["user"] = dict(updated)
                user = session["user"]
                success = "Profile updated successfully!"

    return render_template("edit_profile.html", user=user, success=success, error=error)


@app.route("/hr_company_details", methods=["GET", "POST"])
def hr_company_details():
    if session.get("user", {}).get("role") != "hr":
        return "Access Denied", 403
    hr_id = session["user"]["id"]
    company = fetchone("SELECT * FROM company WHERE hr_id=%s", (hr_id,))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
        industry = request.form.get("industry", "").strip()
        website = request.form.get("website", "").strip()
        description = request.form.get("description", "").strip()
        size = request.form.get("size", "").strip()
        founded_year = request.form.get("founded_year", "").strip()
        contact_email = request.form.get("contact_email", "").strip()
        if company:
            execute("UPDATE company SET name=%s, location=%s, industry=%s, website=%s, description=%s, size=%s, founded_year=%s, contact_email=%s WHERE hr_id=%s",
                    (name, location, industry, website, description, size, founded_year, contact_email, hr_id))
        else:
            execute("INSERT INTO company (hr_id, name, location, industry, website, description, size, founded_year, contact_email) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (hr_id, name, location, industry, website, description, size, founded_year, contact_email))
        return redirect("/dashboard")
    company = fetchone("SELECT * FROM company WHERE hr_id=%s", (hr_id,))
    return render_template("hr_company_details.html", company=company)
# ═══════════════════════════════════════════════════════════════
#  RESUME
# ═══════════════════════════════════════════════════════════════

@app.route("/upload_resume", methods=["GET", "POST"])
def upload_resume():
    if session.get("user", {}).get("role") != "candidate":
        return "Access Denied", 403
    user_id = session["user"]["id"]
    if request.method == "POST":
        f = request.files.get("resume")
        if f and f.filename.endswith(".pdf"):
            resume_id = str(uuid.uuid4())[:8]
            filename  = f"{user_id}_{time.time_ns()}.pdf"
            f.save(os.path.join(RESUME_FOLDER, filename))
            execute("UPDATE resumes SET is_active=0 WHERE user_id=%s", (user_id,))
            execute(
                """INSERT INTO resumes
                   (resume_id,user_id,filename,is_active,analysis_quality,analysis_score,analysis_feedback,analysis_suggestions)
                   VALUES (%s,%s,%s,1,NULL,NULL,NULL,NULL)""",
                (resume_id, user_id, filename)
            )
            return redirect("/resume_analysis")
    return render_template("upload_resume.html")


@app.route("/resume_analysis")
def resume_analysis():
    """Show resume analysis results, or loading page if not ready yet."""
    if session.get("user", {}).get("role") != "candidate":
        return "Access Denied", 403
    user_id = session["user"]["id"]
    resume = fetchone("SELECT * FROM resumes WHERE user_id=%s AND is_active=1", (user_id,))
    if not resume:
        return redirect("/upload_resume")

    # Check if analysis is stored in MySQL
    if resume.get("analysis_quality"):
        analysis = {
            "quality":     resume["analysis_quality"],
            "score":       resume["analysis_score"] or 0,
            "feedback":    json.loads(resume["analysis_feedback"] or "{}"),
            "suggestions": json.loads(resume["analysis_suggestions"] or "[]"),
        }
        return render_template("resume_analysis.html", analysis=analysis, resume=resume)

    # No analysis yet — show loading/polling page
    return render_template("resume_analysis_loading.html", resume=resume, resume_id=resume["resume_id"])


# Track which resume_ids are currently being analyzed (prevents duplicate threads)
_analysis_in_progress = set()
_analysis_lock = threading.Lock()


@app.route("/check_resume_analysis/<resume_id>")
def check_resume_analysis(resume_id):
    """Non-blocking check: reads/writes MySQL instead of JSON files."""
    if session.get("user", {}).get("role") != "candidate":
        return jsonify({"error": "Access Denied"}), 403
    user_id = session["user"]["id"]

    resume = fetchone(
        "SELECT * FROM resumes WHERE resume_id=%s AND user_id=%s",
        (resume_id, user_id)
    )
    if not resume:
        return jsonify({"ready": False, "message": "Resume not found"})

    # ── Already analysed? Return from MySQL immediately ──────────
    if resume.get("analysis_quality"):
        analysis = {
            "quality":     resume["analysis_quality"],
            "score":       resume["analysis_score"] or 0,
            "feedback":    json.loads(resume["analysis_feedback"] or "{}"),
            "suggestions": json.loads(resume["analysis_suggestions"] or "[]"),
        }
        return jsonify({"ready": True, "analysis": analysis})

    # ── Not done — fire background thread once ───────────────────
    with _analysis_lock:
        if resume_id not in _analysis_in_progress:
            _analysis_in_progress.add(resume_id)
            def _run_bg():
                try:
                    print(f"[INFO] Background analysis started for resume {resume_id}")
                    _run_resume_analysis(user_id, resume["filename"], resume_id)
                    print(f"[INFO] Background analysis complete for resume {resume_id}")
                finally:
                    with _analysis_lock:
                        _analysis_in_progress.discard(resume_id)
            t = threading.Thread(target=_run_bg, daemon=True)
            t.start()
        else:
            print(f"[INFO] Analysis already running for resume {resume_id}, skipping duplicate")

    return jsonify({"ready": False, "message": "Analysis in progress…"})


def _run_resume_analysis(user_id, filename, resume_id):
    """Run resume quality analysis and save result to MySQL."""
    try:
        filepath = os.path.join(RESUME_FOLDER, filename)

        print(f"[INFO] Extracting text from resume {filename}...")
        resume_text = extract_text_from_pdf(filepath)
        sample_head = (resume_text or "")[:120].replace("\n", " ")
        sample_tail = (resume_text or "")[-120:].replace("\n", " ")
        print(f"[DEBUG] Extracted chars: {len(resume_text or '')}")
        print(f"[DEBUG] Head sample: {sample_head}")
        print(f"[DEBUG] Tail sample: {sample_tail}")

        if not resume_text or len(resume_text) < 50:
            raise ValueError("Resume text too short or empty")

        print(f"[INFO] Calling AI for quality analysis...")
        result = check_resume_quality(resume_text[:4000])
        print(f"[INFO] AI returned: quality={result.get('quality')}, score={result.get('score')}")

        # Save to MySQL
        execute(
            """UPDATE resumes
               SET analysis_quality=%s, analysis_score=%s,
                   analysis_feedback=%s, analysis_suggestions=%s
               WHERE resume_id=%s""",
            (
                result.get("quality", "unknown"),
                int(result.get("score", 0)),
                json.dumps(result.get("feedback", {})),
                json.dumps(result.get("suggestions", [])),
                resume_id,
            )
        )
        print(f"[INFO] Resume analysis saved to MySQL for resume {resume_id}")
        return result
    except Exception as e:
        print(f"[ERROR] Resume analysis failed: {e}")
        import traceback; traceback.print_exc()
        error_result = {
            "quality": "unknown",
            "score": 0,
            "feedback": {"error": str(e)[:200]},
            "suggestions": ["Unable to analyze. Please try uploading again."]
        }
        # Save error result to MySQL too so polling stops
        try:
            execute(
                """UPDATE resumes
                   SET analysis_quality=%s, analysis_score=%s,
                       analysis_feedback=%s, analysis_suggestions=%s
                   WHERE resume_id=%s""",
                (
                    "unknown", 0,
                    json.dumps(error_result["feedback"]),
                    json.dumps(error_result["suggestions"]),
                    resume_id,
                )
            )
        except Exception as db_err:
            print(f"[ERROR] Could not save error to MySQL: {db_err}")
        return error_result


@app.route("/resume_analysis_download", methods=["POST"])
def resume_analysis_download():
    """Generate a formatted PDF from the edited resume text."""
    if session.get("user", {}).get("role") != "candidate":
        return "Access Denied", 403
    user_id = session["user"]["id"]
    resume = fetchone("SELECT * FROM resumes WHERE user_id=%s AND is_active=1", (user_id,))
    if not resume:
        return "No active resume", 404

    updated_text = request.form.get("resume_text", "").strip()
    if not updated_text:
        return "No text provided", 400

    preview = request.form.get("preview") == "1"

    out_path = _generate_resume_pdf(user_id, updated_text)

    from flask import send_file
    if preview:
        return send_file(out_path, as_attachment=False, download_name="Resume_Preview.pdf", mimetype="application/pdf")
    return send_file(out_path, as_attachment=True, download_name="Resume.pdf", mimetype="application/pdf")


@app.route("/reanalyze_resume", methods=["GET", "POST"])
def reanalyze_resume():
    """Clear cached analysis for active resume and start fresh analysis flow."""
    if session.get("user", {}).get("role") != "candidate":
        return "Access Denied", 403

    user_id = session["user"]["id"]
    resume = fetchone("SELECT * FROM resumes WHERE user_id=%s AND is_active=1", (user_id,))
    if not resume:
        return redirect("/upload_resume")

    execute(
        """UPDATE resumes
           SET analysis_quality=NULL,
               analysis_score=NULL,
               analysis_feedback=NULL,
               analysis_suggestions=NULL
           WHERE resume_id=%s AND user_id=%s""",
        (resume["resume_id"], user_id)
    )
    return redirect("/resume_analysis")


@app.route("/upload_edited_resume", methods=["POST"])
def upload_edited_resume():
    """Save the edited text as a new PDF resume and set it active."""
    if session.get("user", {}).get("role") != "candidate":
        return "Access Denied", 403
    user_id = session["user"]["id"]
    updated_text = request.form.get("resume_text", "").strip()
    if not updated_text:
        return "No text provided", 400

    out_path = _generate_resume_pdf(user_id, updated_text)
    filename = os.path.basename(out_path)
    resume_id = str(uuid.uuid4())[:8]

    # Deactivate old resumes and insert new one
    execute("UPDATE resumes SET is_active=0 WHERE user_id=%s", (user_id,))
    execute(
        """INSERT INTO resumes
           (resume_id,user_id,filename,is_active,analysis_quality,analysis_score,analysis_feedback,analysis_suggestions)
           VALUES (%s,%s,%s,1,NULL,NULL,NULL,NULL)""",
        (resume_id, user_id, filename)
    )

    return redirect("/resume_analysis")


def _generate_resume_pdf(user_id, text):
    """Generate a clean, professional black-and-white resume PDF."""
    import re
    from fpdf import FPDF

    def _clean(t):
        """Remove emojis and non-latin1 characters."""
        t = re.sub(r'[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u200d\ufe0f]', '', t)
        for old, new in {'\u2022':'-', '\u2013':'-', '\u2014':'-',
                         '\u2018':"'", '\u2019':"'", '\u201c':'"', '\u201d':'"',
                         '\u2026':'...', '\u00a0':' '}.items():
            t = t.replace(old, new)
        return t.encode('latin-1', errors='ignore').decode('latin-1')

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(18, 15, 18)

    lines = text.split("\n")
    is_first_line = True

    for line in lines:
        stripped = line.strip()
        if not stripped:
            pdf.ln(3)
            is_first_line = False
            continue

        cleaned = _clean(stripped)
        if not cleaned.strip():
            pdf.ln(3)
            continue

        # Detect name (first non-empty line, typically all caps or title case)
        if is_first_line:
            is_first_line = False
            pdf.set_font("Helvetica", "B", 18)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 9, cleaned, new_x="LMARGIN", new_y="NEXT", align="L")
            pdf.ln(1)
            continue

        # Section headers: all-caps lines like PROFILE, EDUCATION, SKILLS, etc.
        alpha_only = cleaned.replace(' ', '').replace('-', '').replace(':', '').replace('&', '')
        is_header = (
            alpha_only.isalpha() and cleaned.isupper() and len(cleaned) < 50
        )

        if is_header:
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 7, cleaned, new_x="LMARGIN", new_y="NEXT")
            # Black separator line
            pdf.set_draw_color(0, 0, 0)
            pdf.set_line_width(0.4)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(3)
        elif cleaned.startswith(("- ", "* ")) or stripped.startswith(("- ", "* ")):
            # Bullet points
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(0, 0, 0)
            bullet_text = cleaned.lstrip("-* ").strip()
            pdf.cell(5)
            pdf.multi_cell(0, 5, "- " + bullet_text, new_x="LMARGIN", new_y="NEXT")
        else:
            # Regular text — detect sub-headers (lines ending with year or containing | )
            pdf.set_text_color(0, 0, 0)
            # Bold for lines that look like degree/job titles (short + has year or pipe)
            looks_like_title = (
                re.search(r'\b(19|20)\d{2}\b', cleaned) and len(cleaned) < 80
                and not cleaned[0].isdigit()
            )
            if looks_like_title:
                pdf.set_font("Helvetica", "B", 10)
            else:
                pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5, cleaned, new_x="LMARGIN", new_y="NEXT")

    out_filename = f"resume_{user_id}_{time.time_ns()}.pdf"
    out_path = os.path.join(RESUME_FOLDER, out_filename)
    pdf.output(out_path)
    return out_path


@app.route("/resume_history")
def resume_history():
    if session.get("user", {}).get("role") != "candidate":
        return "Access Denied", 403
    rows = fetchall("SELECT * FROM resumes WHERE user_id=%s ORDER BY uploaded_on DESC",
                    (session["user"]["id"],))
    return render_template("resume_history.html", resumes=rows)


@app.route("/set_active_resume/<resume_id>")
def set_active_resume(resume_id):
    uid = session["user"]["id"]
    execute("UPDATE resumes SET is_active=0 WHERE user_id=%s", (uid,))
    execute("UPDATE resumes SET is_active=1 WHERE resume_id=%s AND user_id=%s", (resume_id, uid))
    return redirect("/resume_history")


@app.route("/delete_resume/<resume_id>")
def delete_resume(resume_id):
    uid = session["user"]["id"]
    row = fetchone("SELECT * FROM resumes WHERE resume_id=%s AND user_id=%s", (resume_id, uid))
    if not row: return "Not found", 404
    if row["is_active"]: return "Cannot delete active resume", 400
    try: os.remove(os.path.join(RESUME_FOLDER, row["filename"]))
    except: pass
    execute("DELETE FROM resumes WHERE resume_id=%s", (resume_id,))
    return redirect("/resume_history")


@app.route("/resume_text/<resume_id>")
def resume_text(resume_id):
    """Return extracted text from the candidate's resume PDF."""
    if session.get("user", {}).get("role") != "candidate":
        return jsonify({"error": "Access Denied"}), 403
    user_id = session["user"]["id"]
    resume = fetchone("SELECT * FROM resumes WHERE resume_id=%s AND user_id=%s", (resume_id, user_id))
    if not resume:
        return jsonify({"error": "Resume not found"}), 404
    filepath = os.path.join(RESUME_FOLDER, resume["filename"])
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404
    text = extract_text_from_pdf(filepath)
    return jsonify({"text": text})


@app.route("/download_resume/<filename>")
def download_resume(filename):
    if "user" not in session: return "Unauthorized", 401
    user = session["user"]
    if user["role"] == "candidate":
        if not fetchone("SELECT id FROM resumes WHERE filename=%s AND user_id=%s", (filename, user["id"])):
            return "Unauthorized", 403
    return send_from_directory(RESUME_FOLDER, filename, as_attachment=True)

# ═══════════════════════════════════════════════════════════════
#  JOBS
# ═══════════════════════════════════════════════════════════════

@app.route("/jobs")
def jobs():
    if session.get("user", {}).get("role") != "candidate":
        return "Access Denied", 403
    rows = [_annotate_job_state(dict(job)) for job in fetchall("SELECT j.*, u.company_name FROM jobs j JOIN users u ON u.id=j.hr_id WHERE j.status='open' ORDER BY j.created_at DESC")]
    return render_template("jobs.html", jobs=rows)

@app.route("/job_details/<int:job_id>", methods=["GET"])
def job_details(job_id):
    if session.get("user", {}).get("role") != "candidate":
        return "Access Denied", 403
    job = fetchone("SELECT * FROM jobs WHERE id=%s", (job_id,))
    if not job:
        return "Job not found", 404
    is_closed = job.get("status") == "closed"
    company = fetchone("SELECT * FROM company WHERE hr_id=%s", (job["hr_id"],))
    analysis = None
    user_id = session["user"]["id"]
    # If resume analysis exists for this job/user, load it
    resume = fetchone("SELECT * FROM resumes WHERE user_id=%s AND is_active=1", (user_id,))
    if resume and resume.get("analysis_quality"):
        analysis = {
            "quality":     resume["analysis_quality"],
            "score":       resume["analysis_score"] or 0,
            "feedback":    json.loads(resume["analysis_feedback"] or "{}"),
            "suggestions": json.loads(resume["analysis_suggestions"] or "[]"),
        }
    already_applied = bool(fetchone("SELECT id FROM applications WHERE user_id=%s AND job_id=%s", (user_id, job_id)))
    return render_template("job_details.html", job=job, company=company, analysis=analysis, already_applied=already_applied, is_closed=is_closed)

@app.route("/upload_resume_for_job/<int:job_id>", methods=["POST"])
def upload_resume_for_job(job_id):
    if session.get("user", {}).get("role") != "candidate":
        return "Access Denied", 403
    job = fetchone("SELECT id, title, status FROM jobs WHERE id=%s", (job_id,))
    if not job:
        return "Job not found", 404
    if job.get("status") == "closed":
        return render_template("message.html", message="This job has been closed.")
    user_id = session["user"]["id"]
    f = request.files.get("resume")
    if f and f.filename.endswith(".pdf"):
        resume_id = str(uuid.uuid4())[:8]
        filename  = f"{user_id}_{time.time_ns()}.pdf"
        f.save(os.path.join(RESUME_FOLDER, filename))
        execute("UPDATE resumes SET is_active=0 WHERE user_id=%s", (user_id,))
        execute(
            """INSERT INTO resumes
               (resume_id,user_id,filename,is_active,analysis_quality,analysis_score,analysis_feedback,analysis_suggestions)
               VALUES (%s,%s,%s,1,NULL,NULL,NULL,NULL)""",
            (resume_id, user_id, filename)
        )
        # Run analysis and save to MySQL
        resume_text = extract_text_from_pdf(os.path.join(RESUME_FOLDER, filename))
        quality_result = check_resume_quality(resume_text[:4000])
        execute(
            """UPDATE resumes
               SET analysis_quality=%s, analysis_score=%s,
                   analysis_feedback=%s, analysis_suggestions=%s
               WHERE resume_id=%s""",
            (
                quality_result.get("quality", "unknown"),
                int(quality_result.get("score", 0)),
                json.dumps(quality_result.get("feedback", {})),
                json.dumps(quality_result.get("suggestions", [])),
                resume_id,
            )
        )
    return redirect(f"/job_details/{job_id}")
@app.route("/search_jobs", methods=["GET"])
def search_jobs():
    """Search jobs by title, company, or skills"""
    if session.get("user", {}).get("role") != "candidate":
        return jsonify({"error": "Access Denied"}), 403
    
    query = request.args.get("q", "").strip().lower()
    if not query:
        return jsonify({"jobs": []})
    
    # Search across job title, company name, and skills
    rows = fetchall("""
        SELECT j.*, u.company_name FROM jobs j 
        JOIN users u ON u.id=j.hr_id 
                WHERE j.status='open'
                    AND (LOWER(j.title) LIKE %s 
                     OR LOWER(u.company_name) LIKE %s 
                     OR LOWER(j.skills) LIKE %s)
        ORDER BY j.created_at DESC
    """, (f"%{query}%", f"%{query}%", f"%{query}%"))
    
    jobs_data = []
    for row in rows:
        row = dict(row)
        jobs_data.append(row)
    
    return jsonify({"jobs": jobs_data})


@app.route("/apply_job/<int:job_id>", methods=["POST"])
def apply_job(job_id):
    if "user" not in session or session["user"]["role"] != "candidate":
        return "Access Denied", 403
    uid = session["user"]["id"]
    try:
        exp  = int(request.form["experience"])
        t10  = int(request.form["tenth"])
        t12  = int(request.form["twelfth"])
        grad = int(request.form["graduation"])
    except (KeyError, ValueError):
        return render_template("message.html", message="Please enter valid numeric values.")

    job = fetchone("SELECT * FROM jobs WHERE id=%s", (job_id,))
    if not job: return "Job not found", 404
    if job.get("status") == "closed":
        return render_template("message.html", message="This job has been closed.")

    if not (job["min_exp"] <= exp <= job["max_exp"]):
        return render_template("message.html", message=f"Experience must be {job['min_exp']}–{job['max_exp']} years.")
    if t10 < job["min_10"]:  return render_template("message.html", message=f"Min 10th %: {job['min_10']}%")
    if t12 < job["min_12"]:  return render_template("message.html", message=f"Min 12th %: {job['min_12']}%")
    if grad < job["min_grad"]: return render_template("message.html", message=f"Min Grad %: {job['min_grad']}%")
    if fetchone("SELECT id FROM applications WHERE user_id=%s AND job_id=%s", (uid, job_id)):
        return render_template("message.html", message="You already applied for this job.")

    app_id = str(uuid.uuid4())
    execute("INSERT INTO applications (id,user_id,job_id,job_title,experience,tenth,twelfth,graduation) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (app_id, uid, job_id, job["title"], exp, t10, t12, grad))
    
    # Send email to candidate
    user = session["user"]
    _safe_send(user["email"], f"Application Submitted – {job['title']}",
               f"Hi {user['name']},\n\nYour application for {job['title']} has been submitted successfully.\n\nWe will notify you about the next steps.\n\nAI Recruitment Team")
    
    # Send email to HR
    hr = fetchone("SELECT email, name FROM users WHERE id=%s", (job["hr_id"],))
    if hr:
        send_hr_new_application_email(hr["email"], hr["name"], user["name"], job["title"], user["email"])
    
    threading.Thread(target=_run_gap_analysis, args=(uid, job_id, app_id), daemon=True).start()
    return redirect("/dashboard")


@app.route("/applied_jobs")
def applied_jobs():
    if session.get("user", {}).get("role") != "candidate":
        return "Access Denied", 403
    rows = fetchall("SELECT a.*,j.title AS job_title FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.user_id=%s ORDER BY a.applied_at DESC",
                    (session["user"]["id"],))
    return render_template("applied_jobs.html", jobs=rows)

# ═══════════════════════════════════════════════════════════════
#  MOCK INTERVIEW
# ═══════════════════════════════════════════════════════════════

@app.route("/start_interview")
def start_interview():
    if session.get("user", {}).get("role") != "candidate": return "Access Denied"
    uid    = session["user"]["id"]
    resume = fetchone("SELECT * FROM resumes WHERE user_id=%s AND is_active=1", (uid,))
    if not resume: return redirect("/upload_resume")
    txt    = extract_text_from_pdf(os.path.join(RESUME_FOLDER, resume["filename"]))
    skills = extract_skills_from_resume(txt) or ["python"]
    qs     = generate_questions(skills)
    session["questions"] = qs
    return render_template("interview.html", questions=qs)


@app.route("/submit_interview", methods=["POST"])
def submit_interview():
    if session.get("user", {}).get("role") != "candidate": return "Access Denied"
    qs = session.get("questions", [])
    if not qs: return redirect("/start_interview")
    answers = [request.form.get(f"answer_{i}", "").strip() for i in range(len(qs))]
    score, weak, readiness = evaluate_answers(qs, answers)
    uid = session["user"]["id"]
    execute("DELETE FROM interviews WHERE user_id=%s", (uid,))
    execute("INSERT INTO interviews (user_id,score,weak_areas,readiness) VALUES (%s,%s,%s,%s)",
            (uid, score, json.dumps(weak), readiness))
    session.pop("questions", None)
    return render_template("interview_result.html", score=score, weak_areas=weak, readiness=readiness)


@app.route("/my_interviews")
def my_interviews():
    if session.get("user", {}).get("role") != "candidate": return "Access Denied"
    uid      = session["user"]["id"]
    iviews   = fetchall("SELECT * FROM interviews WHERE user_id=%s ORDER BY taken_at DESC", (uid,))
    schedule = fetchone("SELECT * FROM scheduled_interviews WHERE user_id=%s", (uid,))
    for i in iviews:
        if isinstance(i.get("weak_areas"), str):
            try:    i["weak_areas"] = json.loads(i["weak_areas"])
            except: i["weak_areas"] = []
    return render_template("my_interviews.html", interviews=iviews, schedule=schedule)

# ═══════════════════════════════════════════════════════════════
#  APTITUDE
# ═══════════════════════════════════════════════════════════════

@app.route("/aptitude_test")
def aptitude_test():
    if "user" not in session: return redirect("/")
    uid = session["user"]["id"]
    active_app = fetchone("""
        SELECT a.*,j.hr_id FROM applications a JOIN jobs j ON j.id=a.job_id
        WHERE a.user_id=%s AND a.aptitude_required=1 AND a.aptitude_status='pending' LIMIT 1
    """, (uid,))
    if not active_app:
        return render_template("message.html", message="No pending aptitude test was found for your applications.")

    level = _exp_to_level(active_app["experience"])

    hr_qs = fetchall("SELECT * FROM company_questions WHERE hr_id=%s AND category='aptitude' AND level=%s AND is_hidden=0",
                     (active_app["hr_id"], level))
    hr_formatted = [{"id": str(r["id"]), "question": r["question"],
                     "options": r["options"] if isinstance(r["options"], list) else json.loads(r["options"] or "[]"),
                     "answer": r["answer"]} for r in hr_qs]

    # Try Groq API first, then hardcoded fallback — questions are ALWAYS available
    ai_qs = get_ai_aptitude(level, count=10)
    if not ai_qs:
        ai_qs = _FALLBACK_APTITUDE.get(level, _FALLBACK_APTITUDE["easy"])

    questions = (hr_formatted + ai_qs)[:10]

    # Final safety net — should never hit this with fallbacks in place
    if not questions:
        questions = _FALLBACK_APTITUDE["easy"]

    session["aptitude_app_id"] = active_app["id"]
    return render_template("aptitude_test.html", questions=questions, level=level, job_id=active_app["job_id"])


@app.route("/submit_aptitude", methods=["POST"])
def submit_aptitude():
    user = session.get("user")
    if not user: return redirect("/")
    uid    = user["id"]
    job_id = int(request.form.get("job_id"))
    appn   = fetchone("SELECT a.*,j.hr_id FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.user_id=%s AND a.job_id=%s",
                      (uid, job_id))
    if not appn: return "Application not found", 404

    level = _exp_to_level(appn["experience"])   # BUG FIX: re-calculate, not from session
    hr_qs = fetchall("SELECT * FROM company_questions WHERE hr_id=%s AND category='aptitude' AND level=%s AND is_hidden=0",
                     (appn["hr_id"], level))
    hr_formatted = [{"id": str(r["id"]), "answer": r["answer"]} for r in hr_qs]
    ai_qs = get_ai_aptitude(level, count=10)
    if not ai_qs:
        ai_qs = _FALLBACK_APTITUDE.get(level, _FALLBACK_APTITUDE["easy"])
    all_qs = (hr_formatted + [{"id": q["id"], "answer": q["answer"]} for q in ai_qs])[:10]

    score = sum(1 for q in all_qs if request.form.get(str(q["id"])) == q["answer"])
    total = len(all_qs)
    pct   = round((score / total) * 100, 2) if total else 0

    if pct >= 70:
        decision = "auto_tech"
        execute("""UPDATE applications SET aptitude_required=0,aptitude_status='completed',
            aptitude_score=%s,aptitude_total=%s,aptitude_percentage=%s,
            tech_round=1,tech_status='pending',tech_completed=0,status='tech_enabled' WHERE id=%s""",
            (score, total, pct, appn["id"]))
        send_tech_round_email(user["email"], user["name"])
        # Send candidate email about aptitude completion
        send_candidate_aptitude_completed_email(user["email"], user["name"], score, total, pct)
    else:
        decision = "hr_review"
        execute("""UPDATE applications SET aptitude_required=0,aptitude_status='completed',
            aptitude_score=%s,aptitude_total=%s,aptitude_percentage=%s,
            tech_round=0,tech_status='waiting_hr',status='hr_review' WHERE id=%s""",
            (score, total, pct, appn["id"]))
        # Send candidate email about aptitude completion
        send_candidate_aptitude_completed_email(user["email"], user["name"], score, total, pct)

    execute("INSERT INTO aptitude_results (user_id,job_id,application_id,level,score,total,percentage,decision) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (uid, job_id, appn["id"], level, score, total, pct, decision))

    # Send email to HR about aptitude completion
    hr = fetchone("SELECT email, name FROM users WHERE id=%s", (appn["hr_id"],))
    if hr:
        send_hr_aptitude_completed_email(hr["email"], hr["name"], user["name"], appn["job_title"], score, total, pct)

    result = {"name": user["name"], "email": user["email"], "level": level,
              "score": score, "total": total, "percentage": pct, "decision": decision}
    return render_template("aptitude_result.html", result=result)


@app.route("/aptitude_history")
def aptitude_history():
    if session.get("user", {}).get("role") != "candidate": return "Access Denied"
    rows = fetchall("SELECT * FROM aptitude_results WHERE user_id=%s ORDER BY taken_at DESC",
                    (session["user"]["id"],))
    return render_template("aptitude_history.html", history=rows)

# ═══════════════════════════════════════════════════════════════
#  TECH ROUND
# ═══════════════════════════════════════════════════════════════

@app.route("/tech_round/<app_id>")
def tech_round(app_id):
    if "user" not in session or session["user"]["role"] != "candidate": return "Access Denied", 403
    uid  = session["user"]["id"]
    appn = fetchone("SELECT a.*,j.hr_id FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.id=%s AND a.user_id=%s AND a.tech_status='pending'",
                    (app_id, uid))
    if not appn: return "Tech round not available", 403

    level = _exp_to_level(appn["experience"])
    execute("UPDATE applications SET tech_started=1,tech_level=%s WHERE id=%s", (level, app_id))

    hr_id = appn["hr_id"]
    hr_mcq_rows  = fetchall("SELECT * FROM company_questions WHERE hr_id=%s AND category='tech_mcq'  AND level=%s AND is_hidden=0", (hr_id, level))
    hr_code_rows = fetchall("SELECT * FROM company_questions WHERE hr_id=%s AND category='tech_coding' AND level=%s AND is_hidden=0", (hr_id, level))

    def fmt(rows):
        return [{"id": str(r["id"]), "question": r["question"],
                 "options": r["options"] if isinstance(r["options"], list) else json.loads(r["options"] or "[]"),
                 "answer": r["answer"]} for r in rows]

    # Merge: HR custom questions (MySQL) take priority, AI fills remaining slots
    default_mcqs   = get_ai_tech_mcq(level, count=8)
    if not default_mcqs:
        default_mcqs = _FALLBACK_MCQ.get(level, _FALLBACK_MCQ["easy"])

    default_coding = get_ai_tech_coding(level, count=3)
    if not default_coding:
        default_coding = _FALLBACK_CODING.get(level, _FALLBACK_CODING["easy"])

    mcqs   = (fmt(hr_mcq_rows)   + default_mcqs)[:5]
    coding = (list(hr_code_rows) + default_coding)[:3]
    return render_template("tech_round.html", mcqs=mcqs, coding=coding, application=appn, level=level)


@app.route("/run_code", methods=["POST"])
def run_code():
    code = request.json.get("code", "")
    try:
        local_env     = {}
        safe_builtins = {"range": range, "len": len, "int": int, "str": str, "list": list, "sum": sum}
        exec(code, {"__builtins__": safe_builtins}, local_env)
        if "solution" not in local_env: return {"output": "Function solution() not found"}
        fn = local_env["solution"]
        result = None
        for arg in [5, "hello", [1, 2, 3]]:
            try: result = fn(arg); break
            except: pass
        return {"output": f"Output: {result}"}
    except Exception as e:
        return {"output": f"Error: {str(e)}"}


@app.route("/submit_tech_round", methods=["POST"])
def submit_tech_round():
    if "user" not in session or session["user"]["role"] != "candidate": return "Access Denied", 403
    user   = session["user"]
    app_id = request.form["app_id"]
    appn   = fetchone("SELECT * FROM applications WHERE id=%s AND user_id=%s", (app_id, user["id"]))
    if not appn: return "Not found", 404

    level = appn.get("tech_level") or _exp_to_level(appn["experience"])   # BUG FIX
    hr_id = fetchone("SELECT hr_id FROM jobs WHERE id=%s", (appn["job_id"],))["hr_id"]
    hr_mcq_rows = fetchall("SELECT * FROM company_questions WHERE hr_id=%s AND category='tech_mcq' AND level=%s AND is_hidden=0",
                           (hr_id, level))
    hr_mcq = [{"id": str(r["id"]), "question": r["question"],
               "options": r["options"] if isinstance(r["options"], list) else json.loads(r["options"] or "[]"),
               "answer": r["answer"]} for r in hr_mcq_rows]
    # Use same merge as tech_round — cached AI questions so scoring always matches
    default_mcqs = get_ai_tech_mcq(level, count=8)
    if not default_mcqs:
        default_mcqs = _FALLBACK_MCQ.get(level, _FALLBACK_MCQ["easy"])
    tech_mcq = (hr_mcq + default_mcqs)[:5]

    mcq_results = [{"question": q["question"],
                    "selected_answer": request.form.get(f"mcq_{q['id']}"),
                    "correct_answer":  q["answer"],
                    "is_correct": request.form.get(f"mcq_{q['id']}") == q["answer"]}
                   for q in tech_mcq]

    try:    coding_results = json.loads(request.form.get("coding_data", "[]"))
    except: coding_results = []

    score  = sum(5  for m in mcq_results    if m["is_correct"])
    score += sum(10 for c in coding_results if c and c.get("passed"))

    execute("INSERT INTO tech_results (application_id,user_id,candidate_name,mcq_results,coding_results,final_score) VALUES (%s,%s,%s,%s,%s,%s)",
            (app_id, user["id"], user["name"], json.dumps(mcq_results), json.dumps(coding_results), score))
    execute("UPDATE applications SET tech_completed=1,status='waiting_hr' WHERE id=%s", (app_id,))
    
    # Send email to candidate about tech round completion
    _safe_send(user["email"], "Technical Round Submitted",
               f"Hi {user['name']},\n\nYour technical round has been submitted successfully.\n\nScore: {score}/100\n\nWe will notify you about the next steps.\n\nAI Recruitment Team")
    
    # Send email to HR about tech round completion
    appn = fetchone("SELECT a.job_title, j.hr_id FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.id=%s", (app_id,))
    if appn:
        hr = fetchone("SELECT email, name FROM users WHERE id=%s", (appn["hr_id"],))
        if hr:
            send_hr_tech_completed_email(hr["email"], hr["name"], user["name"], appn["job_title"], score)
    
    return redirect("/dashboard")

# ═══════════════════════════════════════════════════════════════
#  HR
# ═══════════════════════════════════════════════════════════════

@app.route("/hr_dashboard")
def hr_dashboard():
    if session.get("user", {}).get("role") != "hr": return "Access Denied"
    jobs = [_annotate_job_state(dict(job)) for job in fetchall("SELECT * FROM jobs WHERE hr_id=%s ORDER BY created_at DESC", (session["user"]["id"],))]
    return render_template("hr_dashboard.html", jobs=jobs)


@app.route("/post_job", methods=["GET", "POST"])
def post_job():
    if session.get("user", {}).get("role") != "hr": return "Access Denied"
    if request.method == "POST":
        deadline_raw = request.form.get("deadline", "").strip()
        deadline = deadline_raw if deadline_raw else None
        execute(
            "INSERT INTO jobs (hr_id,title,description_full,skills,min_exp,max_exp,min_10,min_12,min_grad,min_salary,max_salary,deadline) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                session["user"]["id"],
                request.form["title"],
                request.form["description_full"],
                request.form["skills"].lower(),
                int(request.form["min_exp"]),
                int(request.form["max_exp"]),
                int(request.form["min_10"]),
                int(request.form["min_12"]),
                int(request.form["min_grad"]),
                int(request.form["min_salary"]),
                int(request.form["max_salary"]),
                deadline,
            )
        )
        # Send new job notification to all registered candidates
        job_title   = request.form["title"]
        skills      = request.form["skills"]
        company     = session["user"].get("company_name") or session["user"]["name"]
        deadline_str = f"Apply by: {deadline_raw}" if deadline_raw else "Open until filled"
        candidates  = fetchall("SELECT email, name FROM users WHERE role='candidate'")

        hr_email = session["user"].get("email")
        hr_name = session["user"].get("name", "HR")
        posted_on = _format_dt(datetime.now())
        threading.Thread(
            target=send_hr_job_posted_email,
            args=(hr_email, hr_name, job_title, company, posted_on, deadline_str),
            daemon=True,
        ).start()

        def _notify_candidates(candidates, job_title, company, skills, deadline_str):
            for c in candidates:
                _safe_send(
                    c["email"],
                    f"New Job Opening: {job_title} at {company}",
                    f"Hi {c['name']},\n\n"
                    f"A new job has been posted that matches your profile!\n\n"
                    f"Position : {job_title}\n"
                    f"Company  : {company}\n"
                    f"Skills   : {skills}\n"
                    f"{deadline_str}\n\n"
                    f"Log in to HireAI to view full details and apply:\n"
                    f"http://Samarth1009.pythonanywhere.com/jobs\n\n"
                    f"Best of luck!\nHireAI Team"
                )
        threading.Thread(target=_notify_candidates,
                         args=(candidates, job_title, company, skills, deadline_str),
                         daemon=True).start()
        return redirect("/hr_dashboard")
    today = datetime.now().strftime("%Y-%m-%d")
    now   = datetime.now().strftime("%d %b %Y")
    return render_template("post_job.html", today=today, now=now)


@app.route("/hr_my_jobs")
def hr_my_jobs():
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    jobs = [_annotate_job_state(dict(job)) for job in fetchall("SELECT * FROM jobs WHERE hr_id=%s ORDER BY created_at DESC", (session["user"]["id"],))]
    return render_template("hr_my_jobs.html", jobs=jobs)


@app.route("/hr_close_job/<int:job_id>", methods=["POST"])
def hr_close_job(job_id):
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    hr_id = session["user"]["id"]
    job = fetchone("SELECT * FROM jobs WHERE id=%s AND hr_id=%s", (job_id, hr_id))
    if not job:
        return "Not found", 404
    if job.get("status") == "closed":
        return redirect("/hr_my_jobs")

    execute("UPDATE jobs SET status='closed', closed_at=NOW() WHERE id=%s AND hr_id=%s", (job_id, hr_id))

    hr_email = session["user"].get("email")
    hr_name = session["user"].get("name", "HR")
    company = session["user"].get("company_name") or session["user"].get("name") or "Your company"
    posted_on = _format_dt(job.get("created_at"))
    closed_on = _format_dt(datetime.now())
    threading.Thread(
        target=send_hr_job_closed_email,
        args=(hr_email, hr_name, job.get("title"), company, posted_on, closed_on),
        daemon=True,
    ).start()
    return redirect("/hr_my_jobs")


@app.route("/hr_delete_job/<int:job_id>", methods=["POST"])
def hr_delete_job(job_id):
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    execute("DELETE FROM jobs WHERE id=%s AND hr_id=%s", (job_id, session["user"]["id"]))
    return redirect("/hr_my_jobs")


@app.route("/hr_edit_job/<int:job_id>", methods=["GET", "POST"])
def hr_edit_job(job_id):
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    hr_id = session["user"]["id"]
    job   = fetchone("SELECT * FROM jobs WHERE id=%s AND hr_id=%s", (job_id, hr_id))
    if not job: return "Not found", 404
    if request.method == "POST":
        execute("UPDATE jobs SET title=%s,skills=%s,min_exp=%s,max_exp=%s,min_10=%s,min_12=%s,min_grad=%s,min_salary=%s,max_salary=%s WHERE id=%s AND hr_id=%s",
                (request.form["title"], request.form["skills"],
                 int(request.form["min_exp"]), int(request.form["max_exp"]),
                 int(request.form["min_10"]), int(request.form["min_12"]), int(request.form["min_grad"]),
                 int(request.form["min_salary"]), int(request.form["max_salary"]),
                 job_id, hr_id))
        return redirect("/hr_my_jobs")
    return render_template("hr_edit_job.html", job=job)


@app.route("/hr_applications")
@app.route("/hr_applications/<int:job_id>")
def hr_applications_all(job_id=None):
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    hr_id = session["user"]["id"]
    base  = """SELECT a.*,u.name AS candidate,u.email,j.title AS job_title,
                 (SELECT filename FROM resumes WHERE user_id=a.user_id AND is_active=1 LIMIT 1) AS resume_filename
               FROM applications a JOIN users u ON u.id=a.user_id JOIN jobs j ON j.id=a.job_id
               WHERE j.hr_id=%s"""
    if job_id:
        rows = fetchall(base + " AND a.job_id=%s ORDER BY a.applied_at DESC", (hr_id, job_id))
    else:
        rows = fetchall(base + " ORDER BY a.applied_at DESC", (hr_id,))
    return render_template("hr_applications.html", applications=rows)


@app.route("/assign_aptitude/<app_id>")
def assign_aptitude(app_id):
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    appn = fetchone("SELECT a.*,u.email,u.name FROM applications a JOIN users u ON u.id=a.user_id WHERE a.id=%s", (app_id,))
    if not appn: return "Not found", 404
    execute("UPDATE applications SET aptitude_required=1,aptitude_status='pending' WHERE id=%s", (app_id,))
    send_aptitude_invite_email(appn["email"], appn["name"], appn["job_title"])
    return redirect("/hr_applications")


@app.route("/hr_direct_decision/<app_id>/<decision>")
def hr_direct_decision(app_id, decision):
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    if decision not in ["shortlisted","rejected"]: return "Invalid", 400
    appn = fetchone("SELECT a.*,u.email,u.name FROM applications a JOIN users u ON u.id=a.user_id WHERE a.id=%s", (app_id,))
    if not appn: return "Not found", 404
    if decision == "shortlisted":
        execute("UPDATE applications SET status='shortlisted',aptitude_required=0,aptitude_status='completed',tech_round=1,tech_status='pending' WHERE id=%s", (app_id,))
    else:
        execute("UPDATE applications SET status='rejected',aptitude_required=0,aptitude_status='completed',tech_round=0,tech_status='rejected' WHERE id=%s", (app_id,))
    send_hr_decision_email(appn["email"], appn["name"], decision, appn["job_title"])
    return redirect("/hr_applications")


@app.route("/hr_aptitude_decision/<app_id>/<decision>")
def hr_aptitude_decision(app_id, decision):
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    if decision not in ["shortlisted","rejected"]: return "Invalid", 400
    appn = fetchone("SELECT a.*,u.email,u.name FROM applications a JOIN users u ON u.id=a.user_id WHERE a.id=%s", (app_id,))
    if not appn: return "Not found", 404
    execute("UPDATE applications SET status=%s WHERE id=%s", (decision, app_id))
    if decision == "shortlisted":
        execute("UPDATE applications SET tech_round=1,tech_status='pending' WHERE id=%s", (app_id,))
        send_tech_round_email(appn["email"], appn["name"])
    execute("UPDATE aptitude_results SET decision=%s WHERE application_id=%s",
            ("tech" if decision == "shortlisted" else "rejected", app_id))
    return redirect("/hr_applications")


@app.route("/hr_aptitude")
def hr_aptitude():
    if session.get("user", {}).get("role") != "hr": return "Access Denied"
    rows = fetchall("SELECT DISTINCT u.id,u.name,u.email FROM aptitude_results ar JOIN users u ON u.id=ar.user_id ORDER BY u.name")
    return render_template("hr_aptitude_list.html", candidates=rows)


@app.route("/hr_aptitude/<int:user_id>")
@app.route("/hr_aptitude_view/<int:user_id>")
def hr_view_aptitude(user_id):
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    u      = fetchone("SELECT * FROM users WHERE id=%s", (user_id,))
    result = fetchone("SELECT * FROM aptitude_results WHERE user_id=%s ORDER BY taken_at DESC LIMIT 1", (user_id,))
    if not result: return "No aptitude result"
    appn   = fetchone("SELECT * FROM applications WHERE id=%s", (result["application_id"],))
    job    = fetchone("SELECT title FROM jobs WHERE id=%s", (appn["job_id"],)) if appn else None
    return render_template("hr_aptitude_view.html", user=u, result=result, application=appn,
                           job_title=job["title"] if job else "N/A")


@app.route("/hr_aptitude_results")
def hr_aptitude_results():
    if session.get("user", {}).get("role") != "hr": return "Access Denied"
    rows = fetchall("SELECT u.name,u.email,ar.level,ar.score,ar.total,ar.percentage,ar.decision,ar.taken_at FROM aptitude_results ar JOIN users u ON u.id=ar.user_id ORDER BY ar.taken_at DESC")
    return render_template("hr_aptitude_results.html", history=rows)


@app.route("/hr_aptitude_history")
def hr_aptitude_history():
    if session.get("user", {}).get("role") != "hr": return redirect("/dashboard")
    rows = fetchall("SELECT u.name,u.email,ar.level,ar.score,ar.total,ar.percentage,ar.decision,ar.taken_at FROM aptitude_results ar JOIN users u ON u.id=ar.user_id ORDER BY ar.taken_at DESC")
    return render_template("hr_aptitude_history.html", results=rows)


@app.route("/hr_select_tech/<application_id>")
def hr_select_tech(application_id):
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    appn = fetchone("SELECT a.*,u.email,u.name FROM applications a JOIN users u ON u.id=a.user_id WHERE a.id=%s", (application_id,))
    if not appn: return "Not found", 404
    execute("UPDATE applications SET tech_round=1,tech_status='pending',tech_completed=0,status='tech_enabled' WHERE id=%s", (application_id,))
    execute("UPDATE aptitude_results SET decision='tech_approved' WHERE application_id=%s", (application_id,))
    send_tech_round_email(appn["email"], appn["name"])
    return redirect("/hr_aptitude")


@app.route("/hr_tech_submissions")
def hr_tech_submissions():
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    hr_id = session["user"]["id"]
    rows  = fetchall("""
        SELECT tr.*,u.email,j.title AS job_title,a.status,a.hr_date,a.hr_time
        FROM tech_results tr
        JOIN users u ON u.id=tr.user_id
        JOIN applications a ON a.id=tr.application_id
        JOIN jobs j ON j.id=a.job_id
        WHERE j.hr_id=%s ORDER BY tr.submitted_at DESC
    """, (hr_id,))
    results = []
    for r in rows:
        r = dict(r)
        r["mcq_results"]    = r["mcq_results"]    if isinstance(r["mcq_results"],    list) else json.loads(r["mcq_results"]    or "[]")
        r["coding_results"] = r["coding_results"] if isinstance(r["coding_results"], list) else json.loads(r["coding_results"] or "[]")
        results.append(r)
    return render_template("hr_tech_submissions.html", results=results)


@app.route("/hr_tech_decision/<app_id>/<decision>")
def hr_tech_decision(app_id, decision):
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    if decision not in ["shortlisted","rejected"]: return "Invalid", 400
    execute("UPDATE tech_results SET hr_decision=%s WHERE application_id=%s", (decision, app_id))
    if decision == "rejected":
        execute("UPDATE applications SET status='rejected',tech_status='rejected',tech_completed=1 WHERE id=%s", (app_id,))
        return redirect("/hr_tech_submissions")
    execute("UPDATE applications SET status='tech_shortlisted',tech_status='shortlisted',tech_completed=1 WHERE id=%s", (app_id,))
    return redirect(f"/hr_schedule_round/{app_id}")


@app.route("/hr_schedule_round/<app_id>", methods=["GET", "POST"])
def hr_schedule_round(app_id):
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    appn = fetchone("SELECT a.*,u.email,u.name FROM applications a JOIN users u ON u.id=a.user_id WHERE a.id=%s", (app_id,))
    if not appn: return "Not found", 404
    if request.method == "POST":
        date    = request.form.get("date")
        time_24 = request.form.get("time")
        if not date or not time_24: return "Date and time required", 400
        time_fmt = datetime.strptime(time_24, "%H:%M").strftime("%I:%M %p")
        execute("UPDATE applications SET status='hr_scheduled',tech_status='scheduled',tech_completed=1,hr_scheduled=1,hr_date=%s,hr_time=%s WHERE id=%s",
                (date, time_fmt, app_id))
        existing = fetchone("SELECT id FROM scheduled_interviews WHERE user_id=%s", (appn["user_id"],))
        if existing:
            execute("UPDATE scheduled_interviews SET job_title=%s,date=%s,time=%s WHERE user_id=%s",
                    (appn["job_title"], date, time_fmt, appn["user_id"]))
        else:
            execute("INSERT INTO scheduled_interviews (user_id,job_title,date,time) VALUES (%s,%s,%s,%s)",
                    (appn["user_id"], appn["job_title"], date, time_fmt))
        send_schedule_email(appn["email"], appn["name"], appn["job_title"], date, time_fmt)
        return redirect("/hr_tech_submissions")
    return render_template("hr_schedule_round.html", application=appn, candidate=appn)


@app.route("/hr_interviews")
def hr_interviews():
    if session.get("user", {}).get("role") != "hr": return "Access Denied"
    rows = fetchall("""
        SELECT i.*,u.name,u.email,
               s.date AS sched_date,s.time AS sched_time,s.mode AS sched_mode
        FROM interviews i JOIN users u ON u.id=i.user_id
        LEFT JOIN scheduled_interviews s ON s.user_id=i.user_id
        ORDER BY i.taken_at DESC
    """)
    reports = []
    for r in rows:
        r = dict(r)
        if isinstance(r.get("weak_areas"), str):
            try: r["weak_areas"] = json.loads(r["weak_areas"])
            except: r["weak_areas"] = []
        reports.append(r)
    return render_template("hr_interviews.html", interviews=reports)


@app.route("/hr_decision/<int:user_id>/<decision>")
def hr_decision(user_id, decision):
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    execute("UPDATE interviews SET hr_decision=%s,readiness=%s WHERE user_id=%s",
            (decision, "Ready" if decision == "shortlisted" else "Not Ready", user_id))
    return "OK", 200


@app.route("/hr_history")
def hr_history():
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    rows = fetchall("""
        SELECT a.*,u.name,u.email FROM applications a
        JOIN users u ON u.id=a.user_id JOIN jobs j ON j.id=a.job_id
        WHERE j.hr_id=%s AND a.status IN ('shortlisted','rejected','hr_scheduled')
        ORDER BY a.applied_at DESC
    """, (session["user"]["id"],))
    return render_template("hr_history.html", history=rows)


# ── Question Management ───────────────────────────────────────

@app.route("/hr_manage_questions")
def hr_manage_questions():
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    hr_id = session["user"]["id"]

    def load_category(category):
        result = {}
        for lvl in ["easy", "medium", "hard"]:
            rows = fetchall("SELECT * FROM company_questions WHERE hr_id=%s AND category=%s AND level=%s",
                            (hr_id, category, lvl))
            result[lvl] = [{"id": str(r["id"]), "question": r["question"],
                             "options": r["options"] if isinstance(r["options"], list) else json.loads(r["options"] or "[]"),
                             "answer": r["answer"]} for r in rows]
        return result

    aptitude    = load_category("aptitude")
    tech_mcq    = load_category("tech_mcq")
    tech_coding = {}
    for lvl in ["easy", "medium", "hard"]:
        tech_coding[lvl] = list(fetchall(
            "SELECT * FROM company_questions WHERE hr_id=%s AND category='tech_coding' AND level=%s",
            (hr_id, lvl)))

    return render_template("hr_manage_questions.html", aptitude=aptitude, tech_mcq=tech_mcq, tech_coding=tech_coding)


@app.route("/hr_add_aptitude_question", methods=["GET","POST"])
def hr_add_aptitude_question():
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    if request.method == "POST":
        opts = [o.strip() for o in request.form.get("options","").split(",")]
        execute("INSERT INTO company_questions (hr_id,category,level,question,options,answer) VALUES (%s,'aptitude',%s,%s,%s,%s)",
                (session["user"]["id"], request.form["level"], request.form["question"], json.dumps(opts), request.form["answer"]))
        return redirect("/hr_manage_questions")
    return render_template("hr_add_aptitude_question.html")


@app.route("/hr_add_tech_mcq", methods=["GET","POST"])
def hr_add_tech_mcq():
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    if request.method == "POST":
        opts = [o.strip() for o in request.form.get("options","").split(",")]
        execute("INSERT INTO company_questions (hr_id,category,level,question,options,answer) VALUES (%s,'tech_mcq',%s,%s,%s,%s)",
                (session["user"]["id"], request.form["level"], request.form["question"], json.dumps(opts), request.form["answer"]))
        return redirect("/hr_manage_questions")
    return render_template("hr_add_tech_mcq.html")


@app.route("/hr_add_coding_question", methods=["GET","POST"])
def hr_add_coding_question():
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    if request.method == "POST":
        execute("INSERT INTO company_questions (hr_id,category,level,question,input_format,output_format,constraints,sample_input,sample_output) VALUES (%s,'tech_coding',%s,%s,%s,%s,%s,%s,%s)",
                (session["user"]["id"], request.form["level"], request.form["question"],
                 request.form.get("input_format"), request.form.get("output_format"),
                 request.form.get("constraints"), request.form.get("sample_input"), request.form.get("sample_output")))
        return redirect("/hr_manage_questions")
    return render_template("hr_add_coding_question.html")


@app.route("/hr_refresh_ai_questions", methods=["POST"])
def hr_refresh_ai_questions():
    """HR-only: clears the AI question cache so fresh questions are generated from Groq on next test."""
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    category = request.form.get("category", "all")
    level    = request.form.get("level", "all")
    refresh_ai_questions(category=category, level=level)
    return jsonify({"status": "ok", "message": f"AI questions refreshed for category='{category}' level='{level}'. New questions will be generated from Groq on the next test."})


@app.route("/debug_ai_questions")
def debug_ai_questions():
    """Debug route — visit in browser to test Groq connection and see generated questions."""
    if not app.debug:
        return "Only available in debug mode", 403
    results = {}
    for level in ["easy", "medium", "hard"]:
        refresh_ai_questions("all", level)   # clear cache to force fresh call
        mcqs    = get_ai_tech_mcq(level)
        coding  = get_ai_tech_coding(level)
        aptitude = get_ai_aptitude(level)
        results[level] = {
            "tech_mcq_count":    len(mcqs),
            "tech_coding_count": len(coding),
            "aptitude_count":    len(aptitude),
            "tech_mcq_sample":   mcqs[0]["question"]    if mcqs    else "NONE",
            "coding_sample":     coding[0]["question"]  if coding  else "NONE",
            "aptitude_sample":   aptitude[0]["question"] if aptitude else "NONE",
        }
    return jsonify(results)


@app.route("/hr_delete_question", methods=["POST"])
def hr_delete_question():
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    execute("DELETE FROM company_questions WHERE id=%s AND hr_id=%s",
            (request.form["question_id"], session["user"]["id"]))
    return redirect("/hr_manage_questions")


@app.route("/hr_hide_default_question", methods=["POST"])
def hr_hide_default_question():
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    execute("INSERT IGNORE INTO hr_hidden_defaults (hr_id,question_type,level,question_id) VALUES (%s,%s,%s,%s)",
            (session["user"]["id"], request.form["question_type"], request.form["level"], str(request.form["question_id"])))
    return redirect("/hr_manage_questions")


@app.route("/hr_unhide_default_question", methods=["POST"])
def hr_unhide_default_question():
    if session.get("user", {}).get("role") != "hr": return "Access Denied", 403
    execute("DELETE FROM hr_hidden_defaults WHERE hr_id=%s AND question_type=%s AND level=%s AND question_id=%s",
            (session["user"]["id"], request.form["question_type"], request.form["level"], request.form["question_id"]))
    return redirect("/hr_manage_questions")


@app.route("/test_email")
def test_email():
    try:
        send_email(SMTP_EMAIL, "SMTP Test", "SMTP is working!")
        return "SMTP WORKING"
    except Exception as e:
        return f"SMTP FAILED: {e}"

# ═══════════════════════════════════════════════════════════════
#  PROCTORING
# ═══════════════════════════════════════════════════════════════

@app.route("/log_violation", methods=["POST"])
def log_violation():
    """Candidate browser logs a proctoring event (tab switch, key block, etc.)"""
    if "user" not in session:
        return jsonify({"ok": False}), 403
    user = session["user"]
    data = request.get_json() or {}
    execute(
        "INSERT INTO proctoring_logs (user_id, application_id, test_type, event_type, snapshot_b64) "
        "VALUES (%s, %s, %s, %s, %s)",
        (
            user["id"],
            data.get("application_id"),
            data.get("test_type", "aptitude"),
            data.get("event_type", "unknown"),
            data.get("snapshot_b64"),       # may be None
        )
    )
    return jsonify({"ok": True})


@app.route("/hr_proctoring_report/<int:user_id>")
def hr_proctoring_report(user_id):
    """HR views proctoring log + snapshots for a candidate."""
    if session.get("user", {}).get("role") != "hr":
        return "Access Denied", 403
    logs = fetchall(
        "SELECT * FROM proctoring_logs WHERE user_id=%s ORDER BY logged_at ASC",
        (user_id,)
    )
    candidate = fetchone("SELECT name FROM users WHERE id=%s", (user_id,))
    candidate_name = candidate["name"] if candidate else f"User #{user_id}"
    total_violations = sum(1 for l in logs if l["event_type"] != "periodic_check")
    return render_template(
        "hr_proctoring_report.html",
        logs=logs,
        candidate_name=candidate_name,
        total_violations=total_violations
    )


# ═══════════════════════════════════════════════════════════════
#  GAP ANALYSIS  (AI-powered, called at application time)
# ═══════════════════════════════════════════════════════════════

def _run_gap_analysis(user_id, job_id, app_id):
    """
    Uses Groq to analyse the candidate's resume against the job,
    identifying experience gaps, education gaps, and skill gaps.
    Result is stored in applications.gap_analysis.
    """
    try:
        from groq import Groq as _Groq
        _client = _Groq(api_key=os.getenv("GROQ_API_KEY", ""))

        resume_row = fetchone(
            "SELECT filename FROM resumes WHERE user_id=%s AND is_active=1 LIMIT 1", (user_id,)
        )
        job = fetchone("SELECT * FROM jobs WHERE id=%s", (job_id,))
        if not resume_row or not job:
            return

        resume_path = os.path.join(RESUME_FOLDER, resume_row["filename"])
        if not os.path.exists(resume_path):
            return

        resume_text = extract_text_from_pdf(resume_path)[:3000]   # trim to 3 k chars

        prompt = f"""You are an expert HR analyst. Analyse the candidate's resume against the job requirements below.

JOB TITLE: {job.get('title','')}
REQUIRED SKILLS: {job.get('skills','')}
EXPERIENCE RANGE: {job.get('min_exp',0)}–{job.get('max_exp',10)} years
JOB DESCRIPTION: {job.get('description_full') or 'Not provided'}

RESUME TEXT:
{resume_text}

Provide a concise gap analysis in plain text with three clearly labelled sections:
1. EXPERIENCE GAP – difference between required experience and what the resume shows
2. EDUCATION GAP – any missing qualifications or degree requirements
3. SKILL GAP – required skills missing from the resume

Keep each section to 2-3 bullet points. Be direct and factual.
"""
        resp = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.3,
        )
        analysis = resp.choices[0].message.content.strip()
        execute("UPDATE applications SET gap_analysis=%s WHERE id=%s", (analysis, app_id))
    except Exception as e:
        print(f"Gap analysis failed: {e}")


@app.route("/test_questions")
def test_questions():
    """Visit this URL to instantly see if questions are loading. No login needed."""
    results = {}
    for level in ["easy", "medium", "hard"]:
        # Force clear cache for this level
        for cat in ["tech_mcq", "tech_coding", "aptitude"]:
            _ai_question_cache.pop(f"{cat}:{level}", None)

        mcqs     = get_ai_tech_mcq(level, count=5)
        if not mcqs:
            mcqs = _FALLBACK_MCQ.get(level, [])

        coding   = get_ai_tech_coding(level, count=2)
        if not coding:
            coding = _FALLBACK_CODING.get(level, [])

        aptitude = get_ai_aptitude(level, count=5)
        if not aptitude:
            aptitude = _FALLBACK_APTITUDE.get(level, [])

        results[level] = {
            "tech_mcq":    {"count": len(mcqs),     "sample": mcqs[0]["question"]     if mcqs     else "EMPTY"},
            "tech_coding": {"count": len(coding),   "sample": coding[0]["question"]   if coding   else "EMPTY"},
            "aptitude":    {"count": len(aptitude), "sample": aptitude[0]["question"] if aptitude else "EMPTY"},
        }

    html = "<h2>Question Load Test</h2><pre style='font-size:14px;line-height:1.8'>"
    all_ok = True
    for level, cats in results.items():
        html += f"\n{'='*50}\n  LEVEL: {level.upper()}\n{'='*50}\n"
        for cat, info in cats.items():
            status = "✅" if info["count"] > 0 else "❌ EMPTY"
            if info["count"] == 0:
                all_ok = False
            html += f"  {cat}: {status}  ({info['count']} questions)\n"
            html += f"  Sample: {info['sample'][:80]}\n\n"
    html += f"\n{'='*50}\n"
    html += "  OVERALL: ✅ ALL GOOD — restart Flask now!" if all_ok else "  OVERALL: ❌ SOME EMPTY — check Flask console for errors"
    html += f"\n{'='*50}</pre>"
    return html


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
