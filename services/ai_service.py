import google.generativeai as genai
import json
import os

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

        genai.configure(api_key=api_key)

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

        model = genai.GenerativeModel(
            model_name="gemini-2.5-pro",
            system_instruction=system_prompt
        )

        response = model.generate_content(
            user_message,
            generation_config={"max_output_tokens": 1000}
        )

        raw_response = response.text.strip()

        # Clean response — remove any accidental markdown
        if raw_response.startswith("```"):
            lines = raw_response.split("\\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            raw_response = "\\n".join(lines).strip()

        try:
            result = json.loads(raw_response)
        except json.JSONDecodeError:
            # Fallback parsing in case of markdown wrapping
            if "{" in raw_response:
                raw_response = raw_response[raw_response.find("{"):raw_response.rfind("}")+1]
                result = json.loads(raw_response)
            else:
                raise

        return result
