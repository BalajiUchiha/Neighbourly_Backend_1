import uuid
from sqlalchemy import Column, String, Boolean, Integer, Float, DateTime, Text, JSON
from database import Base, engine

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
else:
    from sqlalchemy.dialects.postgresql import UUID


class Rating(Base):
    __tablename__ = "ratings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(UUID(as_uuid=True))
    rater_id = Column(UUID(as_uuid=True))           # who gave the rating
    ratee_id = Column(UUID(as_uuid=True))           # who received the rating
    rating_type = Column(String(50))                # 'worker_rating' | 'poster_rating'
    score = Column(Float)                           # e.g. 1.0 – 5.0
    review_text = Column(Text)
    is_revealed = Column(Boolean, default=False)    # blind-reveal system
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
