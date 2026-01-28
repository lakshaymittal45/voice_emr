### 🎙️ Voice-Based EMR System
## 📌 Project Overview

This project implements a voice-driven Electronic Medical Record (EMR) system that converts doctor–patient conversations into secure, structured clinical records using AI.

## The system ingests raw consultation audio and performs:

Speaker diarization (Doctor / Patient)

Speaker-wise speech-to-text transcription

LLM-based clinical note extraction

AES-256 encryption of transcripts

Role-based secure access for clinicians

Relational database storage (MySQL, DB2-ready)

The architecture follows real hospital EMR security principles:
➡️ No plaintext medical conversation is ever stored in the database.
➡️ Decryption occurs only at runtime for authorized roles.


## ✅ Current Project Status

This repository contains a fully functional end-to-end system
(backend + frontend + ML pipeline).

# ✔ Completed

Finalized backend & frontend folder structure

Stable Python virtual environment

Dependency pinning for Windows & Linux

Speaker diarization using pyannote.audio

Low-latency speaker-wise transcription using Whisper (small, CPU-optimized)

Accurate Hindi / Hinglish / English transcription (no forced transliteration)

LLM-based clinical note extraction (Ollama – Gemma 3)

AES-256 encryption of transcripts before database storage

Secure role-based transcript access (doctor, admin)

MySQL database integration (local development)

DB2 schema prepared for hospital deployment

FastAPI backend with upload & retrieval APIs

Frontend UI (Next.js) for upload & consultation viewing

Verified on Windows ML stack



## 🗂️ Project Structure
voice_emr/
│
├── backend/
│   ├── app/
│   │   ├── audio/
│   │   │   └── recordings/        # Uploaded consultation audio
│   │   │
│   │   ├── diarization/           # Pyannote speaker diarization
│   │   ├── transcription/         # Fast speaker-wise Whisper transcription
│   │   ├── llm/                   # Clinical note extraction (Gemma)
│   │   ├── encryption/            # AES-256 encryption / decryption
│   │   ├── db/                    # MySQL & DB2 integration
│   │   └── main.py                # FastAPI entry point
│   │
│   ├── requirements.txt
│   └── .env                       # Secrets (not committed)
│
├── frontend/                      # Next.js clinician UI
│
├── venv/
├── .gitignore
└── README.md



## 🧪 Environment Setup
# Create virtual environment
python -m venv venv
Activate
# Windows
venv\Scripts\activate


# Linux / Mac
source venv/bin/activate
Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r backend/requirements.txt

# ▶️ Running the Application
Start backend-
cd backend
uvicorn app.main:app --reload


Start frontend-
cd frontend
npm install
npm run dev

## 🔍 Testing Components
Test diarization
python app/diarization/diarize.py path/to/audio.wav
Verify ML stack
python -c "import torch; print(torch.__version__)"
python -c "import whisper; print('Whisper OK')"
python -c "from pyannote.audio import Pipeline; print('Pyannote OK')"
python -c "import fastapi; print('FastAPI OK')"


## 🔄 System Workflow
Doctor–Patient Conversation
        ↓
Audio Upload (Frontend)
        ↓
FastAPI Backend
        ↓
Speaker Diarization (Pyannote)
        ↓
Speaker-wise Transcription (Whisper – Small, CPU)
        ↓
LLM Clinical Extraction (Gemma)
        ↓
AES-256 Encryption
        ↓
Database Storage (Encrypted Only)
        ↓
Authorized Decryption (Doctor / Admin)


## 🧠 Key Technical Decisions (Why This Works)

Whisper Small + Array Mode → low latency, high accuracy

No forced transliteration → preserves speech fidelity

Diarization-first pipeline → correct doctor/patient context

Encrypt-before-store → zero trust DB model

LLM extracts only structured notes → no hallucinated transcripts




## ⚠️ Current Limitations
1️⃣ Transcription Quality

The system currently uses Whisper (small) for transcription to reduce end-to-end latency.

As a result, transcription accuracy is lower compared to larger Whisper models (medium, large), especially for:

Fast speech

Accents

Mixed-language conversations (Hindi–English / Hinglish)

This trade-off was made intentionally to keep processing time acceptable on CPU-only systems.

2️⃣ Latency Constraints

End-to-end processing latency is still relatively high due to:

Speaker diarization (Pyannote)

Multiple Whisper inference calls (per speaker segment)

While optimizations were applied (array-based transcription, smaller model), real-time or near-real-time performance is not yet achieved.

GPU acceleration and batch inference are planned future improvements.

3️⃣ Limited LLM Evaluation

LLM-based clinical note extraction has not been extensively evaluated due to:

Limited availability of realistic medical consultation recordings

Use of short or synthetic sample audio during development

Clinical extraction quality is expected to improve significantly once longer, real-world consultation recordings are used.



## 🔮 Planned Improvements

Upgrade transcription to Whisper Medium / Large with GPU support

Implement batched inference to reduce diarization + transcription overhead

Add confidence-based segment filtering

Evaluate LLM extraction using long-form, real consultation recordings

Introduce quantitative accuracy benchmarks (WER, speaker attribution accuracy)



