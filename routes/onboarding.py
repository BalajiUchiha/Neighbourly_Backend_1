from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from models.onboarding import OnboardingAudioFile

router = APIRouter(tags=["onboarding"])

@router.get("/audio")
async def get_onboarding_audio(
    screen: str = Query(..., description="Screen name of the onboarding step"),
    language: str = Query("english", description="Preferred language of the user"),
    db: Session = Depends(get_db)
):
    lang_lower = language.lower() if language else "english"
    
    # Query with exactly screen and language
    audio_file = (
        db.query(OnboardingAudioFile)
        .filter(
            OnboardingAudioFile.screen_name == screen,
            OnboardingAudioFile.language == lang_lower
        )
        .first()
    )
    
    # Fallback to English if not found and requested was not english
    if not audio_file and lang_lower != "english":
        audio_file = (
            db.query(OnboardingAudioFile)
            .filter(
                OnboardingAudioFile.screen_name == screen,
                OnboardingAudioFile.language == "english"
            )
            .first()
        )
        
    if not audio_file:
        raise HTTPException(
            status_code=404,
            detail=f"Audio onboarding file not found for screen '{screen}'"
        )
        
    return {
        "audio_url": audio_file.audio_url,
        "highlight_map": audio_file.highlight_map,
        "duration_seconds": audio_file.duration_seconds
    }
