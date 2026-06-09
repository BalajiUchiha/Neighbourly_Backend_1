import os
from sqlalchemy import Column, String, Boolean, Integer, Float, Date, DateTime, Text, JSON
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
    ARRAY = lambda item_type: JSON
else:
    from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY


class WorkerProfile(Base):
    __tablename__ = "worker_profiles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), unique=True)
    skills = Column(ARRAY(String), default=[])
    experience_levels = Column(JSONB, default={})
    availability_days = Column(ARRAY(String), default=[])
    availability_slots = Column(ARRAY(String), default=[])
    wage_min = Column(Integer)
    wage_max = Column(Integer)
    open_to_no_exp_jobs = Column(Boolean, default=True)
    feed_preferences = Column(ARRAY(String), default=[])
    is_profile_complete = Column(Boolean, default=False)
    willing_to_travel = Column(Boolean, default=False)
    updated_at = Column(DateTime)


class WorkerRAGIndex(Base):
    __tablename__ = "worker_rag_index"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id = Column(UUID(as_uuid=True), unique=True)
    is_dirty = Column(Boolean, default=True)
    index_version = Column(Integer, default=0)
    updated_at = Column(DateTime)
