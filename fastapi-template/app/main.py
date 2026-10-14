import hmac
import os

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import APIKeyHeader

app = FastAPI()
api_token_header = APIKeyHeader(name="X-API-Token", auto_error=False)


def require_api_token(token: str | None = Depends(api_token_header)) -> bool:
    expected_token = os.environ.get("API_TOKEN")
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured",
        )
    if token is None or not hmac.compare_digest(token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )
    return True


@app.get('/')
async def root():
    return {'message': 'FastAPI template is running'}


@app.get('/secure')
async def secure_route(auth: bool = Depends(require_api_token)):
    return {'message': 'You are authorized'}
