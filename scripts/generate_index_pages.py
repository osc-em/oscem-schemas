#!/usr/bin/env python3
"""
Generate index.html pages for artifact directories dynamically.
This script discovers available schema types from the project directory and creates appropriate index pages.
"""

import sys
from pathlib import Path
from typing import List, Dict, Tuple

from schema_utils import format_schema_name, get_schema_description, get_schema_sort_key, is_main_schema


def discover_schemas(project_dir: Path) -> List[Dict[str, str]]:
    """Discover available schema types from the project directory."""
    schemas = []
    if not project_dir.exists():
        print(f"Warning: {project_dir} does not exist", file=sys.stderr)
        return schemas

    for subdir in sorted(project_dir.iterdir(), key=lambda p: get_schema_sort_key(p.name)):
        if subdir.is_dir():
            schemas.append({
                "id": subdir.name,
                "name": format_schema_name(subdir.name),
                "description": get_schema_description(subdir.name)
            })
    return schemas


def generate_html_page(title: str, heading: str, content: str, back_link: Tuple[str, str]) -> str:
    """Generate a new HTML page with consistent styling."""
    back_html = f'<p class="back-link"><a href="{back_link[0]}">{back_link[1]}</a></p>' if back_link else ''

    return f"""<!DOCTYPE html>
      <html>
      <head>
        <link rel="icon" href="https://raw.githubusercontent.com/osc-em/osc-em.github.io/refs/heads/main/docs/assets/img/oscem_icon.svg" type="image/svg+xml">
        <title>{title}</title>
        <style>
          body {{ font-family: Roboto, -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif; max-width: 900px; margin: 50px auto; padding: 20px; }}
          h1 {{ color: #333; }}
          h2 {{ color: #555; margin-top: 30px; margin-bottom: 10px; font-size: 1.3em; }}
          .intro {{ color: #666; margin: 20px 0; }}
          ul {{ list-style: none; padding: 0; }}
          li {{ margin: 10px 0; }}
          a {{ color: #0094ab; text-decoration: none; font-size: 18px; }}
          a:hover {{ text-decoration: underline; }}
          .description {{ color: #666; font-size: 14px; margin-left: 10px; }}
          .back-link {{ margin-top: 30px; }}
          .separator {{ border-top: 1px solid #ddd; margin: 25px 0; }}
        </style>
      </head>
      <body>
        {heading}
        {content}
        <div class="separator"></div>
        {back_html}
      </body>
      </html>"""


def generate_version_index(version: str, schemas: List[Dict[str, str]]) -> str:
    """Generate index.html for a specific version."""
    main_schemas = [s for s in schemas if is_main_schema(s['id'])]
    supporting_schemas = [s for s in schemas if not is_main_schema(s['id'])]
    version_title = "Latest Version" if version == "latest" else f"Version {version}"

    def schema_list(schemas):
        return '\n'.join(
            f'<li><a href="{s["id"]}/">{s["name"]}</a>'
            f'<span class="description">{s["description"]}</span></li>'
            for s in schemas
        )

    content = f"""<p class="intro">Select a schema type to browse the generated artifacts:</p>
      <h2>Main Technique Schemas</h2>
      <ul>
        {schema_list(main_schemas)}
      </ul>
      <div class="separator"></div>
      <h2>Supporting Schemas</h2>
      <ul>
        {schema_list(supporting_schemas)}
      </ul>"""

    return generate_html_page(
        f"Artifacts {version_title} - OSC-EM Schemas",
        f"<h1>OSC-EM Schemas - Artifacts {version_title}</h1>",
        content,
        ("https://osc-em.github.io/oscem-schemas/artifacts/", "Back to all versions")
    )


def generate_schema_index(schema_name: str, artifact_types: List[str], version: str) -> str:
    """Generate index.html for a specific schema directory."""
    version_title = "Latest Version" if version == "latest" else f"Version {version}"
    items = '\n'.join(f'<li><a href="{t}/">{t}</a></li>' for t in sorted(artifact_types))

    content = f"""<p class="intro">Available artifact types:</p>
      <ul>
        {items}
      </ul>"""

    return generate_html_page(
        f"{schema_name} {version_title} - OSC-EM Schemas",
        f"<h1>{schema_name} - {version_title}</h1>",
        content,
        ("../", "Back to all schemas")
    )


def generate_artifact_type_index(schema_name: str, artifact_type: str, files: List[str], version: str) -> str:
    """Generate index.html for a specific artifact type directory."""
    version_title = "Latest Version" if version == "latest" else f"Version {version}"
    items = '\n'.join(f'<li><a href="{f}">{f}</a></li>' for f in sorted(files))

    content = f"""<h2>{artifact_type}</h2>
      <p class="intro">Available files:</p>
      <ul>
        {items}
      </ul>"""

    return generate_html_page(
        f"{artifact_type} - {schema_name} {version_title} - OSC-EM Schemas",
        f"<h1>{schema_name} - {version_title}</h1>",
        content,
        ("../", f"Back to {schema_name}")
    )


def main():
    if len(sys.argv) < 3:
        print("Usage: generate_index_pages.py <project_dir> <output_dir> [version]", file=sys.stderr)
        return 1

    project_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    version = sys.argv[3] if len(sys.argv) > 3 else "latest"

    print(f"Generating index pages for version: {version}")
    print(f"Project directory: {project_dir}")
    print(f"Output directory: {output_dir}")

    schemas = discover_schemas(project_dir)
    print(f"Found {len(schemas)} schema type(s): {', '.join(s['id'] for s in schemas)}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate version-level index page
    index_html = generate_version_index(version, schemas)
    (output_dir / "index.html").write_text(index_html)
    print(f"Generated {output_dir / 'index.html'}")

    # Generate schema-level and artifact-type-level index pages
    index_count = 1
    for schema in schemas:
        schema_id, schema_name = schema['id'], schema['name']
        schema_dir = project_dir / schema_id

        if not schema_dir.exists():
            continue

        # Discover artifact types
        artifact_types = [item.name for item in schema_dir.iterdir() if item.is_dir()]

        # Generate schema-level index
        schema_output_dir = output_dir / schema_id
        schema_output_dir.mkdir(parents=True, exist_ok=True)
        schema_index_file = schema_output_dir / "index.html"
        schema_index_file.write_text(generate_schema_index(schema_name, artifact_types, version))
        print(f"Generated {schema_index_file}")
        index_count += 1

        # Generate artifact-type-level indexes
        for artifact_type in artifact_types:
            files = [f.name for f in (schema_dir / artifact_type).iterdir() if f.is_file()]

            if files:
                artifact_output_dir = schema_output_dir / artifact_type
                artifact_output_dir.mkdir(parents=True, exist_ok=True)
                artifact_index_file = artifact_output_dir / "index.html"
                artifact_index_file.write_text(
                    generate_artifact_type_index(schema_name, artifact_type, files, version)
                )
                print(f"Generated {artifact_index_file}")
                index_count += 1

    print(f"Total index pages generated: {index_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
