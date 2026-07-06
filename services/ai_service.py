from google import genai
from google.genai import types
import json
import os
from dotenv import load_dotenv
from schemas.post import AIRefineResult

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
Extract the task details from the user's text into the requested schema structure.

CRITICAL INSTRUCTION: For the description field, DO NOT just copy the user's input. Rewrite it into a very simple, direct, and conversational 1-2 sentence description. Do NOT use overly formal or corporate language (e.g., avoid "seeking reliable individuals", "prompt assistance appreciated"). It should sound like a neighbor asking another neighbor for help."""

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
                response_schema=AIRefineResult,
                temperature=0.1
            )
        )

        raw_response = response.text.strip()

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