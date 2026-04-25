import os

# Disable the in-process rate limiter for all tests so validation tests
# receive the expected 400 instead of 429.
os.environ.setdefault("DISABLE_RATE_LIMIT", "1")
