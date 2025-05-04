from fastapi import APIRouter, HTTPException, Depends, Header, status
from email_summarization_API.schemas.user_schema import UserInfo, LoginRequest, EmailRequest
from email_summarization_API.services import user_service
from email_summarization_API.database import get_db_connection
from email_summarization_API.services import jwt_service
from jose import jwt, JWTError
from email_summarization_API.services.jwt_service import SECRET_KEY, ALGORITHM

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

def verify_token(authorization: str = Header(...)):
    """
    Verify the Bearer token from Authorization header.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme.",
        )
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

@router.post("/")
async def add_user(user: UserInfo, token_data: dict = Depends(verify_token)):
    try:
        result = user_service.add_or_edit_user(user.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def list_users(token_data: dict = Depends(verify_token)):
    try:
        users = user_service.get_users()
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}")
async def get_single_user(user_id: int, token_data: dict = Depends(verify_token)):
    try:
        user = user_service.get_users(user_id)
        return user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/login")
async def login_user(login_req: LoginRequest):
    """
    Public route: Login and return token.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT user_login(%s, %s);",
            (login_req.email, login_req.password)
        )
        result = cur.fetchone()

        if result and result[0] != {}:
            user_data = result[0]

            access_token = jwt_service.create_access_token(data={"sub": user_data["email"]})

            return {
                "message": "Login successful",
                "user": user_data,
                "token": access_token
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid email or password")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cur.close()
        conn.close()

@router.post("/check-email")
async def check_email_exists(email: EmailRequest, token_data: dict = Depends(verify_token)):
    try:
        result = user_service.check_email_exists(email.email)
        return {"email_exists": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
