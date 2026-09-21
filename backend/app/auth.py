from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from .config import JWT_SECRET

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def hash_mpin(mpin: str) -> str: return pwd_context.hash(mpin)
def verify_mpin(raw: str, hashed: str) -> bool: return pwd_context.verify(raw, hashed)
def create_token(user: dict) -> str:
    payload = {"sub": str(user["_id"]), "email": user["email"], "role": user["role"], "exp": datetime.now(timezone.utc) + timedelta(hours=12)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        return jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired login")

def admin_only(user: dict = Depends(current_user)):
    if user["role"] != "admin": raise HTTPException(403, "Administrator access required")
    return user
