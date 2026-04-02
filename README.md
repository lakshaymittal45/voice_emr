# 🎙️ Voice EMR — AI-Powered Medical Record System

A voice-driven Electronic Medical Record system that converts doctor–patient consultations into structured, encrypted clinical notes using AI.

**Built for North India hospitals** — handles Hindi, Punjabi, Haryanvi, Hinglish, and English seamlessly.

---

## ✨ Features

### Core Features
- 🎤 **Live recording** via WebSocket with real-time incremental transcription (8s intervals)
- 📁 **Bulk audio upload** with background processing queue
- 🗣️ **Speaker diarization** — Generic speaker labels (SPEAKER_00, SPEAKER_01, etc.)
- 🌏 **Multilingual transcription** — Whisper auto-detects Hindi, Punjabi, Haryanvi, Hinglish, English
- 🌐 **Google Translate integration** — native script → natural English for all staff
- 🤖 **LLM clinical extraction** — structured notes (chief complaint, assessment, treatment plan, etc.)
- 🔒 **AES-256 encryption** — transcripts encrypted before database storage, decrypted only at runtime

### New Features (v2.0)
- 👨‍⚕️ **Doctor Dashboard** — Search patients by ID with autocomplete dropdown
- 📋 **Appointment History** — View all consultations for any patient with dates, clinicians, and durations
- 🖨️ **Professional PDF Export** — Medical document styling with proper headers, footers, and page breaks
- ⚡ **Faster Live Transcription** — Reduced from 15s to 8s intervals for near real-time updates
- 🎯 **Fixed Diarization** — No more duplicate text, center-based segment alignment
- 🏷️ **Generic Speaker Labels** — Changed from hardcoded Doctor/Patient to SPEAKER_00, SPEAKER_01, SPEAKER_02

### System Intelligence
- 📊 **Auto hardware detection** — selects optimal Whisper and LLM models based on your CPU/GPU/RAM
- 🛡️ **Security hardened** — tight CORS, input sanitization, no PHI in logs, timezone-aware UTC timestamps
- 🔄 **Automatic fallback** — gracefully degrades to smaller models if primary model fails

---

## 🔧 Requirements

| Dependency | Version | Notes |
|---|---|---|
| Python | 3.10 – 3.11 | 3.12+ not tested |
| Node.js | 18+ | For Next.js frontend |
| MySQL | 8.0+ | Local or remote |
| Ollama | Latest | Local LLM runner |
| ffmpeg | Any recent | Audio conversion |

---

## 🚀 Quick Start

### 1 — Install Ollama & pull a model

## 🤖 Ollama Setup (LLM Backend)

The system uses **Ollama** to run medical-grade Large Language Models (LLMs) locally for clinical note extraction.

### Step 1: Install Ollama

**Windows / Mac / Linux:**
1. Download Ollama from: **https://ollama.ai/download**
2. Install and verify:
   ```bash
   ollama --version
   ```

### Step 2: Pull Models Based on Your Hardware

The system **automatically detects your hardware** and selects the best model. However, you need to install at least one model for your tier.

#### 🔹 For Low-End Systems (16 GB RAM, No GPU)
**Current System Tier** - Optimized for CPU-only processing

```bash
# Primary model (4B parameters, 8 GB RAM required)
ollama pull gemma3:4b

# Fallback model (3B parameters, 6 GB RAM required)
ollama pull qwen2.5:3b-instruct
```

**Recommended:** Pull both models. The system will use `gemma3:4b` by default and fallback to `qwen2.5:3b-instruct` if needed.

#### 🔹 For Mid-Range Systems (24-32 GB RAM OR 8+ GB VRAM GPU)
Upgrade your models when you add RAM or a mid-tier GPU:

```bash
# Best mid-tier model (47B parameters, 32 GB RAM required)
ollama pull mixtral:8x7b

# Alternative mid-tier models
ollama pull llama3.1:8b        # 8B parameters, 16 GB RAM
ollama pull meditron:7b        # Medical specialist, 16 GB RAM

# Keep low-end models as fallbacks
ollama pull gemma3:4b
ollama pull qwen2.5:3b-instruct
```

#### 🔹 For High-End Systems (64+ GB RAM AND 16+ GB VRAM GPU)
For production hospital deployment or cloud instances:

```bash
# Best medical AI model (70B parameters, 64+ GB RAM required)
ollama pull llama3.1:70b

# Mid-tier fallbacks
ollama pull mixtral:8x7b
ollama pull llama3.1:8b

# Low-tier fallbacks
ollama pull gemma3:4b
ollama pull qwen2.5:3b-instruct
```

### Step 3: Verify Ollama is Running
```bash
# Check Ollama service status
ollama list

# Test a model
ollama run gemma3:4b "Hello, test message"
```
### 2 — Python environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate
# Linux / Mac
source venv/bin/activate

pip install --upgrade pip setuptools wheel
pip install -r backend/requirements.txt
```
> **PyTorch note:** if the above installs a CPU-only build by default and you have an NVIDIA GPU, install the CUDA build manually:
> ```bash
> pip install torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cu118
> ```

### 3 — Configure environment

```bash
cd backend
copy .env.example .env      # Windows

# Open .env and fill in your MySQL password, EMR_AES_KEY, and HUGGINGFACE_TOKEN
```
See [Configuration](#️-configuration) below for all variables.

### 4 — Set up the MySQL database
```bash
mysql -u root -p < backend/app/db/mysql_setup.sql
```
### 5 — Start the backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
uvicorn app.main:app --reload
```
API docs: <http://localhost:8000/docs>

### 6 — Start the frontend

```bash
cd frontend
npm install
npm run dev
```
Frontend: <http://localhost:3000>
---
## ⚙️ Configuration

All backend settings live in `backend/.env`

| Variable | Required | Default | Description |
|---|---|---|---|
| `MYSQL_HOST` | ✅ | `localhost` | MySQL server host |
| `MYSQL_USER` | ✅ | `root` | MySQL username |
| `MYSQL_PASSWORD` | ✅ | — | MySQL password |
| `MYSQL_DB` | ✅ | `voice_emr` | Database name |
| `EMR_AES_KEY` | ✅ | — | **Exactly 32 ASCII chars** — encrypts all transcripts |
| `HUGGINGFACE_TOKEN` | ✅ | — | HF token for PyAnnote diarization model |
| `CORS_ORIGINS` | ✅ | `http://localhost:3000` | Comma-separated allowed frontend origins |
| `PATIENT_CONVO_DIR` | ⬜ | `D:\Patient Convo` | Folder where all audio files are stored |
| `WHISPER_DEVICE` | ⬜ | auto | Force `cpu` or `cuda` |
| `TRANSCRIPTION_BACKEND` | ⬜ | `auto` | `auto`, `indicconformer`, or `whisper` |
| `TRANSCRIPT_OUTPUT_MODE` | ⬜ | `romanized` | `native`, `romanized`, or `both` |
| `INDIC_TRANSCRIPTION_LANGUAGE` | ⬜ | `auto` | Use `hi`, `pa`, etc. to force a monolingual Indic model |
| `PARALLEL_DIARIZATION_TRANSCRIPTION` | ⬜ | `true` | Overlap diarization and ASR when the resolved backend is Whisper |
| `LIVE_TRANSCRIPT_HOLDBACK_SEC` | ⬜ | `1.2` | Keep the last active-speech tail out of live transcript updates so utterances are not cut mid-sentence |

For fully local Hindi/Punjabi and other Indic ASR, set `TRANSCRIPTION_BACKEND=indicconformer` after installing the AI4Bharat NeMo fork and downloading the selected model locally.
If your consultations regularly mix Hindi, Punjabi, and English in the same recording, keep `TRANSCRIPTION_BACKEND=auto` and `INDIC_TRANSCRIPTION_LANGUAGE=auto` so the system prefers the multilingual Whisper path.

**Frontend** (`frontend/.env.local`):

```env
NEXT_PUBLIC_API_BASE=http://localhost:8000
NEXT_PUBLIC_WS_BASE=ws://localhost:8000
```

**Audio file naming:** `PatientID_YYYYMMDD_HHMMSS.ext`
> Same patient + exact same second → file is overwritten (prevents duplicates).
---

## 🗂️ Project Structure
```
voice_emr/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI entry point
│   │   ├── config.py        # Hardware detection, model config
│   │   ├── diarization/     # PyAnnote speaker diarization
│   │   ├── transcription/   # Whisper + anti-hallucination filter
│   │   ├── llm/             # Ollama clinical note extraction
│   │   ├── encryption/      # AES-256
│   │   ├── db/              # MySQL (+ DB2 schema)
│   │   └── live/            # WebSocket live recording
│   ├── requirements.txt
│   ├── .env.example         # template — safe to commit
│   └── .env                 # your secrets — git-ignored
├── frontend/                # Next.js UI
│   └── app/
│       ├── upload/               # Single file upload
│       ├── upload-bulk/          # Multiple file upload
│       ├── live-record/          # Real-time recording with WebSocket
│       ├── doctor-dashboard/     # Patient search & appointment history
│       ├── consultation/[audioId]/  # View transcript & clinical notes
│       └── processing/           # Processing status page
│   └── components/
│       ├── LiveRecorder.js       # WebSocket recording component
│       ├── TranscriptViewer.js   # Display speaker-wise transcript
│       └── ClinicalNotes.js      # Display extracted clinical notes
└── venv/
│
├── .gitignore
└── README.md             

```
---
## 📡 API Endpoints
```
| POST` | `/consultation-status-batch` | Batch status check for multiple audio IDs |
| `GET` | `/consultation/{audio_id}` | Retrieve decrypted transcript + clinical notes |
| `GET` | `/patients` | List all patients with appointment stats |
| `GET` | `/patient/{patient_id}/appointments` | Get all appointments for a specific patient |
| `GET` | `/models/status` | Hardware info & active model selection |
| `GET` | `/health` | Health check endpoint |
| `WS` | `/ws/live-record` | WebSocket live recording stream |
```
**Live recording** WebSocket params: `?patient_id=<id>&clinician_id=<id>&role=doctor`

### Doctor Dashboard Workflow

1. **Search Patient**: GET `/patients` returns all patients with their stats
2. **Autocomplete**: Frontend filters patient IDs as doctor types
3. **View History**: GET `/patient/{patient_id}/appointments` returns all consultations
4. **View Details**: Click any appointment → GET `/consultation/{audio_id}` for full transcript & notes
5. **Export PDF**: Print button generates professional medical document with proper styling
```
| `GET` | `/consultation-status/{audio_id}` | Poll processing status |
| `GET` | `/consultation/{audio_id}` | Retrieve decrypted transcript + clinical notes |
| `GET` | `/models/status` | Hardware info & active model selection |
| `WS` | `/ws/live-record` | WebSocket live recording stream |
```
**Live recording** WebSocket params: `?patient_id=<id>&clinician_id=<id>&role=doctor`

---

## 🔄 Pipeline Overview
```
Doctor–Patient Conversation
        ↓
Audio Upload (Frontend)
        ↓
FastAPI Backend (Auto-detect hardware)
        ↓
Speaker Diarization (Pyannote)
        ↓
Speaker-wise Transcription (Whisper – Auto-selected based on hardware)
   • Low-End: small (CPU)
   • Mid-Range: medium (CPU/GPU)
   • High-End: large-v3 (GPU)
        ↓
LLM Clinical Extraction (Ollama – Auto-selected model)
   • Low-End: gemma3:4b
   • Mid-Range: mixtral:8x7b
   • High-End: llama3.1:70b
        ↓
AES-256 Encryption
        ↓
Database Storage (Encrypted Only)
        ↓
Authorized Decryption (Doctor / Admin)
```
---


### Doctor Dashboard
A centralized hub for doctors to search and access patient records:

**Features:**
- **Smart Search**: Type patient ID with autocomplete dropdown
- **Patient Stats**: See total patients and consultations at a glance
- **Appointment History**: View all consultations for any patient
- **Quick Access**: Click any appointment to view full transcript and clinical notes

**How to Use:**
1. Navigate to home page → Click "🔍 Doctor Dashboard"
2. Start typing a patient ID (e.g., "2444")
3. Select from dropdown or press Enter
4. View list of all appointments for that patient
5. Click any appointment card to see full details

### Professional PDF Export
Transform your consultation pages into print-ready medical documents:

**Features:**
- **Medical Document Header**: Facility name, document ID, timestamp
- **Professional Layout**: A4 page size with proper margins
- **Clean Typography**: Serif fonts for body, sans-serif for headers
- **Page Management**: Automatic page breaks, prevents orphaned sections
- **Confidentiality Notice**: Footer with "CONFIDENTIAL MEDICAL RECORD" warning
- **Print-Optimized**: Hides all interactive elements (buttons, navigation)

**How to Use:**
1. Open any consultation page
2. Click the export dropdown → "🖨️ Print"
3. In print dialog, select "Save as PDF" or "Microsoft Print to PDF"
4. Save the professional medical document

### Improved Diarization
Fixed major issues with speaker attribution:

**What Changed:**
- ❌ **Before**: Hardcoded "Doctor" and "Patient" labels
- ✅ **After**: Generic "SPEAKER_00", "SPEAKER_01", "SPEAKER_02", etc.

- ❌ **Before**: Same text appeared for both speakers (duplicate bug)
- ✅ **After**: Each segment assigned to only one speaker (center-based alignment)

**Why This Matters:**
- Works for any number of speakers (doctor + patient + nurse + family)
- No more duplicate text in transcripts
- Accurate speaker attribution even in overlapping speech
- More reliable clinical documentation

### Faster Live Transcription
Reduced latency for real-time recording:

**Performance Improvements:**
- **Incremental Updates**: 15 seconds → **8 seconds** (47% faster)
- **Minimum Duration**: 3.0 seconds → **2.0 seconds** (33% faster start)
- **WebSocket Debugging**: Enhanced logging for connection issues
- **Better Feedback**: Immediate "Connected" confirmation message

**Impact:**
- Doctors see transcription updates almost 2x faster
- More responsive live recording experience
- Better for short consultations

---

## �🌏 Multilingual Support

Whisper auto-detects the language per segment — no manual configuration needed.

| Language | Transcription | Extraction | Notes |
|---|---|---|---|
| English | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Best for medical terms |
| Hindi | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Native Devanagari support |
| Hinglish | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Code-switching handled well |
| Punjabi | ⭐⭐⭐ | ⭐⭐⭐ | Better with Whisper `medium`/`large-v3` |
| Haryanvi | ⭐⭐⭐ | ⭐⭐⭐ | Treated as Hindi dialect |

Both the **native-script transcript** (for legal/audit accuracy) and an **English translation** (for staff readability) are stored in the database.

---

## 🧪 Testing

```bash
# Test diarization on a WAV file
python backend/app/diarization/diarize.py path/to/audio.wav

# Verify ML stack
python -c "import torch; print('torch', torch.__version__)"
python -c "from pyannote.audio import Pipeline; print('Pyannote OK')"
python -c "import faster_whisper; print('Whisper OK')"
python -c "import fastapi; print('FastAPI OK')"

# Verify Ollama
ollama list
```
---
## 🛠️ Troubleshooting

**`EMR_AES_KEY must be set and exactly 32 bytes`**
Generate a valid key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32)[:32])"
```

**`HuggingFace token not found`**
Set `HUGGINGFACE_TOKEN` in `.env`. Accept the model terms at
<https://huggingface.co/pyannote/speaker-diarization-3.1>.

**`Error: model 'gemma3:4b' not found`**
```bash
ollama pull gemma3:4b
```

**`Connection refused` on Ollama**
```bash
# Windows — check system tray for Ollama icon
# Linux/Mac:
ollama serve
# Verify:
curl http://localhost:11434/api/tags
```

**Frontend can't reach backend**
Make sure `NEXT_PUBLIC_API_BASE` in `frontend/.env.local` matches the backend URL and that uvicorn is running.

**LLM too slow / timeout**
Increase `LLM_TIMEOUT` in `.env`, or switch to a smaller model (`qwen2.5:3b-instruct`).
---

The architecture follows real hospital EMR security principles:
➡️ No plaintext medical conversation is ever stored in the database.
➡️ Decryption occurs only at runtime for authorized roles.
➡️ **Language-agnostic output** - clinical notes always in English regardless of consultation language.

**Recording Saving**
- Centralized recordings folder: all uploaded and live-recorded audio now stored under a single configurable folder (`PATIENT_CONVO_DIR`). Default on Windows: `D:\\Patient Convo`.
- File naming: recordings are saved as `PatientID_YYYYMMDD_HHMMSS.ext`. If a file with the exact same name already exists (same patient and same second) it will be overwritten to avoid duplicate files; otherwise a new file is created.
- Live recording: WebSocket endpoint available at `/ws/live-record` for real-time capture and incremental transcription.
- Transcription improvements: added anti-hallucination post-processing and Whisper parameter tuning to reduce repeated-word hallucinations for Hindi/Punjabi.
- Security hardening: tightened CORS (use `CORS_ORIGINS`), removed PHI debug logging, sanitized patient IDs to prevent path traversal, and switched all DB timestamps to timezone-aware UTC.
---

## 🌏 Multilingual Support for North India Hospitals

This system is specifically designed for **North India hospitals** where patients and doctors use multiple languages during consultations.

### 🎯 Supported Languages

**Fully Supported:**
- ✅ **Hindi** - Full native support
- ✅ **English** - Medical terminology and general conversation
- ✅ **Hinglish** - Mixed Hindi-English (code-switching)
- ✅ **Punjabi** - Common in Punjab, Haryana, Delhi NCR
- ✅ **Haryanvi** - Haryana regional dialect

**How It Works:**
1. **Whisper (Transcription)** - Auto-detects language, transcribes in native script (most accurate)
2. **Google Translate** - Converts native scripts → Natural English for universal staff readability
3. **Dual Storage** - Both native (for accuracy/legal) + English (for staff) stored in database
4. **LLM (Clinical Extraction)** - Reads either version, produces structured English clinical notes
5. **No Configuration Needed** - System automatically handles detection, translation, and extraction

**Installation & Configuration:**
```bash
# Install Google Translate API
cd backend
pip install googletrans==4.0.0rc1

# Already enabled by default in transcription/transcribe.py:
# ENABLE_TRANSLATION = True
# STORE_BOTH_VERSIONS = True
```

## 🧠 Key Technical Decisions 

**Intelligent Hardware Detection** → automatic model selection based on system capabilities

**Whisper's Multilingual DNA** → natively trained on 99+ languages including Hindi, Punjabi, regional dialects

**Auto-Language Detection** → no manual configuration, handles code-switching (Hinglish) seamlessly

**No forced transliteration** → preserves speech fidelity, respects native pronunciation

**Diarization-first pipeline** → correct doctor/patient context attribution across languages

**LLM multilingual translation** → internally converts Hindi/Punjabi/Haryanvi to English for structured output

**Encrypt-before-store** → zero trust DB model (no plaintext medical data in database)

**LLM extracts only structured notes** → no hallucinated transcripts, language-agnostic output

**Cascading model fallback** → system degrades gracefully if best model fails

**Auto-upgrade capability** → when you upgrade hardware, system automatically uses better models (improved dialect handling)

## 🔮 Planned Improvements

**Transcription Upgrades**
- Upgrade to Whisper Medium/Large automatically when GPU is available
- GPU-accelerated transcription with CUDA support

**Performance Optimizations**
- Implement batched inference to reduce diarization + transcription overhead
- Real-time or near-real-time processing with GPU acceleration
- Parallel processing of audio segments

**Quality Improvements**
- Add confidence-based segment filtering
- Evaluate LLM extraction using long-form, real consultation recordings
- Introduce quantitative accuracy benchmarks (WER, speaker attribution accuracy)

**Production Readiness**
- Deploy on cloud instances (AWS, Azure, GCP) with high-end GPUs
- Implement model caching and warm-up strategies
- Add monitoring and alerting for model performance



