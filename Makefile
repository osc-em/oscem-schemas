MAKEFLAGS += --warn-undefined-variables
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help
.DELETE_ON_ERROR:
.SUFFIXES:
.SECONDARY:

# environment variables
.EXPORT_ALL_VARIABLES:
include config.public.mk

RUN = poetry run

# List all schema files in the schema directory
ALL_SCHEMA_FILES := $(wildcard src/oscem_schemas/schema/*.yaml)

# Extract all schema names without the directory and extension
ALL_SCHEMA_NAMES := $(notdir $(basename $(ALL_SCHEMA_FILES)))

# For backwards compatibility: main schemas that start with oscem_schemas_
MAIN_SCHEMA_FILES := $(wildcard src/oscem_schemas/schema/oscem_schemas_*.yaml)
SCHEMA_NAMES := $(notdir $(basename $(MAIN_SCHEMA_FILES)))
SCHEMA_NAMES := $(patsubst oscem_schemas_%,%,$(SCHEMA_NAMES))

SRC = src
DEST = project
DOCDIR = docs
EXAMPLEDIR = examples
SITE = site
PERMDOCS = perm_docs

CONFIG_YAML =
ifdef LINKML_GENERATORS_CONFIG_YAML
CONFIG_YAML = ${LINKML_GENERATORS_CONFIG_YAML}
endif

GEN_DOC_ARGS =
ifdef LINKML_GENERATORS_DOC_ARGS
GEN_DOC_ARGS = ${LINKML_GENERATORS_DOC_ARGS}
endif

# basename of a YAML file in model/
.PHONY:  setup gen-project git-init-add git-init git-add git-commit git-status

# note: "help" MUST be the first target in the file,
# when the user types "make" they should get help info
help: status
	@echo ""
	@echo "make setup -- initial setup (run this first)"
	@echo "make site -- makes site locally"
	@echo "make install -- install dependencies"
	@echo "make test -- runs tests"
	@echo "make lint -- perform linting"
	@echo "make testdoc -- builds docs and runs local test server"
	@echo "make serve -- serves docs locally"
	@echo "make -j serve-live -- serves docs locally, regenerating on schema changes"
	@echo "make deploy -- deploys site"
	@echo "make update -- updates linkml version"
	@echo "make gen-project -- generate artifacts for main schemas (oscem_schemas_*.yaml)"
	@echo "make gen-all-schemas -- generate artifacts for all schema files"
	@echo "make gen-artifacts -- alias for gen-all-schemas + examples"
	@echo "make help -- show this help"
	@echo ""

status: check-config
	@echo "Project: $(SCHEMA_NAME)"
	@echo "Source: $(SOURCE_SCHEMA_PATH)"

check-config:
ifndef LINKML_SCHEMA_NAME
	$(error **Project not configured**:\n\n - See '.env.public'\n\n)
else
	$(info Ok)
endif

# generate products and add everything to github
setup: check-config git-init install gen-project gen-examples gendoc git-add git-commit

# install any dependencies required for building
install:
	poetry install
.PHONY: install

# ---
# Project Synchronization
# ---
#
# check we are up to date
check: cruft-check
cruft-check:
	cruft check
cruft-diff:
	cruft diff

update: update-template update-linkml
update-template:
	cruft update

# todo: consider pinning to template
update-linkml:
	poetry add -D linkml@latest

# Generate code for main schemas (oscem_schemas_*.yaml)
.PHONY: gen-project
gen-project: $(SCHEMA_NAMES:%=gen-project-%)

gen-project-%:
	@echo "Generating code for schema $*"
	mkdir -p $(DEST)/$*
	$(RUN) gen-project $(CONFIG_YAML) -d $(DEST)/$* src/oscem_schemas/schema/oscem_schemas_$*.yaml

# Generate code for all schema files (including supporting schemas like instrument, acquisition, etc.)
.PHONY: gen-all-schemas
gen-all-schemas: $(ALL_SCHEMA_NAMES:%=gen-schema-%)

gen-schema-%:
	@echo "Generating artifacts for schema file $*"
	@# Use short name for main schemas (oscem_schemas_*), full name for supporting schemas
	@if [[ "$*" == oscem_schemas_* ]]; then \
		SCHEMA_DIR=$$(echo "$*" | sed 's/^oscem_schemas_//'); \
	else \
		SCHEMA_DIR="$*"; \
	fi; \
	mkdir -p "$(DEST)/$$SCHEMA_DIR"; \
	$(RUN) gen-project $(CONFIG_YAML) -d "$(DEST)/$$SCHEMA_DIR" src/oscem_schemas/schema/$*.yaml || \
		(echo "Warning: Could not generate artifacts for $$SCHEMA_DIR (may be import-only schema)" && rm -rf "$(DEST)/$$SCHEMA_DIR")

# Generate documentation for all schemas
.PHONY: gendoc
gendoc: $(SCHEMA_NAMES:%=gendoc-%)

gendoc-%:
	@echo "Generating documentation for schema $*"
	mkdir -p $(DOCDIR)/$*
	$(RUN) gen-doc --diagram-type er_diagram $(GEN_DOC_ARGS) -d $(DOCDIR)/$* src/oscem_schemas/schema/oscem_schemas_$*.yaml
	@# copy static files only after gen-doc succeeds, so a failed run leaves docs/ untouched
	cp -rf $(SRC)/docs/files/* $(DOCDIR)/$*
	cp $(PERMDOCS)/* $(DOCDIR)/

# Run gendoc for all schemas, showing output only on failure
gendoc-quiet:
	@log=$$(mktemp); \
	if $(MAKE) --no-print-directory gendoc > $$log 2>&1; then \
		printf '\033[1;32m==> gendoc succeeded\033[0m\n'; \
		rm -f $$log; \
	else \
		cat $$log; \
		printf '\a\n\033[1;41;97m ==> gendoc FAILED (see errors above; docs may be stale) \033[0m\n\n'; \
		rm -f $$log; \
		exit 1; \
	fi
.PHONY: gendoc-quiet


# Generate examples for all schemas
.PHONY: gen-examples
gen-examples: $(SCHEMA_NAMES:%=gen-examples-%)

gen-examples-%:
	@echo "Copying examples for schema $*"
	mkdir -p $(EXAMPLEDIR)
	cp -r src/data/examples/example_valid_$*.yaml $(EXAMPLEDIR)/example_valid_$*.yaml 2>/dev/null || true

# Run tests for all schemas
test-python: $(SCHEMA_NAMES:%=test-%)
test-lint: $(SCHEMA_NAMES:%=lint-%)
test-examples: $(SCHEMA_NAMES:%=examples-%)
test: test-lint test-examples
.PHONY: test test-lint test-examples

test-%:
	@echo "Running tests for schema $*"
	@if [ -f tests/test_$*.py ]; then \
		$(RUN) pytest tests/test_$*.py; \
	else \
		echo "No tests found for schema $*"; \
	fi

lint-%:
	@echo "Running lint for schema $*"
	$(RUN) linkml-lint --validate --all --ignore-warnings src/oscem_schemas/schema/oscem_schemas_$*.yaml; \

examples-%:
	@echo "Validating examples against schema $*"
	@if [ -f src/data/examples/example_valid_$*.yaml ]; then \
		$(RUN) linkml-validate -s src/oscem_schemas/schema/oscem_schemas_$*.yaml src/data/examples/example_valid_$*.yaml ; \
	else \
		echo "No example found"; \
	fi

##		 $(RUN) python -m unittest discover; \

prepare-mkdocs: $(SCHEMA_NAMES:%=prepare-mkdocs-%)

# two options, see which works better: 1 project/$*/$(DOCDIR) 2 $(DOCDIR)/$*
prepare-mkdocs-%:
	@echo "Preparing MkDocs configuration for schema $*"
	@mkdir -p $(DOCDIR)/$*
	@echo "site_name: 'OSC-EM_$*_Documentation'" > $(DOCDIR)/$*/mkdocs.yml
	@echo "theme:" >> $(DOCDIR)/$*/mkdocs.yml
	@echo "  name: material" >> $(DOCDIR)/$*/mkdocs.yml
	@echo "  features:" >> $(DOCDIR)/$*/mkdocs.yml
	@echo "    - content.tabs.link" >> $(DOCDIR)/$*/mkdocs.yml
	@echo "plugins:" >> $(DOCDIR)/$*/mkdocs.yml
	@echo "  - search" >> $(DOCDIR)/$*/mkdocs.yml
	@echo "  - mermaid2" >> $(DOCDIR)/$*/mkdocs.yml
	@echo "  - mermaid2:" >> $(DOCDIR)/$*/mkdocs.yml
	@echo "       version: 10.9.0" >> $(DOCDIR)/$*/mkdocs.yml

	@echo "docs_dir: '.'" >> $(DOCDIR)/$*/mkdocs.yml
	@echo "site_dir: ../../$(SITE)/$*" >> $(DOCDIR)/$*/mkdocs.yml
	@echo "nav:" >> $(DOCDIR)/$*/mkdocs.yml
	@echo "  - Home: index.md" >> $(DOCDIR)/$*/mkdocs.yml


	@echo "site_url: https://osc-em.github.io/oscem-schemas_$*" >> $(DOCDIR)/$*/mkdocs.yml
	@echo "repo_url: https://github.com/osc-em/oscem-schemas" >> $(DOCDIR)/$*/mkdocs.yml

# Build Independent MkDocs Sites
mkdocs-build:
	prepare-mkdocs $(SCHEMA_NAMES:%=build-%)

build-test-%:
	@echo "Building site for $*"
	$(RUN) mkdocs build -f $(DOCDIR)/$*/mkdocs.yml
# $(DOCDIR)/$*/
#-d $(SITE)/$*
build:
	@echo "Building site for $*"
	$(RUN) mkdocs build -f mkdocs.yml

# Serve a Specific Schema Locally
serve-test-%:
	@echo "Serving site for $*"
	$(RUN) mkdocs serve -f $(DOCDIR)/$*/mkdocs.yml -a 0.0.0.0:8000

serve:
	$(RUN) mkdocs serve -f mkdocs.yml -a 0.0.0.0:8000

# Serve docs, regenerating them whenever the schema or doc sources change.
# Extra watchmedo args; compose.yaml sets --debug-force-polling because file
# events from the host don't reliably reach Docker bind mounts
WATCH_ARGS =
serve-live: gendoc gen-project
	$(RUN) watchmedo shell-command --recursive --drop $(WATCH_ARGS) \
		--patterns='*.yaml;*.md;*.jinja2' \
		--command='$(MAKE) --no-print-directory -j gendoc gen-project' \
		src/oscem_schemas/schema $(SRC)/docs $(PERMDOCS) & \
	trap "kill $$! 2>/dev/null" EXIT; \
	$(RUN) mkdocs serve -f mkdocs.yml -a 0.0.0.0:8000 2>&1 | $(MKDOCS_LOG_FILTER)

# mkdocs doesn't have a flag for WARN-level verbosity.
MKDOCS_LOG_FILTER = awk '/^[A-Z]+ +- / {keep = !/^INFO/ || /Serving on|Reloading browsers/} \
	keep {print; fflush()}'


.PHONY: serve serve-live prepare-mkdocs mkdocs-build serve-all serve-test build-test

MKDOCS = $(RUN) mkdocs
mkd-%:
	$(MKDOCS) $*
mkdocs-deploy: $(MKDOCS) gh-deploy

git-init-add: git-init git-add git-commit git-status
git-init:
	git init
git-add: .cruft.json
	git add .
git-commit:
	git commit -m 'chore: make setup was run' -a
git-status:
	git status


# Clean generated files
.PHONY: clean
clean:
	rm -rf $(DEST)/*
	rm -rf $(DOCDIR)/* $(SITE)/*
	rm -rf $(EXAMPLEDIR)/*
#	rm -f mkdocs.yml

# Default target
.PHONY: all
gen-artifacts: gen-all-schemas gen-examples
all: gen-all-schemas gen-examples gendoc test
deploy: all mkdocs-deploy