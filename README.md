# TuneSlice 🎵

TuneSlice is a sleek, modern waveform-based song snippet editor designed for visual region selection and 30-second audio clip generation. This application utilizes a premium dark aesthetic inspired by Spotify and features real-time, interactive audio slicing.

---

## 🛠️ Tech Stack

- **Frontend**: Next.js (App Router), React, TypeScript, Tailwind CSS, WaveSurfer.js (with Regions plugin), Axios, and Zustand (state management).
- **Backend**: FastAPI (Python), SQLAlchemy, Pydantic v2, and SQLite (metadata storage).
- **Media Engine**: FFmpeg (audio slicing & transcoding) and local filesystem storage.

---

## 📂 Project Architecture

```text
TuneSlicer/
├── frontend/                # Next.js Frontend Application
│   ├── app/                 # App Router (pages, layouts, globals.css)
│   ├── components/          # Reusable shared UI primitives (buttons, modals, etc.)
│   ├── features/            # Feature-centric modules (waveform-clipping, player, etc.)
│   ├── hooks/               # Custom React hooks (e.g. useWaveSurfer, useAudio)
│   ├── services/            # API integration & clients (axios base, interceptors)
│   ├── lib/                 # Third-party configurations & initializers
│   ├── types/               # TypeScript declarations & interfaces
│   └── utils/               # Shared frontend utility helpers
│
├── backend/                 # FastAPI Backend Application
│   ├── api/                 # API endpoint routing (/api/v1/)
│   ├── schemas/             # Pydantic validation schemas (request/response)
│   ├── models/              # SQLAlchemy database structures (Song, etc.)
│   ├── services/            # Core business logic handlers (FFmpeg wrapper, DB services)
│   ├── db/                  # SQLite connection and session setup
│   ├── core/                # System configuration, setting loads, CORS definitions
│   └── utils/               # Shared backend helper functions
│
├── songs/                   # Root storage directory for raw audio files
├── clips/                   # Target storage folder for generated 30-second MP3 clips
└── thumbnails/              # Album artwork and song thumbnails
```

---

## 🚀 Setup & Execution Guide

### Prerequisites
Make sure you have the following installed:
- **Node.js** (v18.0.0 or higher)
- **Python** (v3.9 or higher)
- **FFmpeg** (added to system environment PATH variable)

---

### 1. Backend Server Setup

Navigate into the backend directory:
```bash
cd backend
```

Create a Python virtual environment and activate it:
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

Install python dependencies:
```bash
pip install -r requirements.txt
```

Verify that the backend environment settings are defined inside `backend/.env` (a `.env.example` has been provided for reference):
```env
PROJECT_NAME="TuneSlice"
API_V1_STR="/api/v1"
BACKEND_CORS_ORIGINS=["http://localhost:3000"]
DATABASE_URL="sqlite:///./tuneslice.db"
SONGS_DIR="../songs"
CLIPS_DIR="../clips"
THUMBNAILS_DIR="../thumbnails"
```

Start the FastAPI application:
```bash
uvicorn main:app --reload --port 8000
```
- Interactive API documentation will be available at: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health status check is served at: [http://localhost:8000/](http://localhost:8000/)

---

### 2. Frontend Application Setup

Navigate into the frontend directory:
```bash
cd frontend
```

Install node packages:
```bash
npm install
```

Configure local environment settings in `frontend/.env.local` (referenced from `frontend/.env.example`):
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

Launch the Next.js dev server:
```bash
npm run dev
```
- Open the application in your browser: [http://localhost:3000](http://localhost:3000)

---

## 🔒 Security & CORS

CORS middleware is fully configured inside `backend/main.py`. By default, the application is set up to allow secure communications from `http://localhost:3000` (Next.js development server). You can adjust this list in `BACKEND_CORS_ORIGINS` inside your `.env` settings.
