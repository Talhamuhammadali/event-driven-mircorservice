from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio
import json
import os
from datetime import datetime

app = FastAPI(title="AI Service Prototype", version="1.0.0")

FEATURE_ID = os.getenv("FEATURE_ID", "default")

@app.get("/")
async def info():
    return {"info": "Test API for Event driven arch"}

@app.get("/heath")
async def health():
    return {"status": "healthy", "feature_id": FEATURE_ID}

@app.get("/stream")
async def stream_messages():
    async def generate():
        for i in range(20):  # Simulate 20 messages
            message = {
                "id": i,
                "feature_id": FEATURE_ID,
                "message": f"Message {i} from feature {FEATURE_ID}",
                "timestamp": datetime.now().isoformat(),
                "container_id": os.getenv("HOSTNAME", "unknown")
            }
            yield f"data: {json.dumps(message)}\n\n"
            await asyncio.sleep(1)  # 1 second delay between messages

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)