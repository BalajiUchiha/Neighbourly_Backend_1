from services.chat_service import ChatService

class ChatController:
    @staticmethod
    async def get_chats(current_user_id: str, db):
        return await ChatService.get_chats(current_user_id, db)

    @staticmethod
    async def get_chat(chat_id: str, current_user_id: str, db):
        return await ChatService.get_chat(chat_id, current_user_id, db)

    @staticmethod
    async def send_message(chat_id: str, current_user_id: str, body: dict, db):
        return await ChatService.send_message(chat_id, current_user_id, body, db)

    @staticmethod
    async def accept_pay(chat_id: str, current_user_id: str, db):
        return await ChatService.accept_pay(chat_id, current_user_id, db)

    @staticmethod
    async def propose_bargain(chat_id: str, current_user_id: str, body: dict, db):
        proposed_amount = body.get("proposed_amount")
        from fastapi import HTTPException
        if proposed_amount is None:
            raise HTTPException(400, "proposed_amount is required")
        return await ChatService.propose_bargain(chat_id, current_user_id, proposed_amount, db)

    @staticmethod
    async def respond_to_bargain(chat_id: str, current_user_id: str, body: dict, db):
        return await ChatService.respond_to_bargain(chat_id, current_user_id, body, db)

    @staticmethod
    async def confirm_date(chat_id: str, current_user_id: str, body: dict, db):
        return await ChatService.confirm_date(chat_id, current_user_id, body, db)

    @staticmethod
    async def complete_chat(chat_id: str, current_user_id: str, db):
        return await ChatService.complete_chat(chat_id, current_user_id, db)

