"""
verify_cli.py - Interactive Manual Verification Tool
Allows you to test with real SMS messages from your own bank without any 3rd-party apps.

Usage:
    python verify_cli.py
"""

import os
import sys
from datetime import datetime, timezone
from bridge import SupabasePaymentBridge
from test_bridge import load_env_file

def main():
    load_env_file()
    print("=" * 60)
    print("🧪 MANUAL PAYMENT BRIDGE VERIFICATION (No 3rd-Party Apps)")
    print("=" * 60)

    bridge = SupabasePaymentBridge()

    print("\nSelect an action:")
    print("1. Create a Test Pending Print Job (e.g. ₹5.04)")
    print("2. Enter a Bank SMS manually to test reconciliation")
    print("3. Check status of a Job in Supabase")
    print("4. Exit")

    while True:
        choice = input("\nEnter choice (1-4): ").strip()

        if choice == "1":
            amount_str = input("Enter amount to charge (e.g. 5.04): ").strip()
            try:
                amt = float(amount_str)
            except ValueError:
                print("Invalid amount!")
                continue

            job_id = f"MANUAL_JOB_{int(datetime.now().timestamp())}"
            mock_job = {
                "id": job_id,
                "filename": "manual_test.pdf",
                "pages": 2,
                "copies": 1,
                "color": "bw",
                "duplex": 0,
                "amount": amt,
                "status": "pending_payment",
                "created": datetime.now(timezone.utc).isoformat()
            }
            bridge._request("jobs", method="POST", data=mock_job)
            print(f"\n✅ Created Job in Supabase: {job_id}")
            print(f"   Amount: ₹{amt} | Status: pending_payment")
            print("   👉 Now go to choice 2 and paste the SMS to unlock this job!")

        elif choice == "2":
            print("\nPaste any SMS received from your bank/UPI (or type sample):")
            sample = input("> ").strip()
            if not sample:
                print("Empty input!")
                continue

            print("\nProcessing SMS...")
            res = bridge.process_sms(sample)
            if res and res.get("matched_job"):
                print(f"\n🎉 SUCCESS! Matched Job ID: {res['matched_job']['id']}")
                print(f"   Job status in Supabase updated to: 'queued' (READY TO PRINT)")
            else:
                print("\n❌ Could not match. Check if amount matches a pending job.")

        elif choice == "3":
            job_id = input("Enter Job ID to inspect: ").strip()
            jobs = bridge._request(f"jobs?id=eq.{job_id}&select=*", method="GET")
            if jobs:
                j = jobs[0]
                print(f"\nJob: {j['id']} | Status: {j['status']} | Amount: ₹{j['amount']} | UTR: {j.get('utr_number')}")
            else:
                print("Job not found!")

        elif choice == "4":
            print("Exiting.")
            sys.exit(0)

if __name__ == "__main__":
    main()
