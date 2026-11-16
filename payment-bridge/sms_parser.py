"""
sms_parser.py - Production-grade SMS & Notification Parser for Indian Banks & UPI

Extracts:
- amount: float (e.g. 10.05)
- utr: 12-digit UPI reference number (or bank txn id)
- sender: Sender name/VPA if present
"""

import re
from typing import Optional, Dict, Any

class IndianPaymentSMSParser:
    def __init__(self):
        # 12-digit UTR regex patterns
        self.utr_patterns = [
            re.compile(r'(?:UPI|Ref|UTR|Txn|Ref\s*no|UPI\s*Ref)[:\s/]*([0-9]{12})', re.IGNORECASE),
            re.compile(r'UPI/([0-9]{12})', re.IGNORECASE),
            re.compile(r'RRN[:\s]*([0-9]{12})', re.IGNORECASE),
            re.compile(r'\b([0-9]{12})\b') # Fallback 12-digit number
        ]

        # Amount regex patterns
        self.amount_patterns = [
            re.compile(r'(?:Rs\.?|INR|₹)\s*([0-9]+(?:\.[0-9]{1,2})?)', re.IGNORECASE),
            re.compile(r'credited\s+(?:by|with)\s+(?:Rs\.?|INR|₹)?\s*([0-9]+(?:\.[0-9]{1,2})?)', re.IGNORECASE),
            re.compile(r'received\s+(?:Rs\.?|INR|₹)?\s*([0-9]+(?:\.[0-9]{1,2})?)', re.IGNORECASE)
        ]

        # Credit keywords - To verify money is coming IN, not debited!
        self.credit_keywords = ['credited', 'received', 'deposited', 'added']
        self.debit_keywords = ['debited', 'spent', 'sent', 'paid to', 'withdrawn']

    def is_credit_transaction(self, text: str) -> bool:
        lower_text = text.lower()
        has_credit = any(k in lower_text for k in self.credit_keywords)
        has_debit = any(k in lower_text for k in self.debit_keywords)
        
        # Guard against "debited" messages
        if has_debit and not has_credit:
            return False
        return has_credit

    def parse(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Parses an incoming SMS string.
        Returns dict with amount, utr, is_credit or None if invalid.
        """
        if not message or not isinstance(message, str):
            return None

        # Check if it's a credit message
        if not self.is_credit_transaction(message):
            return None

        # Extract Amount
        amount = None
        for pattern in self.amount_patterns:
            match = pattern.search(message)
            if match:
                try:
                    amount = float(match.group(1))
                    break
                except ValueError:
                    continue

        if amount is None or amount <= 0:
            return None

        # Extract 12-digit UTR
        utr = None
        for pattern in self.utr_patterns:
            match = pattern.search(message)
            if match:
                potential_utr = match.group(1)
                # UTR in India is strictly 12 digits
                if len(potential_utr) == 12 and potential_utr.isdigit():
                    utr = potential_utr
                    break

        return {
            "amount": amount,
            "utr": utr, # Can be None if bank truncated, but amount is extracted
            "raw_message": message.strip()
        }


if __name__ == "__main__":
    parser = IndianPaymentSMSParser()
    test_cases = [
        "Dear SBI User, A/C 1234 credited by Rs. 6.03 on 16Nov26 by UPI:432187654321. Ref no 432187654321",
        "HDFC Bank: Rs 15.00 credited to a/c **4321 on 16-11-26 by UPI user Amit. UPI Ref: 987654321012",
        "INR 8.04 received in your Paytm Payments Bank A/C from rahul@okhdfcbank (UPI Ref: 112233445566)",
        "Dear Customer, your a/c is debited for Rs 500 on 16Nov26.", # Should be ignored!
    ]

    for tc in test_cases:
        res = parser.parse(tc)
        print(f"INPUT:  {tc}\nRESULT: {res}\n")
