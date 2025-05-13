# redis_client.py
import redis.asyncio as redis

redis_client = redis.Redis(
    host='localhost',  # Replace with your Redis host
    port=6379,         # Replace with your Redis port
    db=0,
    decode_responses=True
)
