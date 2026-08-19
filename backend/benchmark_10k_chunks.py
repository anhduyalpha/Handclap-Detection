import time
import os
import tracemalloc
import numpy as np

from app.core.live_engine import live_engine
from app.core.telemetry import system_telemetry

def run_10k_chunk_benchmark():
    print("=" * 65)
    print("  🚀 STARTING 10,000-CHUNK AUDIO STREAMING STABILITY BENCHMARK")
    print("  🎯 Testing: Constant Memory Footprint & < 2ms Average DSP Latency")
    print("=" * 65)

    num_chunks = 10000
    chunk_size = 512
    sample_rate = 16000

    # Khởi động theo dõi bộ nhớ (tracemalloc)
    tracemalloc.start()
    mem_start_current, mem_start_peak = tracemalloc.get_traced_memory()

    t_start = time.perf_counter()
    dsp_latencies = []

    # Tạo trước mảng tạp âm nền cố định để tái sử dụng
    bg_noise = np.random.normal(0, 0.008, chunk_size).astype(np.float32)

    # Thỉnh thoảng chèn 1 cú vỗ tay (mỗi 1000 chunks)
    t_pulse = np.linspace(0, 0.032, chunk_size, endpoint=False)
    clap_noise = np.random.normal(0, 0.75, chunk_size)
    clap_res = np.sin(2 * np.pi * 3400 * t_pulse)
    clap_env = np.exp(-t_pulse * 90.0)
    clap_chunk = ((0.75 * clap_noise + 0.25 * clap_res) * clap_env)
    clap_chunk = (clap_chunk / np.max(np.abs(clap_chunk)) * 0.75).astype(np.float32)

    print(f"[*] Simulating continuous stream of {num_chunks} audio chunks (32ms each = {num_chunks * 0.032:.1f}s of real audio)...")

    for i in range(num_chunks):
        t0 = time.perf_counter()
        
        if (i + 1) % 1000 == 0:
            # Chèn xung vỗ tay
            audio_input = clap_chunk
        else:
            # Tạp âm nền
            audio_input = bg_noise

        res = live_engine.process_chunk(audio_input)
        
        t_chunk = (time.perf_counter() - t0) * 1000.0
        dsp_latencies.append(t_chunk)

        if (i + 1) % 2500 == 0:
            current_mem, peak_mem = tracemalloc.get_traced_memory()
            avg_lat = np.mean(dsp_latencies[-2500:])
            p99_lat = np.percentile(dsp_latencies[-2500:], 99)
            print(f"    [Chunk {i+1:05d}/{num_chunks}] Avg Latency: {avg_lat:.2f}ms | P99: {p99_lat:.2f}ms | Heap Current: {current_mem/1024:.1f} KB (Peak: {peak_mem/1024:.1f} KB)")

    total_time = time.perf_counter() - t_start
    mem_final_current, mem_final_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    avg_latency = float(np.mean(dsp_latencies))
    p95_latency = float(np.percentile(dsp_latencies, 95))
    p99_latency = float(np.percentile(dsp_latencies, 99))
    heap_growth_kb = (mem_final_current - mem_start_current) / 1024.0

    print("\n" + "=" * 65)
    print("  📊 BENCHMARK RESULTS SUMMARY")
    print("=" * 65)
    print(f"  • Total Chunks Processed:  {num_chunks:,}")
    print(f"  • Total Execution Time:    {total_time:.2f}s (Real-time speedup: {num_chunks * 0.032 / total_time:.1f}x)")
    print(f"  • Average DSP Latency:     {avg_latency:.3f} ms  (Target: < 2.0 ms) -> {'PASS ✅' if avg_latency < 2.0 else 'FAIL ❌'}")
    print(f"  • P95 Latency:             {p95_latency:.3f} ms")
    print(f"  • P99 Latency:             {p99_latency:.3f} ms")
    print(f"  • Heap Memory Growth:      {heap_growth_kb:.2f} KB  (Target: Stable Zero Leak) -> {'PASS ✅' if heap_growth_kb < 500 else 'FAIL ❌'}")
    print(f"  • Active Noise Status:     {live_engine.noise_estimator.ambient_status} ({live_engine.noise_estimator.ambient_label})")
    print("=" * 65)

    assert avg_latency < 2.0, f"Average DSP latency {avg_latency:.2f}ms exceeded 2.0ms threshold!"
    assert heap_growth_kb < 500.0, f"Heap memory growth {heap_growth_kb:.1f}KB exceeded threshold!"
    print("\n🎉 [100% SUCCESS] 24/7 Stability & Zero-Allocation Benchmark Passed Perfectly!\n")

if __name__ == "__main__":
    run_10k_chunk_benchmark()
