from fastapi import APIRouter, Depends, HTTPException, status, Header
from email_summarization_API.schemas.email_schema import EmailSchema, ReplyEmailSchema
from email_summarization_API.services.gmail_service import (
    send_email,
    list_emails,
    reply_email,
    save_sent_email,
    save_replied_email
)
from email_summarization_API.database import get_db_connection
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


# ----------------- Send Email -----------------

@router.post("/send", dependencies=[Depends(verify_jwt_token)])
async def send_email_api(email: EmailSchema):
    try:
        result = send_email(
            to=email.recipient,
            subject=email.subject,
            body=email.body,
            cc=email.cc,
            bcc=email.bcc
        )

        save_sent_email(
            sender="zohbiyazan@gmail.com",
            recipient=email.recipient,
            subject=email.subject,
            body=email.body,
            cc=email.cc,
            bcc=email.bcc,
            status="sent"
        )

        return {"message_id": result['id']}
    except Exception as e:
        print(f"Failed to send email: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")


# ----------------- List Sent Emails -----------------

@router.get("/list", dependencies=[Depends(verify_jwt_token)])
async def list_sent_emails():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, sender, recipient, subject, body, cc, bcc, sent_at, status
            FROM sent_emails
            ORDER BY sent_at DESC
        """)
        rows = cur.fetchall()

        emails = []
        for row in rows:
            emails.append({
                "id": row[0],
                "sender": row[1],
                "recipient": row[2],
                "subject": row[3],
                "preview": row[4][:100],
                "cc": row[5],
                "bcc": row[6],
                "time": row[7].strftime("%I:%M %p"),
                "status": row[8],
                "isRead": False,
                "isStarred": False
            })

        return emails

    except Exception as e:
        print(f"Failed to fetch sent emails: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch sent emails")
    finally:
        cur.close()
        conn.close()


# ----------------- List Received Emails -----------------

@router.get("/receive", dependencies=[Depends(verify_jwt_token)])
async def list_received_emails():
    try:
        emails = list_emails()
        return emails
    except Exception as e:
        print(f"Failed to fetch inbox emails: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch inbox emails")


# ----------------- Reply to Email -----------------

@router.post("/reply", dependencies=[Depends(verify_jwt_token)])
async def reply_to_email_api(email: ReplyEmailSchema):
    try:
        result = reply_email(
            to=email.recipient,
            subject=email.subject,
            body=email.body,
            thread_id=email.thread_id,
            message_id=email.message_id
        )

        save_replied_email(
            sender="zohbiyazan@gmail.com",
            recipient=email.recipient,
            subject=email.subject,
            body=email.body,
            original_message_id=email.message_id
        )

        return {"message_id": result['id']}
    except Exception as e:
        print(f"Failed to reply to email: {e}")
        raise HTTPException(status_code=500, detail="Failed to reply to email")


# ----------------- List Replied Emails -----------------

@router.get("/replies", dependencies=[Depends(verify_jwt_token)])
async def list_replied_emails():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, sender, recipient, subject, body, cc, bcc, replied_at, original_message_id
            FROM replied_emails
            ORDER BY replied_at DESC
        """)
        rows = cur.fetchall()

        emails = []
        for row in rows:
            emails.append({
                "id": row[0],
                "sender": row[1],
                "recipient": row[2],
                "subject": row[3],
                "preview": row[4][:100],
                "cc": row[5],
                "bcc": row[6],
                "time": row[7].strftime("%I:%M %p"),
                "original_message_id": row[8],
                "isRead": False,
                "isStarred": False
            })

        return emails

    except Exception as e:
        print(f"Failed to fetch replied emails: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch replied emails")
    finally:
        cur.close()
        conn.close()
