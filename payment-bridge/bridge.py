"""
bridge.py - Payment Bridge Core
Handles Supabase interaction, payment insertion, and order reconciliation.
Works without heavy external dependencies (uses standard library urllib.request + json).
"""

import os
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sms_parser import IndianPaymentSMSParser

class SupabasePaymentBridge:
    def __init__(self, supabase_url: Optional[str] = None, service_key: Optional[str] = None):
        self.supabase_url = (supabase_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.service_key = service_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_KEY", "")
        self.parser = IndianPaymentSMSParser()

    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

    def _request(self, endpoint: str, method: str = "GET", data: Optional[Dict] = None) -> Any:
        url = f"{self.supabase_url}/rest/v1/{endpoint}"
        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=body, headers=self._headers(), method=method)

        try:
            with urllib.request.urlopen(req) as response:
                resp_text = response.read().decode("utf-8")
                return json.loads(resp_text) if resp_text else None
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            raise RuntimeError(f"Supabase HTTP {e.code} Error on {endpoint}: {err_msg}")
        except Exception as e:
            raise RuntimeError(f"Supabase connection failed: {str(e)}")

    def record_incoming_payment(self, amount: float, utr: Optional[str], raw_message: str, sender_info: Optional[str] = None) -> Dict:
        """
        Inserts new payment into incoming_payments.
        Failsafe: ignores duplicate UTRs.
        """
        payload = {
            "amount": amount,
            "utr_number": utr,
            "raw_message": raw_message,
            "sender_info": sender_info,
            "is_consumed": False
        }
        # PostgREST upsert / insert
        try:
            result = self._request("incoming_payments", method="POST", data=payload)
            return result[0] if isinstance(result, list) and len(result) > 0 else result
        except RuntimeError as e:
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                print(f"[WARN] Duplicate UTR ignored: {utr}")
                return {"duplicate": True, "utr": utr}
            raise e

    def reconcile_payment(self, amount: float, utr: Optional[str] = None) -> Optional[Dict]:
        """
        Matches payment against active pending print jobs.
        1. First tries matching exact UTR.
        2. Next matches exact final_amount (unique paise trick) for non-expired pending jobs.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        matched_job = None

        # 1. Match by UTR if available
        if utr:
            endpoint = f"print_jobs?utr_number=eq.{utr}&payment_status=eq.PENDING&select=*"
            jobs = self._request(endpoint, method="GET")
            if jobs and len(jobs) > 0:
                matched_job = jobs[0]

        # 2. Match by unique amount (Paise Reservation) if not matched yet
        if not matched_job:
            endpoint = f"print_jobs?final_amount=eq.{amount}&payment_status=eq.PENDING&expires_at=gte.{now_iso}&order=created_at.desc&limit=1&select=*"
            jobs = self._request(endpoint, method="GET")
            if jobs and len(jobs) > 0:
                matched_job = jobs[0]

        if not matched_job:
            print(f"[INFO] No pending job matched for amount: Rs. {amount}, UTR: {utr}")
            return None

        # 3. Mark job as PAID and link UTR
        job_id = matched_job["id"]
        update_payload = {
            "payment_status": "PAID",
            "utr_number": utr or matched_job.get("utr_number")
        }
        updated_job = self._request(f"print_jobs?id=eq.{job_id}", method="PATCH", data=update_payload)

        # 4. Mark payment as consumed
        if utr:
            self._request(f"incoming_payments?utr_number=eq.{utr}", method="PATCH", data={"is_consumed": True, "matched_job_id": job_id})
        
        print(f"[SUCCESS] Payment of Rs. {amount} MATCHED to Job {job_id}!")
        return matched_job

    def process_sms(self, sms_text: str) -> Optional[Dict]:
        """
        Full workflow: parse raw SMS -> store payment -> reconcile order.
        """
        parsed = self.parser.parse(sms_text)
        if not parsed:
            print("[INFO] SMS ignored (not a valid credit transaction).")
            return None

        amount = parsed["amount"]
        utr = parsed["utr"]
        print(f"[PARSED] Credit Detected -> Amount: Rs. {amount}, UTR: {utr}")

        # Record in Supabase
        self.record_incoming_payment(amount, utr, sms_text)

        # Attempt immediate reconciliation
        matched_job = self.reconcile_payment(amount, utr)
        return {
            "parsed": parsed,
            "matched_job": matched_job
        }
