from database import execute_query
from datetime import datetime, timedelta
import uuid
import os
import shutil
import json

class PostService:

    @staticmethod
    async def create_post(
        ai_result, additional_details,
        raw_input, input_method,
        image_files, current_user_id, db
    ):
        # === DEBUG LOG: Incoming data ===
        print("\n" + "=" * 60)
        print("[POST_SERVICE] === CREATE POST — INCOMING DATA ===")
        print(f"[POST_SERVICE] current_user_id: {current_user_id}")
        print(f"[POST_SERVICE] raw_input: {raw_input}")
        print(f"[POST_SERVICE] input_method: {input_method}")
        print(f"[POST_SERVICE] ai_result: {json.dumps(ai_result, indent=2)}")
        print(f"[POST_SERVICE] additional_details: {json.dumps(additional_details, indent=2)}")
        print(f"[POST_SERVICE] image_files count: {len(image_files)}")
        print("=" * 60)

        user = execute_query(
            db,
            "SELECT * FROM users WHERE id = %s",
            (current_user_id,),
            fetch="one"
        )
        if not user:
            print("[POST_SERVICE] ERROR: User not found")
            from fastapi import HTTPException
            raise HTTPException(404, "User not found")

        now = datetime.utcnow()
        post_id = str(uuid.uuid4())

        # Merge tags
        ai_tags = ai_result.get("tags", [])
        extra_tags = additional_details.get("tags", [])
        merged_tags = list(set(ai_tags + extra_tags))

        # Calculate urgency_expires_at
        urgency_tag = additional_details.get("urgency_tag") or ai_result.get("urgency_tag", "flexible")
        urgency_expires_at = None
        if urgency_tag == "today":
            urgency_expires_at = now + timedelta(hours=24)
        elif urgency_tag == "tomorrow":
            urgency_expires_at = now + timedelta(hours=48)
        elif urgency_tag == "this_week":
            urgency_expires_at = now + timedelta(days=7)

        # === DEBUG LOG: Processed/merged fields ===
        print("\n" + "=" * 60)
        print("[POST_SERVICE] === PROCESSED FIELDS (after merge) ===")
        print(f"[POST_SERVICE] post_id: {post_id}")
        print(f"[POST_SERVICE] title: {ai_result.get('title', '')}")
        print(f"[POST_SERVICE] description: {ai_result.get('description', '')}")
        print(f"[POST_SERVICE] task_type: {ai_result.get('task_type', 'other')}")
        print(f"[POST_SERVICE] post_category: {ai_result.get('post_category', 'paid')}")
        print(f"[POST_SERVICE] job_nature: {additional_details.get('job_nature') or ai_result.get('job_nature', 'full_day')}")
        print(f"[POST_SERVICE] urgency_tag: {urgency_tag}")
        print(f"[POST_SERVICE] urgency_expires_at: {urgency_expires_at}")
        print(f"[POST_SERVICE] merged_tags: {merged_tags}")
        print(f"[POST_SERVICE] pay_per_person: {ai_result.get('pay_per_person')}")
        print(f"[POST_SERVICE] workers_needed: {ai_result.get('workers_needed', 1)}")
        print(f"[POST_SERVICE] no_exp_needed: {additional_details.get('no_exp_needed') if additional_details.get('no_exp_needed') is not None else ai_result.get('no_exp_needed', False)}")
        print(f"[POST_SERVICE] user district: {user['district']}, area: {user['area_name']}")
        print("=" * 60)

        # Insert post
        execute_query(
            db,
            """INSERT INTO posts (
                id, poster_id, title, description, task_type,
                post_category, job_nature, urgency_tag, urgency_expires_at,
                pay_per_person, workers_needed, slots_remaining,
                no_exp_needed, work_date, work_time_slot,
                area_name, district, latitude, longitude, location_accuracy,
                tags, status, ai_generated, raw_input_text, original_ai_draft,
                current_radius_km, max_radius_km, expansion_count,
                is_remote_area, post_type, original_language,
                created_at, updated_at
            ) VALUES (
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,%s,%s,
                %s,'open',true,%s,%s,
                15,50,0,
                false,'regular',%s,
                %s,%s
            )""",
            (
                post_id, current_user_id,
                ai_result.get("title", ""),
                ai_result.get("description", ""),
                ai_result.get("task_type", "other"),
                ai_result.get("post_category", "paid"),
                additional_details.get("job_nature") or ai_result.get("job_nature", "full_day"),
                urgency_tag,
                urgency_expires_at,
                ai_result.get("pay_per_person"),
                ai_result.get("workers_needed", 1),
                ai_result.get("workers_needed", 1),
                additional_details.get("no_exp_needed") if additional_details.get("no_exp_needed") is not None else ai_result.get("no_exp_needed", False),
                ai_result.get("work_date"),
                ai_result.get("work_time_slot"),
                ai_result.get("area_name") or user["area_name"],
                user["district"],
                user["latitude"],
                user["longitude"],
                user["location_accuracy"],
                merged_tags,
                raw_input if input_method == "type" else None,
                json.dumps(ai_result),
                user["preferred_language"],
                now, now
            )
        )

        # Handle images
        image_urls = []
        os.makedirs("static/post_images", exist_ok=True)
        for i, image_file in enumerate(image_files):
            ext = image_file.filename.split(".")[-1] if "." in image_file.filename else "jpg"
            filename = f"{post_id}_{i+1}.{ext}"
            filepath = f"static/post_images/{filename}"
            with open(filepath, "wb") as f:
                shutil.copyfileobj(image_file.file, f)
            image_url = f"/static/post_images/{filename}"
            image_urls.append(image_url)
            execute_query(
                db,
                "INSERT INTO post_images (id, post_id, image_url, display_order, uploaded_at) VALUES (%s,%s,%s,%s,%s)",
                (str(uuid.uuid4()), post_id, image_url, i+1, now)
            )

        # Insert post_ai_sessions
        execute_query(
            db,
            """INSERT INTO post_ai_sessions
               (id, post_id, user_id, raw_input, ai_extracted_fields,
                fields_edited_by_user, model_used, tokens_used, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                str(uuid.uuid4()), post_id, current_user_id,
                raw_input, json.dumps(ai_result),
                json.dumps(additional_details),
                "gemini-2.5-flash", 0, now
            )
        )

        print("[POST_SERVICE] post_ai_sessions inserted")

        # Insert job_lifecycle_events
        execute_query(
            db,
            """INSERT INTO job_lifecycle_events
               (id, post_id, application_id, event_type, triggered_by, event_data, created_at)
               VALUES (%s,%s,NULL,'post_created',%s,%s,%s)""",
            (
                str(uuid.uuid4()), post_id, current_user_id,
                json.dumps({"post_category": ai_result.get("post_category"), "ai_generated": True}),
                now
            )
        )

        response_data = {
            "post_id": post_id,
            "message": "Post created successfully"
        }

        # === DEBUG LOG: Final response to frontend ===
        print("\n" + "=" * 60)
        print("[POST_SERVICE] === RESPONSE SENT TO FRONTEND ===")
        print(f"[POST_SERVICE] response: {json.dumps(response_data, indent=2)}")
        print(f"[POST_SERVICE] image_urls: {image_urls}")
        print("=" * 60 + "\n")

        return response_data

    @staticmethod
    async def get_my_active_post(current_user_id, db):
        post = execute_query(
            db,
            """SELECT * FROM posts 
               WHERE poster_id = %s AND status = 'open'
               ORDER BY created_at DESC LIMIT 1""",
            (current_user_id,),
            fetch="one"
        )
        if not post:
            return {"post": None}

        images = execute_query(
            db,
            "SELECT image_url, display_order FROM post_images WHERE post_id = %s ORDER BY display_order",
            (str(post["id"]),),
            fetch="all"
        )

        app_count = execute_query(
            db,
            "SELECT COUNT(*) as count FROM applications WHERE post_id = %s AND status != 'withdrawn'",
            (str(post["id"]),),
            fetch="one"
        )

        return {
            "post": {
                "id": str(post["id"]),
                "title": post["title"],
                "status": post["status"],
                "applications_count": app_count["count"] if app_count else 0,
                "images": images or [],
                "created_at": post["created_at"].isoformat() if post["created_at"] else None
            }
        }
