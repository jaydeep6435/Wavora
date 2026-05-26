'use client';

import React, { useEffect, useRef, useState } from 'react';
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
    let finalUrl = url;
    if (url.startsWith('http') || url.startsWith('data:')) {
      finalUrl = url;
    } else {
      finalUrl = `http://localhost:8000${url}`;
    }
    
    // Cloudinary sometimes drops the extension for 'video' resource types.
    // WebAudio strict decoding fails if the Content-Type is wrong. 
    // Forcing .mp3 tells Cloudinary to serve it explicitly as audio/mpeg.
    if (finalUrl.includes('res.cloudinary.com') && !finalUrl.match(/\.(mp3|wav|mp4|webm|raw)$/i)) {
        finalUrl = `${finalUrl}.mp3`;
    }
    return finalUrl;
  };

  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const regionsRef = useRef<RegionsPlugin | null>(null);
  
  const [isPlaying, setIsPlaying] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [selectedRange, setSelectedRange] = useState<{ start: number; end: number } | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedClip, setGeneratedClip] = useState<string | null>(null);
  
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    if (!containerRef.current) return;
    let isCancelled = false;

    const regions = RegionsPlugin.create();
    regionsRef.current = regions;

    const isMobile = window.innerWidth < 768;

    // Create a native HTML5 Audio element. This is infinitely more resilient 
    // to format headers and missing extensions than the strict WebAudio fetch().
    const audioEl = new Audio(getFullUrl(song.audio_url));
    audioEl.crossOrigin = 'anonymous';

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: 'rgba(255, 255, 255, 0.2)',
      progressColor: '#ffffff',
      cursorColor: '#ef4444', 
      cursorWidth: 2, 
      barWidth: 3,
      barGap: 2,
      barRadius: 3,
      height: 140,
      minPxPerSec: isMobile ? 50 : 0, // Force scrolling on mobile
      plugins: [regions],
      media: audioEl, // Force MediaElement backend
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
          content: 'Clip',
          color: 'rgba(255, 255, 255, 0.1)',
          drag: true,
          resize: true,
          minLength: 10,
          maxLength: 30,
        });
        setSelectedRange({ start: 0, end: endTime });
      } catch (e) {
        console.warn("Region could not be added:", e);
      }
    });

    ws.on('audioprocess', (time) => {
      if (!isCancelled) setCurrentTime(time);
      
      // Loop within region if playing
      const region = regionsRef.current?.getRegions()[0];
      if (region && ws.isPlaying()) {
        if (time >= region.end) {
          ws.setTime(region.start);
        }
      }
    });

    ws.on('timeupdate', (time) => {
      if (!isCancelled) setCurrentTime(time);
    });

    ws.on('play', () => { if (!isCancelled) setIsPlaying(true); });
    ws.on('pause', () => { if (!isCancelled) setIsPlaying(false); });
    
    ws.on('error', (err) => {
      if (isCancelled) return;
      console.error('WaveSurfer error:', err);
      toast.error('Failed to load audio visualization.');
    });

    regions.on('region-updated', (region) => {
      if (isCancelled) return;
      setSelectedRange({ start: region.start, end: region.end });

      // Auto-scroll logic for mobile
      if (isMobile) {
        const scrollEl = ws.getWrapper();
        if (scrollEl) {
           // Native scrolling catches up
        }
      }
    });

    return () => {
      isCancelled = true;
      ws.destroy();
    };
  }, [song.audio_url]);

  const togglePlayback = () => {
    if (wavesurferRef.current) {
      const ws = wavesurferRef.current;
      const region = regionsRef.current?.getRegions()[0];
      
      // If we are about to play, and the cursor is outside the clip, jump to the start of the clip
      if (!isPlaying && region) {
        const currentTime = ws.getCurrentTime();
        if (currentTime < region.start || currentTime >= region.end) {
          ws.setTime(region.start);
        }
      }
      
      ws.playPause();
    }
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
      toast.success('Clip generated successfully!', { id: toastId });
    } catch (err) {
      console.error(err);
      toast.error('Failed to generate clip. Please try again.', { id: toastId });
    } finally {
      setIsGenerating(false);
    }
  };

  const handleInstantDownload = async () => {
    if (!generatedClip) return;
    try {
      const toastId = toast.loading('Downloading clip...');
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
    } catch (error) {
      console.error('Download failed:', error);
      toast.error('Failed to download clip.');
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.98 }}
      transition={{ duration: 0.2 }}
      className="bg-black/40 backdrop-blur-2xl rounded-[32px] p-6 md:p-10 w-full mx-auto relative border border-white/10 shadow-2xl"
    >
      <button 
        onClick={onClose}
        className="absolute top-6 right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
      >
        <X className="w-6 h-6" />
      </button>

      <div className="flex flex-col sm:flex-row items-center gap-6 mb-10">
        <div className="relative">
          {song.thumbnail_url ? (
            <img 
              src={getFullUrl(song.thumbnail_url)} 
              alt={song.title} 
              className="w-28 h-28 rounded-2xl object-cover border border-white/10"
            />
          ) : (
            <div className="w-28 h-28 rounded-2xl bg-[#111] flex items-center justify-center border border-white/10">
              <Music2 className="w-10 h-10 text-zinc-700" />
            </div>
          )}
        </div>
        
        <div className="text-center sm:text-left">
          <h2 className="text-3xl font-bold text-white mb-1 tracking-tight">{song.title}</h2>
          <p className="text-zinc-400 font-medium text-lg">{song.artist}</p>
        </div>
      </div>

      <div className="bg-black/20 rounded-2xl p-6 mb-8 border border-white/5 relative overflow-hidden">
        {!isReady && (
          <div className="h-[140px] flex flex-col items-center justify-center text-white gap-3">
            <Loader2 className="w-8 h-8 animate-spin" />
            <span className="text-sm font-medium text-zinc-400">Loading waveform...</span>
          </div>
        )}
        <div ref={containerRef} className={`w-full ${!isReady ? 'hidden' : 'block'} relative z-10`} />
        
        {isReady && (
          <div className="flex justify-between items-center mt-6 px-2 text-sm text-zinc-400 font-medium tracking-tight">
            <span>{selectedRange ? formatTime(selectedRange.start) : '0:00'}</span>
            <span className="text-white px-4 py-1 rounded-full bg-white/10">
              Selected: {selectedRange ? (selectedRange.end - selectedRange.start).toFixed(1) : '0.0'}s / 30s Max
            </span>
            <span>{selectedRange ? formatTime(selectedRange.end) : '0:00'}</span>
          </div>
        )}
      </div>

      <div className="flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-4 w-full md:w-auto">
          <button
            onClick={togglePlayback}
            disabled={!isReady}
            className="btn-primary w-[64px] h-[64px] flex-shrink-0 disabled:opacity-50"
          >
            {isPlaying ? <Pause className="w-7 h-7" fill="currentColor" /> : <Play className="w-7 h-7 ml-1" fill="currentColor" />}
          </button>
          
          <button
            onClick={handleGenerate}
            disabled={!isReady || isGenerating || !selectedRange}
            className="btn-primary flex-1 md:flex-none h-[64px] px-8 gap-3 text-lg disabled:opacity-50"
          >
            {isGenerating ? (
              <Loader2 className="w-6 h-6 animate-spin" />
            ) : (
              <Scissors className="w-6 h-6" />
            )}
            {isGenerating ? 'Slicing...' : 'Generate Clip'}
          </button>
        </div>

        <AnimatePresence>
          {generatedClip && (
            <motion.button 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              onClick={handleInstantDownload}
              className="btn-primary h-[64px] px-8 gap-3 text-lg w-full md:w-auto"
            >
              <Download className="w-6 h-6" />
              Download MP3
            </motion.button>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
