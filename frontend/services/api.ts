import axios from 'axios';

// Set up a base API instance pointing to our FastAPI backend dynamically
export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface Song {
  id: number;
  title: string;
  artist: string;
  audio_path: string;
  thumbnail_path: string | null;
  audio_url: string;
  thumbnail_url: string | null;
  duration: number;
}

export interface ClipRequest {
  songId: number;
  startTime: number;
  endTime: number;
}

export interface ClipResponse {
  clipUrl: string;
  success?: boolean;
}

export const MusicService = {
  // Fetch all available songs
  async getSongs(): Promise<Song[]> {
    const response = await api.get<Song[]>('/songs');
    return response.data;
  },

  // Search songs by title or artist
  async searchSongs(query: string): Promise<Song[]> {
    const response = await api.get<Song[]>('/search', { params: { q: query } });
    return response.data;
  },

  // Request a 30-second maximum clip from a song
  async generateClip(request: ClipRequest): Promise<ClipResponse> {
    const response = await api.post<ClipResponse>('/generate-clip', request);
    return response.data;
  }
};
