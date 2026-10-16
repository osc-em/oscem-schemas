"""
Shared utilities for schema naming and descriptions.
Used by both generate_artifacts_page.py and generate_index_pages.py.
"""

from pathlib import Path
import yaml


def load_schema_metadata(schema_id: str, schema_dir: Path = None) -> dict:
    """Load metadata from a schema YAML file."""
    if schema_dir is None:
        script_dir = Path(__file__).parent
        schema_dir = script_dir.parent / "src" / "oscem_schemas" / "schema"

    schema_file = schema_dir / f"{schema_id}.yaml"

    if not schema_file.exists():
        return {}

    try:
        with open(schema_file, "r") as f:
            data = yaml.safe_load(f)
            return {
                "id": data.get("id", ""),
                "name": data.get("name", ""),
                "description": data.get("description", "").strip(),
            }
    except Exception as e:
        print(f"Warning: Could not load metadata from {schema_file}: {e}")
        return {}


def is_main_schema(schema_id: str) -> bool:
    """
    Check if a schema is a main technique schema.
    Main schemas are those that have a corresponding oscem_schemas_* YAML file.
    """
    script_dir = Path(__file__).parent

    schema_dir = script_dir.parent / "src" / "oscem_schemas" / "schema"
    main_schema_file = schema_dir / f"oscem_schemas_{schema_id}.yaml"

    return main_schema_file.exists()


def get_all_schema_ids(schema_dir: Path = None) -> list:
    """
    Get list of all schema IDs by scanning the schema directory.
    Returns main schemas first (alphabetically), then supporting schemas (alphabetically).
    """
    if schema_dir is None:
        script_dir = Path(__file__).parent
        schema_dir = script_dir.parent / "src" / "oscem_schemas" / "schema"

    if not schema_dir.exists():
        return []

    # Find all YAML files
    yaml_files = list(schema_dir.glob("*.yaml"))
    # Extract schema IDs (filenames without .yaml extension)
    all_ids = [f.stem for f in yaml_files]
    # Separate main and supporting schemas (case-insensitive alphabetical sorting)
    main_schemas = sorted([sid for sid in all_ids if is_main_schema(sid)], key=str.lower)
    supporting_schemas = sorted([sid for sid in all_ids if not is_main_schema(sid)], key=str.lower)

    return main_schemas + supporting_schemas


def get_schema_sort_key(schema_id: str) -> tuple:
    """
    Return a sort key that puts main schemas first, then supporting schemas.
    """
    if is_main_schema(schema_id):
        # Main schemas: group = 0
        return (0, schema_id.lower())
    else:
        # Supporting schemas: group = 1
        return (1, schema_id.lower())


def format_schema_name(schema_id: str, schema_dir: Path = None) -> str:
    """Convert schema ID to a display name using the 'name' from the YAML file."""
    metadata = load_schema_metadata(schema_id, schema_dir)

    if metadata.get("name"):
        return metadata["name"]

    # Fallback: convert schema_id to title case
    return schema_id.replace("_", " ").title()


def get_schema_description(schema_id: str, schema_dir: Path = None) -> str:
    """Get description from the schema YAML file."""
    metadata = load_schema_metadata(schema_id, schema_dir)

    if metadata.get("description"):
        desc = metadata["description"].strip()
        return desc

    return f"Schema for {schema_id}"
