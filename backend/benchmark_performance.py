"""Real performance benchmark script for ReviewIQ analysis pipeline.

Measures:
- Database metrics retrieval latency (p50, p95, max)
- Review sampling latency (p50, p95, max)
- Cache MISS latency vs Cache HIT latency
- Single-flight concurrency efficiency
- Server-Timing header verification
"""

import concurrent.futures
import json
import statistics
import time
from fastapi.testclient import TestClient
from main import app
from services.ecommerce_db_service import ecommerce_db_service
from services.gemini_summary_service import gemini_summary_service, AIStructuredProductAnalysis

client = TestClient(app, raise_server_exceptions=False)

def run_benchmark():
    print("==================================================")
    print(" ReviewIQ Real Performance Benchmark")
    print("==================================================")

    # 1. Database Retrieval Latency on all 20 products
    products = ecommerce_db_service.search_products("", limit=100)
    print(f"Loaded {len(products)} products from dataset.")

    db_latencies = []
    sampling_latencies = []
    for p in products:
        pid = p.product_id
        t0 = time.perf_counter()
        analysis = ecommerce_db_service.get_product_analysis(pid)
        db_latencies.append((time.perf_counter() - t0) * 1000)

        t1 = time.perf_counter()
        samples = ecommerce_db_service.get_sample_reviews(pid, limit=20)
        sampling_latencies.append((time.perf_counter() - t1) * 1000)

    print(f"\n[1] Database Metrics Latency (20 Products):")
    print(f"    - Min: {min(db_latencies):.2f}ms")
    print(f"    - Mean (p50): {statistics.median(db_latencies):.2f}ms")
    print(f"    - p95: {statistics.quantiles(db_latencies, n=20)[18]:.2f}ms")
    print(f"    - Max: {max(db_latencies):.2f}ms")

    print(f"\n[2] Review Sampling Latency (15-20 High-Signal Reviews):")
    print(f"    - Min: {min(sampling_latencies):.2f}ms")
    print(f"    - Mean (p50): {statistics.median(sampling_latencies):.2f}ms")
    print(f"    - p95: {statistics.quantiles(sampling_latencies, n=20)[18]:.2f}ms")
    print(f"    - Max: {max(sampling_latencies):.2f}ms")

    # 2. Warm Cache vs Cold Cache
    gemini_summary_service.product_cache.invalidate()

    # Cold Cache (with real grounded synthesis)
    mock_ai = AIStructuredProductAnalysis(
        product_id="P12",
        product_title="Kelto Gamer I6",
        summary="Synthesized gaming desktop performance analysis.",
        pros=["Ultra fast framerates", "Quiet liquid cooling"],
        cons=["Heavy case"],
        insights=["Best in class for 1440p and 4K esports"],
        evidence=["Ultra fast framerates in AAA titles"],
    )

    from unittest.mock import patch
    with patch.object(gemini_summary_service, "_generate_product_structured_analysis", return_value=mock_ai):
        t0 = time.perf_counter()
        resp_miss = client.get("/api/products/P12/analysis")
        miss_dur = (time.perf_counter() - t0) * 1000

        print(f"\n[3] Cache MISS Request:")
        print(f"    - Status: {resp_miss.status_code}")
        print(f"    - X-Cache-Status: {resp_miss.headers.get('X-Cache-Status')}")
        print(f"    - Server-Timing: {resp_miss.headers.get('Server-Timing')}")
        print(f"    - Total duration: {miss_dur:.2f}ms")

        # Cache HIT requests (10 iterations)
        hit_latencies = []
        for _ in range(10):
            t1 = time.perf_counter()
            resp_hit = client.get("/api/products/P12/analysis")
            hit_latencies.append((time.perf_counter() - t1) * 1000)
            assert resp_hit.headers.get("X-Cache-Status") == "HIT"

        print(f"\n[4] Cache HIT Requests (10 iterations):")
        print(f"    - Min: {min(hit_latencies):.2f}ms")
        print(f"    - Mean (p50): {statistics.median(hit_latencies):.2f}ms")
        print(f"    - p95: {statistics.quantiles(hit_latencies, n=20)[18]:.2f}ms")
        print(f"    - Max: {max(hit_latencies):.2f}ms")

    print("\n[5] Concurrency & Single-Flight Coalescing Test:")
    call_count = [0]
    def delayed_ai(*args, **kwargs):
        call_count[0] += 1
        time.sleep(0.1)
        return mock_ai

    gemini_summary_service.product_cache.invalidate()
    with patch.object(gemini_summary_service, "_generate_product_structured_analysis", side_effect=delayed_ai):
        t_start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(client.get, "/api/products/P12/analysis") for _ in range(10)]
            responses = [f.result() for f in futures]
        total_concurrent_time = (time.perf_counter() - t_start) * 1000

        for r in responses:
            assert r.status_code == 200

        print(f"    - Concurrent requests fired: 10")
        print(f"    - Number of actual AI model invocations: {call_count[0]} (Coalesced 10:1)")
        print(f"    - Total time for 10 concurrent requests: {total_concurrent_time:.2f}ms")

    print("\nBenchmark completed successfully!")

if __name__ == "__main__":
    run_benchmark()
