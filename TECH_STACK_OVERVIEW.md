# Voice EMR - Tech Stack and Models Overview

## Project Summary
Voice EMR is an AI-powered medical documentation system that converts doctor-patient consultation audio into structured clinical notes, with multilingual support, speaker diarization, encryption, and dashboard-based access.

## Architecture at a Glance
- Frontend: Next.js + React web app
- Backend: FastAPI services + WebSocket live pipeline
- AI Pipeline: Diarization + ASR transcription + LLM extraction
- Storage: MySQL for metadata and notes
- Security: AES-256 encryption for transcript storage

## Frontend Stack
- Next.js 16.1.5
- React 19.2.3
- React DOM 19.2.3
- JavaScript App Router structure
- WebSocket client for live recording updates

### Key Frontend Modules
- Single audio upload flow
- Bulk upload flow
- Live recording page
- Doctor dashboard with patient search
- Consultation detail view with transcript + notes
- Processing status pages

## Backend Stack
- Python (3.10-3.11 recommended)
- FastAPI
- Uvicorn
- python-multipart
- websockets
- httpx

### Core Backend Responsibilities
- Receive uploads/live audio streams
- Run AI processing pipeline in background tasks
- Save encrypted transcripts and extracted clinical notes
- Expose REST and WebSocket endpoints for frontend

## AI and ML Stack

### 1) Speaker Diarization
- Library: pyannote.audio
- Model: pyannote/speaker-diarization-3.1
- Purpose: Split conversation by speakers and assign generic labels like SPEAKER_00, SPEAKER_01

### 2) Speech-to-Text (ASR)
- Primary engine: faster-whisper
- Whisper model priority (hardware-aware):
  - large-v3 (best accuracy)
  - medium (balanced)
  - small (fast fallback)
- Optional backend: AI4Bharat IndicConformer for local Indic-focused ASR

### 3) Transliteration Layer
- Library/model component: ai4bharat-transliteration
- Purpose: Convert native Indic script output into romanized text (Latin script) when needed
- Controlled by transcript output mode:
  - native: native script only
  - romanized: romanized output
  - both: native + romanized variants

### 4) Clinical Notes Extraction (LLM)
- Runtime: Ollama (local LLM serving)
- Hardware-aware LLM model priority:
  - High-end: llama3.1:70b, mixtral:8x7b, llama3.1:8b
  - Mid-range: mixtral:8x7b, llama3.1:8b, meditron:7b
  - Low-end: gemma3:4b, qwen2.5:3b-instruct
- Output: Structured JSON clinical notes (chief complaint, HPI, assessment, treatment plan, etc.)

## Data and Database
- Database: MySQL 8+
- Main tables:
  - audio_records: consultation metadata + encrypted transcript blob
  - clinical_notes: structured LLM-extracted notes
- Optional enterprise pathway: DB2 support is present in project

## Security and Privacy
- AES-256 encryption for transcripts before DB storage
- Runtime decryption only when needed
- Input validation and controlled CORS
- Design intent to reduce PHI exposure in logs

## Audio and Processing Utilities
- librosa
- soundfile
- noisereduce (optional for noisy environments)
- ffmpeg (audio conversion support)
- ai4bharat-transliteration (Indic script transliteration support)

## System Intelligence and Reliability
- Hardware auto-detection via psutil and GPUtil
- Device selection (CPU/CUDA) based on machine capabilities
- Automatic model fallback if preferred model fails
- Parallelized processing paths for faster throughput

## Typical Processing Flow
1. User uploads audio or records live.
2. System runs speaker diarization.
3. System transcribes multilingual speech to text.
4. LLM extracts structured medical notes.
5. Transcript is encrypted and stored.
6. Dashboard displays consultation history and notes.

## APIs and Integrations
- REST endpoints for uploads, patient lookup, consultation fetch, and model status
- WebSocket endpoint for live recording/transcription
- Hugging Face token required for pyannote model access
- Ollama required for local LLM inference

## 30-Second Pitch
We built Voice EMR using Next.js and FastAPI with a local AI pipeline. It separates speakers using pyannote, transcribes multilingual consultations with Whisper, and generates structured clinical notes through local Ollama LLMs. Consultation transcripts are AES-256 encrypted before storage in MySQL. The system is hardware-aware and automatically switches to the best available models, so it runs on both low-end CPU systems and high-end GPU servers.

## One-Line Version
Voice EMR is a secure, multilingual, local-AI medical transcription and clinical note generation platform built with Next.js, FastAPI, Whisper, pyannote, Ollama, and MySQL.
