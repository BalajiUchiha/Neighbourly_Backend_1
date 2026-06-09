import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON
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


class RadiusExpansion(Base):
    __tablename__ = "radius_expansions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(UUID(as_uuid=True))
    old_radius_km = Column(Float)
    new_radius_km = Column(Float)
    applicant_count_at_expansion = Column(Integer, default=0)
    expanded_at = Column(DateTime)
