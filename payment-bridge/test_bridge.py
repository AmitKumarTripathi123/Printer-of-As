"""
test_bridge.py - Verification script for Payment Bridge
Run this to test the SMS parser and live Supabase reconciliation.

Usage:
  python test_bridge.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from sms_parser import IndianPaymentSMSParser
from bridge import SupabasePaymentBridge

def test_sms_parser():
    print("\n--- [TEST 1] Verifying SMS & Notification Parser ---")
    parser = IndianPaymentSMSParser()

    test_vectors = [
        {
            "bank": "State Bank of India (SBI)",
            "sms": "Dear SBI User, A/C ...1234 credited by Rs. 6.03 on 16Nov26 by UPI:432187654321. Ref no 432187654321",
            "expected_amount": 6.03,
            "expected_utr": "432187654321",
            "is_valid": True
        },
        {
            "bank": "HDFC Bank",
            "sms": "Rs 15.00 credited to a/c **4321 on 16-11-26 by UPI user Amit. UPI Ref: 987654321012",
            "expected_amount": 15.00,
            "expected_utr": "987654321012",
            "is_valid": True
        },
        {
            "bank": "ICICI Bank",
            "sms": "Dear Customer, Acct ...5566 credited with INR 8.04 on 16-NOV-26. UPI:112233445566-Info.",
            "expected_amount": 8.04,
            "expected_utr": "112233445566",
            "is_valid": True
        },
        {
            "bank": "Paytm / UPI App",
            "sms": "Received Rs. 10.05 in your Paytm Wallet from Rahul. Ref: 554433221100",
            "expected_amount": 10.05,
            "expected_utr": "554433221100",
            "is_valid": True
        },
        {
            "bank": "Debit Alert (Negative Test)",
            "sms": "Your A/C is debited for INR 500.00 on 16Nov26 at Swiggy. Available Bal: Rs. 1200",
            "is_valid": False
        },
        {
            "bank": "OTP Spam (Negative Test)",
            "sms": "Your OTP for login is 482910. Do not share this OTP with anyone.",
            "is_valid": False
        }
    ]

    all_passed = True
    for item in test_vectors:
        res = parser.parse(item["sms"])
        if item["is_valid"]:
            if not res:
                print(f"❌ FAILED on {item['bank']}: Parser returned None for valid SMS!")
                all_passed = False
                continue
            amt_ok = abs(res["amount"] - item["expected_amount"]) < 0.001
            utr_ok = res["utr"] == item["expected_utr"]
            if amt_ok and utr_ok:
                print(f"✅ PASSED: {item['bank']} -> Amount: ₹{res['amount']}, UTR: {res['utr']}")
            else:
                print(f"❌ MISMATCH: {item['bank']} -> Got Amount: ₹{res['amount']} (Expected {item['expected_amount']}), UTR: {res['utr']} (Expected {item['expected_utr']})")
                all_passed = False
        else:
            if res is None:
                print(f"✅ PASSED (Ignored Non-Credit): {item['bank']}")
            else:
                print(f"❌ FAILED: Non-credit SMS was falsely parsed as credit: {res}")
                all_passed = False

    return all_passed

def load_env_file():
    for env_path in [".env", "../.env"]:
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() not in os.environ:
                            os.environ[k.strip()] = v.strip()

def test_supabase_integration():
    print("\n--- [TEST 2] Verifying Supabase Live Connection & Reconciliation ---")
    load_env_file()
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_key:
        print("⚠️  SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables are not set.")
        print("   To test live Supabase integration:")
        print("   export SUPABASE_URL='https://your-project.supabase.co'")
        print("   export SUPABASE_SERVICE_ROLE_KEY='your-service-role-key'")
        print("   python test_bridge.py")
        return None

    bridge = SupabasePaymentBridge(supabase_url=supabase_url, service_key=service_key)

    # 1. Create a dummy pending print job with unique paise (e.g. ₹6.03)
    test_job_id = f"TEST_JOB_{int(datetime.now().timestamp())}"
    now_iso = datetime.now(timezone.utc).isoformat()
    mock_job = {
        "id": test_job_id,
        "filename": "test_document.pdf",
        "pages": 2,
        "copies": 1,
        "color": "bw",
        "duplex": 0,
        "amount": 6.03,
        "reserved_paise_offset": 3,
        "status": "pending_payment",
        "created": now_iso
    }

    try:
        print(f"1. Creating mock pending print job in Supabase table 'jobs' ({test_job_id}) for ₹6.03...")
        bridge._request("jobs", method="POST", data=mock_job)
        print("   ✅ Job created successfully in Supabase.")

        # 2. Simulate incoming bank SMS with ₹6.03
        mock_sms = f"Dear SBI User, A/C ...1234 credited by Rs. 6.03 on 16Nov26 by UPI:889900112233. Ref no 889900112233"
        print(f"2. Simulating incoming Bank SMS:\n   '{mock_sms}'")
        
        result = bridge.process_sms(mock_sms)

        if result and result.get("matched_job"):
            matched_id = result["matched_job"]["id"]
            if matched_id == test_job_id:
                print(f"   🎉 SUCCESS: SMS matched and unlocked Job {test_job_id}!")
                return True
            else:
                print(f"   ❌ Matched unexpected job: {matched_id}")
                return False
        else:
            print("   ❌ Payment was not matched to the job.")
            return False

    except Exception as e:
        print(f"   ❌ Supabase test failed with error: {e}")
        return False

if __name__ == "__main__":
    parser_ok = test_sms_parser()
    if parser_ok:
        print("\n✨ All Parser Unit Tests Passed Successfully!")
    
    test_supabase_integration()
