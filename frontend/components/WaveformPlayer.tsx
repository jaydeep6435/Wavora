'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js';
import { Play, Pause, Scissors, Loader2, Download, X, Music2 } from 'lucide-react';
import { Song, MusicService } from '../services/api';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';

interface WaveformPlayerProps {
  song: Song;
  onClose: () => void;
}

// Mobile: pixels per second of audio. Tuned so ~30s of audio fills the viewport.
// At 12 px/sec on a 375px phone: 31s visible, 30s clip = 360px (fits perfectly).
const MOBILE_PX_PER_SEC = 12;

export default function WaveformPlayer({ song, onClose }: WaveformPlayerProps) {
  const getFullUrl = (url: string | null) => {
    if (!url) return '';
    if (url.startsWith('http') || url.startsWith('data:')) return url;
    return `http://localhost:8000${url}`;
  };

  // ─── Refs ──────────────────────────────────────────────────────
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const regionsRef = useRef<RegionsPlugin | null>(null);
  const wrapperRef = useRef<HTMLElement | null>(null);
  const viewportRef = useRef<HTMLDivElement>(null);

  // Mobile drag tracking
  const dragRef = useRef<{
    type: 'left' | 'right' | 'center';
    startX: number;
    initialStart: number;
    initialEnd: number;
  } | null>(null);

  const scrollTimeRef = useRef(0);
  const clipStartRef = useRef(0);
  const clipEndRef = useRef(30);
  const durationRef = useRef(0);

  // ─── State ─────────────────────────────────────────────────────
  const [isMobile, setIsMobile] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedClip, setGeneratedClip] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [clipStart, setClipStart] = useState(0);
  const [clipEnd, setClipEnd] = useState(30);
  // Incremented on waveform scroll to trigger overlay re-render
  const [, setScrollTick] = useState(0);

  // Keep refs in sync with state (avoids stale closures in event handlers)
  useEffect(() => { clipStartRef.current = clipStart; }, [clipStart]);
  useEffect(() => { clipEndRef.current = clipEnd; }, [clipEnd]);
  useEffect(() => { durationRef.current = duration; }, [duration]);

  // ─── Detect mobile on mount ────────────────────────────────────
  useEffect(() => {
    setIsMobile(window.innerWidth < 768);
  }, []);

  // ─── Helpers ───────────────────────────────────────────────────
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const tenths = Math.floor((seconds % 1) * 10);
    return `${mins}:${secs.toString().padStart(2, '0')}.${tenths}`;
  };

  // ─── Initialize WaveSurfer ─────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    let isCancelled = false;

    // Always check window directly (state might not be set yet on first render)
    const mobile = typeof window !== 'undefined' && window.innerWidth < 768;

    // Desktop uses Regions plugin; mobile uses custom overlay
    const regions = mobile ? null : RegionsPlugin.create();
    if (regions) regionsRef.current = regions;

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: mobile ? 'rgba(255, 255, 255, 0.3)' : 'rgba(255, 255, 255, 0.25)',
      progressColor: mobile ? 'rgba(255, 255, 255, 0.3)' : 'rgba(255, 255, 255, 0.7)',
      cursorColor: mobile ? 'transparent' : '#ef4444',
      cursorWidth: mobile ? 0 : 2,
      barWidth: mobile ? 2 : 3,
      barGap: mobile ? 1 : 2,
      barRadius: 3,
      height: mobile ? 80 : 130,
      minPxPerSec: mobile ? MOBILE_PX_PER_SEC : 0,
      fillParent: !mobile,
      plugins: regions ? [regions] : [],
      url: getFullUrl(song.audio_url),
      interact: !mobile, // Disable WaveSurfer click-to-seek on mobile
    });

    wavesurferRef.current = ws;

    ws.on('ready', () => {
      if (isCancelled) return;
      setIsReady(true);

      const dur = ws.getDuration();
      setDuration(dur);
      durationRef.current = dur;
      const endTime = Math.min(30, dur);
      setClipStart(0);
      setClipEnd(endTime);
      clipStartRef.current = 0;
      clipEndRef.current = endTime;

      // Store wrapper ref for scroll tracking
      const wrapper = ws.getWrapper();
      wrapperRef.current = wrapper;

      if (mobile && wrapper) {
        // Enable smooth horizontal-only touch scrolling
        wrapper.classList.add('hide-scrollbar');
        wrapper.style.touchAction = 'pan-x';
        wrapper.style.overflowX = 'auto';
        (wrapper.style as unknown as Record<string, string>).WebkitOverflowScrolling = 'touch';
        // Hide scrollbar for cleaner look
        wrapper.style.scrollbarWidth = 'none';
        (wrapper.style as unknown as Record<string, string>).msOverflowStyle = 'none';
      }

      // Desktop: add draggable/resizable region
      if (regions) {
        try {
          regions.addRegion({
            start: 0,
            end: endTime,
            content: '✂ Clip',
            color: 'rgba(255, 255, 255, 0.1)',
            drag: true,
            resize: true,
            minLength: 5,
            maxLength: 30,
          });
        } catch (e) {
          console.warn('Region error:', e);
        }
      }
    });

    // Playback events
    ws.on('audioprocess', (time) => {
      if (isCancelled) return;
      setCurrentTime(time);
      // Loop within clip boundaries
      if (ws.isPlaying() && time >= clipEndRef.current) {
        ws.setTime(clipStartRef.current);
      }
    });

    ws.on('timeupdate', (time) => {
      if (!isCancelled) setCurrentTime(time);
    });

    ws.on('play', () => { if (!isCancelled) setIsPlaying(true); });
    ws.on('pause', () => { if (!isCancelled) setIsPlaying(false); });

    ws.on('error', (err) => {
      if (!isCancelled) {
        console.error('WaveSurfer error:', err);
        toast.error('Failed to load audio.');
      }
    });

    // Desktop: sync region changes to state
    if (regions) {
      regions.on('region-updated', (region) => {
        if (!isCancelled) {
          setClipStart(region.start);
          setClipEnd(region.end);
        }
      });
    }

    return () => {
      isCancelled = true;
      ws.destroy();
    };
  }, [song.audio_url]);

  // ─── Mobile: track waveform scroll position ───────────────────
  useEffect(() => {
    if (!isMobile || !isReady || !wrapperRef.current) return;

    const wrapper = wrapperRef.current;
    let rafId: number;

    const onScroll = () => {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        scrollTimeRef.current = wrapper.scrollLeft / MOBILE_PX_PER_SEC;
        setScrollTick((n) => n + 1);
      });
    };

    wrapper.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      wrapper.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(rafId);
    };
  }, [isMobile, isReady]);

  // ─── Mobile: touch drag handlers ──────────────────────────────
  const handleDragStart = useCallback(
    (type: 'left' | 'right' | 'center', e: React.TouchEvent) => {
      e.stopPropagation();
      e.preventDefault();
      const touch = e.touches[0];
      dragRef.current = {
        type,
        startX: touch.clientX,
        initialStart: clipStartRef.current,
        initialEnd: clipEndRef.current,
      };
    },
    [],
  );

  const handleDragMove = useCallback((e: React.TouchEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    e.stopPropagation();
    e.preventDefault();

    const touch = e.touches[0];
    const deltaX = touch.clientX - drag.startX;
    const deltaTime = deltaX / MOBILE_PX_PER_SEC;
    const dur = durationRef.current;
    const clipDur = drag.initialEnd - drag.initialStart;

    if (drag.type === 'center') {
      // Slide the whole selection window through the song
      let newStart = drag.initialStart + deltaTime;
      let newEnd = drag.initialEnd + deltaTime;
      // Clamp to song boundaries, preserving duration
      if (newStart < 0) {
        newStart = 0;
        newEnd = clipDur;
      }
      if (newEnd > dur) {
        newEnd = dur;
        newStart = dur - clipDur;
      }
      setClipStart(newStart);
      setClipEnd(newEnd);
    } else if (drag.type === 'left') {
      let newStart = drag.initialStart + deltaTime;
      newStart = Math.max(0, newStart);
      newStart = Math.min(newStart, drag.initialEnd - 5); // min 5s clip
      if (drag.initialEnd - newStart > 30) newStart = drag.initialEnd - 30; // max 30s
      setClipStart(newStart);
    } else {
      let newEnd = drag.initialEnd + deltaTime;
      newEnd = Math.min(dur, newEnd);
      newEnd = Math.max(drag.initialStart + 5, newEnd); // min 5s clip
      if (newEnd - drag.initialStart > 30) newEnd = drag.initialStart + 30; // max 30s
      setClipEnd(newEnd);
    }
  }, []);

  const handleDragEnd = useCallback(() => {
    dragRef.current = null;
  }, []);

  // ─── Playback ─────────────────────────────────────────────────
  const togglePlayback = () => {
    const ws = wavesurferRef.current;
    if (!ws) return;
    if (!isPlaying) {
      const t = ws.getCurrentTime();
      if (t < clipStart || t >= clipEnd) ws.setTime(clipStart);
    }
    ws.playPause();
  };

  // ─── Generate clip ────────────────────────────────────────────
  const handleGenerate = async () => {
    if (clipEnd <= clipStart) return;
    setIsGenerating(true);
    setGeneratedClip(null);
    const toastId = toast.loading('Slicing your audio clip...');
    try {
      const response = await MusicService.generateClip({
        songId: song.id,
        startTime: Number(clipStart.toFixed(3)),
        endTime: Number(clipEnd.toFixed(3)),
      });
      setGeneratedClip(getFullUrl(response.clipUrl));
      toast.success('Clip generated!', { id: toastId });
    } catch (err) {
      console.error(err);
      toast.error('Failed to generate clip.', { id: toastId });
    } finally {
      setIsGenerating(false);
    }
  };

  // ─── Download ─────────────────────────────────────────────────
  const handleInstantDownload = async () => {
    if (!generatedClip) return;
    const toastId = toast.loading('Downloading...');
    try {
      const response = await fetch(generatedClip);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = `Wavora-${song.title}-Clip.mp3`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success('Downloaded!', { id: toastId });
    } catch {
      toast.error('Download failed.');
    }
  };

  // ─── Computed values ──────────────────────────────────────────
  const clipDuration = clipEnd - clipStart;

  // Mobile overlay pixel positions (relative to the visible viewport)
  const scrollT = scrollTimeRef.current;
  const selLeftPx = (clipStart - scrollT) * MOBILE_PX_PER_SEC;
  const selRightPx = (clipEnd - scrollT) * MOBILE_PX_PER_SEC;
  const selWidthPx = selRightPx - selLeftPx;

  // Playback head position
  const playheadPx = (currentTime - scrollT) * MOBILE_PX_PER_SEC;

  // ─── Render ───────────────────────────────────────────────────
  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.98 }}
      transition={{ duration: 0.2 }}
      className="bg-black/40 backdrop-blur-2xl rounded-[24px] md:rounded-[32px] p-4 md:p-10 w-full mx-auto relative border border-white/10 shadow-2xl"
    >
      {/* Close */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 md:top-6 md:right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/10 transition-colors z-10"
      >
        <X className="w-5 h-5 md:w-6 md:h-6" />
      </button>

      {/* ─── Song Header ─── */}
      <div className="flex items-center gap-3 md:gap-6 mb-4 md:mb-10 pr-10">
        {song.thumbnail_url ? (
          <img
            src={getFullUrl(song.thumbnail_url)}
            alt={song.title}
            className="w-12 h-12 md:w-28 md:h-28 rounded-lg md:rounded-2xl object-cover border border-white/10 flex-shrink-0"
          />
        ) : (
          <div className="w-12 h-12 md:w-28 md:h-28 rounded-lg md:rounded-2xl bg-[#111] flex items-center justify-center border border-white/10 flex-shrink-0">
            <Music2 className="w-5 h-5 md:w-10 md:h-10 text-zinc-700" />
          </div>
        )}
        <div className="min-w-0">
          <h2 className="text-base md:text-3xl font-bold text-white truncate tracking-tight">
            {song.title}
          </h2>
          <p className="text-zinc-400 font-medium text-xs md:text-lg truncate">{song.artist}</p>
        </div>
      </div>

      {/* ─── Waveform Section ─── */}
      <div className="mb-3 md:mb-8">
        {/* Loading spinner */}
        {!isReady && (
          <div className="h-[80px] md:h-[130px] flex flex-col items-center justify-center gap-2 bg-black/20 rounded-xl border border-white/5">
            <Loader2 className="w-6 h-6 animate-spin text-white" />
            <span className="text-xs text-zinc-400 font-medium">Loading waveform...</span>
          </div>
        )}

        {/* Waveform + overlay container */}
        <div
          ref={viewportRef}
          className={`relative overflow-hidden rounded-xl ${
            !isMobile ? 'bg-black/20 p-4 md:p-6 border border-white/5 rounded-2xl' : ''
          }`}
        >
          {/* WaveSurfer renders here — always in same DOM position */}
          <div
            ref={containerRef}
            className={`w-full ${!isReady ? 'hidden' : 'block'}`}
          />

          {/* ===== MOBILE SELECTION OVERLAY ===== */}
          {isMobile && isReady && (
            <>
              {/* ── Left dimmed area ── */}
              <div
                className="absolute top-0 bottom-0 left-0 bg-black/55"
                style={{
                  width: Math.max(0, selLeftPx),
                  pointerEvents: 'none',
                }}
              />

              {/* ── Right dimmed area ── */}
              <div
                className="absolute top-0 bottom-0 bg-black/55"
                style={{
                  left: Math.max(0, selRightPx),
                  right: 0,
                  pointerEvents: 'none',
                }}
              />

              {/* ── Selection frame (visual border) ── */}
              <div
                className="absolute top-0 bottom-0"
                style={{
                  left: selLeftPx,
                  width: Math.max(0, selWidthPx),
                  borderTop: '3px solid rgba(255, 255, 255, 0.75)',
                  borderBottom: '3px solid rgba(255, 255, 255, 0.75)',
                  pointerEvents: 'none',
                  boxSizing: 'border-box',
                }}
              >
                {/* Duration label centered in the selection */}
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none select-none">
                  <span className="text-white/60 font-bold text-xl tabular-nums tracking-tight">
                    {clipDuration.toFixed(1)}
                  </span>
                </div>
              </div>

              {/* ── Center drag zone ── 
                  Touch here and drag left/right to slide the whole clip.
                  Sits between the handles, captures touch to prevent waveform scroll. */}
              <div
                className="absolute top-0 bottom-0"
                style={{
                  left: selLeftPx + 22,
                  width: Math.max(0, selWidthPx - 44),
                  pointerEvents: 'auto',
                  touchAction: 'none',
                  cursor: 'grab',
                  zIndex: 15,
                }}
                onTouchStart={(e) => handleDragStart('center', e)}
                onTouchMove={handleDragMove}
                onTouchEnd={handleDragEnd}
              />

              {/* ── Left handle ── 
                  Visual: 5px white bar. Touch target: 40px wide for easy grabbing. */}
              <div
                className="absolute top-0 bottom-0 flex items-center justify-center"
                style={{
                  left: selLeftPx - 18,
                  width: 40,
                  pointerEvents: 'auto',
                  touchAction: 'none',
                  cursor: 'col-resize',
                  zIndex: 20,
                }}
                onTouchStart={(e) => handleDragStart('left', e)}
                onTouchMove={handleDragMove}
                onTouchEnd={handleDragEnd}
              >
                <div className="w-[5px] h-9 bg-white rounded-full shadow-lg shadow-white/30" />
              </div>

              {/* ── Right handle ── */}
              <div
                className="absolute top-0 bottom-0 flex items-center justify-center"
                style={{
                  left: selRightPx - 22,
                  width: 40,
                  pointerEvents: 'auto',
                  touchAction: 'none',
                  cursor: 'col-resize',
                  zIndex: 20,
                }}
                onTouchStart={(e) => handleDragStart('right', e)}
                onTouchMove={handleDragMove}
                onTouchEnd={handleDragEnd}
              >
                <div className="w-[5px] h-9 bg-white rounded-full shadow-lg shadow-white/30" />
              </div>

              {/* ── Playhead indicator ── */}
              {isPlaying && playheadPx >= 0 && (
                <div
                  className="absolute top-0 bottom-0 w-[2px] bg-red-500 pointer-events-none"
                  style={{ left: playheadPx, zIndex: 25 }}
                />
              )}
            </>
          )}
        </div>

        {/* ─── Time labels ─── */}
        {isReady && (
          <div className="flex justify-between items-center mt-2 md:mt-4 px-1">
            <span className="text-xs text-zinc-500 font-mono">{formatTime(clipStart)}</span>
            <span
              className={`text-[10px] md:text-xs font-bold px-2.5 py-0.5 rounded-full ${
                clipDuration > 28 ? 'bg-orange-500/20 text-orange-400' : 'bg-white/10 text-white'
              }`}
            >
              {clipDuration.toFixed(1)}s / 30s
            </span>
            <span className="text-xs text-zinc-500 font-mono">{formatTime(clipEnd)}</span>
          </div>
        )}

        {/* Mobile interaction hint */}
        {isMobile && isReady && (
          <p className="text-center text-[10px] text-zinc-600 mt-1">
            Swipe waveform to navigate · Drag handles to adjust · Hold center to slide clip
          </p>
        )}
      </div>

      {/* ─── Action Buttons ─── */}
      <div className="flex items-center gap-2.5 md:gap-3">
        <button
          onClick={togglePlayback}
          disabled={!isReady}
          className="btn-primary w-11 h-11 md:w-14 md:h-14 flex-shrink-0 disabled:opacity-50 touch-manipulation"
        >
          {isPlaying ? (
            <Pause className="w-5 h-5 md:w-6 md:h-6" fill="currentColor" />
          ) : (
            <Play className="w-5 h-5 md:w-6 md:h-6 ml-0.5" fill="currentColor" />
          )}
        </button>

        <button
          onClick={handleGenerate}
          disabled={!isReady || isGenerating || clipDuration < 1}
          className="btn-primary flex-1 h-11 md:h-14 gap-2 text-sm md:text-base disabled:opacity-50 touch-manipulation"
        >
          {isGenerating ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Scissors className="w-4 h-4 md:w-5 md:h-5" />
          )}
          {isGenerating ? 'Slicing...' : 'Generate Clip'}
        </button>

        <AnimatePresence>
          {generatedClip && (
            <motion.button
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              onClick={handleInstantDownload}
              className="btn-primary w-11 h-11 md:w-14 md:h-14 flex-shrink-0 touch-manipulation"
              title="Download MP3"
            >
              <Download className="w-4 h-4 md:w-5 md:h-5" />
            </motion.button>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
