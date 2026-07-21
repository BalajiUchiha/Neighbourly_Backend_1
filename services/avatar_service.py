import google.generativeai as genai
import os
import uuid
import json
from datetime import datetime
from database import execute_query
from services.tts_service import TTSService

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

SMART_ACTION_TRIGGERS = {
    "job": {"type": "apply_for_job", "label": "Want me to apply for this job?"},
    "message": {"type": "suggest_reply", "label": "Want me to suggest a reply?"},
    "bargain": {"type": "counter_offer", "label": "Want me to counter this offer?"},
    "worker": {"type": "invite_worker", "label": "Want me to invite this worker?"}
}

class AvatarService:

    @staticmethod
    def detect_smart_action(screen_context: str, selected_content: str) -> dict:
        ctx = (screen_context or '').lower()
        content = (selected_content or '').lower()

        # Chat or bargain screen:
        if 'chat' in ctx or 'bargain' in ctx:
            if any(w in content for w in ['offer', 'bargain', 'amount', 'counter', 'pay', '₹', 'price', 'rate']):
                return SMART_ACTION_TRIGGERS["bargain"]
            return SMART_ACTION_TRIGGERS["message"]

        # Profile or worker view:
        if 'profile' in ctx or 'ask-worker' in ctx or 'applicant' in ctx:
            return SMART_ACTION_TRIGGERS["worker"]

        # Home, explore, or post detail screen (strictly non-chat):
        if ('home' in ctx or 'explore' in ctx or ('post' in ctx and 'chat' not in ctx)):
            if any(w in content for w in ['₹', 'pay', 'worker', 'needed', 'apply', 'job', 'work']):
                return SMART_ACTION_TRIGGERS["job"]

        return None

    @staticmethod
    async def explain(
        selected_content: str,
        screen_context: str,
        language: str,
        session_id: str,
        current_user_id: str,
        db,
        specific_question: str = None
    ) -> dict:

        # Check/deduct credits
        credits_row = execute_query(
            db,
            "SELECT * FROM user_avatar_credits WHERE user_id = %s",
            (current_user_id,),
            fetch="one"
        )
        if not credits_row:
            from fastapi import HTTPException
            raise HTTPException(400, "No credit record found")

        total = (
            credits_row["free_daily_credits_remaining"] +
            credits_row["free_monthly_credits_remaining"] +
            credits_row["purchased_credits_remaining"]
        )
        if total < 2:
            from fastapi import HTTPException
            raise HTTPException(402, "Not enough credits. Need 2 credits per session.")

        # Deduct 2 credits
        now = datetime.utcnow()
        if credits_row["free_daily_credits_remaining"] >= 2:
            execute_query(
                db,
                "UPDATE user_avatar_credits SET free_daily_credits_remaining = free_daily_credits_remaining - 2, updated_at = %s WHERE user_id = %s",
                (now, current_user_id)
            )
        elif credits_row["free_daily_credits_remaining"] + credits_row["free_monthly_credits_remaining"] >= 2:
            daily = credits_row["free_daily_credits_remaining"]
            monthly_deduct = 2 - daily
            execute_query(
                db,
                "UPDATE user_avatar_credits SET free_daily_credits_remaining = 0, free_monthly_credits_remaining = free_monthly_credits_remaining - %s, updated_at = %s WHERE user_id = %s",
                (monthly_deduct, now, current_user_id)
            )
        else:
            execute_query(
                db,
                "UPDATE user_avatar_credits SET purchased_credits_remaining = purchased_credits_remaining - 2, updated_at = %s WHERE user_id = %s",
                (now, current_user_id)
            )

        # Create session if not exists
        if not session_id:
            session_id = str(uuid.uuid4())
            execute_query(
                db,
                """INSERT INTO avatar_sessions
                   (id, user_id, screen_context, selected_content,
                    selected_content_type, language, status,
                    retry_count, created_at)
                   VALUES (%s,%s,%s,%s,'content',%s,'explained',0,%s)""",
                (session_id, current_user_id, screen_context,
                 selected_content, language, now)
            )

        # Call Gemini 2.5 Flash for explanation
        model = genai.GenerativeModel("gemini-2.5-flash")

        language_names = {
            "tamil": "Tamil", "hindi": "Hindi", "telugu": "Telugu",
            "kannada": "Kannada", "malayalam": "Malayalam", "english": "English"
        }
        lang_name = language_names.get(language, "English")

        base_context = f"""You are Monica✨, a friendly AI assistant for Neighbourly — a hyperlocal job platform in India.

The user has circled/selected this content from the app screen:
"{selected_content}"

Screen context: {screen_context}"""

        if specific_question:
            prompt = base_context + f"""

The user has asked this specific question about the circled content:
"{specific_question}"

Please provide a response in simple, friendly {lang_name} language following this exact structure:
1. First, explain what the circled content actually is/means so the user understands the context.
2. Next, answer their specific question directly using the details from the circled content and screen context.

Keep the total explanation to a maximum of 3-4 short, simple sentences. Use clear words a daily wage worker would understand.
Respond ONLY in {lang_name}. Do not include markdown or formatting."""
        else:
            prompt = base_context + f"""

Explain what the circled content is and what to do simply in {lang_name}. Maximum 3 sentences."""

        response = model.generate_content(prompt)
        explanation_text = response.text.strip()

        # Generate chat reply if in chat or bargain screen context
        chat_reply = None
        if 'chat' in screen_context or 'bargain' in screen_context:
            reply_model = genai.GenerativeModel("gemini-2.5-flash")
            reply_prompt = f"""The user is in a chat/bargain screen.
    
Content they circled: "{selected_content}"
User's question: "{specific_question or 'How should I respond?'}"

Generate a short, natural reply message the user can send.
Reply in {lang_name}. Maximum 2 sentences. Just the reply text, nothing else."""
            
            reply_response = reply_model.generate_content(reply_prompt)
            chat_reply = reply_response.text.strip()

        # Generate audio via Google TTS
        audio_url = TTSService.generate_audio(explanation_text, language)

        # Build subtitle schedule
        subtitle_schedule = TTSService.build_subtitle_schedule(
            explanation_text, audio_url
        )

        # Save explanation
        explanation_id = str(uuid.uuid4())
        execute_query(
            db,
            """INSERT INTO avatar_explanations
               (id, session_id, attempt_number, prompt_sent,
                explanation_text, audio_url, language,
                model_used, tokens_used, created_at)
               VALUES (%s,%s,1,%s,%s,%s,%s,'gemini-2.5-flash',0,%s)""",
            (explanation_id, session_id, prompt,
             explanation_text, audio_url, language, now)
        )

        # Log credit transaction
        updated = execute_query(
            db,
            "SELECT free_daily_credits_remaining + free_monthly_credits_remaining + purchased_credits_remaining as total FROM user_avatar_credits WHERE user_id = %s",
            (current_user_id,),
            fetch="one"
        )
        execute_query(
            db,
            """INSERT INTO avatar_credit_transactions
               (id, user_id, transaction_type, credits_changed,
                balance_after, reference_type, reference_id, created_at)
               VALUES (%s,%s,'free_daily_deduct',-2,%s,'avatar_session',%s,%s)""",
            (str(uuid.uuid4()), current_user_id,
             updated["total"] if updated else 0,
             session_id, now)
        )

        # Detect smart action
        smart_action = AvatarService.detect_smart_action(
            screen_context, selected_content
        )

        return {
            "session_id": session_id,
            "simplified_text": explanation_text,
            "audio_url": audio_url,
            "subtitle_schedule": subtitle_schedule,
            "smart_action": smart_action,
            "chat_reply": chat_reply,
            "credits_remaining": updated["total"] if updated else 0
        }

    @staticmethod
    async def reprocess_reply(original_reply: str, session_id: str, language: str) -> dict:
        model = genai.GenerativeModel("gemini-2.5-flash")

        lang_names = {
            "tamil": "Tamil", "hindi": "Hindi", "english": "English",
            "telugu": "Telugu", "kannada": "Kannada", "malayalam": "Malayalam"
        }
        lang = lang_names.get(language, "English")

        prompt = f"""Make this chat message more professional and polite while keeping the same meaning.

Original: "{original_reply}"

Rewrite in {lang}. Keep it natural and conversational. Maximum 2 sentences. Just the rewritten message."""

        response = model.generate_content(prompt)
        return {"reply": response.text.strip()}

    @staticmethod
    async def get_pre_written_audio(audio_type: str, language: str) -> dict:
        PRE_WRITTEN_SCRIPTS = {
            "greeting": {
                "tamil": "வணக்கம்! நான் மோனிகா. நீங்கள் புரிய வேண்டிய விஷயத்தை வட்டமிடுங்கள்.",
                "hindi": "नमस्ते! मैं Monica हूं। जो समझना हो उसे घेर लीजिए।",
                "english": "Hi! I am Monica. Draw a circle around what you need help with.",
                "telugu": "హలో! నేను మోనికా. మీకు సహాయం కావాల్సిన దాన్ని సర్కిల్ చేయండి.",
                "kannada": "ಹಲೋ! ನಾನು ಮೋನಿಕಾ. ನಿಮಗೆ ಸಹಾಯ ಬೇಕಾದುದನ್ನು ಸರ್ಕಲ್ ಮಾಡಿ.",
                "malayalam": "ഹലോ! ഞാൻ മോനിക്ക. സഹായം വേണ്ടത് വട്ടമിടുക."
            },
            "confirming": {
                "tamil": "இதுவா உங்களுக்கு வேண்டும்? 'இதை எப்படி செய்வது?' போன்ற கேள்விகள் இருந்தால் கீழே டைப் செய்யவும்.",
                "hindi": "क्या आपको यह चाहिए? अगर कोई सवाल है जैसे 'आवेदन कैसे करें?', तो नीचे टाइप करें।",
                "english": "Is this what you need help with? If you have specific questions like 'How to apply?', type or select below.",
                "telugu": "దీనికి సహాయం కావాలా? 'ఎలా అప్లై చేయాలి?' వంటి ప్రశ్నలు ఉంటే కింద ఎంచుకోండి.",
                "kannada": "ಇದಕ್ಕೆ ಸಹಾಯ ಬೇಕೇ? 'ಹೇಗೆ ಅರ್ಜಿ ಸಲ್ಲಿಸುವುದು?' ಎಂಬ ಪ್ರಶ್ನೆಗಳಿದ್ದರೆ ಕೆಳಗೆ ಟೈಪ್ ಮಾಡಿ.",
                "malayalam": "ഇതാണോ സഹായം വേണ്ടത്? 'എങ്ങനെ അപേക്ഷിക്കാം?' എന്ന ചോദ്യങ്ങൾ ഉണ്ടെങ്കിൽ താഴെ ടൈപ്പ് ചെയ്യുക."
            }
        }

        scripts = PRE_WRITTEN_SCRIPTS.get(audio_type, PRE_WRITTEN_SCRIPTS["greeting"])
        text = scripts.get(language, scripts["english"])

        audio_url = TTSService.generate_audio(text, language)
        subtitle_schedule = TTSService.build_subtitle_schedule(text, audio_url)

        return {
            "audio_url": audio_url,
            "text": text,
            "subtitle_schedule": subtitle_schedule
        }

    @staticmethod
    async def get_history(current_user_id: str, db) -> dict:
        sessions = execute_query(
            db,
            """SELECT s.id, s.screen_context, s.selected_content,
                      s.language, s.status, s.created_at,
                      e.explanation_text, e.audio_url
               FROM avatar_sessions s
               LEFT JOIN avatar_explanations e ON e.session_id = s.id
               WHERE s.user_id = %s
               ORDER BY s.created_at DESC
               LIMIT 20""",
            (current_user_id,),
            fetch="all"
        )
        return {
            "sessions": [
                {
                    "id": str(s["id"]),
                    "screen_context": s["screen_context"],
                    "selected_content": s["selected_content"],
                    "language": s["language"],
                    "status": s["status"],
                    "explanation_text": s["explanation_text"],
                    "audio_url": s["audio_url"],
                    "created_at": s["created_at"].isoformat() if s["created_at"] else None
                }
                for s in (sessions or [])
            ]
        }

    @staticmethod
    async def execute_action(
        session_id: str,
        action_type: str,
        action_reference_id: str,
        current_user_id: str,
        db
    ) -> dict:
        now = datetime.utcnow()
        result_text = ""

        if action_type == "apply_for_job":
            existing = execute_query(
                db,
                "SELECT id FROM applications WHERE post_id = %s AND worker_id = %s",
                (action_reference_id, current_user_id),
                fetch="one"
            )
            if not existing:
                execute_query(
                    db,
                    """INSERT INTO applications
                       (id, post_id, worker_id, status, source, applied_at, status_updated_at)
                       VALUES (%s,%s,%s,'applied','organic',%s,%s)""",
                    (str(uuid.uuid4()), action_reference_id,
                     current_user_id, now, now)
                )
                result_text = "Applied successfully"
            else:
                result_text = "Already applied"

        elif action_type == "suggest_reply":
            result_text = "Reply suggestion sent to chat"

        execute_query(
            db,
            """INSERT INTO avatar_actions_taken
               (id, session_id, action_type, action_reference_id,
                action_result, user_approved, created_at)
               VALUES (%s,%s,%s,%s,%s,true,%s)""",
            (str(uuid.uuid4()), session_id, action_type,
             action_reference_id, result_text, now)
        )

        return {"message": result_text, "action_type": action_type}