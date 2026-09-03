'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Youtube, Link as LinkIcon, Loader2, ArrowLeft } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import axios from 'axios';
import { Song } from '../../services/api';
import WaveformPlayer from '../../components/WaveformPlayer';

const API_BASE_URL = 'http://localhost:8000/api/v1';

export default function CustomYoutubePage() {
  const router = useRouter();
  const [url, setUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [song, setSong] = useState<Song | null>(null);

  const handleProcessUrl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;

    // Basic YouTube URL validation
    const ytRegex = /^(https?\:\/\/)?(www\.youtube\.com|youtu\.?be|music\.youtube\.com)\/.+$/;
    if (!ytRegex.test(url)) {
      toast.error('Please enter a valid YouTube or YouTube Music link.');
      return;
    }

    setIsLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/youtube-custom/process`, { url });
      
      if (response.data && response.data.success && response.data.song) {
        toast.success('Audio ready to slice!');
        // Map the custom song response to our frontend Song interface
        setSong(response.data.song as Song);
      } else {
        toast.error('Failed to process video.');
      }
    } catch (error: any) {
      console.error(error);
      const msg = error.response?.data?.detail || 'Failed to download YouTube audio.';
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      {/* Background */}
      <div className="fixed inset-0 z-0 pointer-events-none bg-black transition-colors duration-700">
        <AnimatePresence>
          {song && song.thumbnail_url && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.7 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.8, ease: "easeOut" }}
              className="absolute inset-0"
            >
              <img 
                src={song.thumbnail_url.startsWith('http') ? song.thumbnail_url : `${API_BASE_URL.replace('/api/v1', '')}${song.thumbnail_url}`} 
                alt="bg"
                className="w-full h-full object-cover scale-110 blur-[100px] saturate-[1.5]"
              />
              <div className="absolute inset-0 bg-black/30" />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <main className="min-h-screen relative z-10 bg-transparent flex flex-col items-center justify-center p-6">
        
        {/* Editor View */}
        <AnimatePresence>
          {song && (
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 md:p-12 overflow-hidden"
            >
              <div 
                className="absolute inset-0 bg-black/60 backdrop-blur-md"
              />
              <div className="relative z-10 w-full max-w-5xl">
                <WaveformPlayer 
                  song={song} 
                  onClose={() => {
                    setSong(null);
                    setUrl('');
                  }} 
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Input View */}
        {!song && (
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="w-full max-w-2xl bg-zinc-900/50 backdrop-blur-xl border border-white/10 rounded-3xl p-8 md:p-12 shadow-2xl relative"
          >
            <button 
              onClick={() => router.push('/')}
              className="absolute top-6 left-6 text-zinc-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-6 h-6" />
            </button>
            
            <div className="flex flex-col items-center text-center mt-6 mb-10">
              <div className="w-20 h-20 bg-red-500/10 rounded-full flex items-center justify-center mb-6">
                <Youtube className="w-10 h-10 text-red-500" />
              </div>
              <h1 className="text-3xl md:text-4xl font-black text-white mb-4 tracking-tight">Paste YouTube Link</h1>
              <p className="text-zinc-400 text-lg">We'll fetch the audio instantly so you can slice your perfect 30-second ringtone.</p>
            </div>

            <form onSubmit={handleProcessUrl} className="space-y-4">
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-6 flex items-center pointer-events-none">
                  <LinkIcon className="h-6 w-6 text-zinc-400 group-focus-within:text-white transition-colors" />
                </div>
                <input
                  type="text"
                  required
                  disabled={isLoading}
                  placeholder="https://youtube.com/watch?v=..."
                  className="w-full pl-16 pr-6 py-5 bg-black/50 border border-white/10 rounded-2xl text-white text-lg focus:outline-none focus:border-white/30 focus:bg-black/80 transition-all placeholder:text-zinc-600 disabled:opacity-50"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                />
              </div>
              <button
                type="submit"
                disabled={isLoading || !url}
                className="w-full py-5 bg-white text-black hover:bg-zinc-200 disabled:bg-white/10 disabled:text-zinc-500 disabled:cursor-not-allowed rounded-2xl font-bold text-lg transition-all flex items-center justify-center gap-3"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-6 h-6 animate-spin" />
                    Fetching Audio (Takes ~3 seconds)...
                  </>
                ) : (
                  'Load Audio'
                )}
              </button>
            </form>
          </motion.div>
        )}
      </main>
    </>
  );
}
