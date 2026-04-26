from fastapi import APIRouter, HTTPException, status
from src.auth.jwt_handler import create_access_token
from src.auth.models import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# In a real system, you'd validate against a database here.
# For now, we use a hardcoded user to keep focus on the wiring.
FAKE_USER_DB = {
    "admin@tenant1.com": {
        "password": "securepassword123",
        "tenant_id": "tenant-1",
        "role": "admin",
    }
}

@router.post("/token", response_model=TokenResponse)
def login(credentials: LoginRequest):
    """
    This is the 'front door' of authentication.
    The client sends username + password, and gets a JWT back.
    Every subsequent request uses that JWT instead of credentials.
    """
    user = FAKE_USER_DB.get(credentials.username)

    # We check both existence and password in one step to avoid
    # leaking information about which usernames exist (timing attacks)
    if not user or user["password"] != credentials.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, expires_at = create_access_token(
        subject=credentials.username,
        tenant_id=user["tenant_id"],
        role=user["role"],
    )

    return TokenResponse(access_token=token, expires_at=expires_at)