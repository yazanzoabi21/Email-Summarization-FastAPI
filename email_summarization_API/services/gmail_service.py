import base64
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime
import os

from email_summarization_API.database import get_db_connection

# Gmail API Scopes
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

def list_emails(max_results=20):
    service = get_gmail_service()
    results = service.users().messages().list(userId='me', q='-from:me', maxResults=max_results).execute()
    messages = results.get('messages', [])

    emails = []
    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        payload = msg.get('payload', {})
        headers = payload.get('headers', [])

        subject = next((header['value'] for header in headers if header['name'] == 'Subject'), '(No Subject)')
        from_email = next((header['value'] for header in headers if header['name'] == 'From'), '(Unknown Sender)')
        snippet = msg.get('snippet', '')

        internal_date = msg.get('internalDate')
        if internal_date:
            timestamp = int(internal_date) / 1000
            time = datetime.fromtimestamp(timestamp).strftime("%I:%M %p")
        else:
            time = "-"

        thread_id = msg.get('threadId')
        message_id = next((header['value'] for header in headers if header['name'] == 'Message-ID'), None)

        email_data = {
            'id': message['id'],
            'thread_id': thread_id,
            'message_id': message_id,
            'from': from_email,
            'subject': subject,
            'snippet': snippet,
            'time': time
        }

        # Save into database
        save_received_email(
            email_id=message['id'],
            thread_id=thread_id,
            message_id=message_id,
            sender=from_email,
            subject=subject,
            snippet=snippet
        )

        emails.append(email_data)

    return emails

# ------------------- Save Received Email -------------------

def save_received_email(email_id, thread_id, message_id, sender, subject, snippet):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO received_emails (email_id, thread_id, message_id, sender, subject, snippet)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (email_id, thread_id, message_id, sender, subject, snippet))

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
