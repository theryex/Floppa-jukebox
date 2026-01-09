import argparse
import json
from pathlib import Path


def load_schema(schema_path: Path) -> dict:
    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate analysis JSON against schema.json")
    parser.add_argument("analysis_json")
    parser.add_argument("--schema", default="schema.json")
    args = parser.parse_args()

    try:
        import jsonschema
    except ImportError as exc:
        raise RuntimeError("jsonschema is required for validation") from exc

    with Path(args.analysis_json).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    schema = load_schema(Path(args.schema))

    jsonschema.validate(data, schema)
    print("valid")


if __name__ == "__main__":
    main()
