<div align="center">
  <img src="./frontend/public/file.svg" alt="Wavora Logo" width="120" />

  # Wavora

  **A modern, premium audio-clipping web application**
  
  <p>Wavora allows you to visually explore songs, select precise 30-second regions via an interactive waveform, and instantly generate high-quality audio clips. Built with a production-ready stack and a Dialed.gg-inspired glassmorphism aesthetic.</p>

  [![Next.js](https://img.shields.io/badge/Next.js-14-black?style=for-the-badge&logo=next.js)](https://nextjs.org/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
  [![FFmpeg](https://img.shields.io/badge/FFmpeg-Backend-green?style=for-the-badge&logo=ffmpeg)](https://ffmpeg.org/)
  [![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-v4-38B2AC?style=for-the-badge&logo=tailwind-css)](https://tailwindcss.com/)
  [![WaveSurfer.js](https://img.shields.io/badge/WaveSurfer-v7-ff6600?style=for-the-badge)](https://wavesurfer-js.org/)
</div>

---

## ✨ Features
- **Visual Waveform Editor:** Interactively drag and resize a selection region over the song's audio waveform. Max length enforced at 30 seconds.
- **Lightning Fast Clipping:** Asynchronous, non-blocking FFmpeg implementation on the backend for instant MP3 generation.
- **Premium Aesthetics:** Dialed.gg-inspired design featuring deep dark modes, glassmorphism UI, neon green accents, and smooth Framer Motion micro-interactions.
- **Local File Sync:** Drop MP3s in the `/songs` folder and the backend automatically parses durations, metadata, and thumbnails into a local SQLite database.
- **Beautiful Error Handling:** Integrated `react-hot-toast` for elegant, non-blocking toast notifications.

## 🛠 Tech Stack
- **Frontend:** Next.js (App Router), React, TypeScript, Tailwind CSS, Framer Motion, WaveSurfer.js, Axios, React Hot Toast
- **Backend:** Python, FastAPI, SQLAlchemy, SQLite, FFprobe & FFmpeg

## 🚀 Getting Started

### Prerequisites
1. **Node.js** (v18+)
2. **Python** (v3.8+)
3. **FFmpeg** (Must be installed and added to your system PATH)

### 1. Setup Backend
```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload
```
*Note: The backend runs on `http://localhost:8000`. On first run, it will automatically scan your `songs/` directory and populate the SQLite database.*

### 2. Setup Frontend
```bash
cd frontend
npm install
npm run dev
```
*Note: The frontend runs on `http://localhost:3000`.*

### 3. Add Your Music
Drop any `.mp3` files into the root `/songs` directory. If you have album art, drop a matching `.jpg` or `.png` into `/thumbnails` with the exact same base filename (e.g., `song.mp3` -> `song.jpg`). Restart the backend to automatically sync them.

## 🗺 API Overview
- `GET /api/v1/songs` - Retrieve a list of synced songs with pagination.
- `GET /api/v1/search?q=...` - Search songs by title or artist.
- `POST /api/v1/generate-clip` - Submit a clipping request (`songId`, `startTime`, `endTime`) and receive a generated clip URL.

## 🔮 Future Roadmap
- AI Chorus Detection (via Librosa) to automatically highlight the best part of the song.
- Lyric Synchronization.
- Cloud storage integration (AWS S3) for generated clips.

---
*Developed as a high-performance portfolio centerpiece.*
