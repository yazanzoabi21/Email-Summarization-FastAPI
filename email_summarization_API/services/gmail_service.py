import base64
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime
import os
from email_summarization_API.database import get_db_connection

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly'
]

# ------------------- Gmail Connection -------------------

def get_gmail_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES
            )
            creds = flow.run_local_server(port=57475)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    service = build('gmail', 'v1', credentials=creds)
    return service

# ------------------- Send Email -------------------

def send_email(to, subject, body, cc=None, bcc=None):
    service = get_gmail_service()

    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    if cc:
        message['cc'] = cc
    if bcc:
        message['bcc'] = bcc

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    message_body = {'raw': raw}

    send_message = service.users().messages().send(userId='me', body=message_body).execute()
    return send_message

# ------------------- Save Sent Email -------------------

def save_sent_email(sender, recipient, subject, body, cc=None, bcc=None, status="sent"):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO sent_emails (sender, recipient, subject, body, cc, bcc, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (sender, recipient, subject, body, cc, bcc, status))

    conn.commit()
    cur.close()
    conn.close()

# ------------------- List (Fetch) Received Emails -------------------

def get_email_read_status(email_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT is_read FROM received_emails WHERE email_id = %s", (email_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else False

def list_emails(max_results=10):
    service = get_gmail_service()
    results = service.users().messages().list(
        userId='me',
        q='-from:me',
        maxResults=max_results,
        fields='messages(id),nextPageToken'
    ).execute()

    messages = results.get('messages', [])
    emails = []

    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        payload = msg.get('payload', {})
        headers = payload.get('headers', [])

        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(No Subject)')
        from_email = next((h['value'] for h in headers if h['name'] == 'From'), '(Unknown Sender)')
        snippet = msg.get('snippet', '')
        internal_date = msg.get('internalDate')
        received_at = datetime.fromtimestamp(int(internal_date) / 1000) if internal_date else None
        thread_id = msg.get('threadId')
        message_id = next((h['value'] for h in headers if h['name'] == 'Message-ID'), None)

        body = get_email_body(payload)

        # ✅ NEW: handle image/file attachments
        attachments = []
        parts = payload.get('parts', [])
        for part in parts:
            filename = part.get('filename')
            mime_type = part.get('mimeType')
            body_data = part.get('body', {})
            attachment_id = body_data.get('attachmentId')

            if filename and attachment_id:
                attachment = service.users().messages().attachments().get(
                    userId='me',
                    messageId=message['id'],
                    id=attachment_id
                ).execute()
                data = attachment.get('data')
                if data:
                    attachments.append({
                        'filename': filename,
                        'mimeType': mime_type,
                        'base64': data
                    })

        # ✅ Final email object
        email_data = {
            'id': message['id'],
            'email_id': message['id'],
            'thread_id': thread_id,
            'message_id': message_id,
            'from': from_email,
            'subject': subject,
            'snippet': snippet,
            'body': body,
            'received_at': received_at.isoformat() if received_at else None,
            'isRead': get_email_read_status(message['id']),
            'attachments': attachments
        }

        # ✅ Save email to database
        save_received_email(
            email_id=message['id'],
            thread_id=thread_id,
            message_id=message_id,
            sender=from_email,
            subject=subject,
            snippet=snippet,
            received_at=received_at
        )

        emails.append(email_data)

    return emails

def get_email_body(payload):
    import base64

    def decode_body(data):
        return base64.urlsafe_b64decode(data).decode('utf-8')

    def find_body(parts):
        html_body = None
        text_body = None

        for part in parts:
            mime_type = part.get('mimeType', '')
            body_data = part.get('body', {}).get('data')

            if mime_type == 'text/html' and body_data:
                html_body = decode_body(body_data)
            elif mime_type == 'text/plain' and body_data:
                text_body = decode_body(body_data)
            elif 'parts' in part:
                result_html, result_text = find_body(part['parts'])
                if result_html and not html_body:
                    html_body = result_html
                if result_text and not text_body:
                    text_body = result_text

        return html_body, text_body

    if 'parts' in payload:
        html_body, text_body = find_body(payload['parts'])
        return html_body or text_body or "No body content found"
    else:
        body_data = payload.get('body', {}).get('data')
        if body_data:
            return decode_body(body_data)
    
    return "No body content found"

# ------------------- Save Received Email -------------------

def save_received_email(email_id, thread_id, message_id, sender, subject, snippet, received_at):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO received_emails (email_id, thread_id, message_id, sender, subject, snippet, received_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (email_id, thread_id, message_id, sender, subject, snippet, received_at))

    conn.commit()
    cur.close()
    conn.close()

# ------------------- Reply to Email -------------------

def reply_email(to, subject, body, thread_id, message_id, cc=None, bcc=None):
    service = get_gmail_service()

    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    message['In-Reply-To'] = message_id
    message['References'] = message_id
    if cc:
        message['cc'] = cc
    if bcc:
        message['bcc'] = bcc

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    message_body = {
        'raw': raw,
        'threadId': thread_id
    }

    send_message = service.users().messages().send(userId='me', body=message_body).execute()
    return send_message

# ------------------- Save Replied Email -------------------

def save_replied_email(sender, recipient, subject, body, original_message_id, cc=None, bcc=None):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO replied_emails (sender, recipient, subject, body, cc, bcc, original_message_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (sender, recipient, subject, body, cc, bcc, original_message_id))

    conn.commit()
    cur.close()
    conn.close()
