from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from email_summarization_API.routers import email_router, user_router

app = FastAPI(
    title="Email Summarization API",
    description="API for managing cool things.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router.router)
app.include_router(email_router.router)

@app.get("/")
async def root():
    return {"message": "Welcome to the Email Summarization API!"}
