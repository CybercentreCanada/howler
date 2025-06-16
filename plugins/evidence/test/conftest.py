import re
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path(__file__).parent / ".env.test")

# We append the plugin directory for howler to the python part
sys.path.insert(0, str(Path.cwd()))
api_path = Path(re.sub(r"^(.+)/plugins.+$", r"\1", str(Path.cwd())) + "/api")
sys.path.insert(0, str(api_path))

from evidence.odm.hit import modify_odm

load_dotenv()

# We append the plugin directory for howler to the python part
sys.path.insert(0, str(Path.cwd()))
api_path = Path(re.sub(r"^(.+)/plugins.+$", r"\1", str(Path.cwd())) + "/api")
sys.path.insert(0, str(api_path))
from howler.config import config

config.core.plugins.add("evidence")


@pytest.fixture(autouse=True)
def init_odm_changes():
    from howler.odm.models.hit import Hit

    modify_odm(Hit)
