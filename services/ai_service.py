from google import genai
from google.genai import types
import json
import os
from dotenv import load_dotenv

load_dotenv()

class AIService:

    @staticmethod
    async def refine_post(
        raw_input: str,
        retry_reason: str = None,
        previous_result: dict = None,
        preferred_language: str = "english"
    ) -> dict:

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")

        client = genai.Client(api_key=api_key)

        system_prompt = """You are a post creation assistant for Neighbourly — a hyperlocal job and volunteer platform in India.

Your job is to extract structured information from a user's raw text or voice transcript describing a task they want to post.

Always respond with ONLY a valid JSON object. No explanation. No markdown. No code blocks. Just raw JSON.

Extract these fields:
- title: short clear task title (max 8 words)
- description: clean 1-2 sentence description
- task_type: one of [farming, lifting, cleaning, driving, cooking, plumbing, electrical, carpentry, event_setup, security, shifting, other]
- post_category: "paid" if any payment mentioned, "volunteer" if free or community work
- job_nature: "full_day" if all day, "part_time" if few hours, "one_day" if single day, "ongoing" if multiple days, "helper_needed" if assisting someone
- urgency_tag: "today" if today/urgent/immediately, "tomorrow" if tomorrow, "this_week" if this week/weekend, "flexible" if no specific time
- pay_per_person: integer in rupees if mentioned, null if not
- workers_needed: integer, default 1 if not mentioned
- no_exp_needed: true if no skill required or anyone can do it, false if skill needed
- work_date: ISO date string if specific date mentioned, null if not
- work_time_slot: "morning"/"afternoon"/"evening" if time of day mentioned, null if not
- area_name: area or locality name if mentioned, null if not
- tags: array of 2-4 relevant short tags
- confidence_note: short note in English if anything was unclear or assumed, null if everything was clear"""

        # Build user message
        user_message = f"Extract structured post data from this input:\n\n\"{raw_input}\""

        if retry_reason and previous_result:
            user_message = f"""The user said the previous extraction was wrong.

Previous extraction:
{json.dumps(previous_result, indent=2)}

User's correction: "{retry_reason}"

Original input: "{raw_input}"

Please re-extract with the correction applied."""

        # === DEBUG LOG ===
        print("\n" + "=" * 60)
        print("[AI_SERVICE] === INCOMING REQUEST TO GEMINI ===")
        print(f"[AI_SERVICE] raw_input: {raw_input}")
        print(f"[AI_SERVICE] retry_reason: {retry_reason}")
        print("=" * 60)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
            )
        )

        raw_response = response.text.strip()

        # Clean response — remove any accidental markdown
        if raw_response.startswith("```"):
            raw_response = raw_response.split("```")[1]
            if raw_response.startswith("json"):
                raw_response = raw_response[4:]
        
        raw_response = raw_response.strip()

        # === DEBUG LOG ===
        print("\n" + "=" * 60)
        print("[AI_SERVICE] === RAW AI RESPONSE ===")
        print(raw_response)
        print("=" * 60)

        result = json.loads(raw_response)
        return result
    @staticmethod
    async def rag_answer(question: str, context: str, worker_name: str) -> str:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")

        client = genai.Client(api_key=api_key)

        system_prompt = f"""You are a worker profile assistant for Neighbourly — a hyperlocal job platform in India.

Answer questions about {worker_name} based only on the context provided.
Be factual and specific. Use numbers and examples from the data.
If the context does not have enough information — say so honestly.
Keep answers under 100 words."""

        user_message = f"Context about {worker_name}:\n{context}\n\nQuestion: {question}"

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=500,
            )
        )
        return response.text.strip()

    @staticmethod
    async def simplify_answer(raw_answer: str, worker_name: str) -> str:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")

        client = genai.Client(api_key=api_key)

        system_prompt = f"""You simplify answers about workers for people who may not be fluent in English.

Take the answer and rewrite it in very simple, friendly, conversational language.
Use short sentences. Avoid jargon. Keep it under 60 words.
Sound like a helpful friend explaining something."""

        user_message = f"Simplify this answer about {worker_name}:\n\n{raw_answer}"

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=300,
            )
        )
        return response.text.strip()