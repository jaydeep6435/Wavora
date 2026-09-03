from sqlalchemy import select, func
from models.album import Album
from models.song import Song
from db.session import get_db

def check():
    session = next(get_db())
    try:
        # Total albums
        total_albums = session.query(func.count(Album.id)).scalar()
        
        # Albums with 0 songs
        empty_albums = session.query(Album).outerjoin(Song).group_by(Album.id).having(func.count(Song.id) == 0).all()
        
        # Total songs
        total_songs = session.query(func.count(Song.id)).scalar()
        
        # Songs with no album
        songs_no_album = session.query(func.count(Song.id)).filter(Song.album_id == None).scalar()
        
        print(f"Total Albums: {total_albums}")
        print(f"Total Songs: {total_songs}")
        print(f"Songs with NO album: {songs_no_album}")
        print(f"Empty Albums: {len(empty_albums)}")
        
        if empty_albums:
            print("\nFirst 10 Empty Albums:")
            for a in empty_albums[:10]:
                print(f"- ID: {a.id}, Title: {a.title}, Artist: {a.artist}")
    finally:
        session.close()

if __name__ == "__main__":
    check()
