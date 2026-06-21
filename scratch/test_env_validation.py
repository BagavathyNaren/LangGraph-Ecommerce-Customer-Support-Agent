import os
import sys
from unittest.mock import patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from security.env_validator import validate_env


def run_tests():
    print("[TEST] Running Environment Validation Tests...")

    # Test 1: Valid environment
    print("\nTest 1: Valid environment...")
    base_env = {
        "OPENAI_API_KEY": "sk-testkey",
        "DATABASE_URL": "postgresql://postgres:pass@localhost:5432/db",
        "EMAIL_PROVIDER": "resend",
        "RESEND_API_KEY": "re-testkey",
        "TAVILY_API_KEY": "tv-testkey",
    }
    with patch.dict(os.environ, base_env, clear=True):
        try:
            settings = validate_env()
            assert settings.OPENAI_API_KEY == "sk-testkey"
            assert settings.DATABASE_URL == "postgresql://postgres:pass@localhost:5432/db"
            assert settings.EMAIL_PROVIDER == "resend"
            print("[PASS] Test 1 Passed!")
        except Exception as e:
            print(f"[FAIL] Test 1 Failed: {e}")
            sys.exit(1)

    # Test 2: Missing OpenAI Key
    print("\nTest 2: Missing OpenAI Key...")
    test_env = base_env.copy()
    test_env["OPENAI_API_KEY"] = ""
    with patch.dict(os.environ, test_env, clear=True):
        try:
            validate_env()
            print("[FAIL] Test 2 Failed (Validation did not raise an error for missing OpenAI key)")
            sys.exit(1)
        except ValueError as e:
            print(f"[PASS] Test 2 Passed! Correctly caught missing key: {e}")

    # Test 3: Missing Database configuration
    print("\nTest 3: Missing Database configuration...")
    test_env = base_env.copy()
    test_env["DATABASE_URL"] = ""
    with patch.dict(os.environ, test_env, clear=True):
        try:
            validate_env()
            print("[FAIL] Test 3 Failed (Validation did not raise an error for missing DB config)")
            sys.exit(1)
        except ValueError as e:
            print(f"[PASS] Test 3 Passed! Correctly caught missing DB config: {e}")

    # Test 4: Gmail provider validation
    print("\nTest 4: Gmail provider validation (missing sender email or password)...")
    test_env = base_env.copy()
    test_env["EMAIL_PROVIDER"] = "gmail"
    test_env["GMAIL_SENDER_EMAIL"] = ""
    with patch.dict(os.environ, test_env, clear=True):
        try:
            validate_env()
            print("[FAIL] Test 4 Failed (Validation did not raise an error for missing Gmail fields)")
            sys.exit(1)
        except ValueError as e:
            print(f"[PASS] Test 4 Passed! Correctly caught missing Gmail details: {e}")

    # Test 5: Resend provider validation
    print("\nTest 5: Resend provider validation (missing api key)...")
    test_env = base_env.copy()
    test_env["EMAIL_PROVIDER"] = "resend"
    test_env["RESEND_API_KEY"] = ""
    with patch.dict(os.environ, test_env, clear=True):
        try:
            validate_env()
            print("[FAIL] Test 5 Failed (Validation did not raise an error for missing Resend key)")
            sys.exit(1)
        except ValueError as e:
            print(f"[PASS] Test 5 Passed! Correctly caught missing Resend key: {e}")

    print("\n[SUCCESS] All local environment validation test cases passed successfully!")


if __name__ == "__main__":
    run_tests()
