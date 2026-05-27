import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db.session import SessionLocal
from models.song import Song
import requests

def test_song_urls():
    db = SessionLocal()
    songs = db.query(Song).all()
    for s in songs:
        print(f"Testing {s.title} ({s.audio_path})")
        
        # Test original URL
        try:
            r = requests.head(s.audio_path)
            print(f"  HEAD original: {r.status_code} - Content-Type: {r.headers.get('Content-Type')}")
        except Exception as e:
            print(f"  HEAD error: {e}")
            
        # Test appended .mp3
        mp3_url = s.audio_path
        if 'res.cloudinary.com' in mp3_url and not mp3_url.endswith('.mp3'):
            mp3_url += '.mp3'
            try:
                r2 = requests.head(mp3_url)
                print(f"  HEAD + .mp3: {r2.status_code} - Content-Type: {r2.headers.get('Content-Type')}")
            except Exception as e:
                print(f"  HEAD + .mp3 error: {e}")

if __name__ == "__main__":
    test_song_urls()
