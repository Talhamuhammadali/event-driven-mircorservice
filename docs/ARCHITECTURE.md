# Event-Driven Microservice Architecture

## Overview
Containerized AI agent system with isolated worker processes, Redis Stream-based message passing, and SSE streaming to clients.

## Components

### 1. FastAPI Service (`api` container)
- **Port**: 8000
- **Role**: HTTP API gateway, task enqueuing, SSE streaming
- **Key Endpoint**: `POST /stream?feature_id=X&chat_id=Y`

### 2. ARQ Worker (`worker` container)
- **Replicas**: 2 (scalable)
- **Role**: Process background tasks, generate messages, write to Redis Streams
- **Task**: `generate_messages(feature_id, chat_id)`

### 3. Redis Stack (`redis` container)
- **Ports**: 6379 (Redis), 8001 (RedisInsight)
- **Purpose**:
  - ARQ task queue
  - Redis Streams for message output
  - Stream auto-expiry: 60 seconds

## Request Flow

```
Client Request
   │
   └─▶ POST /stream?feature_id=X&chat_id=Y
         │
         ├─▶ Check Redis Stream exists: stream:X:Y
         │     │
         │     ├─ NO  ─▶ Enqueue task to ARQ
         │     │          │
         │     │          └─▶ Worker picks up task
         │     │                │
         │     │                └─▶ Generate 20 messages
         │     │                      │
         │     │                      └─▶ Write to stream:X:Y
         │     │
         │     └─ YES ─▶ Stream already exists
         │
         └─▶ Read from stream:X:Y (XREAD blocking)
               │
               └─▶ Stream SSE events to client
                     │
                     └─▶ Complete on [DONE] marker
```

## Message Format

### Redis Stream Entry
```json
{
  "data": {
    "id": "0",
    "feature_id": "customer-support",
    "chat_id": "chat-123",
    "message": "Message 0 from feature customer-support, chat chat-123",
    "timestamp": "2025-10-01T09:00:00.000000",
    "container_id": "worker-abc123",
    "container_feature_id": "worker-default",
    "worker": "arq"
  }
}
```

### SSE Output
```
data: {"id": "0", "feature_id": "customer-support", ...}

data: [DONE]
```

## Key Features

### ✓ Worker Isolation
- Workers run in separate containers
- Scalable via `docker-compose up --scale worker=5`
- Process-level isolation per task

### ✓ Stream-Based Decoupling
- Workers write, API reads independently
- No direct coupling between API and workers
- Redis Streams handle backpressure

### ✓ Auto-Cleanup
- Streams expire after 60 seconds
- No manual cleanup required

### ✓ Concurrency
- Multiple chat sessions per feature
- Stream key: `stream:{feature_id}:{chat_id}`
- Independent processing per chat

## Resource Configuration

### API Service
- CPU: Not limited (PoC)
- Memory: Not limited (PoC)

### Worker Service
- Max concurrent jobs: 10 per worker
- Job timeout: 60 seconds
- Result retention: 60 seconds

### Redis
- Data persistence: Volume-backed
- Memory: Default Redis Stack limits

## Running the System

### Start All Services
```bash
docker-compose up -d
```

### Scale Workers
```bash
docker-compose up -d --scale worker=5
```

### Test Endpoint
```bash
curl -X POST "http://localhost:8000/stream?feature_id=test&chat_id=chat-1"
```

### Monitor Redis Streams
```bash
# Access RedisInsight at http://localhost:8001
# Or use redis-cli
docker exec -it redis-stack redis-cli
> XLEN stream:test:chat-1
> XRANGE stream:test:chat-1 - +
```

### View Logs
```bash
docker-compose logs -f worker
docker-compose logs -f api
```

## Next Steps (K8s Migration)

### 1. Per-Feature Container Isolation
- Dynamic K8s Deployments per `feature_id`
- Label: `app=ai-agent,feature={feature_id}`

### 2. Horizontal Pod Autoscaling
- HPA triggers: CPU > 70%, Memory > 80%
- Min replicas: 1, Max: 5
- Scale down on idle (5 min timeout)

### 3. Feature-Based Routing
- Gateway/Ingress routes by `feature_id`
- Service discovery: `feature-{feature_id}-service`

### 4. Orchestrator
- Lambda-style handler: `orchestrator.py`
- Events: `create`, `delete`, `cleanup`, `list`
- Dynamic deployment creation via kubectl

## File Structure

```
.
├── app/
│   ├── main.py          # FastAPI service
│   └── worker.py        # ARQ worker tasks
├── Dockerfile           # FastAPI container
├── Dockerfile.worker    # Worker container
├── docker-compose.yaml  # Local dev setup
├── requirements-minimal.txt
└── ARCHITECTURE.md      # This file
```

## Dependencies

- `fastapi==0.104.1` - Web framework
- `uvicorn[standard]==0.24.0` - ASGI server
- `arq==0.25.0` - Async task queue
- `redis==5.0.1` - Redis client

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FEATURE_ID` | `default` | Container feature identifier |
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
