#!/usr/bin/python3

import json
import logging
import re
import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).parents[1]
UI_SOURCE = ROOT / "ui" / "src"
TRANSLATION_CALL = re.compile(
    r"(?<![\w$/\"'`])(?:[\w$]+\.)?t\s*\(\s*(?P<quote>['\"`])(?P<key>[^'\"`]+)(?P=quote)"
)
TRANSLATION_PROP = re.compile(
    r"\b(?:i18nKey|i18nLabel)\s*(?:=|:)\s*(?P<quote>['\"`])(?P<key>[^'\"`]+)(?P=quote)"
)
USE_TRANSLATION = re.compile(
    r"\buseTranslation\s*\(\s*(?P<namespaces>\[[^\]]*\]|['\"][^'\"]+['\"])"
)
NAMESPACE_LITERAL = re.compile(r"['\"]([^'\"]+)['\"]")
LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")


@lru_cache(maxsize=None)
def read_translation_keys(language: str, namespace: str) -> set[str]:
    locale_root = UI_SOURCE / "locales" / language
    if namespace == "translation":
        translation_files = [
            locale_root / "translation.json",
            UI_SOURCE / "plugins" / "clue" / "locales" / f"clue.{language}.json",
        ]
    elif namespace == "helpSearch":
        translation_files = [locale_root / "help" / "search.json"]
    elif namespace == "helpMain":
        translation_files = [locale_root / "help" / "main.json"]
    else:
        return set()

    keys = set()
    for translation_file in translation_files:
        if not translation_file.exists():
            continue
        with translation_file.open("r") as file:
            keys.update(json.load(file).keys())

    return keys


def get_namespaces(source: str) -> tuple[str, ...]:
    namespaces = {
        namespace
        for match in USE_TRANSLATION.finditer(source)
        for namespace in NAMESPACE_LITERAL.findall(match.group("namespaces"))
    }
    return tuple(sorted(namespaces)) or ("translation",)


def find_translation_references() -> dict[
    tuple[str, tuple[str, ...]], set[tuple[str, int]]
]:
    references: dict[tuple[str, tuple[str, ...]], set[tuple[str, int]]] = defaultdict(
        set
    )
    for source_file in sorted(UI_SOURCE.rglob("*")):
        if source_file.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        if (
            ".test." in source_file.name
            or ".spec." in source_file.name
            or "__tests__" in source_file.parts
        ):
            continue

        source = LINE_COMMENT.sub("", source_file.read_text())
        namespaces = get_namespaces(source)
        for pattern in (TRANSLATION_CALL, TRANSLATION_PROP):
            for match in pattern.finditer(source):
                key = match.group("key")
                # Interpolated template literals are dynamic and cannot be checked statically.
                if "${" in key:
                    continue
                reference_namespaces = namespaces
                if ":" in key:
                    namespace, key = key.split(":", 1)
                    reference_namespaces = (namespace,)
                line_number = source.count("\n", 0, match.start()) + 1
                references[(key, reference_namespaces)].add(
                    (source_file.relative_to(ROOT).as_posix(), line_number)
                )

    return references


def report_missing_references() -> bool:
    missing_references = False
    for (key, namespaces), locations in sorted(find_translation_references().items()):
        missing_languages = []
        for language, label in (("en", "English"), ("fr", "French")):
            if not any(
                key in read_translation_keys(language, namespace)
                for namespace in namespaces
            ):
                missing_languages.append(label)

        if missing_languages:
            missing_references = True
            references = ", ".join(f"{path}:{line}" for path, line in sorted(locations))
            logging.error(
                "UI localization key '%s' is missing from %s translation file(s) (used at %s)",
                key,
                " and ".join(missing_languages),
                references,
            )

    return missing_references


en_keys = read_translation_keys("en", "translation")
fr_keys = read_translation_keys("fr", "translation")

fr_missing = sorted(en_keys - fr_keys)

if fr_missing:
    logging.error(f"French i18n missing keys: {', '.join(fr_missing)}")

en_missing = sorted(fr_keys - en_keys)

if en_missing:
    logging.error(f"English i18n missing keys: {', '.join(en_missing)}")

used_keys_missing = report_missing_references()

if en_missing or fr_missing or used_keys_missing:
    sys.exit(1)
