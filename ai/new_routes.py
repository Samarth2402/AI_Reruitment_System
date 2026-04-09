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
