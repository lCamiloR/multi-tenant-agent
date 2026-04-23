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


# --- Internal (payload dentro do JWT) ---

class TokenPayload(BaseModel):
    sub: str                    # subject — identificador do usuário
    tenant_id: str              # essencial para multi-tenant
    role: str = "user"          # ex: "admin", "user", "readonly"
    exp: datetime               # expiry, preenchido pelo jwt_handler
    iat: datetime               # issued at, preenchido pelo jwt_handler