#!/usr/bin/python3

import json
import logging
import sys
from pathlib import Path

with open(
    Path(__file__).parents[1] / "ui" / "src" / "locales" / "en" / "translation.json",
    "r",
) as en_file:
    en_data = json.load(en_file)

with open(
    Path(__file__).parents[1] / "ui" / "src" / "locales" / "fr" / "translation.json",
    "r",
) as fr_file:
    fr_data = json.load(fr_file)

en_keys = set(en_data.keys())
fr_keys = set(fr_data.keys())

fr_missing = en_keys - fr_keys

if fr_missing:
    logging.error(f"French i18n missing keys: {', '.join(fr_missing)}")

en_missing = fr_keys - en_keys

if en_missing:
    logging.error(f"English i18n missing keys: {', '.join(en_missing)}")

if en_missing or fr_missing:
    sys.exit(1)
