import uuid
import os
import shutil
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import UploadFile
from typing import List
from models.post import Post, PostImage

class PostService:
    @staticmethod
    def create_post(
        db: Session,
        current_user,
        ai_result: dict,
        additional_details: dict,
        raw_input: str,
        input_method: str,
        image_urls: List[str]
    ):
        now = datetime.utcnow()
        
        # Merge overrides
        urgency_override = additional_details.get("urgency_tag")
        job_nature_override = additional_details.get("job_nature")
        no_exp_override = additional_details.get("no_exp_needed")
        tags_override = additional_details.get("tags", [])
        
        urgency_tag = urgency_override if urgency_override else ai_result.get("urgency_tag")
        job_nature = job_nature_override if job_nature_override else ai_result.get("job_nature")
        
        if no_exp_override is not None:
            no_exp_needed = no_exp_override
        else:
            no_exp_needed = ai_result.get("no_exp_needed", False)
            
        merged_tags = list(set(tags_override + ai_result.get("tags", [])))
        
        # Parse dates
        work_date_str = ai_result.get("work_date")
        work_date = None
        if work_date_str:
            try:
                work_date = datetime.fromisoformat(work_date_str).date()
            except:
                pass

        # Create post
        post = Post(
            id=uuid.uuid4(),
            poster_id=current_user.id,
            title=ai_result.get("title"),
            description=ai_result.get("description"),
            task_type=ai_result.get("task_type"),
            post_category=ai_result.get("post_category"),
            job_nature=job_nature,
            urgency_tag=urgency_tag,
            pay_per_person=ai_result.get("pay_per_person"),
            workers_needed=ai_result.get("workers_needed", 1),
            slots_remaining=ai_result.get("workers_needed", 1),
            no_exp_needed=no_exp_needed,
            work_date=work_date,
            work_time_slot=ai_result.get("work_time_slot"),
            area_name=ai_result.get("area_name") or getattr(current_user, "area_name", None),
            district=getattr(current_user, "district", None),
            latitude=getattr(current_user, "latitude", None),
            longitude=getattr(current_user, "longitude", None),
            tags=merged_tags,
            raw_input_text=raw_input if input_method == "type" else None,
            has_voice_input=(input_method == "speak"),
            current_radius_km=15.0,
            max_radius_km=50.0,
            status="open",
            created_at=now,
            updated_at=now
        )
        
        db.add(post)
        db.commit()
        db.refresh(post)
        
        # Add images
        for i, url in enumerate(image_urls):
            pi = PostImage(
                id=uuid.uuid4(),
                post_id=post.id,
                image_url=url,
                display_order=i+1,
                created_at=now
            )
            db.add(pi)
        
        db.commit()
        
        # Raw SQL to insert into analytics tables if they exist
        try:
            from sqlalchemy import text
            db.execute(text("""
                INSERT INTO post_ai_sessions (post_id, user_id, raw_input, ai_extracted_fields, fields_edited_by_user, model_used, created_at)
                VALUES (:pid, :uid, :ri, :ai_ext, :edited, :mod, :cat)
            """), {
                "pid": str(post.id), "uid": str(current_user.id), "ri": raw_input, 
                "ai_ext": json.dumps(ai_result), "edited": json.dumps(additional_details),
                "mod": "claude-sonnet-4-20250514", "cat": now
            })
            db.commit()
        except Exception:
            db.rollback()

        try:
            from sqlalchemy import text
            db.execute(text("""
                INSERT INTO job_lifecycle_events (post_id, event_type, triggered_by, event_data, created_at)
                VALUES (:pid, :evt, :trig, :dat, :cat)
            """), {
                "pid": str(post.id), "evt": "post_created", "trig": str(current_user.id), 
                "dat": json.dumps({"post_category": ai_result.get("post_category"), "ai_generated": True}), "cat": now
            })
            db.commit()
        except Exception:
            db.rollback()

        return post.id, post

    @staticmethod
    def upload_images(files: List[UploadFile]) -> List[str]:
        os.makedirs("static/post_images", exist_ok=True)
        urls = []
        for file in files:
            if not file.filename: 
                continue
            ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
            filename = f"{uuid.uuid4()}.{ext}"
            filepath = os.path.join("static/post_images", filename)
            
            with open(filepath, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
                
            urls.append(f"/static/post_images/{filename}")
        return urls
