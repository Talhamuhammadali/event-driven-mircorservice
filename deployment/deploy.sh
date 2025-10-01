#!/bin/bash
set -e

echo "=========================================="
echo "Minikube Deployment Script"
echo "Event-Driven Microservice with Autoscaling"
echo "=========================================="
echo ""

# Check if minikube is running
if ! minikube status &> /dev/null; then
    echo "❌ Minikube is not running!"
    echo "Start minikube with: minikube start --cpus=4 --memory=4096"
    exit 1
fi

echo "✅ Minikube is running"
echo ""

# Enable metrics-server for HPA
echo "📊 Enabling metrics-server addon..."
minikube addons enable metrics-server
echo ""

# Point Docker CLI to minikube's Docker daemon
echo "🐳 Configuring Docker to use minikube's daemon..."
eval $(minikube docker-env)
echo ""

# Build images in minikube
echo "🔨 Building Docker images in minikube..."
echo "Building API image..."
docker build -t myapp-api:latest -f ../Dockerfile ..
echo ""
echo "Building Worker image..."
docker build -t myapp-worker:latest -f ../Dockerfile.worker ..
echo ""

# Apply Kubernetes manifests
echo "☸️  Applying Kubernetes manifests..."
kubectl apply -f 00-namespace.yaml
echo "Waiting for namespace to be ready..."
sleep 2

kubectl apply -f 01-redis.yaml
echo "Waiting for Redis to start..."
kubectl wait --for=condition=ready pod -l app=redis -n event-driven-microservice --timeout=120s

kubectl apply -f 02-api.yaml
kubectl apply -f 03-worker.yaml
echo "Waiting for API and Worker to start..."
kubectl wait --for=condition=ready pod -l app=api -n event-driven-microservice --timeout=120s
kubectl wait --for=condition=ready pod -l app=worker -n event-driven-microservice --timeout=120s

kubectl apply -f 04-hpa.yaml
echo ""

# Show status
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""

echo "📦 Pods:"
kubectl get pods -n event-driven-microservice
echo ""

echo "🌐 Services:"
kubectl get svc -n event-driven-microservice
echo ""

echo "📈 HPA Status:"
kubectl get hpa -n event-driven-microservice
echo ""

# Get API URL
MINIKUBE_IP=$(minikube ip)
echo "=========================================="
echo "🚀 Access Points"
echo "=========================================="
echo "API: http://${MINIKUBE_IP}:30000"
echo "Health: http://${MINIKUBE_IP}:30000/heath"
echo "Stream: curl -X POST \"http://${MINIKUBE_IP}:30000/stream?feature_id=test&chat_id=1\""
echo ""
echo "📊 Monitor HPA: watch -n 1 kubectl get hpa -n event-driven-microservice"
echo "📦 Watch Pods: watch -n 1 kubectl get pods -n event-driven-microservice"
echo "📋 Worker Logs: kubectl logs -f -l app=worker -n event-driven-microservice"
echo ""
