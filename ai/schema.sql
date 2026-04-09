-- ============================================================
--  AI Recruitment System – MySQL Schema
--  Run this once: mysql -u root -p < schema.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS ai_recruitment CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ai_recruitment;

    -- ── Users ────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS users (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        name          VARCHAR(120) NOT NULL,
        email         VARCHAR(180) NOT NULL UNIQUE,
        password      VARCHAR(255) NOT NULL,
        role          ENUM('candidate','hr') NOT NULL DEFAULT 'candidate',
        company_name  VARCHAR(180),
        login_attempts TINYINT DEFAULT 0,
        blocked       TINYINT(1) DEFAULT 0,
        created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    -- New company table for full details
    CREATE TABLE IF NOT EXISTS company (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        hr_id         INT NOT NULL,
        name          VARCHAR(180) NOT NULL,
        location      VARCHAR(180),
        industry      VARCHAR(120),
        website       VARCHAR(180),
        description   TEXT,
        size          VARCHAR(60),
        founded_year  INT,
        contact_email VARCHAR(180),
        created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (hr_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- ── Jobs ─────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS jobs (
        id         INT AUTO_INCREMENT PRIMARY KEY,
        hr_id      INT NOT NULL,
        title      VARCHAR(200) NOT NULL,
        description_full TEXT DEFAULT NULL,
        skills     TEXT,                      -- comma-separated
        min_exp    INT DEFAULT 0,
        max_exp    INT DEFAULT 50,
        min_10     INT DEFAULT 0,
        min_12     INT DEFAULT 0,
        min_grad   INT DEFAULT 0,
        min_salary INT DEFAULT 0,
        max_salary INT DEFAULT 0,
        status     VARCHAR(20) NOT NULL DEFAULT 'open',
        closed_at  DATETIME DEFAULT NULL,
        reminder_sent_at DATETIME DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (hr_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- ── Applications ─────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS applications (
        id                  VARCHAR(36) PRIMARY KEY,   -- UUID
        user_id             INT NOT NULL,
        job_id              INT NOT NULL,
        job_title           VARCHAR(200),
        experience          INT DEFAULT 0,
        tenth               INT DEFAULT 0,
        twelfth             INT DEFAULT 0,
        graduation          INT DEFAULT 0,

        -- main status
        status              VARCHAR(60) DEFAULT 'applied',

        -- aptitude
        aptitude_required   TINYINT(1) DEFAULT 0,
        aptitude_status     VARCHAR(40) DEFAULT 'not_assigned',
        aptitude_score      INT,
        aptitude_total      INT,
        aptitude_percentage FLOAT,

        -- tech round
        tech_round          TINYINT(1) DEFAULT 0,
        tech_started        TINYINT(1) DEFAULT 0,
        tech_completed      TINYINT(1) DEFAULT 0,
        tech_status         VARCHAR(40) DEFAULT 'not_started',
        tech_result         VARCHAR(40),
        tech_level          VARCHAR(20),

        -- HR round schedule
        hr_scheduled        TINYINT(1) DEFAULT 0,
        hr_date             DATE,
        hr_time             VARCHAR(30),

        -- AI gap analysis
        gap_analysis        TEXT DEFAULT NULL,

        applied_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (job_id)  REFERENCES jobs(id)  ON DELETE CASCADE
    );

    -- ── Resumes ──────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS resumes (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        resume_id   VARCHAR(20) NOT NULL UNIQUE,
        user_id     INT NOT NULL,
        filename    VARCHAR(255) NOT NULL,
        is_active   TINYINT(1) DEFAULT 0,
        analysis_quality     VARCHAR(20) DEFAULT NULL,
        analysis_score       INT DEFAULT NULL,
        analysis_feedback    JSON,
        analysis_suggestions JSON,
        uploaded_on DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- ── Mock Interviews ──────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS interviews (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        user_id     INT NOT NULL,
        score       INT DEFAULT 0,
        weak_areas  TEXT,
        readiness   VARCHAR(60),
        hr_decision VARCHAR(40) DEFAULT 'pending',
        taken_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- ── Scheduled Interviews (HR round) ──────────────────────────
    CREATE TABLE IF NOT EXISTS scheduled_interviews (
        id         INT AUTO_INCREMENT PRIMARY KEY,
        user_id    INT NOT NULL,
        job_title  VARCHAR(200),
        date       DATE,
        time       VARCHAR(30),
        mode       VARCHAR(60),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- ── Aptitude Results ─────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS aptitude_results (
        id             INT AUTO_INCREMENT PRIMARY KEY,
        user_id        INT NOT NULL,
        job_id         INT NOT NULL,
        application_id VARCHAR(36) NOT NULL,
        level          VARCHAR(20),
        score          INT DEFAULT 0,
        total          INT DEFAULT 0,
        percentage     FLOAT DEFAULT 0,
        decision       VARCHAR(40) DEFAULT 'hr_review',
        taken_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
        min_salary     INT DEFAULT 0,
        max_salary     INT DEFAULT 0
    );

    -- ── Tech Results ─────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS tech_results (
        id             INT AUTO_INCREMENT PRIMARY KEY,
        application_id VARCHAR(36) NOT NULL,
        user_id        INT NOT NULL,
        candidate_name VARCHAR(120),
        mcq_results    JSON,
        coding_results JSON,
        final_score    INT DEFAULT 0,
        hr_decision    VARCHAR(40) DEFAULT 'pending',
        submitted_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- ── OTP Store ────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS otp_store (
        email      VARCHAR(180) PRIMARY KEY,
        otp        VARCHAR(10),
        expires_at DATETIME
    );

    -- ── Company Questions (HR custom) ────────────────────────────
    CREATE TABLE IF NOT EXISTS company_questions (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        hr_id         INT NOT NULL,
        category      ENUM('aptitude','tech_mcq','tech_coding') NOT NULL,
        level         ENUM('easy','medium','hard') NOT NULL,
        question      TEXT NOT NULL,
        options       JSON,                  -- array of strings
        answer        VARCHAR(255),
        input_format  TEXT,
        output_format TEXT,
        constraints   TEXT,
        sample_input  TEXT,
        sample_output TEXT,
        is_hidden     TINYINT(1) DEFAULT 0,
        created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (hr_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- ── Default question hide list per HR ────────────────────────
    CREATE TABLE IF NOT EXISTS hr_hidden_defaults (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        hr_id         INT NOT NULL,
        question_type VARCHAR(30),
        level         VARCHAR(20),
        question_id   VARCHAR(80),
        UNIQUE KEY unique_hide (hr_id, question_type, level, question_id),
        FOREIGN KEY (hr_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- ── Proctoring Logs ──────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS proctoring_logs (
        id             INT AUTO_INCREMENT PRIMARY KEY,
        user_id        INT NOT NULL,
        application_id VARCHAR(36),
        test_type      VARCHAR(20) DEFAULT 'aptitude',
        event_type     VARCHAR(60),
        snapshot_b64   MEDIUMTEXT,
        logged_at      DATETIME DEFAULT CURRENT_TIMESTAMP
    );