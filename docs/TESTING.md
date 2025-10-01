# Testing Guide

## Quick Start

### 1. Build and Start Services
```bash
cd /home/talhamuammad/Desktop/Experimental\ files/event-driven-mircorservice

# Build and start all containers
docker-compose up --build -d

# Check all services are running
docker-compose ps
```

Expected output: `api`, `worker`, `redis` all showing "Up"

### 2. Test the Stream Endpoint
```bash
# Test basic stream
curl -X POST "http://localhost:8000/stream?feature_id=test-feature&chat_id=chat-1"

# Test multiple concurrent chats
curl -X POST "http://localhost:8000/stream?feature_id=feature-a&chat_id=chat-1" &
curl -X POST "http://localhost:8000/stream?feature_id=feature-a&chat_id=chat-2" &
curl -X POST "http://localhost:8000/stream?feature_id=feature-b&chat_id=chat-1" &
```

Expected: SSE stream with 20 messages, then `data: [DONE]`

## Monitoring

### Container Logs
```bash
# Watch all services
docker-compose logs -f

# Watch specific service
docker-compose logs -f worker
docker-compose logs -f api

# View last 50 lines
docker-compose logs --tail=50 worker
```

### Redis Streams
```bash
# Access Redis CLI
docker exec -it redis-stack redis-cli

# Inside Redis CLI:
KEYS stream:*                           # List all streams
XLEN stream:test-feature:chat-1        # Stream length
XRANGE stream:test-feature:chat-1 - +  # View all messages
XINFO STREAM stream:test-feature:chat-1 # Stream info

# Exit
exit
```

### RedisInsight (Web UI)
```
Open browser: http://localhost:8001
- Connect to localhost:6379
- View Streams tab
- Monitor real-time data
```

### ARQ Queue
```bash
# Check ARQ job queue
docker exec -it redis-stack redis-cli

# Inside Redis CLI:
KEYS arq:*           # List ARQ keys
LLEN arq:queue      # Queue length
LRANGE arq:queue 0 -1  # View queued jobs
```

### Container Stats
```bash
# Real-time resource usage
docker stats

# Check worker replicas
docker-compose ps worker
```

### Health Checks
```bash
# API health
curl http://localhost:8000/heath

# API info
curl http://localhost:8000/

# Redis health
docker exec redis-stack redis-cli ping
```

## Testing Scenarios

### Test Worker Processing
```bash
# In one terminal, watch worker logs
docker-compose logs -f worker

# In another terminal, trigger a job
curl -X POST "http://localhost:8000/stream?feature_id=debug&chat_id=test-123"
```

You should see:
- Worker logs: Task picked up, processing messages
- Client: SSE stream of 20 messages
- Redis: Stream created and auto-expires after 60s

### Test Auto-Expiry
```bash
# Create a stream
curl -X POST "http://localhost:8000/stream?feature_id=expire-test&chat_id=chat-1"

# Check it exists (within 60 seconds)
docker exec -it redis-stack redis-cli EXISTS stream:expire-test:chat-1

# Wait 60+ seconds, check again
docker exec -it redis-stack redis-cli EXISTS stream:expire-test:chat-1
```

Should return `1` then `0` after expiry.

### Scale Workers
```bash
# Scale to 5 workers
docker-compose up -d --scale worker=5

# Verify
docker-compose ps worker

# Send multiple requests and watch load distribution
for i in {1..10}; do
  curl -X POST "http://localhost:8000/stream?feature_id=load-test&chat_id=chat-$i" &
done
```

### Test Concurrent Features
```bash
# Run automated test script
python tests/test_concurrent.py
```

## Troubleshooting

### Worker Not Processing
```bash
docker-compose logs worker | grep -i error
docker exec arq-worker ps aux  # Check process running
```

### Redis Connection Issues
```bash
docker-compose logs redis
docker exec redis-stack redis-cli ping
```

### API Errors
```bash
docker-compose logs api
curl -v http://localhost:8000/heath
```

### Stream Not Expiring
```bash
# Check TTL on stream
docker exec -it redis-stack redis-cli TTL stream:test:chat-1
```

### Worker Not Picking Up Jobs
```bash
# Check ARQ queue
docker exec -it redis-stack redis-cli LLEN arq:queue

# Restart workers
docker-compose restart worker
```

## Cleanup

### Stop Services
```bash
# Stop all services
docker-compose down

# Remove volumes (Redis data)
docker-compose down -v

# Remove images
docker-compose down --rmi all
```

### Clean Redis Data Only
```bash
# Flush all Redis data
docker exec redis-stack redis-cli FLUSHALL
```

## Performance Testing

### Load Test
```bash
# Install dependencies
pip install requests

# Run load test
python tests/load_test.py --concurrent=10 --features=5
```

### Monitor Resource Usage
```bash
# Watch in real-time
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
```

## Minikube Testing (Kubernetes with Autoscaling)

### Prerequisites
```bash
# Install minikube (if not already installed)
# See: https://minikube.sigs.k8s.io/docs/start/

# Start minikube with sufficient resources
minikube start --cpus=4 --memory=4096

# Verify minikube is running
minikube status
```

### Deploy to Minikube
```bash
cd deployment/

# Run automated deployment script
./deploy.sh

# This script will:
# 1. Enable metrics-server for HPA
# 2. Build Docker images in minikube's daemon
# 3. Apply all Kubernetes manifests
# 4. Wait for pods to be ready
# 5. Display access URLs and monitoring commands
```

### Access the Application
```bash
# Get minikube IP
MINIKUBE_IP=$(minikube ip)

# Test health endpoint
curl http://${MINIKUBE_IP}:30000/heath

# Test streaming endpoint
curl -X POST "http://${MINIKUBE_IP}:30000/stream?feature_id=test&chat_id=1"
```

### Monitor Autoscaling

#### Watch HPA Status
```bash
# Monitor HPA in real-time
kubectl get hpa -n event-driven-microservice -w

# Expected output:
# NAME         REFERENCE           TARGETS         MINPODS   MAXPODS   REPLICAS
# worker-hpa   Deployment/worker   15%/50%, 30%/70%   2         10        2
```

#### Watch Pod Scaling
```bash
# Monitor pods in real-time
kubectl get pods -n event-driven-microservice -w

# You should see worker pods scaling up/down based on load
```

#### View HPA Details
```bash
# Get detailed HPA information
kubectl describe hpa worker-hpa -n event-driven-microservice

# View HPA events (scaling decisions)
kubectl get events -n event-driven-microservice --sort-by='.lastTimestamp' | grep HorizontalPodAutoscaler
```

### Test Autoscaling

#### Generate Load to Trigger Scaling
```bash
# Run autoscaling test (5 minutes, 20 concurrent requests)
python3 tests/autoscale_test.py --concurrent=20 --duration=300

# In another terminal, watch the scaling:
watch -n 1 kubectl get hpa,pods -n event-driven-microservice
```

#### Expected Behavior:
1. **Initial state**: 2 worker replicas (baseline)
2. **Under load**: CPU/Memory increases above 50%/70% thresholds
3. **Scale up**: HPA adds workers (up to max 10 replicas)
4. **Load removed**: After 60s stabilization, HPA scales down

#### Manual Load Test
```bash
# Generate heavy concurrent load
for i in {1..50}; do
  curl -X POST "http://$(minikube ip):30000/stream?feature_id=test&chat_id=$i" &
done

# Watch scaling happen
kubectl get hpa -n event-driven-microservice -w
```

### Monitoring Commands

#### View Worker Logs
```bash
# All workers
kubectl logs -f -l app=worker -n event-driven-microservice

# Specific worker
kubectl logs -f worker-<pod-hash> -n event-driven-microservice

# Previous logs (if crashed)
kubectl logs --previous worker-<pod-hash> -n event-driven-microservice
```

#### View API Logs
```bash
kubectl logs -f -l app=api -n event-driven-microservice
```

#### Check Resource Usage
```bash
# Pod resource consumption
kubectl top pods -n event-driven-microservice

# Node resource usage
kubectl top nodes
```

#### Access Redis
```bash
# Port-forward Redis
kubectl port-forward -n event-driven-microservice svc/redis-service 6379:6379

# In another terminal, access Redis CLI
redis-cli -h localhost -p 6379

# Inside Redis:
KEYS stream:*
XLEN stream:test:1
```

### Troubleshooting Minikube

#### HPA Shows "unknown" for Metrics
```bash
# Check metrics-server is running
kubectl get pods -n kube-system | grep metrics-server

# If not running, enable it
minikube addons enable metrics-server

# Wait 30-60s for metrics to populate
kubectl get hpa -n event-driven-microservice
```

#### Pods Not Starting (ImagePullBackOff)
```bash
# Ensure images were built in minikube's Docker daemon
eval $(minikube docker-env)
docker images | grep myapp

# Rebuild if needed
docker build -t myapp-api:latest -f Dockerfile .
docker build -t myapp-worker:latest -f Dockerfile.worker .
```

#### Can't Access API via NodePort
```bash
# Get minikube IP
minikube ip

# Get service details
kubectl get svc -n event-driven-microservice

# Test connection
curl http://$(minikube ip):30000/heath

# Alternative: Use port-forward
kubectl port-forward -n event-driven-microservice svc/api-service 8000:8000
# Then access at http://localhost:8000
```

#### Workers Not Processing Jobs
```bash
# Check worker logs
kubectl logs -l app=worker -n event-driven-microservice

# Check Redis connection
kubectl exec -it -n event-driven-microservice $(kubectl get pod -l app=redis -n event-driven-microservice -o jsonpath='{.items[0].metadata.name}') -- redis-cli ping

# Restart workers
kubectl rollout restart deployment/worker -n event-driven-microservice
```

### Cleanup Minikube Deployment
```bash
# Delete all resources
kubectl delete namespace event-driven-microservice

# Stop minikube
minikube stop

# Delete minikube cluster (removes everything)
minikube delete
```

---

## Expected Results

### Successful Stream Response
```
data: {"id": "0", "feature_id": "test", "chat_id": "chat-1", ...}
data: {"id": "1", "feature_id": "test", "chat_id": "chat-1", ...}
...
data: {"id": "19", "feature_id": "test", "chat_id": "chat-1", ...}
data: [DONE]
```

### Healthy Service Status
```json
{
  "status": "healthy",
  "feature_id": "default"
}
```
