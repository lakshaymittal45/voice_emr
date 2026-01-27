# 🎙️ Voice-Based EMR System

## 📌 Project Overview

This project implements a **voice-driven Electronic Medical Record (EMR) system** that converts doctor–patient conversations into **secure, structured clinical records** using AI.

The system processes raw consultation audio and performs:

- Speaker diarization (doctor vs patient)
- Speaker-wise speech-to-text transcription
- LLM-based clinical note extraction
- AES-256 encryption of transcripts
- Secure, role-based decryption for clinicians
- Database storage (MySQL, DB2-ready)

The design follows **real hospital EMR principles**:  
data is encrypted at rest and decrypted only for authorized medical staff.

---

## ✅ Current Project Status

This repository contains a **fully functional backend pipeline**.

### ✔ Completed
- Project folder structure finalized
- Python virtual environment setup
- Stable dependency management
- Speaker diarization using `pyannote.audio`
- Speaker-wise transcription using `Whisper (medium)`
- LLM-based clinical note extraction (Ollama – Gemma)
- AES-256 encryption of transcripts before storage
- Secure decryption API for authorized access
- MySQL database integration (local development)
- IBM DB2 schema prepared (hospital phase)
- FastAPI backend with upload & retrieval APIs
- Windows-compatible ML stack verified

### ⏳ Deferred / Planned
- MySQL → DB2 synchronization
- JWT-based authentication (RBAC hardening)
- Frontend UI integration
- Hospital deployment configuration

---

## 🗂️ Project Structure

```text
voice_emr/
│
├── backend/
│   ├── app/
│   │   ├── audio/
│   │   │   └── recordings/        # Uploaded consultation audio
│   │   │
│   │   ├── diarization/           # Speaker diarization logic
│   │   ├── transcription/         # Speaker-wise Whisper transcription
│   │   ├── llm/                   # LLM clinical note extraction
│   │   ├── encryption/            # AES-256 encryption / decryption
│   │   ├── db/                    # MySQL & DB2 integration
│   │   └── main.py                # FastAPI application entry point
│   │
│   ├── requirements.txt
│   └── .env                       # Environment variables (not committed)
│
├── venv/
├── .gitignore
└── README.md


## Environment Setup
python -m venv venv

venv\Scripts\activate
## Install Dependencies
pip install -r backend/requirements.txt


start backend from backend folder-
cd backend
uvicorn app.main:app --reload

start frontend
cd frontend
npm install
npm run dev



Test dairaization -
python app/diarization/diarize.py D:\voice_emr\audio\Test.wav

## Installation Verification Checks
python -c "import numpy; print(numpy.__version__)"
python -c "import torch; print(torch.__version__)"
python -c "import whisper; print('Whisper OK')"
python -c "from pyannote.audio import Pipeline; print('Pyannote OK')"
python -c "import fastapi; print('FastAPI OK')"
python -c "from cryptography.fernet import Fernet; print('Crypto OK')"


## Planned System Workflow
Doctor–Patient Conversation
        ↓
Audio Upload (FastAPI)
        ↓
Speaker Diarization (Pyannote)
        ↓
Speaker-wise Transcription (Whisper – Medium)
        ↓
LLM Clinical Extraction (Gemma)
        ↓
AES-256 Encryption
        ↓
Database Storage (MySQL)
        ↓
Secure Decryption for Authorized Users



## Secuirty Design
Encryption at Rest

All consultation transcripts are encrypted using AES-256

Encryption key is stored in .env, never in the database

Database stores only encrypted Base64 text

Secure Decryption

Decryption occurs only in the backend

Only authorized roles (doctor, admin) can access decrypted transcripts

Database administrators cannot read patient conversations

This aligns with real hospital EMR security practices.

## 🚀 Next Milestones

MySQL → DB2 synchronization

JWT-based authentication & RBAC

Frontend dashboard for clinicians

Audit logging and compliance hardening

Hospital deployment configuration