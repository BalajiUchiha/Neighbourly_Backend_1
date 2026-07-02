from database import execute_query
from services.vector_service import VectorService
from services.simplify_service import SimplifyService
from datetime import datetime
import uuid
import json

class RagService:

    @staticmethod
    def fetch_worker_full_data(worker_id: str, db) -> dict:
        # Profile
        user = execute_query(
            db,
            "SELECT * FROM users WHERE id = %s",
            (worker_id,),
            fetch="one"
        )
        if not user:
            return None

        worker_profile = execute_query(
            db,
            "SELECT * FROM worker_profiles WHERE user_id = %s",
            (worker_id,),
            fetch="one"
        )

        # All completed applications
        completed_apps = execute_query(
            db,
            """SELECT a.*, p.title as post_title, p.task_type, p.work_date,
                      p.pay_per_person, p.area_name
               FROM applications a
               JOIN posts p ON p.id = a.post_id
               WHERE a.worker_id = %s AND a.status = 'selected'
               ORDER BY a.applied_at DESC""",
            (worker_id,),
            fetch="all"
        )

        # All ratings received
        ratings = execute_query(
            db,
            """SELECT r.stars, r.review_text, r.rating_type,
                      r.submitted_at, p.title as post_title
               FROM ratings r
               JOIN posts p ON p.id = r.post_id
               WHERE r.rated_id = %s AND r.is_revealed = true
               ORDER BY r.submitted_at DESC""",
            (worker_id,),
            fetch="all"
        )

        # Bargain history
        bargains = execute_query(
            db,
            """SELECT br.round_number, br.proposed_amount, br.status,
                      p.title as post_title, p.pay_per_person as original_pay
               FROM bargain_rounds br
               JOIN chats c ON c.id = br.chat_id
               JOIN posts p ON p.id = c.post_id
               WHERE br.proposed_by = %s
               ORDER BY br.created_at DESC""",
            (worker_id,),
            fetch="all"
        )

        # Cancellations
        cancellations = execute_query(
            db,
            """SELECT c.cancellation_type, c.reason,
                      c.cancelled_after_pay_locked,
                      c.cancelled_after_work_started,
                      p.title as post_title
               FROM cancellations c
               JOIN posts p ON p.id = c.post_id
               WHERE c.cancelled_by = %s""",
            (worker_id,),
            fetch="all"
        )

        # Trust score logs
        trust_logs = execute_query(
            db,
            """SELECT event_type, score_change, reason, created_at
               FROM trust_score_logs
               WHERE user_id = %s
               ORDER BY created_at DESC
               LIMIT 20""",
            (worker_id,),
            fetch="all"
        )

        return {
            "user": user,
            "worker_profile": worker_profile,
            "completed_apps": completed_apps or [],
            "ratings": ratings or [],
            "bargains": bargains or [],
            "cancellations": cancellations or [],
            "trust_logs": trust_logs or []
        }

    @staticmethod
    def build_chunks(data: dict) -> list[str]:
        user = data["user"]
        wp = data["worker_profile"]
        chunks = []

        # Chunk 1 — basic profile
        profile_text = f"""Worker Profile:
Name: {user['name']}
Trust Score: {user['trust_score']} ({user['trust_badge']} level)
Member since: {user['created_at'].strftime('%B %Y') if user.get('created_at') else 'Unknown'}
Location: {user.get('area_name', 'Unknown')}, {user.get('district', '')}
Aadhaar verified: {'Yes' if user.get('aadhaar_verified') else 'No'}"""

        if wp:
            profile_text += f"""
Skills: {', '.join(wp.get('skills') or [])}
Experience levels: {json.dumps(wp.get('experience_levels') or {})}
Available days: {', '.join(wp.get('availability_days') or [])}
Available slots: {', '.join(wp.get('availability_slots') or [])}
Expected wage: ₹{wp.get('wage_min', '?')} to ₹{wp.get('wage_max', '?')} per day
Open to no-experience jobs: {'Yes' if wp.get('open_to_no_exp_jobs') else 'No'}
Willing to travel: {'Yes' if wp.get('willing_to_travel') else 'No'}"""
        chunks.append(profile_text)

        # Chunk 2 — work history
        if data["completed_apps"]:
            history_text = f"Work History ({len(data['completed_apps'])} completed jobs):\n"
            for app in data["completed_apps"][:10]:
                history_text += f"- {app.get('post_title', 'Unknown task')} ({app.get('task_type', '')}) in {app.get('area_name', '')} on {app.get('work_date', 'Unknown date')}\n"
            chunks.append(history_text)

        # Chunk 3 — ratings and reviews
        if data["ratings"]:
            avg_stars = sum(r["stars"] for r in data["ratings"]) / len(data["ratings"])
            ratings_text = f"Ratings and Reviews (average: {avg_stars:.1f} stars from {len(data['ratings'])} reviews):\n"
            for r in data["ratings"][:8]:
                if r.get("review_text"):
                    ratings_text += f"- {r['stars']} stars: \"{r['review_text']}\" (for {r.get('post_title', 'a job')})\n"
            chunks.append(ratings_text)

        # Chunk 4 — bargain history
        if data["bargains"]:
            total_bargains = len(data["bargains"])
            accepted = sum(1 for b in data["bargains"] if b["status"] == "accepted")
            bargain_text = f"""Bargaining History:
Total bargain attempts: {total_bargains}
Accepted bargains: {accepted}
Rejected bargains: {total_bargains - accepted}
Details:\n"""
            for b in data["bargains"][:5]:
                bargain_text += f"- Round {b['round_number']}: proposed ₹{b['proposed_amount']} (original ₹{b.get('original_pay', '?')}) — {b['status']} for job: {b.get('post_title', 'Unknown')}\n"
            chunks.append(bargain_text)

        # Chunk 5 — cancellations and reliability
        reliability_text = f"Reliability Record:\n"
        if data["cancellations"]:
            reliability_text += f"Total cancellations: {len(data['cancellations'])}\n"
            for c in data["cancellations"]:
                reliability_text += f"- {c['cancellation_type']} for job: {c.get('post_title', 'Unknown')}"
                if c.get("cancelled_after_pay_locked"):
                    reliability_text += " (after pay was locked — serious)"
                if c.get("cancelled_after_work_started"):
                    reliability_text += " (after work started — very serious)"
                reliability_text += "\n"
        else:
            reliability_text += "No cancellations on record. Excellent reliability.\n"

        if data["trust_logs"]:
            reliability_text += f"\nRecent trust score events:\n"
            for log in data["trust_logs"][:5]:
                reliability_text += f"- {log['event_type']}: {'+' if log['score_change'] > 0 else ''}{log['score_change']} points ({log.get('reason', '')})\n"
        chunks.append(reliability_text)

        return chunks

    @staticmethod
    async def get_or_init_session(post_id, worker_id, current_user_id, db):

        # Get worker basic info
        worker_user = execute_query(
            db,
            "SELECT id, name, photo_url, trust_score, trust_badge, latitude, longitude FROM users WHERE id = %s",
            (worker_id,),
            fetch="one"
        )
        if not worker_user:
            from fastapi import HTTPException
            raise HTTPException(404, "Worker not found")

        worker_profile = execute_query(
            db,
            "SELECT skills, wage_min, wage_max, availability_days FROM worker_profiles WHERE user_id = %s",
            (worker_id,),
            fetch="one"
        )

        # Get user credits
        credits = execute_query(
            db,
            """SELECT free_daily_credits_remaining + free_monthly_credits_remaining + purchased_credits_remaining as total
               FROM user_avatar_credits WHERE user_id = %s""",
            (current_user_id,),
            fetch="one"
        )

        # Check worker rag index — is it dirty or missing
        rag_index = execute_query(
            db,
            "SELECT * FROM worker_rag_index WHERE worker_id = %s",
            (worker_id,),
            fetch="one"
        )

        needs_indexing = (
            not rag_index or
            rag_index["is_dirty"] or
            not VectorService.is_worker_indexed(worker_id)
        )

        if needs_indexing:
            # Fetch full worker data
            full_data = RagService.fetch_worker_full_data(worker_id, db)

            # Build chunks
            chunks = RagService.build_chunks(full_data)

            # Index into ChromaDB
            VectorService.index_worker(
                worker_id=worker_id,
                chunks=chunks,
                metadata={"worker_id": worker_id, "indexed_at": datetime.utcnow().isoformat()}
            )

            # Update or insert rag index record
            now = datetime.utcnow()
            if rag_index:
                execute_query(
                    db,
                    """UPDATE worker_rag_index
                       SET is_dirty = false, last_indexed_at = %s,
                           index_version = index_version + 1, updated_at = %s
                       WHERE worker_id = %s""",
                    (now, now, worker_id)
                )
            else:
                execute_query(
                    db,
                    """INSERT INTO worker_rag_index
                       (id, worker_id, is_dirty, last_indexed_at, index_version, updated_at)
                       VALUES (%s, %s, false, %s, 1, %s)""",
                    (str(uuid.uuid4()), worker_id, now, now)
                )

        # Check for existing session for this user + post + worker
        existing_session = execute_query(
            db,
            """SELECT * FROM rag_chat_sessions
               WHERE post_id = %s AND worker_id = %s AND asker_id = %s
               ORDER BY created_at DESC LIMIT 1""",
            (post_id, worker_id, current_user_id),
            fetch="one"
        )

        session_data = None
        if existing_session:
            # Load messages
            messages = execute_query(
                db,
                """SELECT role, content, simplified_content, credits_charged, created_at
                   FROM rag_chat_messages
                   WHERE session_id = %s
                   ORDER BY created_at ASC""",
                (str(existing_session["id"]),),
                fetch="all"
            )
            session_data = {
                "id": str(existing_session["id"]),
                "messages": [
                    {
                        "role": m["role"],
                        "content": m["content"],
                        "simplified_content": m.get("simplified_content"),
                        "credits_charged": m["credits_charged"],
                        "created_at": m["created_at"].isoformat() if m["created_at"] else None
                    }
                    for m in (messages or [])
                ]
            }

        # Calculate distance
        poster_post = execute_query(
            db,
            "SELECT latitude, longitude FROM posts WHERE id = %s",
            (post_id,),
            fetch="one"
        )
        distance_km = 0.0
        if poster_post and worker_user.get("latitude") and worker_user.get("longitude"):
            from services.feed_service import FeedService
            distance_km = FeedService.calculate_distance_km(
                poster_post["latitude"], poster_post["longitude"],
                worker_user["latitude"], worker_user["longitude"]
            )

        # Get bargain stats
        bargain_count = execute_query(
            db,
            "SELECT COUNT(*) as count FROM bargain_rounds WHERE proposed_by = %s",
            (worker_id,),
            fetch="one"
        )

        # Get total jobs
        total_jobs = execute_query(
            db,
            "SELECT COUNT(*) as count FROM applications WHERE worker_id = %s AND status = 'selected'",
            (worker_id,),
            fetch="one"
        )

        # Get completion rate
        completed = execute_query(
            db,
            """SELECT COUNT(*) as count FROM applications a
               JOIN posts p ON p.id = a.post_id
               WHERE a.worker_id = %s AND p.status = 'completed'""",
            (worker_id,),
            fetch="one"
        )

        total = total_jobs["count"] if total_jobs else 0
        done = completed["count"] if completed else 0
        completion_rate = f"{int((done/total)*100)}%" if total > 0 else "New"

        return {
            "worker": {
                "id": str(worker_user["id"]),
                "name": worker_user["name"],
                "photo_url": worker_user["photo_url"],
                "trust_score": worker_user["trust_score"],
                "trust_score_display": str(worker_user["trust_score"]),
                "trust_badge": worker_user["trust_badge"],
                "distance_km": distance_km,
                "skills": worker_profile["skills"] if worker_profile else [],
                "total_jobs": total,
                "completion_rate": completion_rate,
                "bargain_attempts": bargain_count["count"] if bargain_count else 0,
                "avg_response_time": "Fast"
            },
            "session": session_data,
            "credits_remaining": credits["total"] if credits else 0
        }

    @staticmethod
    async def ask(post_id, worker_id, question, session_id, source, current_user_id, db):
        from fastapi import HTTPException

        # Check credits
        credits_row = execute_query(
            db,
            "SELECT * FROM user_avatar_credits WHERE user_id = %s",
            (current_user_id,),
            fetch="one"
        )
        if not credits_row:
            raise HTTPException(400, "No credit record found")

        total_credits = (
            credits_row["free_daily_credits_remaining"] +
            credits_row["free_monthly_credits_remaining"] +
            credits_row["purchased_credits_remaining"]
        )
        if total_credits <= 0:
            raise HTTPException(402, "No credits remaining")

        # Deduct 1 credit — daily first, then monthly, then purchased
        now = datetime.utcnow()
        if credits_row["free_daily_credits_remaining"] > 0:
            execute_query(
                db,
                "UPDATE user_avatar_credits SET free_daily_credits_remaining = free_daily_credits_remaining - 1, updated_at = %s WHERE user_id = %s",
                (now, current_user_id)
            )
            deduct_type = "free_daily_deduct"
        elif credits_row["free_monthly_credits_remaining"] > 0:
            execute_query(
                db,
                "UPDATE user_avatar_credits SET free_monthly_credits_remaining = free_monthly_credits_remaining - 1, updated_at = %s WHERE user_id = %s",
                (now, current_user_id)
            )
            deduct_type = "free_monthly_deduct"
        else:
            execute_query(
                db,
                "UPDATE user_avatar_credits SET purchased_credits_remaining = purchased_credits_remaining - 1, updated_at = %s WHERE user_id = %s",
                (now, current_user_id)
            )
            deduct_type = "purchased_deduct"

        # Log credit transaction
        updated_credits = execute_query(
            db,
            "SELECT free_daily_credits_remaining + free_monthly_credits_remaining + purchased_credits_remaining as total FROM user_avatar_credits WHERE user_id = %s",
            (current_user_id,),
            fetch="one"
        )
        balance_after = updated_credits["total"] if updated_credits else 0

        execute_query(
            db,
            """INSERT INTO avatar_credit_transactions
               (id, user_id, transaction_type, credits_changed, balance_after, reference_type, created_at)
               VALUES (%s, %s, %s, -1, %s, 'rag_chat', %s)""",
            (str(uuid.uuid4()), current_user_id, deduct_type, balance_after, now)
        )

        # Create session if not exists
        if not session_id:
            session_id = str(uuid.uuid4())

            # Take snapshot of worker context
            full_data = RagService.fetch_worker_full_data(worker_id, db)
            chunks = RagService.build_chunks(full_data)
            context_snapshot = {"chunks": chunks, "worker_id": worker_id}

            execute_query(
                db,
                """INSERT INTO rag_chat_sessions
                   (id, post_id, asker_id, worker_id, source, worker_context_snapshot,
                    total_questions_asked, credits_used, invited_after, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, 0, 0, false, %s)""",
                (
                    session_id, post_id, current_user_id, worker_id,
                    source, json.dumps(context_snapshot), now
                )
            )

        # Query ChromaDB for relevant chunks
        relevant_chunks = VectorService.query_worker(worker_id, question)
        context = "\n\n".join(relevant_chunks) if relevant_chunks else "No specific data found."

        # RAG answer via Gemini
        import os
        from google import genai
        from google.genai import types
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            from fastapi import HTTPException
            raise HTTPException(500, "GEMINI_API_KEY not set")
        client = genai.Client(api_key=api_key)

        # Get conversation history for context
        history = execute_query(
            db,
            """SELECT role, content FROM rag_chat_messages
               WHERE session_id = %s ORDER BY created_at ASC LIMIT 10""",
            (session_id,),
            fetch="all"
        )

        conversation_history = []
        for h in (history or []):
            conversation_history.append(
                types.Content(
                    role="model" if h["role"] == "assistant" else "user",
                    parts=[types.Part.from_text(text=h["content"])]
                )
            )

        system_prompt = f"""You are an AI assistant helping a job poster evaluate a worker on Neighbourly, a hyperlocal job platform in India.

Answer questions about the worker based ONLY on the context provided below. Be factual and honest. If data is not available say so clearly.

Worker context:
{context}

Keep answers concise — 3 to 5 sentences maximum. Be direct and helpful."""

        conversation_history.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=question)]
            )
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=conversation_history,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=500,
            )
        )

        raw_answer = response.text.strip()

        # Simplify with second agent
        simplified_answer = await SimplifyService.simplify(raw_answer)

        # Save user message
        execute_query(
            db,
            """INSERT INTO rag_chat_messages
               (id, session_id, role, content, simplified_content, credits_charged, created_at)
               VALUES (%s, %s, 'user', %s, NULL, 1, %s)""",
            (str(uuid.uuid4()), session_id, question, now)
        )

        # Save assistant message
        execute_query(
            db,
            """INSERT INTO rag_chat_messages
               (id, session_id, role, content, simplified_content, credits_charged, created_at)
               VALUES (%s, %s, 'assistant', %s, %s, 0, %s)""",
            (str(uuid.uuid4()), session_id, raw_answer, simplified_answer, now)
        )

        # Update session stats
        execute_query(
            db,
            """UPDATE rag_chat_sessions
               SET total_questions_asked = total_questions_asked + 1,
                   credits_used = credits_used + 1
               WHERE id = %s""",
            (session_id,)
        )

        return {
            "answer": raw_answer,
            "simplified": simplified_answer,
            "session_id": session_id,
            "credits_remaining": balance_after
        }

    @staticmethod
    async def get_history(post_id, current_user_id, db):
        sessions = execute_query(
            db,
            """SELECT rcs.id, rcs.worker_id, rcs.total_questions_asked,
                      rcs.credits_used, rcs.invited_after, rcs.created_at,
                      u.name as worker_name, u.photo_url as worker_photo
               FROM rag_chat_sessions rcs
               JOIN users u ON u.id = rcs.worker_id
               WHERE rcs.post_id = %s AND rcs.asker_id = %s
               ORDER BY rcs.created_at DESC""",
            (post_id, current_user_id),
            fetch="all"
        )

        result = []
        for s in (sessions or []):
            # Get last message
            last_msg = execute_query(
                db,
                """SELECT content FROM rag_chat_messages
                   WHERE session_id = %s AND role = 'assistant'
                   ORDER BY created_at DESC LIMIT 1""",
                (str(s["id"]),),
                fetch="one"
            )
            result.append({
                "id": str(s["id"]),
                "worker_id": str(s["worker_id"]),
                "worker_name": s["worker_name"],
                "worker_photo": s["worker_photo"],
                "total_questions": s["total_questions_asked"],
                "credits_used": s["credits_used"],
                "invited_after": s["invited_after"],
                "last_message": last_msg["content"][:80] + "..." if last_msg and len(last_msg["content"]) > 80 else (last_msg["content"] if last_msg else None),
                "created_at": s["created_at"].isoformat() if s["created_at"] else None
            })

        return {"sessions": result}

    @staticmethod
    async def invite_worker(post_id, worker_id, session_id, current_user_id, db):
        now = datetime.utcnow()

        # Update rag_suggestions — mark invited
        execute_query(
            db,
            """UPDATE rag_suggestions
               SET invited_by_poster = true
               WHERE post_id = %s AND worker_id = %s""",
            (post_id, worker_id)
        )

        # Mark session as invited
        if session_id:
            execute_query(
                db,
                "UPDATE rag_chat_sessions SET invited_after = true WHERE id = %s",
                (session_id,)
            )

        return {"message": "Invite sent", "worker_id": worker_id}