from pydantic import BaseModel

class UserInfo(BaseModel):
    email: str
    password: str
    full_name: str

class LoginRequest(BaseModel):
    email: str
    password: str

class EmailRequest(BaseModel):
    email: str