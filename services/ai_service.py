import google.generativeai as genai
import json
import os
from dotenv import load_dotenv

load_dotenv()

class AIService:

    @staticmethod
    async def refine_post(
        raw_input: str,
        retry_reason: str = None,
        previous_result: dict = None
    ) -> dict:

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")

        genai.configure(api_key=api_key)

        system_prompt = """You are a post creation assistant for Neighbourly — a hyperlocal job and volunteer platform in India.

Extract structured information from raw text describing a task.

Respond ONLY with a valid JSON object. No explanation. No markdown. No code blocks. Just raw JSON.

Fields to extract:
- title: short task title max 8 words
- description: clean 1-2 sentence description
- task_type: one of [farming, lifting, cleaning, driving, cooking, plumbing, electrical, carpentry, event_setup, security, shifting, gardening, painting, other]
- post_category: "paid" if payment mentioned, "volunteer" if free or community
- job_nature: "full_day", "part_time", "one_day", "ongoing", "helper_needed"
- urgency_tag: "today", "tomorrow", "this_week", "flexible"
- pay_per_person: integer or null
- workers_needed: integer default 1
- no_exp_needed: boolean
- work_date: ISO date string or null
- work_time_slot: string like "morning", "afternoon", "evening", "full_day" or null
- area_name: string or null
- tags: list of relevant tags
- confidence_note: string explaining any assumptions made"""

        user_message = f"Input:\n{raw_input}"

        if retry_reason and previous_result:
            user_message = f"Previous: {json.dumps(previous_result)}\nCorrection: {retry_reason}\nInput: {raw_input}"

        # === DEBUG LOG: What AI receives ===
        print("\n" + "=" * 60)
        print("[AI_SERVICE] === INCOMING REQUEST ===")
        print(f"[AI_SERVICE] raw_input: {raw_input}")
        print(f"[AI_SERVICE] retry_reason: {retry_reason}")
        print(f"[AI_SERVICE] previous_result: {json.dumps(previous_result) if previous_result else None}")
        print(f"[AI_SERVICE] full user_message:\n{user_message}")
        print("=" * 60)

        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_prompt
        )

        response = model.generate_content(
            user_message,
            generation_config={
                "response_mime_type": "application/json"
            }
        )

        raw_response = response.text.strip()

        # === DEBUG LOG: Raw AI response ===
        print("\n" + "=" * 60)
        print("[AI_SERVICE] === RAW AI RESPONSE ===")
        print(f"[AI_SERVICE] raw_response: {raw_response}")
        print("=" * 60)

        try:
            result = json.loads(raw_response)
        except json.JSONDecodeError:
            print(f"[AI_SERVICE] ERROR: Failed to parse JSON from AI response")
            raise ValueError(f"Failed to parse JSON from AI response: {raw_response}")

        # === DEBUG LOG: Parsed result sent back ===
        print("\n" + "=" * 60)
        print("[AI_SERVICE] === PARSED RESULT (sent to controller) ===")
        print(f"[AI_SERVICE] result: {json.dumps(result, indent=2)}")
        print("=" * 60 + "\n")

        return result
