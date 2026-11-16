"""
termux_listener.py - Runs on Android phone inside Termux
Requires: Termux:API (from F-Droid) and `pkg install termux-api`
Usage: python termux_listener.py
"""

import subprocess
import json
import time
import os
from bridge import SupabasePaymentBridge

POLL_INTERVAL_SECONDS = 3
SEEN_MESSAGES_CACHE_FILE = "seen_sms_ids.txt"

def get_recent_sms(limit: int = 5):
    """
    Calls termux-sms-list command to fetch recent incoming SMS.
    """
    try:
        result = subprocess.run(
            ["termux-sms-list", "-l", str(limit), "-t", "inbox"],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except FileNotFoundError:
        print("[ERROR] 'termux-sms-list' not found. Make sure termux-api is installed:")
        print("Run: pkg install termux-api and install Termux:API app from F-Droid.")
        return []
    except Exception as e:
        print(f"[ERROR] Failed to read SMS via Termux: {e}")
        return []

def load_seen_ids():
    if os.path.exists(SEEN_MESSAGES_CACHE_FILE):
        with open(SEEN_MESSAGES_CACHE_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_seen_id(sms_id: str):
    with open(SEEN_MESSAGES_CACHE_FILE, "a") as f:
        f.write(f"{sms_id}\n")

def main():
    print("=" * 60)
    print("🚀 Termux Autonomous UPI/Bank Payment Listener Started")
    print(f"Polling inbox every {POLL_INTERVAL_SECONDS} seconds...")
    print("=" * 60)

    bridge = SupabasePaymentBridge()
    seen_ids = load_seen_ids()

    while True:
        try:
            messages = get_recent_sms(limit=5)
            for msg in messages:
                sms_id = str(msg.get("_id") or msg.get("received") or msg.get("body"))
                if sms_id in seen_ids:
                    continue

                body = msg.get("body", "")
                sender = msg.get("number", "UNKNOWN")

                print(f"\n[NEW SMS from {sender}]: {body[:60]}...")
                result = bridge.process_sms(body)

                # Cache this SMS as processed
                seen_ids.add(sms_id)
                save_seen_id(sms_id)

        except KeyboardInterrupt:
            print("\nStopping Termux listener.")
            break
        except Exception as e:
            print(f"[LOOP ERROR]: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
