# from fastapi import APIRouter, Depends, HTTPException, Query, status, Header
# from email_summarization_API.schemas.email_schema import EmailSchema, ReplyEmailSchema, EmailReadStatus, EmailStarStatus
# from email_summarization_API.services.gmail_service import (
#     send_email,
#     list_emails,
#     reply_email,
#     save_sent_email,
#     save_replied_email
# )
# from email_summarization_API.database import get_db_connection
# from jose import jwt, JWTError
# from email_summarization_API.services.jwt_service import SECRET_KEY, ALGORITHM
# from email_summarization_API.redis_client import redis_client
# from fastapi.responses import JSONResponse
# import json
# import traceback

# router = APIRouter(
#     prefix="/email",
#     tags=["Email"],
# )

# def verify_jwt_token(authorization: str = Header(...)):
#     if not authorization.startswith("Bearer "):
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")

#     token = authorization.split(" ")[1]

#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#     except JWTError:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


# # ----------------- Send Email -----------------

# @router.post("/send", dependencies=[Depends(verify_jwt_token)])
# async def send_email_api(email: EmailSchema):
#     try:
#         result = send_email(
#             to=email.recipient,
#             subject=email.subject,
#             body=email.body,
#             cc=email.cc,
#             bcc=email.bcc
#         )

#         save_sent_email(
#             sender="zohbiyazan@gmail.com",
#             recipient=email.recipient,
#             subject=email.subject,
#             body=email.body,
#             cc=email.cc,
#             bcc=email.bcc,
#             status="sent"
#         )
#         await redis_client.set(result['id'], email.recipient, ex=60)
#         return {"message_id": result['id']}
#     except Exception as e:
#         print(f"Failed to send email: {e}")
#         raise HTTPException(status_code=500, detail="Failed to send email")
    
# # ----------------- Get From Redis -----------------

# @router.get("/get_redis")
# async def get_value(key: str = Query(default=None)):
#     values = {}

#     if key:
#         value = await redis_client.get(key)
#         if value is None:
#             return {"message": f"Key '{key}' not found in Redis"}
#         return {"key": key, "value": value}
    
#     # No key provided: return all keys and values
#     keys = await redis_client.keys("*")
#     for k in keys:
#         val = await redis_client.get(k)
#         values[k] = val

#     return {"all_keys": values}

# # ----------------- List Sent Emails -----------------

# @router.get("/list", dependencies=[Depends(verify_jwt_token)])
# async def list_sent_emails():
#     conn = get_db_connection()
#     cur = conn.cursor()

#     try:
#         cur.execute("""
#             SELECT id, sender, recipient, subject, body, cc, bcc, sent_at, status, is_read, is_starred
#             FROM sent_emails
#             ORDER BY sent_at DESC
#         """)
#         rows = cur.fetchall()

#         emails = []
#         for row in rows:
#             emails.append({
#                 "id": row[0],
#                 "sender": row[1],
#                 "recipient": row[2],
#                 "subject": row[3],
#                 "preview": row[4][:100],
#                 "cc": row[5],
#                 "bcc": row[6],
#                 "time": row[7].strftime("%I:%M %p"),
#                 "status": row[8],
#                 "isRead": row[9],
#                 "isStarred": row[10]
#             })

#         return emails

#     except Exception as e:
#         print(f"Failed to fetch sent emails: {e}")
#         raise HTTPException(status_code=500, detail="Failed to fetch sent emails")
#     finally:
#         cur.close()
#         conn.close()

# # ----------------- List Received Emails -----------------

# # @router.get("/receive", dependencies=[Depends(verify_jwt_token)])
# # async def list_received_emails():
# #     try:
# #         cached = await redis_client.get("cached_inbox")
# #         if cached:
# #             return JSONResponse(content=json.loads(cached))
        
# #         emails = list_emails()
# #         for email in emails:
# #             if not email.get("body"):
# #                 email["body"] = email["snippet"]

# #         await redis_client.set("cached_inbox", json.dumps(emails), ex=60)
# #         return emails
# #     except Exception as e:
# #         print(f"Failed to fetch inbox emails: {e}")
# #         raise HTTPException(status_code=500, detail="Failed to fetch inbox emails")

# @router.get("/receive", dependencies=[Depends(verify_jwt_token)])
# async def list_received_emails():
#     conn = get_db_connection()
#     cur = conn.cursor()

#     try:
#         cur.execute("""
#             SELECT id, email_id, thread_id, message_id, sender, subject, snippet, received_at, is_read, body
#             FROM received_emails
#             ORDER BY received_at DESC
#         """)
#         rows = cur.fetchall()

#         emails = []
#         for row in rows:
#             emails.append({
#                 "id": row[0],
#                 "email_id": row[1],
#                 "thread_id": row[2],
#                 "message_id": row[3],
#                 "from": row[4],
#                 "subject": row[5],
#                 "snippet": row[6],
#                 "received_at": row[7],
#                 "time": row[7].strftime("%I:%M %p") if row[7] else None,
#                 "isRead": row[8],
#                 "body": row[9]
#             })

#         return emails

#     except Exception as e:
#         print(f"Failed to fetch received emails: {e}")
#         raise HTTPException(status_code=500, detail="Failed to fetch received emails")
#     finally:
#         cur.close()
#         conn.close()

# # ----------------- Reply to Email -----------------

# @router.post("/reply", dependencies=[Depends(verify_jwt_token)])
# async def reply_to_email_api(email: ReplyEmailSchema):
#     try:
#         result = reply_email(
#             to=email.recipient,
#             subject=email.subject,
#             body=email.body,
#             thread_id=email.thread_id,
#             message_id=email.message_id
#         )

#         save_replied_email(
#             sender="zohbiyazan@gmail.com",
#             recipient=email.recipient,
#             subject=email.subject,
#             body=email.body,
#             original_message_id=email.message_id
#         )

#         await redis_client.set(f"replied:{email.message_id}", "true", ex=60)

#         return {"message_id": result['id']}
#     except Exception as e:
#         print(f"Failed to reply to email: {e}")
#         raise HTTPException(status_code=500, detail="Failed to reply to email")

# # ----------------- List Replied Emails -----------------

# @router.get("/replies", dependencies=[Depends(verify_jwt_token)])
# async def list_replied_emails():
#     conn = get_db_connection()
#     cur = conn.cursor()

#     try:
#         cur.execute("""
#             SELECT id, sender, recipient, subject, body, cc, bcc, replied_at, original_message_id
#             FROM replied_emails
#             ORDER BY replied_at DESC
#         """)
#         rows = cur.fetchall()

#         emails = []
#         for row in rows:
#             emails.append({
#                 "id": row[0],
#                 "sender": row[1],
#                 "recipient": row[2],
#                 "subject": row[3],
#                 "preview": row[4][:100],
#                 "cc": row[5],
#                 "bcc": row[6],
#                 "time": row[7].strftime("%I:%M %p"),
#                 "original_message_id": row[8],
#                 "isRead": False,
#                 "isStarred": False
#             })

#         return emails

#     except Exception as e:
#         print(f"Failed to fetch replied emails: {e}")
#         raise HTTPException(status_code=500, detail="Failed to fetch replied emails")
#     finally:
#         cur.close()
#         conn.close()

# # ----------------- Mark Email as Read/Unread -----------------
# @router.put("/mark-as-read/{email_id}", dependencies=[Depends(verify_jwt_token)])
# def mark_as_read(email_id: int, data: EmailReadStatus):
#     conn = get_db_connection()
#     cur = conn.cursor()

#     try:
#         cur.execute("""
#             UPDATE sent_emails
#             SET is_read = %s
#             WHERE id = %s
#         """, (data.is_read, email_id))

#         if cur.rowcount == 0:
#             raise HTTPException(status_code=404, detail="Email not found")

#         conn.commit()
#         return {"message": f"Email marked as {'read' if data.is_read else 'unread'}"}

#     except Exception as e:
#         print(f"Error updating email read status: {e}")
#         raise HTTPException(status_code=500, detail="Internal server error")

#     finally:
#         cur.close()
#         conn.close()

# @router.put("/receive/mark-as-read/{email_id}", dependencies=[Depends(verify_jwt_token)])
# async def mark_received_email_as_read(email_id: str, data: EmailReadStatus):
#     conn = get_db_connection()
#     cur = conn.cursor()

#     try:
#         cur.execute("""
#             UPDATE received_emails
#             SET is_read = %s
#             WHERE email_id = %s
#         """, (data.is_read, email_id))

#         if cur.rowcount == 0:
#             raise HTTPException(status_code=404, detail="Received email not found")

#         conn.commit()
#         await redis_client.delete("cached_inbox")

#         return {"message": f"Received email marked as {'read' if data.is_read else 'unread'}"}

#     except Exception as e:
#         import traceback; traceback.print_exc()
#         raise HTTPException(status_code=500, detail="Internal server error")

#     finally:
#         cur.close()
#         conn.close()

# @router.get("/starred", dependencies=[Depends(verify_jwt_token)])
# def get_starred_emails():
#     conn = get_db_connection()
#     cur = conn.cursor()
#     try:
#         cur.execute("""
#             SELECT id, sender, recipient, subject, body, cc, bcc, sent_at, status, is_read, is_starred
#             FROM sent_emails
#             WHERE is_starred = TRUE
#             ORDER BY sent_at DESC
#         """)
#         rows = cur.fetchall()

#         emails = []
#         for row in rows:
#             emails.append({
#                 "id": row[0],
#                 "sender": row[1],
#                 "recipient": row[2],
#                 "subject": row[3],
#                 "preview": row[4][:100],
#                 "cc": row[5],
#                 "bcc": row[6],
#                 "time": row[7].strftime("%I:%M %p"),
#                 "status": row[8],
#                 "isRead": row[9],
#                 "isStarred": row[10]
#             })

#         return emails

#     except Exception as e:
#         print(f"Failed to fetch starred emails: {e}")
#         raise HTTPException(status_code=500, detail="Failed to fetch starred emails")
#     finally:
#         cur.close()
#         conn.close()

from fastapi import APIRouter, Depends, HTTPException, Query, status, Header
from email_summarization_API.schemas.email_schema import EmailSchema, ReplyEmailSchema, EmailReadStatus, EmailStarStatus
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
from email_summarization_API.redis_client import redis_client
from fastapi.responses import JSONResponse
import json
import traceback

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
        await redis_client.set(result['id'], email.recipient, ex=60)
        return {"message_id": result['id']}
    except Exception as e:
        print(f"Failed to send email: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")
    
# ----------------- Get From Redis -----------------

@router.get("/get_redis")
async def get_value(key: str = Query(default=None)):
    values = {}

    if key:
        value = await redis_client.get(key)
        if value is None:
            return {"message": f"Key '{key}' not found in Redis"}
        return {"key": key, "value": value}
    
    # No key provided: return all keys and values
    keys = await redis_client.keys("*")
    for k in keys:
        val = await redis_client.get(k)
        values[k] = val

    return {"all_keys": values}

# ----------------- List Sent Emails -----------------

@router.get("/list", dependencies=[Depends(verify_jwt_token)])
async def list_sent_emails():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, sender, recipient, subject, body, cc, bcc, sent_at, status, is_read, is_starred
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
                "isRead": row[9],
                "isStarred": row[10]
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
        cached = await redis_client.get("cached_inbox")
        if cached:
            return JSONResponse(content=json.loads(cached))
        
        emails = list_emails()
        await redis_client.set("cached_inbox", json.dumps(emails), ex=60)
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

        await redis_client.set(f"replied:{email.message_id}", "true", ex=60)

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

# ----------------- Mark Email as Read/Unread -----------------
@router.put("/mark-as-read/{email_id}", dependencies=[Depends(verify_jwt_token)])
def mark_as_read(email_id: int, data: EmailReadStatus):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE sent_emails
            SET is_read = %s
            WHERE id = %s
        """, (data.is_read, email_id))

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Email not found")

        conn.commit()
        return {"message": f"Email marked as {'read' if data.is_read else 'unread'}"}

    except Exception as e:
        print(f"Error updating email read status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        cur.close()
        conn.close()

@router.put("/receive/mark-as-read/{email_id}", dependencies=[Depends(verify_jwt_token)])
def mark_received_email_as_read(email_id: str, data: EmailReadStatus):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE received_emails
            SET is_read = %s
            WHERE email_id = %s
        """, (data.is_read, email_id))

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Received email not found")

        conn.commit()
        return {"message": f"Received email marked as {'read' if data.is_read else 'unread'}"}

    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        cur.close()
        conn.close()

@router.put("/starred/{email_id}", dependencies=[Depends(verify_jwt_token)])
def toggle_starred_email(email_id: int, data: EmailStarStatus):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE sent_emails
            SET is_starred = %s
            WHERE id = %s
        """, (data.is_starred, email_id))

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Email not found")

        conn.commit()
        return {"message": f"Email {'starred' if data.is_starred else 'unstarred'} successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update star status")

    finally:
        cur.close()
        conn.close()
