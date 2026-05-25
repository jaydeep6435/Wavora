import httpx
import logging
import base64
import os
import asyncio
from core.config import settings

logger = logging.getLogger("tuneslice.spotify")

class SpotifyService:
    def __init__(self):
        self.client_id = settings.SPOTIFY_CLIENT_ID
        self.client_secret = settings.SPOTIFY_CLIENT_SECRET
        self.token = None

    async def get_token(self) -> str | None:
        """Deprecated: No longer needed for iTunes API."""
        return None

    async def search_track_thumbnail(self, title: str, artist: str) -> dict | None:
        """Search iTunes for the track and return official metadata and thumbnail URL."""
        clean_title = title.split("(")[0].strip() # Remove (feat. X) or (Live)
        
        # If the file didn't have a dash, artist is "Unknown Artist", which ruins the search
        if artist.lower() == "unknown artist":
            query = clean_title
        else:
            query = f"{clean_title} {artist}"
        
        params = {
            "term": query,
            "media": "music",
            "entity": "song",
            "limit": 1
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("https://itunes.apple.com/search", params=params)
                response.raise_for_status()
                data = response.json()
                
                results = data.get("results", [])
                
                # FALLBACK: If we got no results, and it was an Unknown Artist (messy title), try searching just the first 2 words
                if not results and artist.lower() == "unknown artist":
                    words = clean_title.split()
                    if len(words) > 2:
                        fallback_query = " ".join(words[:2])
                        logger.info(f"No results for {query}, trying fallback query: {fallback_query}")
                        fallback_params = {
                            "term": fallback_query,
                            "media": "music",
                            "entity": "song",
                            "limit": 1
                        }
                        fallback_response = await client.get("https://itunes.apple.com/search", params=fallback_params)
                        fallback_response.raise_for_status()
                        fallback_data = fallback_response.json()
                        results = fallback_data.get("results", [])

                if not results:
                    logger.info(f"No track found for {query} on iTunes")
                    return None
                
                track = results[0]
                artwork_url = track.get("artworkUrl100")
                if not artwork_url:
                    return None
                    
                best_image_url = artwork_url.replace("100x100bb", "600x600bb")
                
                return {
                    "thumbnail_url": best_image_url,
                    "title": track.get("trackName"),
                    "artist": track.get("artistName")
                }
        except Exception as e:
            logger.error(f"Failed to search track {query}: {e}")
            return None

    async def download_thumbnail(self, url: str, filename_no_ext: str, thumbnails_dir: str) -> str | None:
        """Download the image URL to the thumbnails directory."""
        if not url:
            return None
            
        try:
            os.makedirs(thumbnails_dir, exist_ok=True)
            # Assuming Spotify returns JPEGs usually
            file_name = f"{filename_no_ext}.jpg"
            file_path = os.path.join(thumbnails_dir, file_name)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                
                with open(file_path, "wb") as f:
                    f.write(response.content)
                    
            logger.info(f"Successfully downloaded Spotify thumbnail to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to download thumbnail from {url}: {e}")
            return None

# Singleton instance
spotify_service = SpotifyService()
