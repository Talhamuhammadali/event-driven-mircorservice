#!/usr/bin/env python3
"""
Load testing script for event-driven microservice
Tests system behavior under concurrent load
"""
import requests
import time
import json
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List
import sys
from collections import defaultdict

API_URL = "http://localhost:8000"


class LoadTester:
    def __init__(self, concurrent: int, features: int):
        self.concurrent = concurrent
        self.features = features
        self.results = []

    def stream_request(self, feature_id: str, chat_id: str) -> Dict:
        """Execute a single streaming request"""
        url = f"{API_URL}/stream?feature_id={feature_id}&chat_id={chat_id}"

        start_time = time.time()
        message_count = 0
        first_byte_time = None
        last_byte_time = None

        try:
            response = requests.post(url, stream=True, timeout=90)

            if response.status_code != 200:
                return {
                    "success": False,
                    "feature_id": feature_id,
                    "chat_id": chat_id,
                    "error": f"HTTP {response.status_code}",
                    "duration": time.time() - start_time
                }

            for line in response.iter_lines():
                if line:
                    if first_byte_time is None:
                        first_byte_time = time.time()

                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]

                        if data == "[DONE]":
                            last_byte_time = time.time()
                            break

                        try:
                            json.loads(data)
                            message_count += 1
                        except json.JSONDecodeError:
                            pass

            duration = time.time() - start_time
            ttfb = first_byte_time - start_time if first_byte_time else 0
            streaming_time = last_byte_time - first_byte_time if last_byte_time and first_byte_time else 0

            return {
                "success": True,
                "feature_id": feature_id,
                "chat_id": chat_id,
                "message_count": message_count,
                "duration": duration,
                "ttfb": ttfb,  # Time to first byte
                "streaming_time": streaming_time
            }

        except Exception as e:
            return {
                "success": False,
                "feature_id": feature_id,
                "chat_id": chat_id,
                "error": str(e),
                "duration": time.time() - start_time
            }

    def run_load_test(self):
        """Execute load test with specified parameters"""
        print("\n" + "="*70)
        print("LOAD TEST CONFIGURATION")
        print("="*70)
        print(f"Concurrent requests: {self.concurrent}")
        print(f"Number of features: {self.features}")
        print(f"Total requests: {self.concurrent}")
        print("="*70 + "\n")

        # Generate tasks
        tasks = []
        for i in range(self.concurrent):
            feature_id = f"feature-{i % self.features}"
            chat_id = f"chat-{i}"
            tasks.append((feature_id, chat_id))

        print(f"Starting {len(tasks)} concurrent requests...\n")

        # Execute
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.concurrent) as executor:
            futures = {
                executor.submit(self.stream_request, fid, cid): (fid, cid)
                for fid, cid in tasks
            }

            completed = 0
            for future in as_completed(futures):
                result = future.result()
                self.results.append(result)
                completed += 1

                if completed % 10 == 0 or completed == len(tasks):
                    elapsed = time.time() - start_time
                    print(f"Progress: {completed}/{len(tasks)} ({elapsed:.1f}s)")

        total_duration = time.time() - start_time

        print(f"\n✓ All requests completed in {total_duration:.2f}s\n")

        self.print_results(total_duration)

    def print_results(self, total_duration: float):
        """Print detailed results"""
        print("="*70)
        print("LOAD TEST RESULTS")
        print("="*70 + "\n")

        successful = [r for r in self.results if r["success"]]
        failed = [r for r in self.results if not r["success"]]

        # Success rate
        success_rate = len(successful) / len(self.results) * 100 if self.results else 0
        print(f"Success Rate: {len(successful)}/{len(self.results)} ({success_rate:.1f}%)")

        if failed:
            print(f"\nFailed Requests: {len(failed)}")
            error_types = defaultdict(int)
            for r in failed:
                error = r.get("error", "Unknown")
                error_types[error] += 1

            print("\nError Breakdown:")
            for error, count in error_types.items():
                print(f"  - {error}: {count}")

        if not successful:
            print("\n✗ No successful requests to analyze")
            return

        # Performance metrics
        durations = [r["duration"] for r in successful]
        ttfbs = [r["ttfb"] for r in successful]
        message_counts = [r["message_count"] for r in successful]
        streaming_times = [r["streaming_time"] for r in successful]

        print("\n" + "-"*70)
        print("PERFORMANCE METRICS")
        print("-"*70)

        print(f"\nTotal Duration: {total_duration:.2f}s")
        print(f"Requests per second: {len(self.results) / total_duration:.2f}")

        print(f"\nRequest Duration:")
        print(f"  Min:     {min(durations):.2f}s")
        print(f"  Max:     {max(durations):.2f}s")
        print(f"  Average: {sum(durations) / len(durations):.2f}s")

        print(f"\nTime to First Byte (TTFB):")
        print(f"  Min:     {min(ttfbs):.3f}s")
        print(f"  Max:     {max(ttfbs):.3f}s")
        print(f"  Average: {sum(ttfbs) / len(ttfbs):.3f}s")

        print(f"\nStreaming Time:")
        print(f"  Min:     {min(streaming_times):.2f}s")
        print(f"  Max:     {max(streaming_times):.2f}s")
        print(f"  Average: {sum(streaming_times) / len(streaming_times):.2f}s")

        print(f"\nMessages Received:")
        print(f"  Total:   {sum(message_counts)}")
        print(f"  Average: {sum(message_counts) / len(message_counts):.1f} per request")

        # Per-feature breakdown
        if self.features > 1:
            print("\n" + "-"*70)
            print("PER-FEATURE BREAKDOWN")
            print("-"*70)

            by_feature = defaultdict(list)
            for r in successful:
                by_feature[r["feature_id"]].append(r)

            for feature_id in sorted(by_feature.keys()):
                results = by_feature[feature_id]
                avg_duration = sum(r["duration"] for r in results) / len(results)
                print(f"\n{feature_id}:")
                print(f"  Requests: {len(results)}")
                print(f"  Avg Duration: {avg_duration:.2f}s")

        # Percentiles
        sorted_durations = sorted(durations)
        p50 = sorted_durations[len(sorted_durations) // 2]
        p95 = sorted_durations[int(len(sorted_durations) * 0.95)]
        p99 = sorted_durations[int(len(sorted_durations) * 0.99)]

        print("\n" + "-"*70)
        print("LATENCY PERCENTILES")
        print("-"*70)
        print(f"P50: {p50:.2f}s")
        print(f"P95: {p95:.2f}s")
        print(f"P99: {p99:.2f}s")

        print("\n" + "="*70)


def main():
    parser = argparse.ArgumentParser(
        description="Load test for event-driven microservice"
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=10,
        help="Number of concurrent requests (default: 10)"
    )
    parser.add_argument(
        "--features",
        type=int,
        default=3,
        help="Number of different features to test (default: 3)"
    )

    args = parser.parse_args()

    # Check API availability
    try:
        response = requests.get(f"{API_URL}/heath", timeout=5)
        print(f"\n✓ API is healthy: {response.json()}")
    except Exception as e:
        print(f"\n✗ API is not available: {e}")
        print("Make sure services are running: docker-compose up -d")
        sys.exit(1)

    # Run load test
    tester = LoadTester(concurrent=args.concurrent, features=args.features)
    tester.run_load_test()


if __name__ == "__main__":
    main()
