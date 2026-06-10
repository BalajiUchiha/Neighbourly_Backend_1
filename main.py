import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Load environment variables from backend/.env at the top
load_dotenv()

# Read config from environment variables
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# ---------------------------------------------------------------------------
# APScheduler — radius expansion runs every 6 hours
# ---------------------------------------------------------------------------
scheduler = AsyncIOScheduler()


async def _run_radius_expansion():
    """Wrapper: creates a DB session and calls RadiusService.expand_radii."""
    from database import SessionLocal
    from services.radius_service import RadiusService
    if SessionLocal is None:
        return
    db = SessionLocal()
    try:
        await RadiusService().expand_radii(db)
    except Exception as exc:
        print(f"[RadiusService] expand_radii error: {exc}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Startup
    scheduler.add_job(
        _run_radius_expansion,
        trigger=IntervalTrigger(hours=6),
        id="radius_expansion",
        replace_existing=True,
    )
    scheduler.start()
    print("[Scheduler] Radius expansion job scheduled every 6 hours.")
    yield
    # Shutdown
    scheduler.shutdown(wait=False)
    print("[Scheduler] Stopped.")


app = FastAPI(
    title="Neighbourly API",
    description="Hyperlocal job and volunteer platform for India API Scaffolding",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware configuration
origins = []
if FRONTEND_URL:
    origins.append(FRONTEND_URL)
# Fallback localhost origins for development ease
for fallback in ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]:
    if fallback not in origins:
        origins.append(fallback)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables if they do not exist
from database import engine, Base, SessionLocal
import models.auth
import models.onboarding
if engine:
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[Startup] create_all skipped (tables may already exist): {e}")
    
    # Ensure tech_comfort_level column exists in users table (migration helper)
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        if 'users' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('users')]
            if 'tech_comfort_level' not in columns:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN tech_comfort_level VARCHAR(50)"))
                print("Successfully migrated users table to add tech_comfort_level.")
    except Exception as e:
        print(f"Migration helper error: {e}")
    
    # Seed onboarding audio files if empty
    from models.onboarding import OnboardingAudioFile
    db = SessionLocal()
    try:
        if db.query(OnboardingAudioFile).count() == 0:
            import uuid
            seeds = [
                OnboardingAudioFile(
                    id=uuid.uuid4(),
                    screen_name="worker_question",
                    language="english",
                    audio_url="https://www.w3schools.com/html/horse.mp3",
                    duration_seconds=16.0,
                    highlight_map=[
                        { "from": 0, "to": 5.2, "highlight": None },
                        { "from": 5.2, "to": 9.8, "highlight": "worker-btn" },
                        { "from": 9.8, "to": 13.5, "highlight": "poster-btn" },
                        { "from": 13.5, "to": 16.0, "highlight": "replay-btn" }
                    ]
                ),
                OnboardingAudioFile(
                    id=uuid.uuid4(),
                    screen_name="worker_question",
                    language="tamil",
                    audio_url="https://www.w3schools.com/html/horse.mp3",
                    duration_seconds=16.0,
                    highlight_map=[
                        { "from": 0, "to": 5.2, "highlight": None },
                        { "from": 5.2, "to": 9.8, "highlight": "worker-btn" },
                        { "from": 9.8, "to": 13.5, "highlight": "poster-btn" },
                        { "from": 13.5, "to": 16.0, "highlight": "replay-btn" }
                    ]
                ),
                OnboardingAudioFile(
                    id=uuid.uuid4(),
                    screen_name="tech_comfort",
                    language="english",
                    audio_url="https://www.w3schools.com/html/horse.mp3",
                    duration_seconds=12.0,
                    highlight_map=[
                        { "from": 0.0, "to": 3.0, "highlight": None },
                        { "from": 3.0, "to": 6.0, "highlight": "new_to_this" },
                        { "from": 6.0, "to": 9.0, "highlight": "getting_comfortable" },
                        { "from": 9.0, "to": 12.0, "highlight": "know_my_way_around" }
                    ]
                ),
                OnboardingAudioFile(
                    id=uuid.uuid4(),
                    screen_name="tech_comfort",
                    language="tamil",
                    audio_url="https://www.w3schools.com/html/horse.mp3",
                    duration_seconds=12.0,
                    highlight_map=[
                        { "from": 0.0, "to": 3.0, "highlight": None },
                        { "from": 3.0, "to": 6.0, "highlight": "new_to_this" },
                        { "from": 6.0, "to": 9.0, "highlight": "getting_comfortable" },
                        { "from": 9.0, "to": 12.0, "highlight": "know_my_way_around" }
                    ]
                )
            ]
            db.add_all(seeds)
            db.commit()
            print("Successfully seeded onboarding audio files.")
    except Exception as e:
        print(f"Error seeding onboarding audio files: {e}")
        db.rollback()
    finally:
        db.close()

from routes.auth import router as auth_router, language_router, users_router
from routes.location import router as location_router
from routes.onboarding import router as onboarding_router
from routes.feed import router as feed_router
from routes.post import router as post_router
from fastapi.staticfiles import StaticFiles

import os
os.makedirs("static/post_images", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth_router, prefix="/api/auth")
app.include_router(location_router, prefix="/api/location")
app.include_router(onboarding_router, prefix="/api/onboarding")
app.include_router(users_router, prefix="/api/users")
app.include_router(language_router, prefix="/api")
app.include_router(feed_router, prefix="/api/feed")
app.include_router(post_router, prefix="/api/posts")

@app.get("/health")
def health_check():
    """Health check endpoint to verify backend status."""
    return {"status": "ok"}
