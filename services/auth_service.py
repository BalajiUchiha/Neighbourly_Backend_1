from database import execute_query
from utils.jwt import (
    hash_password, verify_password,
    create_access_token, create_refresh_token
)
from fastapi import HTTPException
from datetime import datetime, timedelta
import uuid
import os

class AuthService:

    @staticmethod
    async def login(identifier, password, response, db, request):

        # Find credential
        credential = execute_query(
            db,
            "SELECT * FROM user_credentials WHERE login_identifier = %s AND is_active = true",
            (identifier,),
            fetch="one"
        )

        if not credential:
            raise HTTPException(401, "Invalid credentials")

        # Check lock
        if credential["locked_until"]:
            if datetime.utcnow() < credential["locked_until"]:
                raise HTTPException(423, f"Account locked. Try again after {credential['locked_until'].strftime('%H:%M')}")

        # Verify password
        if not verify_password(password, credential["password_hash"]):
            new_attempts = (credential["failed_attempts"] or 0) + 1
            if new_attempts >= 5:
                locked_until = datetime.utcnow() + timedelta(minutes=30)
                execute_query(
                    db,
                    "UPDATE user_credentials SET failed_attempts = %s, locked_until = %s WHERE id = %s",
                    (new_attempts, locked_until, credential["id"])
                )
                raise HTTPException(423, "Too many failed attempts. Account locked for 30 minutes.")
            execute_query(
                db,
                "UPDATE user_credentials SET failed_attempts = %s WHERE id = %s",
                (new_attempts, credential["id"])
            )
            raise HTTPException(401, "Invalid credentials")

        # Get user
        user = execute_query(
            db,
            "SELECT * FROM users WHERE id = %s AND is_active = true",
            (str(credential["user_id"]),),
            fetch="one"
        )

        if not user:
            raise HTTPException(403, "Account suspended")

        # Reset failed attempts
        execute_query(
            db,
            "UPDATE user_credentials SET failed_attempts = 0, locked_until = NULL, last_login_at = %s WHERE id = %s",
            (datetime.utcnow(), credential["id"])
        )

        # Generate tokens
        access_token = create_access_token(str(user["id"]))
        refresh_token = create_refresh_token(str(user["id"]))
        refresh_hash = hash_password(refresh_token)

        # Store session
        execute_query(
            db,
            """INSERT INTO user_sessions 
               (id, user_id, refresh_token_hash, device_info, ip_address, is_active, expires_at, created_at, last_used_at)
               VALUES (%s, %s, %s, %s, %s, true, %s, %s, %s)""",
            (
                str(uuid.uuid4()),
                str(user["id"]),
                refresh_hash,
                request.headers.get("user-agent", ""),
                request.client.host,
                datetime.utcnow() + timedelta(days=30),
                datetime.utcnow(),
                datetime.utcnow()
            )
        )

        # Set cookie
        secure = os.getenv("COOKIE_SECURE", "False") == "True"
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=secure,
            samesite="lax",
            max_age=30 * 24 * 60 * 60
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": str(user["id"]),
                "name": user["name"],
                "username": user["username"],
                "email": user["email"],
                "phone": user["phone"],
                "photo_url": user["photo_url"],
                "preferred_language": user["preferred_language"],
                "is_worker": user["is_worker"],
                "trust_score": user["trust_score"],
                "trust_badge": user["trust_badge"],
                "area_name": user["area_name"],
                "city": user["city"],
                "district": user["district"],
                "latitude": str(user["latitude"]) if user["latitude"] else None,
                "longitude": str(user["longitude"]) if user["longitude"] else None
            }
        }

    @staticmethod
    async def signup(body, response, db, request):

        name = body.get("name", "").strip()
        username = body.get("username", "").strip()
        email = body.get("email")
        phone = body.get("phone")
        password = body.get("password", "")

        # Validations
        if not name:
            raise HTTPException(400, "Name is required")
        if len(username) < 4:
            raise HTTPException(400, "Username must be at least 4 characters")
        if not email and not phone:
            raise HTTPException(400, "At least email or phone is required")
        if len(password) < 6:
            raise HTTPException(400, "Password must be at least 6 characters")

        # Check uniqueness
        existing = execute_query(
            db,
            "SELECT id FROM user_credentials WHERE login_identifier = %s",
            (username,),
            fetch="one"
        )
        if existing:
            raise HTTPException(409, "Username already taken")

        if email:
            existing = execute_query(
                db,
                "SELECT id FROM user_credentials WHERE login_identifier = %s",
                (email,),
                fetch="one"
            )
            if existing:
                raise HTTPException(409, "Email already registered")

        if phone:
            existing = execute_query(
                db,
                "SELECT id FROM user_credentials WHERE login_identifier = %s",
                (phone,),
                fetch="one"
            )
            if existing:
                raise HTTPException(409, "Phone already registered")

        password_hash = hash_password(password)
        user_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Insert user
        execute_query(
            db,
            """INSERT INTO users 
               (id, name, username, phone, email, photo_url, date_of_birth, gender,
                preferred_language, latitude, longitude, area_name, city, state,
                district, location_accuracy, is_worker, trust_score, trust_badge,
                is_active, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,'new',true,%s,%s)""",
            (
                user_id, name, username, phone or None, email or None,
                body.get("photo_url"), body.get("date_of_birth"),
                body.get("gender"), body.get("preferred_language", "english"),
                body.get("latitude"), body.get("longitude"),
                body.get("area_name"), body.get("city"), body.get("state"),
                body.get("district"),
                body.get("location_accuracy", "district_level"),
                body.get("is_worker", False),
                now, now
            )
        )

        # Insert credentials — username always
        execute_query(
            db,
            """INSERT INTO user_credentials
               (id, user_id, login_identifier, identifier_type, password_hash,
                is_active, failed_attempts, created_at, updated_at)
               VALUES (%s,%s,%s,'username',%s,true,0,%s,%s)""",
            (str(uuid.uuid4()), user_id, username, password_hash, now, now)
        )

        if email:
            execute_query(
                db,
                """INSERT INTO user_credentials
                   (id, user_id, login_identifier, identifier_type, password_hash,
                    is_active, failed_attempts, created_at, updated_at)
                   VALUES (%s,%s,%s,'email',%s,true,0,%s,%s)""",
                (str(uuid.uuid4()), user_id, email, password_hash, now, now)
            )

        if phone:
            execute_query(
                db,
                """INSERT INTO user_credentials
                   (id, user_id, login_identifier, identifier_type, password_hash,
                    is_active, failed_attempts, created_at, updated_at)
                   VALUES (%s,%s,%s,'phone',%s,true,0,%s,%s)""",
                (str(uuid.uuid4()), user_id, phone, password_hash, now, now)
            )

        # Insert user_verifications
        execute_query(
            db,
            """INSERT INTO user_verifications
               (id, user_id, aadhaar_verified, verification_attempt_count, updated_at)
               VALUES (%s,%s,false,0,%s)""",
            (str(uuid.uuid4()), user_id, now)
        )

        # Insert user_avatar_credits
        execute_query(
            db,
            """INSERT INTO user_avatar_credits
               (id, user_id, free_daily_credits_remaining, free_monthly_credits_remaining,
                purchased_credits_remaining, total_credits_used_lifetime,
                daily_reset_at, monthly_reset_at, updated_at)
               VALUES (%s,%s,5,20,0,0,%s,%s,%s)""",
            (str(uuid.uuid4()), user_id, now, now, now)
        )

        # Insert worker_profiles if is_worker
        worker_profile = body.get("worker_profile")
        if body.get("is_worker") and worker_profile:
            import json
            execute_query(
                db,
                """INSERT INTO worker_profiles
                   (id, user_id, skills, experience_levels, availability_days,
                    availability_slots, wage_min, wage_max, open_to_no_exp_jobs,
                    feed_preferences, is_profile_complete, willing_to_travel, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s,%s)""",
                (
                    str(uuid.uuid4()), user_id,
                    worker_profile.get("skills", []),
                    json.dumps(worker_profile.get("experience_levels", {})),
                    worker_profile.get("availability_days", []),
                    worker_profile.get("availability_slots", []),
                    worker_profile.get("wage_min"),
                    worker_profile.get("wage_max"),
                    worker_profile.get("open_to_no_exp_jobs", True),
                    worker_profile.get("feed_preferences", []),
                    worker_profile.get("willing_to_travel", False),
                    now
                )
            )

            # Insert worker_rag_index
            execute_query(
                db,
                """INSERT INTO worker_rag_index
                   (id, worker_id, is_dirty, index_version, updated_at)
                   VALUES (%s,%s,true,0,%s)""",
                (str(uuid.uuid4()), user_id, now)
            )

        # Generate tokens and session
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)
        refresh_hash = hash_password(refresh_token)

        execute_query(
            db,
            """INSERT INTO user_sessions
               (id, user_id, refresh_token_hash, device_info, ip_address,
                is_active, expires_at, created_at, last_used_at)
               VALUES (%s,%s,%s,%s,%s,true,%s,%s,%s)""",
            (
                str(uuid.uuid4()), user_id, refresh_hash,
                request.headers.get("user-agent", ""),
                request.client.host,
                now + timedelta(days=30), now, now
            )
        )

        secure = os.getenv("COOKIE_SECURE", "False") == "True"
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=secure,
            samesite="lax",
            max_age=30 * 24 * 60 * 60
        )

        user = execute_query(
            db,
            "SELECT * FROM users WHERE id = %s",
            (user_id,),
            fetch="one"
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "name": user["name"],
                "username": user["username"],
                "email": user["email"],
                "phone": user["phone"],
                "photo_url": user["photo_url"],
                "preferred_language": user["preferred_language"],
                "is_worker": user["is_worker"],
                "trust_score": user["trust_score"],
                "trust_badge": user["trust_badge"],
                "area_name": user["area_name"],
                "city": user["city"],
                "district": user["district"],
                "latitude": str(user["latitude"]) if user["latitude"] else None,
                "longitude": str(user["longitude"]) if user["longitude"] else None
            }
        }

    @staticmethod
    async def check_username(username: str, db):
        existing = execute_query(
            db,
            "SELECT id FROM user_credentials WHERE login_identifier = %s AND identifier_type = 'username'",
            (username,),
            fetch="one"
        )
        return {"available": existing is None}

    @staticmethod
    async def refresh(request, response, db):
        from utils.jwt import decode_token
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            raise HTTPException(401, "No refresh token")
        try:
            payload = decode_token(refresh_token)
            user_id = payload.get("sub")
        except Exception:
            raise HTTPException(401, "Invalid refresh token")

        session = execute_query(
            db,
            "SELECT * FROM user_sessions WHERE user_id = %s AND is_active = true ORDER BY created_at DESC LIMIT 1",
            (user_id,),
            fetch="one"
        )
        if not session:
            raise HTTPException(401, "Session not found")

        if not verify_password(refresh_token, session["refresh_token_hash"]):
            raise HTTPException(401, "Invalid session")

        execute_query(
            db,
            "UPDATE user_sessions SET last_used_at = %s WHERE id = %s",
            (datetime.utcnow(), session["id"])
        )

        access_token = create_access_token(user_id)
        return {"access_token": access_token, "token_type": "bearer"}

    @staticmethod
    async def logout(request, response, db):
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            from utils.jwt import decode_token
            try:
                payload = decode_token(refresh_token)
                user_id = payload.get("sub")
                execute_query(
                    db,
                    "UPDATE user_sessions SET is_active = false WHERE user_id = %s AND is_active = true",
                    (user_id,)
                )
            except Exception:
                pass
        response.delete_cookie("refresh_token")
        return {"message": "Logged out successfully"}
