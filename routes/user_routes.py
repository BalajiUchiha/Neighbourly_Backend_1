from fastapi import APIRouter, Depends, Request, UploadFile, File
from database import get_db, execute_query
from utils.dependencies import get_current_user
import os, uuid, shutil

router = APIRouter()


@router.patch("/me/preferences")
async def update_preferences(
    request: Request,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    body = await request.json()
    tech_comfort = body.get("tech_comfort_level")
    if tech_comfort:
        execute_query(
            db,
            "UPDATE users SET tech_comfort_level = %s WHERE id = %s",
            (tech_comfort, current_user_id)
        )
    return {"message": "Preferences updated"}


@router.post("/me/photo")
async def upload_photo(
    file: UploadFile = File(...),
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    # Save to static/profile_photos/
    os.makedirs("static/profile_photos", exist_ok=True)
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    filepath = f"static/profile_photos/{filename}"

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    api_base = os.getenv("VITE_API_URL", "http://127.0.0.1:8000")
    photo_url = f"/static/profile_photos/{filename}"

    execute_query(
        db,
        "UPDATE users SET photo_url = %s WHERE id = %s",
        (photo_url, current_user_id)
    )

    return {"photo_url": photo_url, "message": "Photo uploaded successfully"}
