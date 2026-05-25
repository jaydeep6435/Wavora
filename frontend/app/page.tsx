'use client';

import React, { useEffect, useState } from 'react';
import { Search, Music2, Disc, Play, RefreshCw } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { MusicService, Song } from '../services/api';
import WaveformPlayer from '../components/WaveformPlayer';
import { SongCardSkeleton } from '../components/ui/Skeleton';
import { EmptyState } from '../components/ui/EmptyState';
import toast from 'react-hot-toast';

export default function Home() {
  const [songs, setSongs] = useState<Song[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [selectedSong, setSelectedSong] = useState<Song | null>(null);
  const [hoveredSong, setHoveredSong] = useState<Song | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      const result = await MusicService.syncLibrary();
      if (result.success) {
        toast.success(`Synced! Added ${result.results.added} new tracks.`);
        await loadSongs();
      }
    } catch (error) {
      toast.error('Failed to sync library.');
      console.error(error);
    } finally {
      setIsSyncing(false);
    }
  };

  useEffect(() => {
    loadSongs();
  }, []);

  const loadSongs = async (query?: string) => {
    setIsLoading(true);
    try {
      if (query) {
        setSongs(await MusicService.searchSongs(query));
      } else {
        setSongs(await MusicService.getSongs());
      }
    } catch (error) {
      console.error('Failed to load songs:', error);
      toast.error('Failed to load music library.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value;
    setSearchQuery(query);
    const timeoutId = setTimeout(() => {
      loadSongs(query);
    }, 500);
    return () => clearTimeout(timeoutId);
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const bgSong = selectedSong || hoveredSong;

  return (
    <>
      {/* Dynamic Ambient Background */}
      <div className="fixed inset-0 z-0 pointer-events-none bg-black transition-colors duration-700">
        <AnimatePresence>
          {bgSong && bgSong.thumbnail_url && (
            <motion.div
              key={bgSong.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.7 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.8, ease: "easeOut" }}
              className="absolute inset-0"
            >
              <img 
                src={bgSong.thumbnail_url.startsWith('http') ? bgSong.thumbnail_url : `http://localhost:8000${bgSong.thumbnail_url}`} 
                alt="bg"
                className="w-full h-full object-cover scale-110 blur-[100px] saturate-[1.5]"
              />
              <div className="absolute inset-0 bg-black/30" />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <main className="min-h-screen p-6 md:p-12 lg:p-16 max-w-[1400px] mx-auto relative z-10 bg-transparent transition-colors duration-700">
        {/* Header */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center mb-16 gap-8">
        <motion.div 
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          className="flex-1"
        >
          <h1 className="text-5xl md:text-6xl font-black tracking-tighter flex items-center gap-4 text-white hover-rainbow-text cursor-default group">
            <div className="relative w-14 h-14 flex items-center justify-center">
              <svg className="w-12 h-12 text-white group-hover:scale-110 transition-transform duration-500 ease-out" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" className="opacity-20" />
                <path d="M2 12h4l2.5 -5 3 10 3 -8 2.5 3h5" className="animate-[pulse_3s_ease-in-out_infinite]" />
              </svg>
            </div>
            Wavora
          </h1>
          <p className="text-zinc-400 mt-4 text-lg font-medium max-w-md leading-relaxed tracking-tight">
            Select a track and create your custom 30-second masterpiece.
          </p>
        </motion.div>

        <motion.div 
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          className="flex items-center gap-4 w-full md:w-auto"
        >
          <div className="relative w-full md:w-[400px] group">
            <div className="absolute inset-y-0 left-0 pl-5 flex items-center pointer-events-none">
              <Search className="h-5 w-5 text-white" />
            </div>
            <input
              type="text"
              className="dialed-input w-full pl-14 pr-6 py-4 text-lg h-[65px]"
              placeholder="Search artists or tracks..."
              value={searchQuery}
              onChange={handleSearch}
            />
          </div>
          
          <button 
            onClick={handleSync}
            disabled={isSyncing}
            className={`h-[65px] px-6 rounded-[58px] border-2 ${isSyncing ? 'border-[#14b861] text-[#14b861]' : 'border-white/20 text-white hover:border-white'} font-medium flex items-center justify-center transition-all bg-black`}
          >
            <RefreshCw className={`w-6 h-6 ${isSyncing ? 'animate-spin' : ''}`} />
          </button>
        </motion.div>
      </header>

      {/* Main Content */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6 md:gap-8">
        {isLoading ? (
          Array.from({ length: 10 }).map((_, i) => <SongCardSkeleton key={i} />)
        ) : songs.length > 0 ? (
          songs.map((song, index) => (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              key={song.id}
              onClick={() => setSelectedSong(song)}
              onMouseEnter={() => setHoveredSong(song)}
              onMouseLeave={() => setHoveredSong(null)}
              className="dialed-card group cursor-pointer rounded-[24px] overflow-hidden flex flex-col"
            >
              <div className="relative aspect-square w-full p-3 pb-0">
                <div className="w-full h-full relative rounded-[16px] overflow-hidden bg-zinc-900 border border-white/10">
                  {song.thumbnail_url ? (
                    <img 
                      src={song.thumbnail_url.startsWith('http') ? song.thumbnail_url : `http://localhost:8000${song.thumbnail_url}`} 
                      alt={song.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-[#111]">
                      <Music2 className="w-12 h-12 text-zinc-700" />
                    </div>
                  )}
                  {/* Hover Play Overlay */}
                  <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity duration-150 flex items-center justify-center">
                    <div className="w-16 h-16 rounded-full bg-white flex items-center justify-center transition-transform duration-150 group-active:scale-95">
                      <Play className="w-8 h-8 text-black ml-1" fill="currentColor" />
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="p-5 flex-1 flex flex-col justify-between">
                <div>
                  <h3 className="font-bold text-lg text-white truncate mb-1">{song.title}</h3>
                  <p className="text-sm text-zinc-400 truncate font-medium">{song.artist}</p>
                </div>
                <div className="mt-4 flex items-center justify-between">
                  <span className="text-xs py-1 px-3 rounded-full bg-white/10 text-white font-medium tracking-tight">
                    {formatDuration(song.duration)}
                  </span>
                </div>
              </div>
            </motion.div>
          ))
        ) : (
          <div className="col-span-full">
            <EmptyState 
              icon={Music2} 
              title="No tracks found" 
              description={searchQuery ? `We couldn't find anything for "${searchQuery}".` : "Your music library is currently empty. Drop some songs in the /songs folder to begin."} 
            />
          </div>
        )}
      </div>

      {/* Overlay Waveform Studio */}
      <AnimatePresence>
        {selectedSong && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 md:p-12 overflow-hidden">
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-black/90 backdrop-blur-md"
              onClick={() => setSelectedSong(null)}
            />
            <div className="relative z-10 w-full max-w-5xl">
              <WaveformPlayer 
                song={selectedSong} 
                onClose={() => setSelectedSong(null)} 
              />
            </div>
          </div>
        )}
      </AnimatePresence>
      </main>
    </>
  );
}
