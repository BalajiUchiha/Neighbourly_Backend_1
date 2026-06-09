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


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100))
    username = Column(String(50), unique=True)
    phone = Column(String(15))
    email = Column(String(150))
    photo_url = Column(String)
    preferred_language = Column(String(20), default="english")
    latitude = Column(String)
    longitude = Column(String)
    area_name = Column(String(100))
    city = Column(String(100))
    state = Column(String(100))
    district = Column(String(100))
    is_worker = Column(Boolean, default=False)
    trust_score = Column(Integer, default=0)
    trust_badge = Column(String, default="new")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    
    # New signup fields
    date_of_birth = Column(Date)
    gender = Column(String(50))
    location_accuracy = Column(String(50), default="district_level")
    tech_comfort_level = Column(String(50))


class UserCredential(Base):
    __tablename__ = "user_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True))
    login_identifier = Column(String(150), unique=True)
    identifier_type = Column(String)
    password_hash = Column(String)
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime)
    failed_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True))
    refresh_token_hash = Column(String)
    device_info = Column(String)
    ip_address = Column(String(45))
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime)
    created_at = Column(DateTime)
    last_used_at = Column(DateTime)


class UserVerification(Base):
    __tablename__ = "user_verifications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), unique=True)
    aadhaar_number_hash = Column(String)
    aadhaar_verified = Column(Boolean, default=False)
    aadhaar_verified_at = Column(DateTime)
    verification_attempt_count = Column(Integer, default=0)
    updated_at = Column(DateTime)


class UserAvatarCredits(Base):
    __tablename__ = "user_avatar_credits"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), unique=True)
    free_daily_credits_remaining = Column(Integer, default=5)
    free_monthly_credits_remaining = Column(Integer, default=20)
    purchased_credits_remaining = Column(Integer, default=0)
    total_credits_used_lifetime = Column(Integer, default=0)
    daily_reset_at = Column(DateTime)
    monthly_reset_at = Column(DateTime)
    updated_at = Column(DateTime)
