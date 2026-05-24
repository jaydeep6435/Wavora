'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js';
import { Play, Pause, Scissors, Loader2, Download } from 'lucide-react';
import { Song, MusicService } from '../services/api';
import { motion, AnimatePresence } from 'framer-motion';

interface WaveformPlayerProps {
  song: Song;
  onClose: () => void;
}

export default function WaveformPlayer({ song, onClose }: WaveformPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const regionsRef = useRef<RegionsPlugin | null>(null);
  
  const [isPlaying, setIsPlaying] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [selectedRange, setSelectedRange] = useState<{ start: number; end: number } | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedClip, setGeneratedClip] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Format seconds to mm:ss
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  useEffect(() => {
    if (!containerRef.current) return;
    let isCancelled = false;

    // Initialize Regions plugin
    const regions = RegionsPlugin.create();
    regionsRef.current = regions;

    // Initialize WaveSurfer
    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: 'rgba(255, 255, 255, 0.4)',
      progressColor: '#1db954',
      cursorColor: '#1ed760',
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      height: 120,
      plugins: [regions],
      url: `http://localhost:8000${song.audio_url}`,
    });

    wavesurferRef.current = ws;

    ws.on('ready', () => {
      if (isCancelled) return;
      setIsReady(true);
      
      // Calculate initial region (first 30 seconds or full duration if < 30)
      const duration = ws.getDuration();
      const endTime = Math.min(30, duration);
      
      try {
        regions.addRegion({
          start: 0,
          end: endTime,
          content: 'Clip',
          color: 'rgba(29, 185, 84, 0.3)',
          drag: true,
          resize: true,
        });
        setSelectedRange({ start: 0, end: endTime });
      } catch (e) {
        console.warn("Region could not be added:", e);
      }
    });

    ws.on('play', () => { if (!isCancelled) setIsPlaying(true); });
    ws.on('pause', () => { if (!isCancelled) setIsPlaying(false); });
    
    ws.on('error', (err) => {
      if (isCancelled) return;
      console.error('WaveSurfer error:', err);
      setError('Failed to load audio visualization.');
    });

    // Handle region events
    regions.on('region-updated', (region) => {
      if (isCancelled) return;
      // Enforce max 30s length
      const length = region.end - region.start;
      if (length > 30) {
        // Automatically resize to 30s
        region.setOptions({
          end: region.start + 30
        });
      }
      setSelectedRange({ start: region.start, end: region.start + 30 > region.end ? region.end : region.start + 30 });
    });

    return () => {
      isCancelled = true;
      ws.destroy();
    };
  }, [song.audio_url]);

  const togglePlayback = () => {
    if (wavesurferRef.current) {
      wavesurferRef.current.playPause();
    }
  };

  const handleGenerate = async () => {
    if (!selectedRange) return;
    
    setIsGenerating(true);
    setError(null);
    setGeneratedClip(null);
    
    try {
      const response = await MusicService.generateClip({
        songId: song.id,
        startTime: selectedRange.start,
        endTime: selectedRange.end,
      });
      
      setGeneratedClip(`http://localhost:8000${response.clipUrl}`);
    } catch (err) {
      console.error(err);
      setError('Failed to generate clip. Please try again.');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
      className="glass-panel rounded-2xl p-6 w-full max-w-4xl mx-auto shadow-2xl relative"
    >
      <button 
        onClick={onClose}
        className="absolute top-4 right-4 text-zinc-400 hover:text-white transition-colors"
      >
        ✕
      </button>

      <div className="flex items-center gap-6 mb-8">
        {song.thumbnail_url ? (
          <img 
            src={`http://localhost:8000${song.thumbnail_url}`} 
            alt={song.title} 
            className="w-24 h-24 rounded-lg object-cover shadow-lg"
          />
        ) : (
          <div className="w-24 h-24 rounded-lg bg-zinc-800 flex items-center justify-center">
            <span className="text-zinc-500 text-3xl">♪</span>
          </div>
        )}
        
        <div>
          <h2 className="text-2xl font-bold text-white mb-1">{song.title}</h2>
          <p className="text-zinc-400 text-lg">{song.artist}</p>
        </div>
      </div>

      <div className="bg-zinc-900/50 rounded-xl p-4 mb-6">
        {!isReady && (
          <div className="h-[120px] flex items-center justify-center text-zinc-500 gap-2">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Analyzing waveform...</span>
          </div>
        )}
        <div ref={containerRef} className={`w-full ${!isReady ? 'hidden' : 'block'}`} />
        
        {isReady && (
          <div className="flex justify-between items-center mt-4 px-2 text-sm text-zinc-400">
            <span>{selectedRange ? formatTime(selectedRange.start) : '0:00'}</span>
            <span className="text-primary font-medium">
              Selected: {selectedRange ? (selectedRange.end - selectedRange.start).toFixed(1) : '0.0'}s / 30s Max
            </span>
            <span>{selectedRange ? formatTime(selectedRange.end) : '0:00'}</span>
          </div>
        )}
      </div>

      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex gap-3">
          <button
            onClick={togglePlayback}
            disabled={!isReady}
            className="flex items-center justify-center w-12 h-12 rounded-full bg-primary text-black hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {isPlaying ? <Pause className="w-6 h-6" fill="currentColor" /> : <Play className="w-6 h-6 ml-1" fill="currentColor" />}
          </button>
          
          <button
            onClick={handleGenerate}
            disabled={!isReady || isGenerating || !selectedRange}
            className="flex items-center gap-2 px-6 py-3 rounded-full bg-zinc-800 text-white hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all font-medium shadow-md border border-white/5"
          >
            {isGenerating ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Scissors className="w-5 h-5" />
            )}
            {isGenerating ? 'Slicing...' : 'Generate Clip'}
          </button>
        </div>

        <AnimatePresence>
          {generatedClip && (
            <motion.div 
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex items-center gap-3 bg-primary/10 border border-primary/20 px-4 py-2 rounded-full"
            >
              <audio src={generatedClip} controls className="h-10 w-48" />
              <a 
                href={generatedClip} 
                download
                className="p-2 text-primary hover:bg-primary/20 rounded-full transition-colors"
                title="Download Clip"
              >
                <Download className="w-5 h-5" />
              </a>
            </motion.div>
          )}
        </AnimatePresence>

        {error && (
          <div className="text-red-400 text-sm">{error}</div>
        )}
      </div>
    </motion.div>
  );
}
