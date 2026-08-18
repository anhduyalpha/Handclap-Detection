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
        min_interval_ms=70,
        max_interval_ms=550,
        cooldown_ms=400,
        on_pattern_callback=on_pattern
    )

    print("[*] 1. Testing Single Clap (Should arm silently, NO action triggered)...")
    res1 = matcher.register_clap(0.85)
    print(f"    [+] Clap 1 response: {res1}")
    assert res1 is None
    assert len(dispatched_events) == 0

    print("\n[*] 2. Testing 2nd Clap at 150ms (Should trigger Double Clap INSTANTLY)...")
    time.sleep(0.15)
    t_start = time.time()
    res2 = matcher.register_clap(0.90)
    t_latency = (time.time() - t_start) * 1000.0
    print(f"    [+] Clap 2 response: {res2} (Latency = {t_latency:.2f}ms)")
    assert res2 == "double"
    assert len(dispatched_events) == 1
    assert dispatched_events[0]["pattern"] == "double"
    assert dispatched_events[0]["count"] == 2

    print("\n[*] 3. Testing Cooldown Rejection (Clap arriving within 400ms cooldown)...")
    time.sleep(0.10)
    res_cd = matcher.register_clap(0.92)
    print(f"    [+] Cooldown clap response: {res_cd}")
    assert res_cd is None
    assert len(dispatched_events) == 1

    print("\n[*] 4. Testing Interval Expiry (> 550ms between claps)...")
    time.sleep(0.50) # Wait out cooldown
    res_a = matcher.register_clap(0.88)
    assert res_a is None

    time.sleep(0.60) # Wait > 550ms
    res_b = matcher.register_clap(0.89)
    print(f"    [+] Clap after expiry response: {res_b} (Silently reset as new 1st clap)")
    assert res_b is None
    assert len(dispatched_events) == 1

    print("\n[SUCCESS] Instant Double-Clap Engine verified 100%!")

if __name__ == "__main__":
    test_instant_double_clap()
