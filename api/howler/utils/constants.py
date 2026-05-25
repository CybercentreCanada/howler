import os
import sys

TESTING = os.getenv("TESTING", "false").lower() in ["true", "1", "yes"] or "pytest" in sys.modules
