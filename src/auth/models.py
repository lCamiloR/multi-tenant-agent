from pydantic import BaseModel, Field
from datetime import datetime


# --- Input ---

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


# --- Output ---

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


# --- Internal (payload inside the JWT) ---

class TokenPayload(BaseModel):
    sub: str                    # subject — user identifier
    tenant_id: str              # essential for multi-tenant
    role: str = "user"          # e.g.: "admin", "user", "readonly"
    exp: datetime               # expiry, set by jwt_handler
    iat: datetime               # issued at, set by jwt_handler
