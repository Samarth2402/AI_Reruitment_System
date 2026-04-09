# AI Recruitment System – MySQL Edition

## Setup Guide

### 1. Database Setup
```bash
# Create database and tables
mysql -u root -p < schema.sql
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Database
Edit `db.py` (or set environment variables):
```python
DB_CONFIG = {
    "host":     "localhost",
    "user":     "root",
    "password": "YOUR_MYSQL_PASSWORD",
    "database": "ai_recruitment",
}
```

Or use environment variables:
```bash
export DB_HOST=localhost
export DB_USER=root
export DB_PASSWORD=yourpassword
export DB_NAME=ai_recruitment
export SMTP_EMAIL=your_email@gmail.com
export SMTP_PASSWORD=your_gmail_app_password
export SECRET_KEY=your_secret_key
```

### 4. Run the App
```bash
python app.py
# or for production:
gunicorn app:app
```

Open: http://localhost:5000

---

## Bug Fixes (vs. original JSON version)

| Bug | Fix |
|-----|-----|
| `hr_schedule_direct` used array index instead of UUID lookup | Now uses `application_id` UUID correctly |
| `submit_aptitude` used session-stored level (never set in some paths) | Level always re-calculated from `experience` |
| `submit_tech_round` always loaded 'easy' MCQs regardless of candidate level | Now uses `tech_level` saved on application |
| `hr_aptitude_history` crashed when result file missing | DB always available, no crash |
| Duplicate `send_tech_round_email` definitions | Merged into single function |
| `otp_verified` session flag not initialized on `/send_otp` | Explicitly set to `False` |
| `read_json` returned `{}` for some missing files but code iterated it as list | All data now in MySQL |

---

## Architecture

```
app.py              ← Main Flask app (MySQL, all bug fixes)
db.py               ← PyMySQL connection helper
schema.sql          ← Full MySQL schema
static/style.css    ← Light + Dark theme CSS
templates/
  base.html         ← Layout with navbar + theme toggle
  login.html        ← Shared login page for users and admin
  admin_panel.html  ← Admin management console
  dashboard.html    ← Role-aware dashboard
  ... (all pages)
data/
  aptitude_questions.json   ← Default aptitude questions
  tech_mcq.json             ← Default tech MCQs
  tech_coding.json          ← Default coding problems
resumes/            ← Uploaded PDF resumes
```

## Theme Toggle
Click the 🌙/☀️ button in the top-right corner to switch between Dark and Light mode.
Preference is saved in `localStorage`.
