import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.pattern_matcher import ClapPatternMatcher

def test_instant_double_clap():
    dispatched_events = []

    def on_pattern(pattern, count, events):
        dispatched_events.append({"pattern": pattern, "count": count, "time": time.time()})

    matcher = ClapPatternMatcher(
        min_interval_ms=140,
        max_interval_ms=500,
        cooldown_ms=400,
        on_pattern_callback=on_pattern
    )

    print("[*] 1. Testing Loud Single Clap with Room Echo at 90ms...")
    res_loud = matcher.register_clap(0.95)
    assert res_loud is None
    time.sleep(0.09) # 90ms later (room echo / reverberation of the loud clap)
    res_echo = matcher.register_clap(0.80)
    print(f"    [+] Echo pulse response at 90ms: {res_echo} (Must be rejected as echo)")
    assert res_echo is None
    assert len(dispatched_events) == 0, "Echo must not trigger action!"

    print("\n[*] 2. Testing Two Real Claps separated by 200ms (Must trigger Double Clap)...")
    time.sleep(0.50) # Reset previous state
    matcher.register_clap(0.90) # Clap 1
    time.sleep(0.20) # 200ms interval (Human physical double-clap)
    t_start = time.time()
    res2 = matcher.register_clap(0.92) # Clap 2
    t_latency = (time.time() - t_start) * 1000.0
    print(f"    [+] Clap 2 response: {res2} (Latency = {t_latency:.2f}ms)")
    assert res2 == "double"
    assert len(dispatched_events) == 1
    assert dispatched_events[0]["pattern"] == "double"
    assert dispatched_events[0]["count"] == 2

    print("\n[*] 3. Testing Cooldown Rejection (Pulse arriving within 400ms cooldown)...")
    time.sleep(0.10)
    res_cd = matcher.register_clap(0.92)
    print(f"    [+] Cooldown clap response: {res_cd}")
    assert res_cd is None
    assert len(dispatched_events) == 1

    print("\n[*] 4. Testing Interval Expiry (> 500ms between claps)...")
    time.sleep(0.50) # Wait out cooldown
    matcher.register_clap(0.88)

    time.sleep(0.55) # Wait > 500ms
    res_b = matcher.register_clap(0.89)
    print(f"    [+] Clap after expiry response: {res_b} (Silently reset as new 1st clap)")
    assert res_b is None
    assert len(dispatched_events) == 1

    print("\n[SUCCESS] Anti-Echo (140ms) & Instant Double-Clap Engine verified 100%!")

if __name__ == "__main__":
    test_instant_double_clap()
