import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, Float
from .database import Base

def gen_id():
    return uuid.uuid4().hex[:12]

class User(Base):
    __tablename__ = "users"
    id = Column(String(12), primary_key=True, default=gen_id)
    email = Column(String(255), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=True)
    google_id = Column(String(255), unique=True, nullable=True)
    nickname = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

class GreetingCard(Base):
    __tablename__ = "greeting_cards"
    id = Column(String(12), primary_key=True, default=gen_id)
    user_id = Column(String(12), nullable=True)
    recipient_name = Column(String(100))
    sender_name = Column(String(100))
    poem = Column(Text)
    style = Column(String(50), default="shuimo")
    music_id = Column(String(12), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    view_count = Column(Integer, default=0)
    is_public = Column(Boolean, default=True)

class MusicTrack(Base):
    __tablename__ = "music_tracks"
    id = Column(String(12), primary_key=True, default=gen_id)
    title = Column(String(200))
    artist = Column(String(200), default="AI")
    style = Column(String(100))
    file_path = Column(String(500))
    lyrics = Column(Text)
    duration_sec = Column(Integer, default=60)
    play_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
