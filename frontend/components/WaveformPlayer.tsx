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
    type: 'left' | 'right';
    startX: number;
    initialLeft: number;
    initialRight: number;
  } | null>(null);
  
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // ─── State ─────────────────────────────────────────────────────
  const [isMobile, setIsMobile] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedClip, setGeneratedClip] = useState<string | null>(null);
  
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  
  // Desktop state
  const [clipStart, setClipStart] = useState(0);
  const [clipEnd, setClipEnd] = useState(30);

  // Mobile state (Fixed Window Model)
  const [pxPerSec, setPxPerSec] = useState(10);
  const [scrollPx, setScrollPx] = useState(0);
  const [mobileEdges, setMobileEdges] = useState({ left: 0, right: 300 });

  // ─── Sync Refs for Callbacks ───────────────────────────────────
  const pxPerSecRef = useRef(pxPerSec);
  useEffect(() => { pxPerSecRef.current = pxPerSec; }, [pxPerSec]);

  // Derived unified boundaries
  const actualClipStart = isMobile ? Math.min(duration, (scrollPx + mobileEdges.left) / pxPerSec) : clipStart;
  const actualClipEnd = isMobile ? Math.min(duration, (scrollPx + mobileEdges.right) / pxPerSec) : clipEnd;
  const actualClipDuration = Math.max(0, actualClipEnd - actualClipStart);

  const actualClipStartRef = useRef(0);
  const actualClipEndRef = useRef(30);
  useEffect(() => {
    actualClipStartRef.current = actualClipStart;
    actualClipEndRef.current = actualClipEnd;
  }, [actualClipStart, actualClipEnd]);

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
    if (!containerRef.current || !viewportRef.current) return;
    let isCancelled = false;

    const mobile = typeof window !== 'undefined' && window.innerWidth < 768;
    
    // Dynamically calculate pxPerSec so 32 seconds fits the screen width perfectly
    let currentPxPerSec = 10;
    if (mobile) {
      currentPxPerSec = viewportRef.current.clientWidth / 32;
      setPxPerSec(currentPxPerSec);
    }

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
      minPxPerSec: mobile ? currentPxPerSec : 0,
      fillParent: !mobile,
      plugins: regions ? [regions] : [],
      url: getFullUrl(song.audio_url),
      interact: !mobile,
      autoScroll: false,
    });

    wavesurferRef.current = ws;

    ws.on('ready', () => {
      if (isCancelled) return;
      setIsReady(true);

      const dur = ws.getDuration();
      setDuration(dur);

      const wrapper = ws.getWrapper();
      wrapperRef.current = wrapper;

      if (mobile && wrapper) {
        wrapper.style.touchAction = 'pan-x';
        wrapper.style.overflowX = 'auto';
        (wrapper.style as unknown as Record<string, string>).WebkitOverflowScrolling = 'touch';
        
        // The scrollable element is actually inside WaveSurfer's shadow DOM.
        // We must inject a style tag to kill the global red scrollbar thumb.
        const shadow = wrapper.shadowRoot;
        if (shadow) {
          const style = document.createElement('style');
          style.innerHTML = `
            *::-webkit-scrollbar { display: none !important; width: 0 !important; height: 0 !important; }
            * { scrollbar-width: none !important; -ms-overflow-style: none !important; }
            [part="cursor"] { display: none !important; }
          `;
          shadow.appendChild(style);
        }

        // Initialize fixed mobile window edges (e.g. 10px padding from edges, up to 30s)
        const vw = viewportRef.current!.clientWidth;
        const initLeft = 10;
        const initRight = Math.min(vw - 10, initLeft + 30 * currentPxPerSec);
        setMobileEdges({ left: initLeft, right: initRight });
      } else {
        const endTime = Math.min(30, dur);
        setClipStart(0);
        setClipEnd(endTime);
        if (regions) {
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
        }
      }
    });

    ws.on('audioprocess', (time) => {
      if (isCancelled) return;
      setCurrentTime(time);
      if (ws.isPlaying() && time >= actualClipEndRef.current) {
        ws.setTime(actualClipStartRef.current);
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

  // ─── Mobile: Native scroll tracking ──────────────────────────────
  useEffect(() => {
    if (!isMobile || !isReady || !wavesurferRef.current) return;
    const ws = wavesurferRef.current;
    let rafId: number;

    const onScroll = (visibleStartTime: number, visibleEndTime: number, newScrollLeft: number) => {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        setScrollPx(newScrollLeft);
        
        if (ws) {
          if (ws.isPlaying()) {
            ws.pause();
          }
          
          // Instantly snap the playhead to the left bar so that
          // manual play or auto-play always starts exactly from the beginning of the clip.
          const newClipStart = Math.min(duration, (newScrollLeft + mobileEdges.left) / pxPerSecRef.current);
          ws.setTime(newClipStart);
        }

        if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current);
        
        scrollTimeoutRef.current = setTimeout(() => {
          if (ws) {
            ws.play();
          }
        }, 150);
      });
    };

    ws.on('scroll', onScroll);
    return () => {
      ws.un('scroll', onScroll);
      cancelAnimationFrame(rafId);
    };
  }, [isMobile, isReady, duration, mobileEdges.left]);

  // ─── Mobile: Fixed handle drag logic ───────────────────────────
  const handleDragStart = useCallback(
    (type: 'left' | 'right', e: React.TouchEvent) => {
      e.stopPropagation();
      const touch = e.touches[0];
      dragRef.current = {
        type,
        startX: touch.clientX,
        initialLeft: mobileEdges.left,
        initialRight: mobileEdges.right,
      };
    },
    [mobileEdges],
  );

  const handleDragMove = useCallback((e: React.TouchEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    e.stopPropagation();

    const touch = e.touches[0];
    const deltaX = touch.clientX - drag.startX;
    const viewportWidth = viewportRef.current?.clientWidth || 300;
    const pps = pxPerSecRef.current;

    if (drag.type === 'left') {
      let newLeft = drag.initialLeft + deltaX;
      newLeft = Math.max(0, newLeft);
      newLeft = Math.min(newLeft, drag.initialRight - 5 * pps); // min 5s
      setMobileEdges(prev => ({ ...prev, left: newLeft }));
    } else if (drag.type === 'right') {
      let newRight = drag.initialRight + deltaX;
      newRight = Math.min(viewportWidth, newRight);
      newRight = Math.max(drag.initialLeft + 5 * pps, newRight); // min 5s
      if (newRight - drag.initialLeft > 30 * pps) {
          newRight = drag.initialLeft + 30 * pps; // max 30s
      }
      setMobileEdges(prev => ({ ...prev, right: newRight }));
    }
  }, []);

  const handleDragEnd = useCallback(() => {
    dragRef.current = null;
    
    // Play instantly after resizing
    setTimeout(() => {
      const ws = wavesurferRef.current;
      if (ws && actualClipStartRef.current !== undefined) {
        ws.setTime(actualClipStartRef.current);
        ws.play();
      }
    }, 50);
  }, []);

  // ─── Playback ─────────────────────────────────────────────────
  const togglePlayback = () => {
    const ws = wavesurferRef.current;
    if (!ws) return;
    if (!isPlaying) {
      const t = ws.getCurrentTime();
      if (t < actualClipStart || t >= actualClipEnd) {
        ws.setTime(actualClipStart);
      }
    }
    ws.playPause();
  };

  // ─── Generate clip ────────────────────────────────────────────
  const handleGenerate = async () => {
    if (actualClipDuration < 1) return;
    setIsGenerating(true);
    setGeneratedClip(null);
    const toastId = toast.loading('Slicing your audio clip...');
    try {
      const response = await MusicService.generateClip({
        songId: song.id,
        startTime: Number(actualClipStart.toFixed(3)),
        endTime: Number(actualClipEnd.toFixed(3)),
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

  // Mobile playhead screen position
  const playheadScreenPx = isMobile ? (currentTime * pxPerSec) - scrollPx : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.98 }}
      transition={{ duration: 0.2 }}
      className="bg-black/40 backdrop-blur-2xl rounded-[24px] md:rounded-[32px] p-4 md:p-10 w-full mx-auto relative border border-white/10 shadow-2xl"
    >
      <button
        onClick={onClose}
        className="absolute top-4 right-4 md:top-6 md:right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/10 transition-colors z-10"
      >
        <X className="w-5 h-5 md:w-6 md:h-6" />
      </button>

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

      <div className="mb-3 md:mb-8">
        {!isReady && (
          <div className="h-[80px] md:h-[130px] flex flex-col items-center justify-center gap-2 bg-black/20 rounded-xl border border-white/5">
            <Loader2 className="w-6 h-6 animate-spin text-white" />
            <span className="text-xs text-zinc-400 font-medium">Loading waveform...</span>
          </div>
        )}

        <div
          ref={viewportRef}
          className={`relative overflow-hidden rounded-xl ${
            !isMobile ? 'bg-black/20 p-4 md:p-6 border border-white/5 rounded-2xl' : ''
          }`}
        >
          <div
            ref={containerRef}
            className={`w-full ${!isReady ? 'hidden' : 'block'} ${isMobile ? 'mobile-waveform' : ''}`}
          />

          {/* ===== FIXED MOBILE OVERLAY ===== */}
          {isMobile && isReady && (
            <div className="absolute inset-0 z-10 pointer-events-none">
              
              {/* Dimmed Left */}
              <div
                className="absolute top-0 bottom-0 left-0 bg-black/55 backdrop-blur-[1px]"
                style={{ width: mobileEdges.left }}
              />

              {/* Dimmed Right */}
              <div
                className="absolute top-0 bottom-0 bg-black/55 backdrop-blur-[1px]"
                style={{ left: mobileEdges.right, right: 0 }}
              />

              {/* Selection Frame */}
              <div
                className="absolute top-0 bottom-0 box-border border-t-[3px] border-b-[3px] border-white/80"
                style={{ left: mobileEdges.left, width: mobileEdges.right - mobileEdges.left }}
              >
                <div className="absolute inset-0 flex items-center justify-center opacity-50">
                  <span className="text-white font-bold text-xl tabular-nums tracking-tight drop-shadow-md">
                    {actualClipDuration.toFixed(1)}
                  </span>
                </div>
              </div>

              {/* Left Handle */}
              <div
                className="absolute top-0 bottom-0 flex items-center justify-center pointer-events-auto"
                style={{ left: mobileEdges.left - 20, width: 40, cursor: 'col-resize' }}
                onTouchStart={(e) => handleDragStart('left', e)}
                onTouchMove={handleDragMove}
                onTouchEnd={handleDragEnd}
              >
                <div className="w-1.5 h-10 bg-white rounded-full shadow-[0_0_8px_rgba(255,255,255,0.5)]" />
              </div>

              {/* Right Handle */}
              <div
                className="absolute top-0 bottom-0 flex items-center justify-center pointer-events-auto"
                style={{ left: mobileEdges.right - 20, width: 40, cursor: 'col-resize' }}
                onTouchStart={(e) => handleDragStart('right', e)}
                onTouchMove={handleDragMove}
                onTouchEnd={handleDragEnd}
              >
                <div className="w-1.5 h-10 bg-white rounded-full shadow-[0_0_8px_rgba(255,255,255,0.5)]" />
              </div>

              {/* Clean Playhead */}
              {isPlaying && playheadScreenPx >= mobileEdges.left && playheadScreenPx <= mobileEdges.right && (
                <div
                  className="absolute top-0 bottom-0 w-0.5 bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)] pointer-events-none"
                  style={{ left: playheadScreenPx, zIndex: 25 }}
                />
              )}
            </div>
          )}
        </div>

        {isReady && (
          <div className="flex justify-between items-center mt-2 md:mt-4 px-1">
            <span className="text-xs text-zinc-500 font-mono">{formatTime(actualClipStart)}</span>
            <span
              className={`text-[10px] md:text-xs font-bold px-2.5 py-0.5 rounded-full ${
                actualClipDuration > 28 ? 'bg-orange-500/20 text-orange-400' : 'bg-white/10 text-white'
              }`}
            >
              {actualClipDuration.toFixed(1)}s / 30s
            </span>
            <span className="text-xs text-zinc-500 font-mono">{formatTime(actualClipEnd)}</span>
          </div>
        )}

        {isMobile && isReady && (
          <p className="text-center text-[10px] text-zinc-600 mt-1">
            Scrub waveform to seek · Drag handles to adjust
          </p>
        )}
      </div>

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
          disabled={!isReady || isGenerating || actualClipDuration < 1}
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
