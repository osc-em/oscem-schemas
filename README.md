# OSC-EM Schemas

This repository contains schema definitions for the _Open Standards Community for Electron Microscopy_ (OSC-EM).

## Overview

The OSC-EM schemas are designed to standardize metadata for electron microscopy, structured modularly to accommodate various methods and use cases. Each module can represent different aspects of an experiment, such as "sample", "instrument", "author" and "processing". These modules are combined into a comprehensive schema that defines the required metadata for a specific method. This standard ensures consistency in data collection, facilitates data validation, and enhances comparability between datasets.

To increase compatibility with different formats, we utilize [LinkML](https://linkml.io/), which allows us to export the schema to widely used formats.

## Currently implemented schemas

Five schemas are currently implemented. The `general` schema is the broadest definition, while other schemas specify additional structure relevant for particular experimental techniques.

1. `general`: **General** metadata schema. Used for materials science and general EM data.
2. `spa`: **Single particle analysis**
3. `subtomo`: **Subtomogram averaging**
4. `cellular_tomo`: **Cellular tomography** with a well-characterized sample
5. `env_tomo`: **Environmental tomography** on samples taken from the environment.

## Usage

### Source Schemas

All schemas are available in YAML format under the directory `src/oscem_schemas/schema`. Files prefixed with `oscem_*` refer to collections of subschemas, such as those for single particle analysis. Files with more specific names, like "instrument," represent individual subschemas that can be modularly incorporated into `oscem_*` schemas.

### Generated Artifacts

Schemas are automatically exported to various formats (JSON Schema, JSON-LD, OWL, GraphQL, etc.) and made available through:

- **Persistent URLs**: (Recommended) Access via `w3id.org` for stable, citable links
  that will always resolve to a valid file:
  - URL Pattern: `https://w3id.org/oscem-schemas/{VERSION}/{SCHEMA}/{FORMAT}/{FILE}`
- **GitHub Pages**: Direct access to the release artifacts without a redirect:
  - URL Pattern: `https://osc-em.github.io/oscem-schemas/artifacts/{VERSION}/{SCHEMA}/{FORMAT}/{FILE}`
  - Browse all versions: [Artifacts Documentation](https://osc-em.github.io/oscem-schemas/artifacts)
- **Release Assets**: Downloadable zip archives from [GitHub Releases](https://github.com/osc-em/oscem-schemas/releases)

`VERSION` can be 'latest' or any valid git release (eg `v1.0.0`). `SCHEMA` can refer to any of the main technique schemas (spa, cellular_tomo, env_tomo, subtomo, general) or supporting schemas (instrument, acquisition, processing, etc.). The following `FORMAT` values are supported:

| FORMAT     | FILE                                    |
| ---------- | --------------------------------------- |
| excel      | `oscem_schemas_{SCHEMA}.xlsx`           |
| graphql    | `oscem_schemas_{SCHEMA}.graphql`        |
| java       | `oscem_schemas_{SCHEMA}.java`           |
| jsonld     | `oscem_schemas_{SCHEMA}.jsonld`         |
| jsonld     | `oscem_schemas_{SCHEMA}.context.jsonld` |
| jsonschema | `oscem_schemas_{SCHEMA}.schema.json`    |
| owl        | `oscem_schemas_{SCHEMA}.owl.ttl`        |
| prefixmap  | `oscem_schemas_{SCHEMA}.yaml`           |
| protobuf   | `oscem_schemas_{SCHEMA}.proto`          |
| shacl      | `oscem_schemas_{SCHEMA}.shacl.ttl`      |
| shex       | `oscem_schemas_{SCHEMA}.shex`           |
| sqlschema  | `oscem_schemas_{SCHEMA}.sql`            |

For example, the latest json schema files can be accessed at

- <https://w3id.org/oscem-schemas/latest/general/jsonschema/oscem_schemas_general.schema.json>
- <https://w3id.org/oscem-schemas/latest/spa/jsonschema/oscem_schemas_spa.schema.json>
- <https://w3id.org/oscem-schemas/latest/subtomo/jsonschema/oscem_schemas_subtomo.schema.json>
- <https://w3id.org/oscem-schemas/latest/cellular_tomo/jsonschema/oscem_schemas_cellular_tomo.schema.json>
- <https://w3id.org/oscem-schemas/latest/env_tomo/jsonschema/oscem_schemas_env_tomo.schema.json>

You can also access supporting schemas (instrument, acquisition, etc.) individually:

- <https://w3id.org/oscem-schemas/latest/instrument/jsonschema/instrument.schema.json>
- <https://w3id.org/oscem-schemas/latest/acquisition/jsonschema/acquisition.schema.json>

For metadata validation, we recommend using the JSON Schema versions.

## Documentation

Detailed descriptions of the schemas and individual terms can be viewed in the [schema
documentation](https://osc-em.github.io/oscem-schemas/), which is automatically updated
from LinkML.

## Developer Documentation

### Repository Structure

- [src/](src/) - source files (edit these)
  - [oscem_schemas](src/oscem_schemas)
    - [schema](src/oscem_schemas/schema) -- LinkML schema files (edit these). Files starting with `oscem_schemas_` are main technique schemas; others are supporting modules.
    - [datamodel](src/oscem_schemas/datamodel) -- generated Python datamodel
- [tests/](tests/) - Python tests
- [tests/data/examples/](tests/data/examples/) - example data
- [perm_docs/](perm_docs/) - permanent documentation files
- [src/docs/files/](src/docs/files/) - additional documentation
- [scripts/](scripts/) - automation scripts for artifact generation

**Note**: Generated artifacts (JSON Schema, OWL, etc.) are not stored in the repository. They are automatically generated and deployed to GitHub Pages on each release. See [artifacts documentation](https://osc-em.github.io/oscem-schemas/artifacts) for available versions.

### Building the project

Use the `make` command to generate project artifacts:

- `make setup`: one-time setup
- `make all`: make everything
- `make gen-project`: generate schema outputs
- `make gendocs`: generate documentation
- `make deploy`: deploys site
- `make test`: run tests and linting
- `make serve`: run docs locally on <http://127.0.0.1:8000/oscem-schemas/>
- `make serve-live`: run docs locally, rebuilding automatically on schema changes
- `make gen-all-schemas`: generate artifacts for all schema files (main + supporting)
- `make gen-project`: generate artifacts for main schemas only (oscem_schemas_*.yaml)
- `make clean` : remove generated files

**Development workflow**: Edit source schemas in `src/oscem_schemas/schema/`, run `make gen-all-schemas` locally for testing, then create a release to deploy artifacts.

### Project Structure Notes

This project uses a multi-schema approach with automated deployment:

- **Multiple schemas**: Targets multiple schemas following the `oscem_schemas_*.yaml` pattern in `src/oscem_schemas/schema/` where `*` corresponds to the schema name (spa, cellular_tomo, etc.). These are the main technique schemas.
- **Supporting schemas**: Individual module schemas (instrument, acquisition, processing, etc.) that are imported by the main schemas. These can also be accessed independently.
- **Automatic discovery**: New schemas are automatically discovered and included in artifact generation. Schema metadata (name, description) is read directly from the YAML files.
- **Documentation**: Generates an overall documentation webpage with subpages for each schema. The [artifacts page](https://osc-em.github.io/oscem-schemas/artifacts) is automatically updated with all available versions and schemas.
- **Examples**: Example data goes in `src/data/examples/` following the pattern `example_valid_*.yaml`
- **Automated deployment**: On each release, artifacts are automatically:
  - Generated in multiple formats (JSON Schema, OWL, JSON-LD, etc.) for all schemas
  - Deployed to GitHub Pages for permanent URLs with browsable navigation
  - Created as downloadable release assets (per-schema zip archives)
  - Published to PyPI as a Python package

For more information, please read the [Artifact Generation Scripts documentation](./scripts/README.md).

### Adding a New Schema

To add a new schema:

1. Create a YAML file in `src/oscem_schemas/schema/` with standard LinkML structure including `id`, `name`, and `description` fields
2. If it's a main technique schema, name it `oscem_schemas_*.yaml`; otherwise use a descriptive name for supporting schemas. Remember that for new main schemas the following changes are required, to update the website:
    - Add the navigation link in [mkdocs.yml](./mkdocs.yml)
    - Add it in the list of available schemas in [./perm_docs/index.md](./perm_docs/index.md)
3. Run `make gen-all-schemas` to test locally
4. The schema will automatically appear in all generated documentation and artifacts on the next release

No code changes needed - the system automatically discovers and processes new schemas.
For more information, please read the [Artifact Generation Scripts documentation](./scripts/README.md).

## Credits

This project was made with
[linkml-project-cookiecutter](https://github.com/linkml/linkml-project-cookiecutter).
