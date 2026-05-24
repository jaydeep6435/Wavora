'use client';

import React, { useEffect, useState } from 'react';
import { Search, Music2, Loader2, Disc } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { MusicService, Song } from '../services/api';
import WaveformPlayer from '../components/WaveformPlayer';

export default function Home() {
  const [songs, setSongs] = useState<Song[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [selectedSong, setSelectedSong] = useState<Song | null>(null);

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
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value;
    setSearchQuery(query);
    
    // Debounce basic implementation
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

  return (
    <main className="min-h-screen p-8 md:p-12 lg:p-16 max-w-7xl mx-auto">
      {/* Header */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center mb-12 gap-6">
        <div>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight flex items-center gap-3">
            <span className="text-primary"><Disc className="w-10 h-10 animate-[spin_10s_linear_infinite]" /></span>
            TuneSlice
          </h1>
          <p className="text-zinc-400 mt-2 text-lg">Select a track and create your custom 30-second masterpiece.</p>
        </div>

        <div className="relative w-full md:w-96 group">
          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
            <Search className="h-5 w-5 text-zinc-500 group-focus-within:text-primary transition-colors" />
          </div>
          <input
            type="text"
            className="w-full pl-12 pr-4 py-4 bg-zinc-900/80 border border-zinc-800 rounded-2xl text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all shadow-lg"
            placeholder="Search for songs or artists..."
            value={searchQuery}
            onChange={handleSearch}
          />
        </div>
      </header>

      {/* Main Content */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center h-64 text-primary">
          <Loader2 className="w-10 h-10 animate-spin mb-4" />
          <p className="text-zinc-400">Loading library...</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
          {songs.length > 0 ? (
            songs.map((song, index) => (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                key={song.id}
                onClick={() => setSelectedSong(song)}
                className="group cursor-pointer glass-panel rounded-2xl overflow-hidden hover:bg-zinc-800/50 hover:-translate-y-1 transition-all duration-300"
              >
                <div className="relative aspect-square overflow-hidden bg-zinc-800">
                  {song.thumbnail_url ? (
                    <img 
                      src={`http://localhost:8000${song.thumbnail_url}`} 
                      alt={song.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Music2 className="w-12 h-12 text-zinc-600" />
                    </div>
                  )}
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <div className="w-14 h-14 rounded-full bg-primary flex items-center justify-center transform translate-y-4 group-hover:translate-y-0 transition-all shadow-xl">
                      <Disc className="w-7 h-7 text-black" />
                    </div>
                  </div>
                </div>
                
                <div className="p-4">
                  <h3 className="font-bold text-lg text-white truncate mb-1">{song.title}</h3>
                  <p className="text-sm text-zinc-400 truncate">{song.artist}</p>
                  <p className="text-xs text-zinc-600 mt-2 font-medium">{formatDuration(song.duration)}</p>
                </div>
              </motion.div>
            ))
          ) : (
            <div className="col-span-full flex flex-col items-center justify-center py-24 text-center">
              <Music2 className="w-16 h-16 text-zinc-700 mb-4" />
              <h3 className="text-xl font-bold text-white mb-2">No songs found</h3>
              <p className="text-zinc-400">Try adjusting your search or add more songs to your library.</p>
            </div>
          )}
        </div>
      )}

      {/* Overlay Waveform Studio */}
      <AnimatePresence>
        {selectedSong && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 md:p-12">
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-black/80 backdrop-blur-sm"
              onClick={() => setSelectedSong(null)}
            />
            <div className="relative z-10 w-full">
              <WaveformPlayer 
                song={selectedSong} 
                onClose={() => setSelectedSong(null)} 
              />
            </div>
          </div>
        )}
      </AnimatePresence>
    </main>
  );
}
