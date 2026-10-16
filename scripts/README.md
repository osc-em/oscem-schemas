# Artifact Generation Scripts Documentation

### `generate_artifacts_page.py`

**Purpose**: Dynamically generates the `docs/artifacts.md` page by discovering versions from GitHub Pages.

**Usage**:
```bash
python3 scripts/generate_artifacts_page.py
```

**Description**:
1. Queries the GitHub API to discover all deployed versions in the `gh-pages` branch
2. Discovers available schema types from the `project/` directory
3. Generates a markdown page with links to all versions and schemas
4. MkDocs converts this to HTML with proper styling during the build process

**Used in**: `.github/workflows/release.yaml` during the release process

**Output**: The generated markdown is converted to HTML by MkDocs and deployed to `gh-pages/artifacts/index.html`

---

### `generate_index_pages.py`

**Purpose**: Creates `index.html` pages for artifact version directories (latest/, v1.0.2/, etc.).

**Usage**:
```bash
python3 scripts/generate_index_pages.py <project_dir> <output_dir> [version]
```

**Arguments**:
- `project_dir`: Path to the project directory containing schema subdirectories
- `output_dir`: Path where the index.html should be created
- `version` (optional): Version string to display in the page. Default: `latest`

**Description**:
1. Scans the project directory to discover all schema types
2. Generates an HTML index page with links to each schema type
3. Separates main technique schemas from supporting schemas
4. Includes descriptions for each schema type

**Used in**: `.github/workflows/release.yaml` to create browsable navigation pages for each version

**Output**: Creates `index.html` files at `gh-pages/artifacts/latest/` and `gh-pages/artifacts/v1.0.2/` etc.

---

### `schema_utils.py`

**Purpose**: Shared utility module for schema naming and descriptions.

**Used by**: Both `generate_artifacts_page.py` and `generate_index_pages.py`

**Note**: When updating the 'name' or 'description' at the top of a schema's YAML file, these changes will be automatically picked up next time the scripts run.
When adding a new schema file, make sure to include 'id', 'name' and 'description', and it will be automatically indexed in the docs.

---

## Development

### Running Locally

To test artifact generation locally:

```bash
# Generate artifacts for all schemas (simulates release workflow)
make gen-all-schemas

# Generate artifacts for main schemas only (oscem_schemas_*.yaml)
make gen-project

# Test the artifacts page generator
python3 scripts/generate_artifacts_page.py

# Test the index page generator
python3 scripts/generate_index_pages.py project /tmp/test-output latest
```

### Full Local Testing Workflow

To completely simulate what the release workflow will do:

```bash
# 1. Clean and generate all artifacts
make clean
make gen-all-schemas

# 2. Create local artifact pages (simulates GitHub Pages structure)
python3 scripts/generate_index_pages.py project /tmp/artifacts-test/latest latest
python3 scripts/generate_index_pages.py project /tmp/artifacts-test/v1.0.0 v1.0.0

# 3. Copy artifacts to test directory
cp -r project/* /tmp/artifacts-test/latest/
cp -r project/* /tmp/artifacts-test/v1.0.0/

# 4. Generate the artifacts.md documentation
python3 scripts/generate_artifacts_page.py

# 5. Serve locally to test navigation
cd /tmp/artifacts-test && python3 -m http.server 8080
# Then visit: http://localhost:8080
```

### Adding New Schema Types

The system automatically discovers new schema types - just add a new `.yaml` file to `src/oscem_schemas/schema/` and run `make gen-all-schemas`.
