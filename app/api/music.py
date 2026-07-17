from fastapi import APIRouter
from fastapi.responses import FileResponse
import os

router = APIRouter()

MUSIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "music")

TRACK_META = {
    "bach_goldberg_aria.mp3": {"title": "Goldberg Variations - Aria", "composer": "J.S. Bach", "style": "classical"},
    "bach_aria_da_capo.mp3": {"title": "Goldberg Variations - Aria da Capo", "composer": "J.S. Bach", "style": "classical"},
    "bach_variation1.mp3": {"title": "Goldberg Variations - Variation 1", "composer": "J.S. Bach", "style": "classical"},
    "bach_variation2.mp3": {"title": "Goldberg Variations - Variation 2", "composer": "J.S. Bach", "style": "classical"},
    "bach_variation29.mp3": {"title": "Goldberg Variations - Variation 29", "composer": "J.S. Bach", "style": "classical"},
    "grieg_morning.mp3": {"title": "Peer Gynt - Morning Mood", "composer": "Edvard Grieg", "style": "romantic"},
    "grieg_anitra.mp3": {"title": "Peer Gynt - Anitra's Dance", "composer": "Edvard Grieg", "style": "romantic"},
    "dvorak_lento.mp3": {"title": "American Quartet - Lento", "composer": "Antonín Dvořák", "style": "romantic"},
    "borodin_nocturne.mp3": {"title": "String Quartet No.2 - Nocturne", "composer": "Alexander Borodin", "style": "romantic"},
    "mendelssohn_andante.mp3": {"title": "Italian Symphony - Andante con Moto", "composer": "Felix Mendelssohn", "style": "romantic"},
    "mozart_andante.mp3": {"title": "String Quartet K.421 - Andante", "composer": "W.A. Mozart", "style": "classical"},
    "mozart_symph40_andante.mp3": {"title": "Symphony No.40 - Andante", "composer": "W.A. Mozart", "style": "classical"},
    "schubert_andante.mp3": {"title": "Piano Sonata D.664 - Andante", "composer": "Franz Schubert", "style": "romantic"},
    "haydn_adagio.mp3": {"title": "Lark Quartet - Adagio Cantabile", "composer": "Joseph Haydn", "style": "classical"},
    "suk_meditation.mp3": {"title": "Meditation on an Old Czech Hymn", "composer": "Josef Suk", "style": "romantic"},
}

@router.get("/music/list")
async def list_music():
    tracks = []
    for filename, meta in TRACK_META.items():
        filepath = os.path.join(MUSIC_DIR, filename)
        if not os.path.exists(filepath):
            continue
        size = os.path.getsize(filepath)
        tracks.append({
            "id": filename.replace(".mp3", ""),
            "file": f"/api/music/play/{filename}",
            "title": meta["title"],
            "composer": meta["composer"],
            "style": meta["style"],
            "size": size
        })
    return {"tracks": tracks, "total": len(tracks)}

@router.get("/music/play/{filename}")
async def play_music(filename: str):
    filepath = os.path.join(MUSIC_DIR, filename)
    if not os.path.exists(filepath):
        return {"error": "not found"}, 404
    return FileResponse(filepath, media_type="audio/mpeg", filename=filename)
