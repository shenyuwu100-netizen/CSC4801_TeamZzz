CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('Candidate', 'Employer')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_profiles (
    user_id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL,
    skills_json TEXT NOT NULL DEFAULT '[]',
    resume_text TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS company_profiles (
    user_id INTEGER PRIMARY KEY,
    company_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employer_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    required_skills_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (employer_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    job_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('Pending', 'Interviewing', 'Rejected', 'Accepted')),
    created_at TEXT NOT NULL,
    UNIQUE(candidate_id, job_id),
    FOREIGN KEY (candidate_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS interview_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    employer_id INTEGER NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE RESTRICT,
    FOREIGN KEY (employer_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL UNIQUE,
    slot_id INTEGER NOT NULL UNIQUE,
    booked_at TEXT NOT NULL,
    FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE RESTRICT,
    FOREIGN KEY (slot_id) REFERENCES interview_slots(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_jobs_employer ON jobs(employer_id);
CREATE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_applications_candidate ON applications(candidate_id);
CREATE INDEX IF NOT EXISTS idx_slots_job ON interview_slots(job_id);
