# Event-Driven Microservice Prototype Makefile

.PHONY: run stop

# Variables
IMAGE_NAME := ai-service-prototype
CONTAINER_NAME := ai-service-container
PORT := 8000
FEATURE_ID := default

# Build and run the container
run:
	@echo "Building and running container..."
	docker build -t $(IMAGE_NAME) .
	docker run --rm -p $(PORT):8000 -e FEATURE_ID=$(FEATURE_ID) --name $(CONTAINER_NAME) $(IMAGE_NAME)

# Stop running container
stop:
	@echo "Stopping container..."
	@docker stop $(CONTAINER_NAME) 2>/dev/null || echo "Container not running"