import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path(__file__).parent / ".env.test")

# We append the plugin directory for howler to the python part
sys.path.insert(0, str(Path.cwd()))
api_path = Path(re.sub(r"^(.+)/plugins.+$", r"\1", str(Path.cwd())) + "/api")
sys.path.insert(0, str(api_path))

load_dotenv()

# We append the plugin directory for howler to the python part
sys.path.insert(0, str(Path.cwd()))
api_path = Path(re.sub(r"^(.+)/plugins.+$", r"\1", str(Path.cwd())) + "/api")
sys.path.insert(0, str(api_path))
from howler.config import config

config.core.plugins.add("evidence")
