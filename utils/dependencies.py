from fastapi import Depends, HTTPException, Header
from utils.jwt import decode_token


async def get_current_user(authorization: str = Header(...)):
    """
    Dependency that validates a Bearer access token from the Authorization header
    and returns the authenticated user_id string.
    Raises 401 for any missing, malformed, or expired token.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")

    token = authorization.split(" ", 1)[1]

    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except Exception:
        raise HTTPException(status_code=401, detail="Token expired or invalid")
