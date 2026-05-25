import asyncio
import logging
from services.youtube_sync import sync_trending_youtube_song

# Setup minimal logging to see the output
logging.basicConfig(level=logging.INFO)

def main():
    print("Testing YouTube Sync...")
    result = sync_trending_youtube_song()
    print("Result:", result)

if __name__ == "__main__":
    main()
