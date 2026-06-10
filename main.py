from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os

load_dotenv()

app = FastAPI(title="Neighbourly API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static/post_images", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

from routes.auth_routes import router as auth_router
from routes.feed_routes import router as feed_router
from routes.post_routes import router as post_router
from routes.location_routes import router as location_router

app.include_router(auth_router, prefix="/api/auth")
app.include_router(feed_router, prefix="/api/feed")
app.include_router(post_router, prefix="/api/posts")
app.include_router(location_router, prefix="/api/location")

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup():
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
