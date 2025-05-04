from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "mmy_0HLYaqqO7r7h;}M_?ZIEE*=>3H"
ALGORITHM = "HS256" # HMAC (Hash-based Message Authentication Code) using SHA-256 hash function
ACCESS_TOKEN_EXPIRE_MINUTES = (23 * 60) + 55 # 1435 minutes

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
