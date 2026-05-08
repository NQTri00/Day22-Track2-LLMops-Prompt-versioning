import re
import json
from guardrails import Guard, OnFailAction, Validator, register_validator
from guardrails.validators import PassResult, FailResult

# ── 1. Validator A: PII Detector ─────────────────────────────────────────────
@register_validator(name="custom/pii-detector", data_type="string")
class PIIDetector(Validator):
    """
    Detects PII like email, phone numbers, SSN, and credit card numbers.
    """
    def validate(self, value: str, metadata: dict) -> [PassResult, FailResult]:
        patterns = {
            "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "phone": r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
            "ssn": r"\d{3}-\d{2}-\d{4}",
            "credit_card": r"\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}"
        }
        
        redacted_value = value
        found_pii = False
        
        for pii_type, pattern in patterns.items():
            if re.search(pattern, redacted_value):
                found_pii = True
                redacted_value = re.sub(pattern, "[REDACTED]", redacted_value)
        
        if found_pii:
            return FailResult(
                error_message="PII detected in output",
                fix_value=redacted_value
            )
        
        return PassResult()

# ── 2. Validator B: JSON Formatter ───────────────────────────────────────────
@register_validator(name="custom/json-repair", data_type="string")
class JSONRepairValidator(Validator):
    """
    Checks for valid JSON and attempts auto-repair.
    """
    def validate(self, value: str, metadata: dict) -> [PassResult, FailResult]:
        repaired = value.strip()
        
        # 1. Strip markdown fences
        if repaired.startswith("```json"):
            repaired = repaired[7:]
        if repaired.endswith("```"):
            repaired = repaired[:-3]
        repaired = repaired.strip()
        
        # 2. Fix single quotes to double quotes (naive approach)
        # Note: This is simplified for the lab
        if "'" in repaired and '"' not in repaired:
            repaired = repaired.replace("'", '"')
            
        # 3. Try to parse
        try:
            json.loads(repaired)
            return PassResult() # If it was already valid or minor cleanup worked
        except json.JSONDecodeError:
            # 4. Fallback
            error_json = json.dumps({
                "error": "Failed to parse JSON",
                "raw_output": value[:100]
            })
            return FailResult(
                error_message="Invalid JSON format",
                fix_value=error_json
            )

# ── 3. Test Cases ───────────────────────────────────────────────────────────
def test_pii():
    print("\n--- Testing PII Detector ---")
    guard = Guard().use(PIIDetector(on_fail=OnFailAction.FIX))
    
    test_cases = [
        "Hello, my name is John Doe and I have no PII.",
        "My email is john.doe@example.com, please contact me.",
        "You can reach me at 555-123-4567 or 123-45-6789.",
        "My card number is 1234-5678-9012-3456.",
        "Mix: user@site.com and (555) 555-5555"
    ]
    
    for i, text in enumerate(test_cases, 1):
        result = guard.validate(text)
        print(f"Case {i}: {'PASS' if result.validation_passed else 'FIXED'}")
        print(f"  Input:  {text}")
        print(f"  Output: {result.validated_output}\n")

def test_json():
    print("\n--- Testing JSON Repair ---")
    guard = Guard().use(JSONRepairValidator(on_fail=OnFailAction.FIX))
    
    test_cases = [
        '{"status": "ok", "message": "Valid JSON"}',
        '```json\n{"status": "fenced", "count": 10}\n```',
        "{'status': 'single-quotes', 'key': 'value'}",
        '{"status": "broken", "unclosed": "brace"',
    ]
    
    for i, text in enumerate(test_cases, 1):
        result = guard.validate(text)
        print(f"Case {i}: {'PASS' if result.validation_passed else 'FIXED'}")
        print(f"  Input:  {text}")
        print(f"  Output: {result.validated_output}\n")

# ── 4. Main ─────────────────────────────────────────────────────────────────
def main():
    import sys
    
    test_type = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if test_type == "pii":
        test_pii()
    elif test_type == "json":
        test_json()
    else:
        print("=" * 60)
        print("  Step 4: Guardrails AI Validators")
        print("=" * 60)
        test_pii()
        test_json()

if __name__ == "__main__":
    main()
