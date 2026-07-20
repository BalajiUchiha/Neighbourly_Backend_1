from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os

from routes.auth_routes import router as auth_router
from routes.feed_routes import router as feed_router
from routes.post_routes import router as post_router
from routes.location_routes import router as location_router
from routes.rag_routes import router as rag_router
from routes.application_routes import router as application_router
from routes.chat_routes import router as chat_router
from routes.rating_routes import router as rating_router
from routes.notification_routes import router as notification_router
from routes.profile_routes import router as profile_router
from routes.user_routes import router as user_router
from routes.avatar_routes import router as avatar_router
from routes.explore_routes import router as explore_router
os.makedirs("static/avatar_audio", exist_ok=True)
load_dotenv()

app = FastAPI(title="Neighbourly API")

origins = os.getenv("FRONTEND_URL", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Routes in exact checklist order
app.include_router(auth_router, prefix="/api/auth")
app.include_router(feed_router, prefix="/api/feed")
app.include_router(post_router, prefix="/api/posts")
app.include_router(location_router, prefix="/api/location")
app.include_router(rag_router, prefix="/api/rag")
app.include_router(application_router, prefix="/api/applications")
app.include_router(chat_router, prefix="/api/chats")
app.include_router(rating_router, prefix="/api/ratings")
app.include_router(notification_router, prefix="/api/notifications")
app.include_router(profile_router, prefix="/api/profile")
# Additional routes not explicitly in the integration list but required by the app
app.include_router(user_router, prefix="/api/users")

app.include_router(avatar_router, prefix="/api/avatar")
app.include_router(explore_router, prefix="/api/explore")

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup():
    os.makedirs("static/post_images", exist_ok=True)
    os.makedirs("static/agreements", exist_ok=True)
    
    from services.radius_service import RadiusService
    scheduler.add_job(
        RadiusService.expand_radii,
        'interval',
        hours=6,
        id='radius_expansion'
    )
    scheduler.start()

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()

@app.get("/health")
def health():
    return {"status": "ok"}

