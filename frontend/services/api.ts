import axios from 'axios';

// Set up a base API instance pointing to our FastAPI backend dynamically
export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface Song {
  id: number | string;
  title: string;
  artist: string;
  audio_path?: string;
  thumbnail_path?: string | null;
  audio_url: string;
  thumbnail_url: string | null;
  duration: number;
  album_id?: number | null;
}

export interface Album {
  id: number;
  title: string;
  artist: string;
  thumbnail_path: string | null;
  songs: Song[];
}

export interface ClipRequest {
  songId: number;
  startTime: number;
  endTime: number;
}

export interface CustomClipRequest {
  videoId: string;
  startTime: number;
  endTime: number;
}

export interface ClipResponse {
  clipUrl: string;
  success?: boolean;
}

export const MusicService = {
  // Fetch all available albums with their nested songs
  async getAlbums(): Promise<Album[]> {
    const response = await api.get<Album[]>('/albums');
    return response.data;
  },

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
  },

  // Request a clip from a temporarily downloaded YouTube custom song
  async generateCustomClip(request: { videoId: string; startTime: number; endTime: number }): Promise<ClipResponse> {
    const response = await api.post<ClipResponse>('/youtube-custom/generate-custom-clip', request);
    return response.data;
  },

  // Manually trigger a bucket scan to find new songs
  async syncLibrary(): Promise<{ success: boolean; results: any }> {
    const response = await api.post<{ success: boolean; results: any }>('/sync');
    return response.data;
  }
};
