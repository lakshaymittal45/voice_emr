-- =========================================
-- IBM DB2 Database Setup for Voice EMR System
-- =========================================

-- -----------------------------------------
-- TABLE 1: Audio + Raw Transcript Metadata
-- -----------------------------------------
CREATE TABLE audio_records (
    audio_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    patient_id VARCHAR(100) NOT NULL,
    handling_clinician VARCHAR(100) NOT NULL,

    time_of_capture TIMESTAMP NOT NULL,

    audio_file_path VARCHAR(255) NOT NULL,
    audio_duration_seconds DECIMAL(10,2),

    transcript_encrypted CLOB NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT TIMESTAMP
);

-- -----------------------------------------
-- TABLE 2: Structured Clinical Notes (LLM)
-- -----------------------------------------
CREATE TABLE clinical_notes (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    audio_id INTEGER NOT NULL,
    handling_clinician VARCHAR(100) NOT NULL,

    chief_complaint CLOB,
    history_of_present_illness CLOB,
    associated_diseases CLOB,
    past_medical_history CLOB,
    drug_history CLOB,
    allergies CLOB,
    assessment CLOB,
    treatment_plan CLOB,

    created_at TIMESTAMP DEFAULT CURRENT TIMESTAMP,

    CONSTRAINT fk_audio_records
        FOREIGN KEY (audio_id)
        REFERENCES audio_records(audio_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_audio_patient
ON audio_records (patient_id);

CREATE INDEX idx_notes_audio
ON clinical_notes (audio_id);
