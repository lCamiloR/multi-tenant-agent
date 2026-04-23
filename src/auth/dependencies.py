from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from src.auth.jwt_handler import decode_token
from src.auth.models import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def _get_token_payload(token: str = Depends(oauth2_scheme)) -> TokenPayload:
    try:
        return decode_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


# --- Dependencies públicas (use estas nos routes) ---

def get_current_user(payload: TokenPayload = Depends(_get_token_payload)) -> TokenPayload:
    """Qualquer usuário autenticado."""
    return payload


def require_admin(payload: TokenPayload = Depends(_get_token_payload)) -> TokenPayload:
    """Apenas usuários com role=admin."""
    if payload.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return payload


def get_tenant_id(payload: TokenPayload = Depends(_get_token_payload)) -> str:
    """Extrai o tenant_id diretamente — útil para filtrar dados no banco."""
    return payload.tenant_id