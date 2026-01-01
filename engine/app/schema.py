"""Schema helpers for analysis output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_schema(path: str | Path = "schema.json") -> dict[str, Any]:
    schema_path = Path(path)
    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_schema(data: dict[str, Any], path: str | Path = "schema.json") -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema is not installed"]

    schema = load_schema(path)
    errors = []
    for error in jsonschema.Draft7Validator(schema).iter_errors(data):
        location = "/".join(str(part) for part in error.path)
        errors.append(f"{location}: {error.message}")
    return errors
