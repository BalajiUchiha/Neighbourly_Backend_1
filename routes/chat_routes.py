from fastapi import APIRouter, Depends, Request
from controllers.chat_controller import ChatController
from database import get_db
from utils.dependencies import get_current_user

router = APIRouter()

@router.get("")
async def get_chats(
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await ChatController.get_chats(current_user_id, db)

@router.get("/{chat_id}")
async def get_chat(
    chat_id: str,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await ChatController.get_chat(chat_id, current_user_id, db)

@router.post("/{chat_id}/message")
async def send_message(
    chat_id: str,
    request: Request,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    body = await request.json()
    return await ChatController.send_message(chat_id, current_user_id, body, db)

@router.post("/{chat_id}/accept-pay")
async def accept_pay(
    chat_id: str,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await ChatController.accept_pay(chat_id, current_user_id, db)

@router.post("/{chat_id}/bargain")
async def propose_bargain(
    chat_id: str,
    request: Request,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    body = await request.json()
    return await ChatController.propose_bargain(chat_id, current_user_id, body, db)

@router.post("/{chat_id}/bargain-respond")
async def respond_to_bargain(
    chat_id: str,
    request: Request,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    body = await request.json()
    return await ChatController.respond_to_bargain(chat_id, current_user_id, body, db)

@router.post("/{chat_id}/confirm-date")
async def confirm_date(
    chat_id: str,
    request: Request,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    body = await request.json()
    return await ChatController.confirm_date(chat_id, current_user_id, body, db)

@router.post("/{chat_id}/complete")
async def complete_chat(
    chat_id: str,
    db=Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await ChatController.complete_chat(chat_id, current_user_id, db)

