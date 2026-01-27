-- =========================================
-- MySQL Database Setup for Voice EMR System
-- =========================================

CREATE DATABASE IF NOT EXISTS voice_emr;
USE voice_emr;

-- -----------------------------------------
-- TABLE 1: Audio + Raw Transcript Metadata
-- -----------------------------------------
CREATE TABLE IF NOT EXISTS audio_records (
    audio_id INT AUTO_INCREMENT PRIMARY KEY,

    patient_id VARCHAR(100) NOT NULL,          -- Case number
    handling_clinician VARCHAR(100) NOT NULL,

    time_of_capture DATETIME NOT NULL,

    audio_file_path VARCHAR(255) NOT NULL,
    audio_duration_seconds DECIMAL(10,2),

    transcript_encrypted TEXT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------
-- TABLE 2: Structured Clinical Notes (LLM)
-- -----------------------------------------
CREATE TABLE IF NOT EXISTS clinical_notes (
    id INT AUTO_INCREMENT PRIMARY KEY,

    audio_id INT NOT NULL,
    handling_clinician VARCHAR(100) NOT NULL,

    chief_complaint TEXT,
    history_of_present_illness TEXT,
    associated_diseases TEXT,
    past_medical_history TEXT,
    drug_history TEXT,
    allergies TEXT,
    assessment TEXT,
    treatment_plan TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_audio_records
        FOREIGN KEY (audio_id)
        REFERENCES audio_records(audio_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_audio_patient
ON audio_records (patient_id);

CREATE INDEX idx_audio_time
ON audio_records (time_of_capture);

CREATE INDEX idx_notes_audio
ON clinical_notes (audio_id);
