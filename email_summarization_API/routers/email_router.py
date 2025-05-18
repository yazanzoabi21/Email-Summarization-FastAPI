from fastapi import APIRouter, Depends, HTTPException, Query, status, Header
from email_summarization_API.schemas.email_schema import EmailSchema, ReplyEmailSchema, EmailReadStatus, EmailStarStatus
from email_summarization_API.services.gmail_service import (
    send_email,
    list_emails,
    reply_email,
    save_sent_email,
    save_replied_email,
    get_gmail_service
)
from email_summarization_API.database import get_db_connection
from jose import jwt, JWTError
from email_summarization_API.services.jwt_service import SECRET_KEY, ALGORITHM
from email_summarization_API.redis_client import redis_client
from fastapi.responses import JSONResponse
import json
from collections import defaultdict
from email_summarization_API.utils.html_utils import strip_html
# import traceback
# import asyncio
# from fastapi import Request
import re

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


def extract_name_and_email(full_string):
    """
    Parse a string like 'Yazan Zoabi <yazanz@example.com>' into ('Yazan Zoabi', 'yazanz@example.com')
    or fallback to ('', 'yazanz@example.com') if no name.
    """
    match = re.match(r'^(.*?)\s*<(.+?)>$', full_string)
    if match:
        name = match.group(1).strip()
        email = match.group(2).strip()
        return name if name else None, email
    return None, full_string.strip()

# ----------------- Send Email -----------------

@router.post("/send", dependencies=[Depends(verify_jwt_token)])
async def send_email_api(email: EmailSchema):
    try:
        # Send the email via Gmail
        result = send_email(
            to=email.recipient,
            subject=email.subject,
            body=email.body,
            cc=email.cc,
            bcc=email.bcc
        )

        thread_id = result.get('threadId')

        # Extract headers to get the real "From" field
        msg_id = result.get("id")
        service = get_gmail_service()
        full_message = service.users().messages().get(userId='me', id=msg_id, format="metadata").execute()
        headers = full_message.get("payload", {}).get("headers", [])

        from_value = next((h["value"] for h in headers if h["name"].lower() == "from"), "zohbiyazan@gmail.com")
        to_value = email.recipient

        sender_name, sender_email = extract_name_and_email(from_value)
        recipient_name, recipient_email = extract_name_and_email(to_value)

        save_sent_email(
            sender=f"{sender_name} <{sender_email}>",
            sender_email=sender_email,
            recipient=f"{recipient_name} <{recipient_email}>",
            recipient_email=recipient_email,
            subject=email.subject,
            body=email.body,
            cc=email.cc,
            bcc=email.bcc,
            status="sent",
            thread_id=thread_id
        )

        await redis_client.set(result['id'], email.recipient, ex=10)
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
            SELECT id, sender, recipient, subject, body, cc, bcc, sent_at, status, is_starred, thread_id
            FROM sent_emails
            ORDER BY sent_at DESC
        """)
        rows = cur.fetchall()

        emails = []
        for row in rows:
            sender_name, sender_email = extract_name_and_email(row[1])
            recipient_name, recipient_email = extract_name_and_email(row[2])

            emails.append({
                "id": row[0],
                "sender": sender_name or '',
                "sender_email": sender_email,
                "recipient": recipient_name or '',
                "recipient_email": recipient_email,
                "subject": row[3],
                "preview": strip_html(row[4]),
                "cc": row[5],
                "bcc": row[6],
                "time": row[7].strftime("%I:%M %p"),
                "date": row[7].strftime("%m/%d/%y"),
                "status": row[8],
                "isStarred": row[9],
                "thread_id": row[10]
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

        # ✅ Strip HTML from snippet and body
        for email in emails:
            if "snippet" in email and email["snippet"]:
                email["snippet"] = strip_html(email["snippet"])
            if "body" in email and email["body"]:
                email["body"] = strip_html(email["body"])

        # ✅ Cache cleaned version
        await redis_client.set("cached_inbox", json.dumps(emails), ex=60)
        return emails

    except Exception as e:
        print(f"Failed to fetch inbox emails: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch inbox emails")

@router.get("/threads", dependencies=[Depends(verify_jwt_token)])
async def list_emails_with_replies():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT email_id, thread_id, message_id, sender, subject, snippet, received_at, is_read, body
            FROM received_emails
            ORDER BY received_at DESC
        """)
        primary_emails = cur.fetchall()

        emails_dict = {}

        for email in primary_emails:
            email_id, thread_id, message_id, sender, subject, snippet, received_at, is_read, body = email

            # ✅ Clean snippet (optional - for preview display)
            clean_snippet = strip_html(snippet)

            cur.execute("""
                SELECT id, sender, recipient, subject, body, replied_at
                FROM replied_emails
                WHERE original_message_id = %s
                ORDER BY replied_at DESC
            """, (message_id,))
            replies = cur.fetchall()

            replies_list = []
            for r in replies:
                replies_list.append({
                    "id": r[0],
                    "sender": r[1],
                    "recipient": r[2],
                    "subject": r[3],
                    "body": strip_html(r[4]),  # ✅ Clean reply body
                    "replied_at": r[5].isoformat() if r[5] else None,
                })

            if email_id not in emails_dict:
                emails_dict[email_id] = {
                    "email_id": email_id,
                    "thread_id": thread_id,
                    "message_id": message_id,
                    "from": sender,
                    "subject": subject,
                    "snippet": clean_snippet,
                    "body": body,  # ✅ include full HTML body
                    "received_at": received_at.isoformat() if received_at else None,
                    "isRead": is_read,
                    "replies": replies_list
                }
            else:
                emails_dict[email_id]["replies"].extend(replies_list)

        emails_with_replies = list(emails_dict.values())
        return emails_with_replies

    except Exception as e:
        print(f"Failed to fetch emails with replies: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch emails with replies")
    finally:
        cur.close()
        conn.close()

@router.get("/threads/{thread_id}", dependencies=[Depends(verify_jwt_token)])
async def get_email_thread(thread_id: str):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Get all emails in the thread (both received and replied)
        cur.execute("""
            WITH RECURSIVE thread_tree AS (
                -- Base case: root emails (no in_reply_to)
                SELECT 
                    r.id,
                    r.email_id,
                    r.thread_id,
                    r.message_id,
                    r.sender,
                    r.subject,
                    r.snippet,
                    r.received_at,
                    r.is_read,
                    r.body,
                    r.in_reply_to,
                    'received' as email_type,
                    1 as depth,
                    ARRAY[r.received_at] as path
                FROM received_emails r
                WHERE r.thread_id = %s AND r.in_reply_to IS NULL
                
                UNION ALL
                
                -- Recursive case: replies to received emails
                SELECT 
                    r.id,
                    r.email_id,
                    r.thread_id,
                    r.message_id,
                    r.sender,
                    r.subject,
                    r.snippet,
                    r.received_at,
                    r.is_read,
                    r.body,
                    r.in_reply_to,
                    'received' as email_type,
                    tt.depth + 1,
                    tt.path || r.received_at
                FROM received_emails r
                JOIN thread_tree tt ON r.in_reply_to = tt.message_id
                WHERE r.thread_id = %s
                
                UNION ALL
                
                -- Include replied emails in the thread
                SELECT 
                    re.id,
                    re.id as email_id,  # Use id since these don't have email_id
                    re.thread_id,
                    NULL as message_id,
                    re.sender,
                    re.subject,
                    re.body as snippet,
                    re.replied_at as received_at,
                    NULL as is_read,
                    re.body,
                    re.original_message_id as in_reply_to,
                    'replied' as email_type,
                    CASE 
                        WHEN tt.depth IS NULL THEN 1
                        ELSE tt.depth + 1
                    END as depth,
                    CASE
                        WHEN tt.path IS NULL THEN ARRAY[re.replied_at]
                        ELSE tt.path || re.replied_at
                    END as path
                FROM replied_emails re
                LEFT JOIN thread_tree tt ON re.original_message_id = tt.message_id
                WHERE re.thread_id = %s
            )
            SELECT * FROM thread_tree
            ORDER BY path ASC;
        """, (thread_id, thread_id, thread_id))

        rows = cur.fetchall()
        
        # Build the email hierarchy
        def build_hierarchy(emails):
            email_map = {}
            root_emails = []
            
            # First pass: create map and initialize replies
            for email in emails:
                email['replies'] = []
                email_map[email['message_id']] = email
                
                # Handle replied emails without message_id
                if email['email_type'] == 'replied' and not email['message_id']:
                    email_map[f"replied_{email['id']}"] = email
            
            # Second pass: build hierarchy
            for email in emails:
                if email['in_reply_to']:
                    parent = email_map.get(email['in_reply_to'])
                    if parent:
                        parent['replies'].append(email)
                        # Sort replies chronologically
                        parent['replies'].sort(key=lambda x: x['received_at'])
                    else:
                        print(f"Warning: no parent found for reply with in_reply_to: {email['in_reply_to']}")
                        root_emails.append(email)
                else:
                    root_emails.append(email)
            
            # Sort root emails chronologically
            root_emails.sort(key=lambda x: x['received_at'])
            return root_emails

        # Format the rows into proper email objects
        emails = []
        for row in rows:
            email = {
                "id": row[0],
                "email_id": row[1],
                "thread_id": row[2],
                "message_id": row[3],
                "sender": row[4],
                "subject": row[5],
                "snippet": row[6],
                "received_at": row[7].isoformat() if row[7] else None,
                "is_read": row[8],
                "body": row[9],
                "in_reply_to": row[10],
                "type": row[11],
                "depth": row[12],
                "replies": []  # Will be populated by build_hierarchy
            }
            emails.append(email)

        # Build the hierarchical structure
        hierarchical_emails = build_hierarchy(emails)

        return {
            "thread_id": thread_id,
            "emails": hierarchical_emails,
            "count": len(emails),
            "depth": max([e.get('depth', 1) for e in emails], default=1)
        }

    except Exception as e:
        print(f"Failed to fetch emails for thread {thread_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch emails for thread: {str(e)}"
        )

    finally:
        cur.close()
        conn.close()

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

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE received_emails
            SET is_read = TRUE
            WHERE email_id = %s
        """, (email.message_id,))
        conn.commit()
        cur.close()
        conn.close()

        await redis_client.delete("cached_emails_with_replies")
        await redis_client.delete("cached_replies")
        await redis_client.delete("cached_inbox")
        await redis_client.set(f"replied:{email.message_id}", "true", ex=10)

        return {"message_id": result['id']}
    except Exception as e:
        print(f"Failed to reply to email: {e}")
        raise HTTPException(status_code=500, detail="Failed to reply to email")

@router.get("/replies", dependencies=[Depends(verify_jwt_token)])
async def list_replied_emails(refresh: bool = Query(default=False)):
    cache_key = "cached_replies"

    try:
        if not refresh:
            cached = await redis_client.get(cache_key)
            if cached:
                return JSONResponse(content=json.loads(cached))

        conn = get_db_connection()
        cur = conn.cursor()

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
                "body": row[4],
                "cc": row[5],
                "bcc": row[6],
                "time": row[7].strftime("%I:%M %p") if row[7] else None,
                "sent_at": row[7].isoformat() if row[7] else None,
                "original_message_id": row[8],
                "isRead": False,
                "isStarred": False
            })

        await redis_client.set(cache_key, json.dumps(emails), ex=3600)

        return emails

    except Exception as e:
        print(f"Failed to fetch replied emails: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch replied emails")

    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
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
async def mark_received_email_as_read(email_id: str, data: EmailReadStatus):
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

        import asyncio
        await redis_client.delete("cached_inbox")
        await redis_client.delete("cached_emails_with_replies")
        await asyncio.sleep(1) 

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
