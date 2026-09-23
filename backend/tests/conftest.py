import os
import sys

# Allow imports like "from services.ai_analyzer import ..." when running
# pytest from the repository root.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
