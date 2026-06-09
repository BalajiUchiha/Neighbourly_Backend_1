import os
from sqlalchemy import Column, String, Float, JSON
from database import Base, engine
import uuid

# SQLite compatibility layer
is_sqlite = engine.url.drivername == "sqlite" if engine else False

if is_sqlite:
    from sqlalchemy.types import TypeDecorator
    
    class SQLiteUUID(TypeDecorator):
        impl = String(36)
        cache_ok = True
        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            return str(value)
        def process_result_value(self, value, dialect):
            if value is None:
                return None
            try:
                return uuid.UUID(value)
            except ValueError:
                return value
            
    UUID = SQLiteUUID
    JSONB = JSON
else:
    from sqlalchemy.dialects.postgresql import UUID, JSONB

class OnboardingAudioFile(Base):
    __tablename__ = "onboarding_audio_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    screen_name = Column(String(100), nullable=False)
    language = Column(String(50), nullable=False)
    audio_url = Column(String, nullable=False)
    highlight_map = Column(JSONB, nullable=False)
    duration_seconds = Column(Float, nullable=False)
