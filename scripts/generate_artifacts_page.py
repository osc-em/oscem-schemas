#!/usr/bin/env python3
"""
Dynamically generate the artifacts.md page by discovering versions from GitHub Pages.
This script fetches the actual deployed versions instead of maintaining a hardcoded list.
"""

import sys
import json
import os
from pathlib import Path
from typing import List, Dict, Optional
import urllib.request
import urllib.error

from schema_utils import (
    format_schema_name,
    get_schema_description,
    get_schema_sort_key,
    is_main_schema,
)


def fetch_github_pages_versions(token: Optional[str] = None) -> List[str]:
    """
    Fetch available versions from the GitHub Pages artifacts directory.
    This queries the GitHub API to list directories in the gh-pages branch.
    
    Args:
        token: Optional GitHub token for authenticated requests
    """
    api_url = "https://api.github.com/repos/osc-em/oscem-schemas/contents/artifacts?ref=gh-pages"

    try:
        req = urllib.request.Request(api_url)
        if token:
            req.add_header("Authorization", f"token {token}")
        
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())

        # Filter for directories that look like version tags
        versions = []
        for item in data:
            if item["type"] == "dir":
                name = item["name"]
                # Include version tags (v1.0.0, etc.) but exclude 'latest'
                if name.startswith("v") and name[1:2].isdigit():
                    versions.append(name)

        # Sort versions in reverse order (newest first)
        versions.sort(reverse=True)
        return versions

    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("Warning: gh-pages branch or artifacts directory not found", file=sys.stderr)
            return []
        raise
    except Exception as e:
        print(f"Warning: Could not fetch versions from GitHub Pages: {e}", file=sys.stderr)
        return []


def discover_schema_types(project_dir: Path) -> List[Dict[str, str]]:
    """
    Discover available schema types from the project directory.
    Returns a list of dicts with 'id', 'name', and 'description'.
    """
    if not project_dir.exists():
        print(f"Warning: {project_dir} does not exist.", file=sys.stderr)
        return []

    schema_types = []
    for subdir in sorted(project_dir.iterdir(), key=lambda p: get_schema_sort_key(p.name)):
        if subdir.is_dir():
            schema_id = subdir.name
            # Convert directory name to a display name
            # e.g., 'spa' -> 'Single Particle Analysis (SPA)'
            schema_name = format_schema_name(schema_id)
            schema_types.append({
                "id": schema_id,
                "name": schema_name,
                "description": get_schema_description(schema_id)
            })

    return schema_types if schema_types else []


def generate_artifacts_page(versions: List[str], schema_types: List[Dict[str, str]]) -> str:
    """Generate the complete artifacts.md content."""

    # Separate main and supporting schemas
    main_schemas = [s for s in schema_types if is_main_schema(s["id"])]
    supporting_schemas = [s for s in schema_types if not is_main_schema(s["id"])]

    # Build schema links for main schemas
    main_links = []
    for schema in main_schemas:
        main_links.append(
            f"- [{schema['name']}](https://osc-em.github.io/oscem-schemas/artifacts/latest/{schema['id']}/)"
        )
    
    # Build schema links for supporting schemas
    supporting_links = []
    for schema in supporting_schemas:
        supporting_links.append(
            f"- [{schema['name']}](https://osc-em.github.io/oscem-schemas/artifacts/latest/{schema['id']}/)"
        )

    # Build version list
    version_links = []
    for version in versions:
        version_links.append(
            f"- [{version}](https://osc-em.github.io/oscem-schemas/artifacts/{version}/)"
        )

    version_list = "\n".join(version_links) if version_links else "- No versions deployed yet"
    main_list = "\n".join(main_links)
    supporting_list = "\n".join(supporting_links)

    content = f"""# Schema Artifacts

This page provides access to all versions of the generated schema artifacts in various formats.

## Latest Version

Browse the latest release artifacts:

- [**Latest**](https://osc-em.github.io/oscem-schemas/artifacts/latest/)

### Main Technique Schemas

{main_list}

### Supporting Schemas

{supporting_list}

## Available Versions

{version_list}

## Permanent URLs via w3id.org

For stable, permanent URLs that will redirect to the latest version, use:
```
https://w3id.org/oscem-schemas/latest/{{schema_type}}/{{format}}/...
```

Example:
```
https://w3id.org/oscem-schemas/latest/spa/jsonschema/oscem_schemas_spa.schema.json
```

## Available Formats

Each schema type includes multiple formats for different use cases:

- **excel/** - Excel spreadsheets summarizing the schemas
- **graphql/** - GraphQL schema definitions
- **jsonld/** - JSON-LD context files
- **jsonschema/** - JSON Schema format (for validation)
- **owl/** - OWL ontology format
- **prefixmap/** - Prefix mapping files
- **protobuf/** - Protocol Buffer definitions
- **shacl/** - SHACL shapes
- **shex/** - ShEx schemas
- **sqlschema/** - SQL schema definitions
- **python script** - Python dataclass definitions

## Version History

New versions are deployed automatically when new releases are published. Each version remains accessible at its versioned URL.

---

*This page is automatically generated from deployed artifacts. Last updated: {versions[0] if versions else 'N/A'}*
"""
    return content


def main():
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    artifacts_file = repo_root / "docs" / "artifacts.md"
    project_dir = repo_root / "project"
    
    # Get GitHub token from environment if available
    github_token = os.environ.get("GITHUB_TOKEN")

    print("Fetching versions from GitHub Pages...")
    versions = fetch_github_pages_versions(token=github_token)
    print(f"Found {len(versions)} version(s): {', '.join(versions) if versions else 'none'}")

    print("Discovering schema types...")
    schema_types = discover_schema_types(project_dir)
    print(f"Found {len(schema_types)} schema type(s): {', '.join(s['id'] for s in schema_types)}")

    content = generate_artifacts_page(versions, schema_types)

    artifacts_file.parent.mkdir(parents=True, exist_ok=True)
    artifacts_file.write_text(content)
    print(f"Successfully generated {artifacts_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
