-- ============================================================
-- AI Recruitment System – PostgreSQL Schema
-- ============================================================

-- ── Users ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(180) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'candidate',
    company_name VARCHAR(180),
    login_attempts SMALLINT DEFAULT 0,
    blocked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Company ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS company (
    id SERIAL PRIMARY KEY,
    hr_id INT NOT NULL,
    name VARCHAR(180) NOT NULL,
    location VARCHAR(180),
    industry VARCHAR(120),
    website VARCHAR(180),
    description TEXT,
    size VARCHAR(60),
    founded_year INT,
    contact_email VARCHAR(180),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hr_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── Jobs ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    hr_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    description_full TEXT,
    skills TEXT,
    min_exp INT DEFAULT 0,
    max_exp INT DEFAULT 50,
    min_10 INT DEFAULT 0,
    min_12 INT DEFAULT 0,
    min_grad INT DEFAULT 0,
    min_salary INT DEFAULT 0,
    max_salary INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'open',
    closed_at TIMESTAMP,
    reminder_sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hr_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── Applications ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS applications (
    id VARCHAR(36) PRIMARY KEY,
    user_id INT NOT NULL,
    job_id INT NOT NULL,
    job_title VARCHAR(200),
    experience INT DEFAULT 0,
    tenth INT DEFAULT 0,
    twelfth INT DEFAULT 0,
    graduation INT DEFAULT 0,
    status VARCHAR(60) DEFAULT 'applied',

    aptitude_required BOOLEAN DEFAULT FALSE,
    aptitude_status VARCHAR(40) DEFAULT 'not_assigned',
    aptitude_score INT,
    aptitude_total INT,
    aptitude_percentage FLOAT,

    tech_round BOOLEAN DEFAULT FALSE,
    tech_started BOOLEAN DEFAULT FALSE,
    tech_completed BOOLEAN DEFAULT FALSE,
    tech_status VARCHAR(40) DEFAULT 'not_started',
    tech_result VARCHAR(40),
    tech_level VARCHAR(20),

    hr_scheduled BOOLEAN DEFAULT FALSE,
    hr_date DATE,
    hr_time VARCHAR(30),

    gap_analysis TEXT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

-- ── Resumes ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS resumes (
    id SERIAL PRIMARY KEY,
    resume_id VARCHAR(20) UNIQUE,
    user_id INT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    analysis_quality VARCHAR(20),
    analysis_score INT,
    analysis_feedback JSON,
    analysis_suggestions JSON,
    uploaded_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── Interviews ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS interviews (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    score INT DEFAULT 0,
    weak_areas TEXT,
    readiness VARCHAR(60),
    hr_decision VARCHAR(40) DEFAULT 'pending',
    taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── Scheduled Interviews ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS scheduled_interviews (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    job_title VARCHAR(200),
    date DATE,
    time VARCHAR(30),
    mode VARCHAR(60),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── Aptitude Results ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS aptitude_results (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    job_id INT NOT NULL,
    application_id VARCHAR(36),
    level VARCHAR(20),
    score INT DEFAULT 0,
    total INT DEFAULT 0,
    percentage FLOAT DEFAULT 0,
    decision VARCHAR(40) DEFAULT 'hr_review',
    taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    min_salary INT DEFAULT 0,
    max_salary INT DEFAULT 0
);

-- ── Tech Results ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tech_results (
    id SERIAL PRIMARY KEY,
    application_id VARCHAR(36),
    user_id INT NOT NULL,
    candidate_name VARCHAR(120),
    mcq_results JSON,
    coding_results JSON,
    final_score INT DEFAULT 0,
    hr_decision VARCHAR(40) DEFAULT 'pending',
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── OTP Store ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS otp_store (
    email VARCHAR(180) PRIMARY KEY,
    otp VARCHAR(10),
    expires_at TIMESTAMP
);

-- ── Company Questions ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS company_questions (
    id SERIAL PRIMARY KEY,
    hr_id INT NOT NULL,
    category VARCHAR(20),
    level VARCHAR(20),
    question TEXT,
    options JSON,
    answer VARCHAR(255),
    input_format TEXT,
    output_format TEXT,
    constraints TEXT,
    sample_input TEXT,
    sample_output TEXT,
    is_hidden BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hr_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── HR Hidden Defaults ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS hr_hidden_defaults (
    id SERIAL PRIMARY KEY,
    hr_id INT NOT NULL,
    question_type VARCHAR(30),
    level VARCHAR(20),
    question_id VARCHAR(80),
    UNIQUE (hr_id, question_type, level, question_id),
    FOREIGN KEY (hr_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── Proctoring Logs ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS proctoring_logs (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    application_id VARCHAR(36),
    test_type VARCHAR(20) DEFAULT 'aptitude',
    event_type VARCHAR(60),
    snapshot_b64 TEXT,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
