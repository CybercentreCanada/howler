import os
import sys

TESTING = os.getenv("TESTING", "false").lower() in ["true", "1", "yes"] or "pytest" in sys.modules
DEBUG_FORCE_REFRESH = True  # TODO change this to a real config if needed
