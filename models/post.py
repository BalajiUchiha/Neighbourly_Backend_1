import uuid
from sqlalchemy import Column, String, Boolean, Integer, Float, Date, DateTime, Text, JSON
from database import Base, engine

# SQLite compatibility layer (mirrors pattern from user.py)
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


class Post(Base):
    __tablename__ = "posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    poster_id = Column(UUID(as_uuid=True))
    title = Column(String(200))
    description = Column(Text)
    task_type = Column(String(100))
    post_category = Column(String(50))          # 'paid' | 'volunteer'
    workers_needed = Column(Integer, default=1)
    slots_remaining = Column(Integer, default=1)
    pay_per_person = Column(Integer)
    no_exp_needed = Column(Boolean, default=False)
    job_nature = Column(String(50))             # 'full_time' | 'part_time' | 'one_time'
    urgency_tag = Column(String(50))            # 'today' | 'tomorrow' | 'this_week' | 'flexible'
    status = Column(String(50), default="open") # 'open' | 'closed' | 'completed'
    area_name = Column(String(200))
    district = Column(String(100))
    latitude = Column(String)
    longitude = Column(String)
    work_date = Column(Date)
    work_time_slot = Column(String(100))
    tags = Column(ARRAY(String), default=[])
    raw_input_text = Column(Text)
    has_voice_input = Column(Boolean, default=False)
    current_radius_km = Column(Float, default=15.0)
    max_radius_km = Column(Float, default=50.0)
    is_remote_area = Column(Boolean, default=False)
    last_radius_expanded_at = Column(DateTime)
    expansion_count = Column(Integer, default=0)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class PostImage(Base):
    __tablename__ = "post_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(UUID(as_uuid=True))
    image_url = Column(String)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime)
