import uuid
from datetime import datetime, date
from fastapi import HTTPException
from database import execute_query
from services.pdf_service import PDFService
from services.trust_service import TrustService
from services.notification_service import NotificationService

def _serialize_row(row):
    if not row:
        return row
    res = {}
    for k, v in row.items():
        if isinstance(v, uuid.UUID):
            res[k] = str(v)
        elif isinstance(v, (datetime, date)):
            res[k] = v.isoformat()
        else:
            res[k] = v
    return res

class ChatService:
    @staticmethod
    async def get_chats(current_user_id: str, db):
        chats = execute_query(
            db,
            """SELECT c.*, p.title as post_title, p.status as post_status,
                      u.name as other_user_name, u.photo_url as other_user_photo
               FROM chats c
               JOIN posts p ON c.post_id = p.id
               JOIN users u ON u.id = CASE
                   WHEN c.poster_id::text = %s THEN c.worker_id
                   ELSE c.poster_id
               END
               WHERE c.poster_id::text = %s OR c.worker_id::text = %s
               ORDER BY c.created_at DESC""",
            (current_user_id, current_user_id, current_user_id),
            fetch="all"
        )
        return [_serialize_row(chat) for chat in (chats or [])]

    @staticmethod
    async def get_chat(chat_id: str, current_user_id: str, db):
        # Fetch chat
        chat = execute_query(db, "SELECT * FROM chats WHERE id = %s", (chat_id,), fetch="one")
        if not chat:
            raise HTTPException(404, "Chat not found")
            
        poster_id = str(chat["poster_id"])
        worker_id = str(chat["worker_id"])
        
        # Verify current user is part of the chat
        if current_user_id not in (poster_id, worker_id):
            raise HTTPException(403, "Not authorized to access this chat")
            
        # Fetch post
        post = execute_query(
            db,
            "SELECT title, pay_per_person, work_date, task_type, status, post_category, area_name, district, description FROM posts WHERE id = %s",
            (str(chat["post_id"]),),
            fetch="one"
        )
        if not post:
            raise HTTPException(404, "Post not found")
            
        # Fetch other user
        other_user_id = worker_id if current_user_id == poster_id else poster_id
        other_user = execute_query(
            db,
            "SELECT name, photo_url FROM users WHERE id = %s",
            (other_user_id,),
            fetch="one"
        )
        if not other_user:
            other_user = {"name": "Deleted User", "photo_url": None}
            
        # Fetch messages
        messages_raw = execute_query(
            db,
            "SELECT * FROM messages WHERE chat_id = %s ORDER BY sent_at ASC",
            (chat_id,),
            fetch="all"
        )
        messages = [_serialize_row(msg) for msg in (messages_raw or [])]
        
        # Fetch current bargain
        current_bargain_raw = execute_query(
            db,
            "SELECT * FROM bargain_rounds WHERE chat_id = %s AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
            (chat_id,),
            fetch="one"
        )
        current_bargain = _serialize_row(current_bargain_raw)
        
        chat_dict = _serialize_row(chat)
        chat_dict["completed"] = (post.get("status") == "completed")

        return {
            "chat": chat_dict,
            "post": _serialize_row(post),
            "other_user": other_user,
            "messages": messages,
            "current_bargain": current_bargain
        }

    @staticmethod
    async def send_message(chat_id: str, current_user_id: str, body: dict, db):
        content = body.get("content")
        message_type = body.get("message_type", "text")
        
        if not content:
            raise HTTPException(400, "Content cannot be empty")
            
        chat = execute_query(db, "SELECT poster_id, worker_id FROM chats WHERE id = %s", (chat_id,), fetch="one")
        if not chat:
            raise HTTPException(404, "Chat not found")
            
        poster_id = str(chat["poster_id"])
        worker_id = str(chat["worker_id"])
        
        if current_user_id not in (poster_id, worker_id):
            raise HTTPException(403, "Not authorized to send messages in this chat")
            
        other_user_id = worker_id if current_user_id == poster_id else poster_id
        
        sender = execute_query(db, "SELECT name FROM users WHERE id = %s", (current_user_id,), fetch="one")
        sender_name = sender["name"] if sender else "Someone"
        
        msg_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Insert message
        execute_query(
            db,
            """INSERT INTO messages (id, chat_id, sender_id, content, message_type, is_deleted, sent_at)
               VALUES (%s, %s, %s, %s, %s, false, %s)""",
            (msg_id, chat_id, current_user_id, content, message_type, now)
        )
        
        # Fetch inserted message
        inserted_msg = execute_query(db, "SELECT * FROM messages WHERE id = %s", (msg_id,), fetch="one")
        
        # Insert notification
        NotificationService.create(
            db,
            other_user_id,
            "chat_message",
            f"New message from {sender_name}",
            content,
            "chat",
            chat_id
        )
        
        return _serialize_row(inserted_msg)

    @staticmethod
    async def accept_pay(chat_id: str, current_user_id: str, db):
        chat = execute_query(db, "SELECT * FROM chats WHERE id = %s", (chat_id,), fetch="one")
        if not chat:
            raise HTTPException(404, "Chat not found")
            
        poster_id = str(chat["poster_id"])
        worker_id = str(chat["worker_id"])
        
        if current_user_id not in (poster_id, worker_id):
            raise HTTPException(403, "Not authorized")
            
        if chat["bargain_status"] != "not_started":
            raise HTTPException(400, "Bargaining already started")
            
        post = execute_query(db, "SELECT pay_per_person, title FROM posts WHERE id = %s", (str(chat["post_id"]),), fetch="one")
        if not post:
            raise HTTPException(404, "Post not found")
            
        pay = post["pay_per_person"]
        other_user_id = worker_id if current_user_id == poster_id else poster_id
        now = datetime.utcnow()
        
        # Transaction
        with db.cursor() as cur:
            # Update chat
            cur.execute(
                """UPDATE chats 
                   SET bargain_status = 'skipped', agreed_pay = %s, pay_locked_at = %s 
                   WHERE id = %s""",
                (pay, now, chat_id)
            )
            # Insert system message
            cur.execute(
                """INSERT INTO messages (id, chat_id, sender_id, content, message_type, is_deleted, sent_at)
                   VALUES (%s, %s, %s, %s, 'system', false, %s)""",
                (str(uuid.uuid4()), chat_id, current_user_id, f"Pay accepted at ₹{pay}/day", now)
            )
            # Insert notification
            NotificationService.create(
                cur,
                other_user_id,
                "pay_locked",
                "Pay agreed ✓",
                f"Pay locked at ₹{pay}/day for {post['title']}",
                "chat",
                chat_id
            )
            
        db.commit()
        return {"agreed_pay": pay}

    @staticmethod
    async def propose_bargain(chat_id: str, current_user_id: str, proposed_amount: int, db):
        chat = execute_query(db, "SELECT * FROM chats WHERE id = %s", (chat_id,), fetch="one")
        if not chat:
            raise HTTPException(404, "Chat not found")
            
        poster_id = str(chat["poster_id"])
        worker_id = str(chat["worker_id"])
        
        if current_user_id not in (poster_id, worker_id):
            raise HTTPException(403, "Not authorized")
            
        other_user_id = worker_id if current_user_id == poster_id else poster_id
        
        # Count rounds
        count_row = execute_query(db, "SELECT COUNT(*) as count FROM bargain_rounds WHERE chat_id = %s", (chat_id,), fetch="one")
        rounds_count = count_row["count"] if count_row else 0
        if rounds_count >= 3:
            raise HTTPException(400, "Maximum 3 bargain rounds reached")
            
        # Check pending
        pending_row = execute_query(db, "SELECT COUNT(*) as count FROM bargain_rounds WHERE chat_id = %s AND status = 'pending'", (chat_id,), fetch="one")
        if pending_row and pending_row["count"] > 0:
            raise HTTPException(400, "Previous offer still pending")
            
        round_id = str(uuid.uuid4())
        round_number = rounds_count + 1
        now = datetime.utcnow()
        
        with db.cursor() as cur:
            # Insert bargain round
            cur.execute(
                """INSERT INTO bargain_rounds (id, chat_id, round_number, proposed_by, proposed_amount, status, created_at)
                   VALUES (%s, %s, %s, %s, %s, 'pending', %s)""",
                (round_id, chat_id, round_number, current_user_id, proposed_amount, now)
            )
            # Update chat
            cur.execute(
                "UPDATE chats SET bargain_status = 'in_progress' WHERE id = %s",
                (chat_id,)
            )
            # Insert message
            cur.execute(
                """INSERT INTO messages (id, chat_id, sender_id, content, message_type, is_deleted, sent_at)
                   VALUES (%s, %s, %s, %s, 'bargain_offer', false, %s)""",
                (
                    str(uuid.uuid4()),
                    chat_id,
                    current_user_id,
                    f"Counter offer: ₹{proposed_amount}/day (Round {round_number} of 3)",
                    now
                )
            )
            # Get sender name
            sender = execute_query(db, "SELECT name FROM users WHERE id = %s", (current_user_id,), fetch="one")
            sender_name = sender["name"] if sender else "Someone"
            
            # Insert notification
            NotificationService.create(
                cur,
                other_user_id,
                "chat_message",
                f"New message from {sender_name}",
                f"Counter offer: ₹{proposed_amount}/day (Round {round_number} of 3)",
                "chat",
                chat_id
            )
            
        db.commit()
        return {
            "bargain_round": {
                "id": round_id,
                "round_number": round_number,
                "proposed_amount": proposed_amount
            }
        }

    @staticmethod
    async def respond_to_bargain(chat_id: str, current_user_id: str, body: dict, db):
        action = body.get("action")
        bargain_round_id = body.get("bargain_round_id")
        
        if action not in ("accept", "reject") or not bargain_round_id:
            raise HTTPException(400, "Invalid parameters")
            
        chat = execute_query(db, "SELECT * FROM chats WHERE id = %s", (chat_id,), fetch="one")
        if not chat:
            raise HTTPException(404, "Chat not found")
            
        poster_id = str(chat["poster_id"])
        worker_id = str(chat["worker_id"])
        
        if current_user_id not in (poster_id, worker_id):
            raise HTTPException(403, "Not authorized")
            
        other_user_id = worker_id if current_user_id == poster_id else poster_id
        
        # Fetch bargain round
        round_data = execute_query(db, "SELECT * FROM bargain_rounds WHERE id = %s AND chat_id = %s", (bargain_round_id, chat_id), fetch="one")
        if not round_data:
            raise HTTPException(404, "Bargain round not found")
            
        if str(round_data["proposed_by"]) == current_user_id:
            raise HTTPException(400, "You cannot respond to your own counter offer")
            
        if round_data["status"] != "pending":
            raise HTTPException(400, "Bargain round is already completed")
            
        round_number = round_data["round_number"]
        proposed_amount = round_data["proposed_amount"]
        now = datetime.utcnow()
        
        if action == "accept":
            with db.cursor() as cur:
                # Update bargain round
                cur.execute(
                    "UPDATE bargain_rounds SET status = 'accepted', responded_at = %s WHERE id = %s",
                    (now, bargain_round_id)
                )
                # Update chat
                cur.execute(
                    """UPDATE chats 
                       SET bargain_status = 'agreed', agreed_pay = %s, pay_locked_at = %s 
                       WHERE id = %s""",
                    (proposed_amount, now, chat_id)
                )
                # Insert bargain message
                cur.execute(
                    """INSERT INTO messages (id, chat_id, sender_id, content, message_type, is_deleted, sent_at)
                       VALUES (%s, %s, %s, %s, 'bargain_accept', false, %s)""",
                    (str(uuid.uuid4()), chat_id, current_user_id, f"Pay locked at ₹{proposed_amount}/day — both agreed ✓", now)
                )
                # Get post title
                post = execute_query(db, "SELECT title FROM posts WHERE id = %s", (str(chat["post_id"]),), fetch="one")
                post_title = post["title"] if post else "Task"

                # Insert notification
                NotificationService.create(
                    cur,
                    other_user_id,
                    "pay_locked",
                    "Pay agreed ✓",
                    f"Pay locked at ₹{proposed_amount}/day for {post_title}",
                    "chat",
                    chat_id
                )
                
            db.commit()
            return {"agreed_pay": proposed_amount, "next_bargain": None}
            
        else: # action == "reject"
            if round_number >= 3:
                # Fallback to original pay
                post = execute_query(db, "SELECT pay_per_person, title FROM posts WHERE id = %s", (str(chat["post_id"]),), fetch="one")
                if not post:
                    raise HTTPException(404, "Post not found")
                original_pay = post["pay_per_person"]
                
                with db.cursor() as cur:
                    # Update bargain round
                    cur.execute(
                        "UPDATE bargain_rounds SET status = 'rejected', responded_at = %s WHERE id = %s",
                        (now, bargain_round_id)
                    )
                    # Update chat
                    cur.execute(
                        """UPDATE chats 
                           SET bargain_status = 'skipped', agreed_pay = %s, pay_locked_at = %s 
                           WHERE id = %s""",
                        (original_pay, now, chat_id)
                    )
                    # Insert message
                    cur.execute(
                        """INSERT INTO messages (id, chat_id, sender_id, content, message_type, is_deleted, sent_at)
                           VALUES (%s, %s, %s, %s, 'system', false, %s)""",
                        (str(uuid.uuid4()), chat_id, current_user_id, f"Bargaining ended. Pay set to original ₹{original_pay}/day", now)
                    )
                    # Insert notification
                    NotificationService.create(
                        cur,
                        other_user_id,
                        "pay_locked",
                        "Pay agreed ✓",
                        f"Pay locked at ₹{original_pay}/day for {post['title']}",
                        "chat",
                        chat_id
                    )
                    
                db.commit()
                return {"agreed_pay": original_pay, "next_bargain": None}
            else:
                with db.cursor() as cur:
                    # Update bargain round
                    cur.execute(
                        "UPDATE bargain_rounds SET status = 'rejected', responded_at = %s WHERE id = %s",
                        (now, bargain_round_id)
                    )
                    # Insert message
                    cur.execute(
                        """INSERT INTO messages (id, chat_id, sender_id, content, message_type, is_deleted, sent_at)
                           VALUES (%s, %s, %s, %s, 'system', false, %s)""",
                        (str(uuid.uuid4()), chat_id, current_user_id, "Offer rejected. You can send a new counter offer.", now)
                    )
                    
                db.commit()
                return {"next_bargain": None}

    @staticmethod
    async def confirm_date(chat_id: str, current_user_id: str, body: dict, db):
        work_date = body.get("work_date")
        work_time_slot = body.get("work_time_slot")
        
        if not work_date or not work_time_slot:
            raise HTTPException(400, "work_date and work_time_slot are required")
            
        chat = execute_query(db, "SELECT * FROM chats WHERE id = %s", (chat_id,), fetch="one")
        if not chat:
            raise HTTPException(404, "Chat not found")
            
        poster_id = str(chat["poster_id"])
        worker_id = str(chat["worker_id"])
        
        if current_user_id not in (poster_id, worker_id):
            raise HTTPException(403, "Not authorized")
            
        if chat["agreed_pay"] is None:
            raise HTTPException(400, "Pay must be locked before confirming date")
            
        now = datetime.utcnow()
        
        with db.cursor() as cur:
            # Update chat
            cur.execute(
                """UPDATE chats 
                   SET work_date_confirmed = true, work_date = %s, work_time_slot = %s 
                   WHERE id = %s""",
                (work_date, work_time_slot, chat_id)
            )
            # Insert message
            cur.execute(
                """INSERT INTO messages (id, chat_id, sender_id, content, message_type, is_deleted, sent_at)
                   VALUES (%s, %s, %s, %s, 'system', false, %s)""",
                (str(uuid.uuid4()), chat_id, current_user_id, f"Work confirmed for {work_date} {work_time_slot}", now)
            )
            # Insert notifications for both poster and worker
            NotificationService.create(
                cur,
                poster_id,
                "work_date_confirmed",
                "Work date confirmed 📅",
                f"Work confirmed for {work_date} {work_time_slot}",
                "chat",
                chat_id
            )
            NotificationService.create(
                cur,
                worker_id,
                "work_date_confirmed",
                "Work date confirmed 📅",
                f"Work confirmed for {work_date} {work_time_slot}",
                "chat",
                chat_id
            )
            
        db.commit()
        
        # Fetch updated chat, post, and users to generate PDF
        updated_chat = execute_query(db, "SELECT * FROM chats WHERE id = %s", (chat_id,), fetch="one")
        post = execute_query(db, "SELECT * FROM posts WHERE id = %s", (str(updated_chat["post_id"]),), fetch="one")
        poster = execute_query(db, "SELECT * FROM users WHERE id = %s", (poster_id,), fetch="one")
        worker = execute_query(db, "SELECT * FROM users WHERE id = %s", (worker_id,), fetch="one")
        
        # Generate Agreement PDF
        pdf_url = PDFService.generate_agreement(updated_chat, post, poster, worker)
        
        # Save into job_agreements if not exists
        existing_agr = execute_query(db, "SELECT id FROM job_agreements WHERE chat_id = %s", (chat_id,), fetch="one")
        if not existing_agr:
            task_desc = post.get("description") or post.get("title") or ""
            execute_query(
                db,
                """INSERT INTO job_agreements
                   (id, chat_id, post_id, poster_id, worker_id, agreed_pay,
                    work_date, work_time_slot, task_description, pdf_url,
                    generated_at, poster_acknowledged, worker_acknowledged)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,false,false)""",
                (str(uuid.uuid4()), chat_id, str(updated_chat["post_id"]), poster_id, worker_id,
                 updated_chat.get("agreed_pay"), updated_chat.get("work_date"),
                 updated_chat.get("work_time_slot"), task_desc, pdf_url, now)
            )
        
        # Update chat with agreement_pdf_url and insert system message
        with db.cursor() as cur:
            cur.execute(
                "UPDATE chats SET agreement_pdf_url = %s WHERE id = %s",
                (pdf_url, chat_id)
            )
            cur.execute(
                """INSERT INTO messages (id, chat_id, sender_id, content, message_type, is_deleted, sent_at)
                   VALUES (%s, %s, %s, %s, 'system', false, %s)""",
                (str(uuid.uuid4()), chat_id, current_user_id, "Job agreement generated — tap to view", now)
            )
            
        db.commit()
        
        return {"agreement_pdf_url": pdf_url}

    @staticmethod
    async def generate_agreement(chat_id: str, current_user_id: str, db):
        chat_row = execute_query(
            db,
            """SELECT c.*, p.title, p.description, p.task_type, p.area_name,
                      poster.name as poster_name,
                      worker.name as worker_name
               FROM chats c
               JOIN posts p ON p.id = c.post_id
               JOIN users poster ON poster.id = c.poster_id
               JOIN users worker ON worker.id = c.worker_id
               WHERE c.id = %s""",
            (chat_id,),
            fetch="one"
        )
        if not chat_row:
            raise HTTPException(404, "Chat not found")
            
        poster_id = str(chat_row["poster_id"])
        worker_id = str(chat_row["worker_id"])
        
        if current_user_id not in (poster_id, worker_id):
            raise HTTPException(403, "Not authorized")
            
        if not chat_row.get("work_date_confirmed"):
            raise HTTPException(400, "Work date must be confirmed before generating agreement")
            
        # Check if agreement already exists
        existing = execute_query(
            db,
            "SELECT pdf_url FROM job_agreements WHERE chat_id = %s",
            (chat_id,),
            fetch="one"
        )
        if existing and existing.get("pdf_url"):
            return {"agreement_pdf_url": existing["pdf_url"]}

        post_id = str(chat_row["post_id"])
        post = execute_query(db, "SELECT * FROM posts WHERE id = %s", (post_id,), fetch="one")
        poster = execute_query(db, "SELECT * FROM users WHERE id = %s", (poster_id,), fetch="one")
        worker = execute_query(db, "SELECT * FROM users WHERE id = %s", (worker_id,), fetch="one")

        pdf_url = PDFService.generate_agreement(chat_row, post, poster, worker)
        now = datetime.utcnow()
        agreement_id = str(uuid.uuid4())
        task_desc = chat_row.get("description") or chat_row.get("title") or ""

        execute_query(
            db,
            """INSERT INTO job_agreements
               (id, chat_id, post_id, poster_id, worker_id, agreed_pay,
                work_date, work_time_slot, task_description, pdf_url,
                generated_at, poster_acknowledged, worker_acknowledged)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,false,false)""",
            (agreement_id, chat_id, post_id, poster_id, worker_id,
             chat_row.get("agreed_pay"), chat_row.get("work_date"),
             chat_row.get("work_time_slot"), task_desc, pdf_url, now)
        )

        execute_query(
            db,
            "UPDATE chats SET agreement_pdf_url = %s WHERE id = %s",
            (pdf_url, chat_id)
        )

        return {"agreement_pdf_url": pdf_url}

    @staticmethod
    async def complete_chat(chat_id: str, current_user_id: str, db):
        chat = execute_query(db, "SELECT * FROM chats WHERE id = %s", (chat_id,), fetch="one")
        if not chat:
            raise HTTPException(404, "Chat not found")
            
        poster_id = str(chat["poster_id"])
        worker_id = str(chat["worker_id"])
        application_id = str(chat["application_id"])
        post_id = str(chat["post_id"])
        
        if current_user_id != poster_id:
            raise HTTPException(403, "Only the job poster can mark work as complete")
            
        if not chat["work_date_confirmed"]:
            raise HTTPException(400, "Work date must be confirmed before marking work as complete")
            
        post = execute_query(db, "SELECT title FROM posts WHERE id = %s", (post_id,), fetch="one")
        post_title = post["title"] if post else "Task"
        
        now = datetime.utcnow()
        
        poster_user = execute_query(db, "SELECT name FROM users WHERE id = %s", (poster_id,), fetch="one")
        worker_user = execute_query(db, "SELECT name FROM users WHERE id = %s", (worker_id,), fetch="one")
        poster_name = poster_user["name"] if poster_user else "Poster"
        worker_name = worker_user["name"] if worker_user else "Worker"

        # Transaction
        with db.cursor() as cur:
            # Update post status
            cur.execute(
                "UPDATE posts SET status = 'completed', completed_at = %s, updated_at = %s WHERE id = %s",
                (now, now, post_id)
            )
            # Update application status updated timestamp (status remains 'selected' as 'completed' is not in application_status_enum)
            cur.execute(
                "UPDATE applications SET status_updated_at = %s WHERE id = %s",
                (now, application_id)
            )
            # Insert lifecycle event
            cur.execute(
                """INSERT INTO job_lifecycle_events (id, post_id, application_id, event_type, triggered_by, created_at)
                   VALUES (%s, %s, %s, 'work_completed', %s, %s)""",
                (str(uuid.uuid4()), post_id, application_id, current_user_id, now)
            )
            # Insert notifications
            NotificationService.create(
                cur, worker_id, "work_completed", "Work marked complete 🎉",
                f"{post_title} has been completed", "chat", chat_id
            )
            NotificationService.create(
                cur, poster_id, "rate_prompt", "Rate your experience ⭐",
                f"How was {worker_name}? Leave a review for {post_title}", "chat", chat_id
            )
            NotificationService.create(
                cur, worker_id, "rate_prompt", "Rate your experience ⭐",
                f"How was {poster_name}? Leave a review for {post_title}", "chat", chat_id
            )
            
        db.commit()
        
        # Apply completion score (+8 points) to worker
        TrustService.apply_completion_score(db, worker_id, application_id)
        
        return {"message": "Work marked complete"}
