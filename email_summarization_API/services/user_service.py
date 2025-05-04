import psycopg2
import json
from email_summarization_API.database import get_db_connection

import psycopg2
import json
from email_summarization_API.database import get_db_connection

def add_or_edit_user(user_info: dict, user_id: int = -1):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        user_json = {"Users": [user_info]}
        cur.execute("CALL add_edit_user(%s, %s, NULL, NULL, NULL)", (json.dumps(user_json), user_id))
        conn.commit()
        return {"message": "User inserted/updated successfully!"}
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

def get_users(user_id: int = -1):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        query = f"SELECT get_users(%s);"
        cur.execute(query, (user_id,))
        result = cur.fetchone()
        if result and result[0]:
            return result[0]
        else:
            return []
    except Exception as e:
        raise e
    finally:
        cur.close()
        conn.close()

def check_email_exists(email: str) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT COUNT(*) FROM users WHERE email = %s;", (email,))
        result = cur.fetchone()
        return result[0] > 0
    except Exception as e:
        raise e
    finally:
        cur.close()
        conn.close()

