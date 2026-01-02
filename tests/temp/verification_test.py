
import os
import sys

print("Running verification test from:", os.getcwd())
print("Script location:", os.path.dirname(os.path.abspath(__file__)))

# Check if we can import server (if needed, usually we run server separately)
# This is just a dummy test to see if we can run python scripts here
print("Verification successful.")
