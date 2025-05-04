from fastapi import APIRouter, Depends, HTTPException, status, Header
from email_summarization_API.schemas.email_schema import EmailSchema
from email_summarization_API.services.gmail_service import send_email
from jose import jwt, JWTError
from email_summarization_API.services.jwt_service import SECRET_KEY, ALGORITHM

router = APIRouter(
    prefix="/email",
    tags=["Email"],
)

def verify_jwt_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")

    token = authorization.split(" ")[1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

@router.post("/send", dependencies=[Depends(verify_jwt_token)])
async def send_email_api(email: EmailSchema):
    result = send_email(
        to=email.to,
        subject=email.subject,
        body=email.body,
        cc=email.cc,
        bcc=email.bcc
    )
    return {"message_id": result['id']}
