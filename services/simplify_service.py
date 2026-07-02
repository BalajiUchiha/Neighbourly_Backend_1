import os
from google import genai
from google.genai import types

class SimplifyService:

    @staticmethod
    async def simplify(raw_text: str) -> str:
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return raw_text

            client = genai.Client(api_key=api_key)

            system_prompt = """You are a plain language assistant for a hyperlocal job app used in India.

Rewrite the given text in simple, friendly, easy-to-understand language.
- Use short sentences
- Avoid technical words
- Sound like a helpful friend explaining something
- Keep the same meaning but make it simpler
- Maximum 3 sentences
- Respond with only the simplified text, nothing else"""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"Simplify this:\n\n{raw_text}",
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=300,
                )
            )

            return response.text.strip()
        except Exception:
            # If simplification fails — return original
            return raw_text