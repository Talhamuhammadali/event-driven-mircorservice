"""
ARQ Worker for generating messages and writing to Redis Streams
"""
import asyncio
import json
import os
from datetime import datetime
from redis.asyncio import Redis
from arq.connections import RedisSettings


async def generate_messages(ctx, feature_id: str, chat_id: str):
    """
    Worker task: Generate 20 messages and write to Redis Stream

    Args:
        ctx: ARQ context (contains redis connection)
        feature_id: Feature identifier
        chat_id: Chat session identifier
    """
    # Get Redis connection from context
    redis: Redis = ctx['redis_stream']
    stream_key = f"stream:{feature_id}:{chat_id}"

    container_id = os.getenv("HOSTNAME", "unknown")
    container_feature_id = os.getenv("FEATURE_ID", "default")

    try:
        for i in range(20):
            message = {
                "id": str(i),
                "feature_id": feature_id,
                "chat_id": chat_id,
                "message": f"Message {i} from feature {feature_id}, chat {chat_id}",
                "timestamp": datetime.now().isoformat(),
                "container_id": container_id,
                "container_feature_id": container_feature_id,
                "worker": "arq"
            }

            # Write to Redis Stream
            await redis.xadd(stream_key, {"data": json.dumps(message)})
            await asyncio.sleep(1)  # 1 second delay between messages

        # Write completion marker
        done_message = {"data": "[DONE]"}
        await redis.xadd(stream_key, done_message)

        # Set expiry on stream (60 seconds)
        await redis.expire(stream_key, 60)

        return f"Generated 20 messages for {feature_id}:{chat_id}"

    except Exception as e:
        # Log error and write error message to stream
        error_message = {
            "data": json.dumps({
                "error": str(e),
                "feature_id": feature_id,
                "chat_id": chat_id
            })
        }
        await redis.xadd(stream_key, error_message)
        raise


async def startup(ctx):
    """
    Startup hook - Initialize Redis Stream connection
    """
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))

    ctx['redis_stream'] = Redis(host=redis_host, port=redis_port, decode_responses=False)


async def shutdown(ctx):
    """
    Shutdown hook - Close Redis connection
    """
    await ctx['redis_stream'].close()


class WorkerSettings:
    """ARQ Worker Configuration"""

    # Redis connection for task queue
    redis_settings = RedisSettings(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379"))
    )

    # Worker functions
    functions = [generate_messages]

    # Worker lifecycle hooks
    on_startup = startup
    on_shutdown = shutdown

    # Worker configuration
    max_jobs = 10  # Max concurrent jobs per worker
    keep_result = 30  # Keep job results for 60 seconds