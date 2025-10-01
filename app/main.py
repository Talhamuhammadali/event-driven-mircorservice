from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio
import json
import os
from datetime import datetime
from redis.asyncio import Redis
from arq import create_pool
from arq.connections import RedisSettings
from typing import AsyncGenerator

FEATURE_ID = os.getenv("FEATURE_ID", "default")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Async lifespan for startup/shutdown"""
    # Startup
    redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)
    arq_pool = await create_pool(RedisSettings(host=REDIS_HOST, port=REDIS_PORT))

    app.state.redis = redis_client
    app.state.arq = arq_pool

    yield

    # Shutdown
    await redis_client.close()
    await arq_pool.close()


app = FastAPI(title="AI Service Prototype", version="1.0.0", lifespan=lifespan)

@app.get("/")
async def info():
    return {"info": "Test API for Event driven arch"}

@app.get("/heath")
async def health():
    return {"status": "healthy", "feature_id": FEATURE_ID}

@app.post("/stream")
async def stream_messages(feature_id: str, chat_id: str):
    """
    Stream messages from Redis Stream
    Enqueues worker task if stream doesn't exist yet
    """
    redis_client: Redis = app.state.redis
    arq_pool = app.state.arq
    stream_key = f"stream:{feature_id}:{chat_id}"

    # Check if stream exists
    stream_exists = await redis_client.exists(stream_key)

    if not stream_exists:
        # Enqueue worker task to generate messages
        await arq_pool.enqueue_job('generate_messages', feature_id, chat_id)

    async def generate():
        last_id = "0-0"  # Start from beginning
        retries = 0
        max_retries = 30  # 30 seconds max wait for first message

        while True:
            # Read from Redis Stream (blocking with timeout)
            messages = await redis_client.xread({stream_key: last_id}, count=1, block=1000)

            if messages:
                # messages format: [(stream_key, [(message_id, {field: value})])]
                for stream, entries in messages:
                    for message_id, data in entries:
                        last_id = message_id.decode() if isinstance(message_id, bytes) else message_id

                        # Extract message data
                        msg_data = data.get(b"data") or data.get("data")
                        if isinstance(msg_data, bytes):
                            msg_data = msg_data.decode()

                        # Check for completion
                        if msg_data == "[DONE]":
                            yield "data: [DONE]\n\n"
                            return

                        # Yield SSE formatted message
                        yield f"data: {msg_data}\n\n"
                        retries = 0  # Reset retry counter on successful read

            else:
                # No messages yet, check if we should keep waiting
                retries += 1
                if retries > max_retries:
                    yield f'data: {{"error": "Timeout waiting for messages"}}\n\n'
                    return

                # Continue waiting
                await asyncio.sleep(0.1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)