import urllib.request
import json

def inspect_dell():
    url = "http://192.168.2.171:8000/openapi.json"
    print(f"[*] Fetching OpenAPI schema from {url}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            paths = list(data.get("paths", {}).keys())
            print("\n[+] Registered Endpoints on Dell Server (192.168.2.171:8000):")
            for p in sorted(paths):
                methods = list(data["paths"][p].keys())
                print(f"  - {methods} {p}")
            
            print("\n--- Diagnostic Check ---")
            if "/api/training/record-continuous-session" in paths:
                print("✅ /api/training/record-continuous-session IS REGISTERED!")
            else:
                print("❌ /api/training/record-continuous-session IS MISSING on Dell server!")

            if "/api/training/record-hardware-sample" in paths:
                print("✅ /api/training/record-hardware-sample IS REGISTERED!")
            else:
                print("❌ /api/training/record-hardware-sample IS MISSING on Dell server!")
    except Exception as e:
        print(f"[!] Cannot connect to Dell server: {e}")

if __name__ == "__main__":
    inspect_dell()
