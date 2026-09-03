'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js';
import { Play, Pause, Scissors, Loader2, Download, X, Music2, ZoomIn, ZoomOut } from 'lucide-react';
import { Song, MusicService } from '../services/api';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';

interface WaveformPlayerProps {
  song: Song;
  onClose: () => void;
}

// Zoom levels in px-per-second. Higher = more spread out = easier to grab handles on mobile
const ZOOM_LEVELS = [30, 60, 100, 150, 220, 300];
const DEFAULT_ZOOM_INDEX = 1; // Start at 60 px/sec

export default function WaveformPlayer({ song, onClose }: WaveformPlayerProps) {
  const getFullUrl = (url: string | null) => {
    if (!url) return '';
    if (url.startsWith('http') || url.startsWith('data:')) return url;
    return `http://localhost:8000${url}`;
  };

  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const regionsRef = useRef<RegionsPlugin | null>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [selectedRange, setSelectedRange] = useState<{ start: number; end: number } | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedClip, setGeneratedClip] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [zoomIndex, setZoomIndex] = useState(DEFAULT_ZOOM_INDEX);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  useEffect(() => {
    if (!containerRef.current) return;
    let isCancelled = false;

    const regions = RegionsPlugin.create();
    regionsRef.current = regions;

    const isMobile = window.innerWidth < 768;
    const initialZoom = ZOOM_LEVELS[DEFAULT_ZOOM_INDEX];

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: 'rgba(255, 255, 255, 0.25)',
      progressColor: 'rgba(255, 255, 255, 0.7)',
      cursorColor: '#ef4444',
      cursorWidth: 2,
      barWidth: isMobile ? 2 : 3,
      barGap: isMobile ? 1 : 2,
      barRadius: 3,
      height: isMobile ? 90 : 130,
      minPxPerSec: initialZoom,
      fillParent: false,
      plugins: [regions],
      url: getFullUrl(song.audio_url),
    });

    wavesurferRef.current = ws;

    ws.on('ready', () => {
      if (isCancelled) return;
      setIsReady(true);
      const audioDuration = ws.getDuration();
      setDuration(audioDuration);
      const endTime = Math.min(30, audioDuration);

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
        setSelectedRange({ start: 0, end: endTime });
      } catch (e) {
        console.warn('Region error:', e);
      }
    });

    ws.on('audioprocess', (time) => {
      if (!isCancelled) setCurrentTime(time);
      const region = regionsRef.current?.getRegions()[0];
      if (region && ws.isPlaying() && time >= region.end) {
        ws.setTime(region.start);
      }
    });

    ws.on('timeupdate', (time) => { if (!isCancelled) setCurrentTime(time); });
    ws.on('play', () => { if (!isCancelled) setIsPlaying(true); });
    ws.on('pause', () => { if (!isCancelled) setIsPlaying(false); });
    ws.on('error', (err) => {
      if (!isCancelled) {
        console.error('WaveSurfer error:', err);
        toast.error('Failed to load audio visualization.');
      }
    });

    regions.on('region-updated', (region) => {
      if (!isCancelled) setSelectedRange({ start: region.start, end: region.end });
    });

    return () => {
      isCancelled = true;
      ws.destroy();
    };
  }, [song.audio_url]);

  // Zoom handler — called when user taps + or -
  const handleZoom = useCallback((direction: 'in' | 'out') => {
    const ws = wavesurferRef.current;
    if (!ws || !isReady) return;

    setZoomIndex((prev) => {
      const next = direction === 'in'
        ? Math.min(prev + 1, ZOOM_LEVELS.length - 1)
        : Math.max(prev - 1, 0);

      if (next !== prev) {
        ws.zoom(ZOOM_LEVELS[next]);
        // Scroll so the current region start stays in view
        const region = regionsRef.current?.getRegions()[0];
        if (region) {
          const wrapper = ws.getWrapper();
          if (wrapper) {
            const scrollTarget = region.start * ZOOM_LEVELS[next] - 40;
            wrapper.scrollLeft = Math.max(0, scrollTarget);
          }
        }
      }
      return next;
    });
  }, [isReady]);

  const togglePlayback = () => {
    const ws = wavesurferRef.current;
    if (!ws) return;
    const region = regionsRef.current?.getRegions()[0];
    if (!isPlaying && region) {
      const t = ws.getCurrentTime();
      if (t < region.start || t >= region.end) ws.setTime(region.start);
    }
    ws.playPause();
  };

  const handleGenerate = async () => {
    if (!selectedRange) return;
    setIsGenerating(true);
    setGeneratedClip(null);
    const toastId = toast.loading('Slicing your audio clip...');
    try {
      const response = await MusicService.generateClip({
        songId: song.id,
        startTime: Number(selectedRange.start.toFixed(3)),
        endTime: Number(selectedRange.end.toFixed(3)),
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
    const toastId = toast.loading('Downloading clip...');
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
      toast.success('Download complete!', { id: toastId });
    } catch {
      toast.error('Failed to download clip.');
    }
  };

  const clipDuration = selectedRange ? selectedRange.end - selectedRange.start : 0;
  const zoomPercent = Math.round(((zoomIndex) / (ZOOM_LEVELS.length - 1)) * 100);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.98 }}
      transition={{ duration: 0.2 }}
      className="bg-black/40 backdrop-blur-2xl rounded-[32px] p-5 md:p-10 w-full mx-auto relative border border-white/10 shadow-2xl"
    >
      <button
        onClick={onClose}
        className="absolute top-5 right-5 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/10 transition-colors z-10"
      >
        <X className="w-6 h-6" />
      </button>

      {/* Song Header */}
      <div className="flex items-center gap-4 mb-6">
        {song.thumbnail_url ? (
          <img
            src={getFullUrl(song.thumbnail_url)}
            alt={song.title}
            className="w-16 h-16 rounded-xl object-cover border border-white/10 flex-shrink-0"
          />
        ) : (
          <div className="w-16 h-16 rounded-xl bg-[#111] flex items-center justify-center border border-white/10 flex-shrink-0">
            <Music2 className="w-7 h-7 text-zinc-700" />
          </div>
        )}
        <div className="min-w-0">
          <h2 className="text-xl md:text-3xl font-bold text-white truncate tracking-tight">{song.title}</h2>
          <p className="text-zinc-400 font-medium text-sm md:text-base truncate">{song.artist}</p>
        </div>
      </div>

      {/* Waveform Section */}
      <div className="bg-black/20 rounded-2xl p-4 mb-4 border border-white/5">
        {/* Zoom Controls Row */}
        {isReady && (
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-zinc-500 font-medium">Zoom</span>
            <div className="flex items-center gap-2">
              {/* Zoom Out */}
              <button
                onClick={() => handleZoom('out')}
                disabled={zoomIndex === 0}
                className="w-9 h-9 rounded-xl bg-white/10 hover:bg-white/20 active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center transition-all touch-manipulation"
                aria-label="Zoom out"
              >
                <ZoomOut className="w-4 h-4 text-white" />
              </button>

              {/* Zoom Level Bar */}
              <div className="flex items-center gap-1">
                {ZOOM_LEVELS.map((_, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      const ws = wavesurferRef.current;
                      if (!ws) return;
                      ws.zoom(ZOOM_LEVELS[i]);
                      setZoomIndex(i);
                    }}
                    className={`w-2 h-2 rounded-full transition-all touch-manipulation ${
                      i === zoomIndex ? 'bg-white scale-125' : 'bg-white/30'
                    }`}
                    aria-label={`Zoom level ${i + 1}`}
                  />
                ))}
              </div>

              {/* Zoom In */}
              <button
                onClick={() => handleZoom('in')}
                disabled={zoomIndex === ZOOM_LEVELS.length - 1}
                className="w-9 h-9 rounded-xl bg-white/10 hover:bg-white/20 active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center transition-all touch-manipulation"
                aria-label="Zoom in"
              >
                <ZoomIn className="w-4 h-4 text-white" />
              </button>
            </div>
            <span className="text-xs text-zinc-500 font-mono">{zoomPercent}%</span>
          </div>
        )}

        {/* Loading State */}
        {!isReady && (
          <div className="h-[90px] md:h-[130px] flex flex-col items-center justify-center text-white gap-3">
            <Loader2 className="w-8 h-8 animate-spin" />
            <span className="text-sm font-medium text-zinc-400">Loading waveform...</span>
          </div>
        )}

        {/* Waveform */}
        <div
          ref={containerRef}
          className={`w-full overflow-x-auto ${!isReady ? 'hidden' : 'block'} relative z-10`}
          style={{ WebkitOverflowScrolling: 'touch' }}
        />

        {/* Time Labels */}
        {isReady && (
          <div className="flex justify-between items-center mt-3 px-1">
            <span className="text-xs text-zinc-500 font-mono">{formatTime(selectedRange?.start ?? 0)}</span>
            <div className="flex items-center gap-2">
              <span className={`text-xs font-bold px-3 py-1 rounded-full ${
                clipDuration > 28 ? 'bg-orange-500/20 text-orange-400' : 'bg-white/10 text-white'
              }`}>
                {clipDuration.toFixed(1)}s / 30s
              </span>
            </div>
            <span className="text-xs text-zinc-500 font-mono">{formatTime(selectedRange?.end ?? 0)}</span>
          </div>
        )}
      </div>

      {/* Zoom Hint for mobile */}
      {isReady && (
        <p className="text-center text-xs text-zinc-600 mb-4">
          Tip: Zoom in (+) to spread the waveform and grab handles easily
        </p>
      )}

      {/* Action Buttons */}
      <div className="flex items-center gap-3">
        <button
          onClick={togglePlayback}
          disabled={!isReady}
          className="btn-primary w-14 h-14 flex-shrink-0 disabled:opacity-50 touch-manipulation"
        >
          {isPlaying
            ? <Pause className="w-6 h-6" fill="currentColor" />
            : <Play className="w-6 h-6 ml-0.5" fill="currentColor" />}
        </button>

        <button
          onClick={handleGenerate}
          disabled={!isReady || isGenerating || !selectedRange || clipDuration < 1}
          className="btn-primary flex-1 h-14 gap-2 text-base disabled:opacity-50 touch-manipulation"
        >
          {isGenerating
            ? <Loader2 className="w-5 h-5 animate-spin" />
            : <Scissors className="w-5 h-5" />}
          {isGenerating ? 'Slicing...' : 'Generate Clip'}
        </button>

        <AnimatePresence>
          {generatedClip && (
            <motion.button
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              onClick={handleInstantDownload}
              className="btn-primary w-14 h-14 flex-shrink-0 touch-manipulation"
              title="Download MP3"
            >
              <Download className="w-5 h-5" />
            </motion.button>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
