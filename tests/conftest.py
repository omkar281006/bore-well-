import os
import sys

# Make `simulator`, `backend` and `dashboard` importable when pytest runs from any folder.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Tests never touch AWS.
os.environ.pop("DYNAMODB_TABLE", None)
