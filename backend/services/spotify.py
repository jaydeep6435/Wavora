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
        """Fetch Client Credentials token from Spotify."""
        if not self.client_id or not self.client_secret:
            return None

        auth_string = f"{self.client_id}:{self.client_secret}"
        b64_auth = base64.b64encode(auth_string.encode()).decode()

        headers = {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {"grant_type": "client_credentials"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
                response.raise_for_status()
                token_data = response.json()
                self.token = token_data.get("access_token")
                return self.token
        except Exception as e:
            logger.error(f"Failed to get Spotify token: {e}")
            return None

    async def search_track_thumbnail(self, title: str, artist: str) -> str | None:
        """Search Spotify for the track and return the highest resolution thumbnail URL."""
        if not self.token:
            token = await self.get_token()
            if not token:
                return None

        # Clean up the search query slightly
        clean_title = title.split("(")[0].strip() # Remove (feat. X) or (Live)
        query = f"track:{clean_title} artist:{artist}"
        
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {
            "q": query,
            "type": "track",
            "limit": 1
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("https://api.spotify.com/v1/search", headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                tracks = data.get("tracks", {}).get("items", [])
                if not tracks:
                    logger.info(f"No Spotify track found for {title} - {artist}")
                    return None
                
                track = tracks[0]
                images = track.get("album", {}).get("images", [])
                if not images:
                    return None
                    
                # Images are typically sorted largest to smallest. Grab the first one.
                best_image_url = images[0].get("url")
                return best_image_url
        except Exception as e:
            logger.error(f"Failed to search Spotify track {title} - {artist}: {e}")
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
