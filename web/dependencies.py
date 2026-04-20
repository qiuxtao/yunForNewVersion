from fastapi import Request
from fastapi.responses import RedirectResponse
from core.security import verify_token

class NotAuthenticatedException(Exception):
    pass

def check_admin(request: Request):
    token = request.cookies.get("admin_session")
    if not token or not verify_token(token):
        raise NotAuthenticatedException()
    return True
