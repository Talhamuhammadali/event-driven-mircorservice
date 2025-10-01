#!/usr/bin/env python3
"""
Autoscaling test script for Kubernetes/Minikube
Generates sustained load to trigger HPA worker scaling
"""
import requests
import time
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event

stop_event = Event()


def stream_request(api_url: str, request_id: int):
    """
    Execute a single streaming request
    Runs continuously until stopped
    """
    feature_id = f"feature-{request_id % 5}"
    chat_id = f"chat-{request_id}"
    url = f"{api_url}/stream?feature_id={feature_id}&chat_id={chat_id}"

    while not stop_event.is_set():
        try:
            response = requests.post(url, stream=True, timeout=90)

            # Consume the stream
            for line in response.iter_lines():
                if stop_event.is_set():
                    break
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == "[DONE]":
                            break

            print(f"Request {request_id}: Stream completed")

        except Exception as e:
            print(f"Request {request_id}: Error - {e}")
            time.sleep(1)  # Brief pause before retry


def run_sustained_load(api_url: str, concurrent: int, duration: int):
    """
    Run sustained load for specified duration
    """
    print("\n" + "="*70)
    print("AUTOSCALING LOAD TEST")
    print("="*70)
    print(f"API URL: {api_url}")
    print(f"Concurrent requests: {concurrent}")
    print(f"Test duration: {duration} seconds")
    print("="*70 + "\n")

    print("Starting load generation...")
    print("Monitor with: kubectl get hpa -n event-driven-microservice -w")
    print("Watch pods with: kubectl get pods -n event-driven-microservice -w")
    print("\nPress Ctrl+C to stop early\n")

    start_time = time.time()

    try:
        with ThreadPoolExecutor(max_workers=concurrent) as executor:
            # Submit all concurrent tasks
            futures = [
                executor.submit(stream_request, api_url, i)
                for i in range(concurrent)
            ]

            # Monitor progress
            while time.time() - start_time < duration:
                elapsed = time.time() - start_time
                remaining = duration - elapsed
                print(f"\r⏱️  Elapsed: {elapsed:.0f}s / {duration}s | Remaining: {remaining:.0f}s", end="")
                time.sleep(5)

            print("\n\n✓ Test duration reached. Stopping load generation...\n")
            stop_event.set()

            # Wait for threads to finish
            time.sleep(2)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Stopping load generation...\n")
        stop_event.set()

    total_time = time.time() - start_time

    print("="*70)
    print("TEST COMPLETE")
    print("="*70)
    print(f"Total runtime: {total_time:.1f}s")
    print("\n📊 Check scaling results:")
    print("  kubectl get hpa -n event-driven-microservice")
    print("  kubectl get pods -n event-driven-microservice")
    print("\n📋 View worker logs:")
    print("  kubectl logs -l app=worker -n event-driven-microservice --tail=50")
    print("\n📈 View HPA events:")
    print("  kubectl describe hpa worker-hpa -n event-driven-microservice")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Autoscaling test for Kubernetes deployment"
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default=None,
        help="API URL (default: auto-detect from minikube)"
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=20,
        help="Number of concurrent requests (default: 20)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Test duration in seconds (default: 300)"
    )

    args = parser.parse_args()

    # Auto-detect API URL if not provided
    api_url = args.api_url
    if not api_url:
        try:
            import subprocess
            minikube_ip = subprocess.check_output(
                ["minikube", "ip"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            api_url = f"http://{minikube_ip}:30000"
            print(f"Auto-detected API URL: {api_url}")
        except Exception:
            print("❌ Could not auto-detect minikube IP")
            print("Please provide --api-url or ensure minikube is running")
            sys.exit(1)

    # Check API availability
    try:
        response = requests.get(f"{api_url}/heath", timeout=5)
        print(f"✓ API is healthy: {response.json()}\n")
    except Exception as e:
        print(f"❌ API is not available at {api_url}")
        print(f"Error: {e}\n")
        sys.exit(1)

    # Run sustained load test
    run_sustained_load(api_url, args.concurrent, args.duration)


if __name__ == "__main__":
    main()
