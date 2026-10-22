#!/usr/bin/env python3
"""
Apply SSSOM mapping files to the OSC-EM LinkML schema modules.

Each row maps an OSC-EM term (a slot, class or enum in the https://w3id.org/oscem-schemas/
namespace) to an external term. The OSC-EM term may be either the subject or the object;
if it is the object, the predicate is inverted (broadMatch <-> narrowMatch). The OSC-EM
term gets:
- the external CURIE in the LinkML mapping slot matching the predicate
  (skos:exactMatch -> exact_mappings, skos:closeMatch -> close_mappings, ...)
- the links in the row's see_also column in see_also (SSSOM separates multiple values
  with |). Rows without see_also use the external CURIE, so leave the column empty when
  the external IRIs resolve to useful pages, and fill it when they don't (e.g. PDBx).
- the prefixes of the external CURIE and of the see_also links declared in the module

URLs in see_also are compacted using the mapping file's curie_map.

The mapping file is the source of truth for the external prefixes it uses (e.g. emg:,
or pdbx: and the see_also prefix mmcif:).
For each OSC-EM term in the file, mappings with those prefixes that are no longer in the
file (e.g. after changing the predicate or the external term) are removed. Mappings with
other prefixes are left untouched, as are elements not mentioned in the file.

Schema files are edited line by line rather than re-serialized, so formatting and
comments elsewhere in the file are preserved.

Usage:
    poetry run python scripts/apply_sssom_mappings.py [--check] MAPPING.sssom.tsv

Applies one mapping file; `make apply-mappings` runs it over src/mappings/*.sssom.tsv.
With --check, nothing is written and the exit status is 1 if any schema file would change.
"""

import argparse
import csv
import difflib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from linkml_runtime import SchemaView
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

REPO_DIR = Path(__file__).parent.parent
SCHEMA_DIR = REPO_DIR / "src" / "oscem_schemas" / "schema"

# Prefixes that SSSOM files may use without declaring them in the curie_map
BUILTIN_PREFIXES = {
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "semapv": "https://w3id.org/semapv/vocab/",
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "sssom": "https://w3id.org/sssom/",
}

SKOS = BUILTIN_PREFIXES["skos"]
PREDICATE_SLOTS = {
    SKOS + "exactMatch": "exact_mappings",
    SKOS + "closeMatch": "close_mappings",
    SKOS + "broadMatch": "broad_mappings",
    SKOS + "narrowMatch": "narrow_mappings",
    SKOS + "relatedMatch": "related_mappings",
}
# Predicate to use when the OSC-EM term is the object; the others are symmetric
INVERSE_PREDICATES = {
    SKOS + "broadMatch": SKOS + "narrowMatch",
    SKOS + "narrowMatch": SKOS + "broadMatch",
}
OSCEM_NAMESPACE = "https://w3id.org/oscem-schemas/"
# Order in which new keys are added to an element
MANAGED_SLOTS = ["see_also"] + list(PREDICATE_SLOTS.values())

SECTIONS = {"slots": "slot", "classes": "class", "enums": "enum"}


class MappingError(Exception):
    pass


@dataclass(frozen=True)
class Element:
    path: Path
    section: str  # slots, classes or enums
    name: str

    def __str__(self):
        return f"{self.path.name}: {SECTIONS[self.section]} {self.name}"


@dataclass
class MappingRow:
    line: int
    subject_id: str
    subject_label: str
    predicate_id: str
    object_id: str
    object_label: str
    see_also: List[str]


# --- SSSOM ---------------------------------------------------------------------------


def read_sssom(path: Path) -> Tuple[dict, List[MappingRow]]:
    """Read an SSSOM/TSV file. Returns the metadata block and the mapping rows."""
    header_lines = []
    body_start = 0
    lines = path.read_text().splitlines()
    for body_start, line in enumerate(lines):
        if not line.startswith("#"):
            break
        header_lines.append(line[1:])
    metadata = yaml.safe_load("\n".join(header_lines)) or {}

    reader = csv.DictReader(lines[body_start:], delimiter="\t")
    missing = {"subject_id", "predicate_id", "object_id"} - set(reader.fieldnames or [])
    if missing:
        raise MappingError(f"{path}: missing columns {', '.join(sorted(missing))}")
    rows = []
    for i, rec in enumerate(reader):
        if not any((v or "").strip() for v in rec.values() if isinstance(v, str)):
            continue
        rows.append(
            MappingRow(
                line=body_start + 2 + i,  # 1-based, after the column header line
                subject_id=rec["subject_id"].strip(),
                subject_label=(rec.get("subject_label") or "").strip(),
                predicate_id=rec["predicate_id"].strip(),
                object_id=rec["object_id"].strip(),
                object_label=(rec.get("object_label") or "").strip(),
                see_also=[v.strip() for v in (rec.get("see_also") or "").split("|") if v.strip()],
            )
        )
    return metadata, rows


def expand(curie: str, prefixes: Dict[str, str]) -> Optional[str]:
    """Expand a CURIE to a URI. Full URIs are returned unchanged; unknown prefixes give None."""
    if "://" in curie:
        return curie
    prefix, sep, local = curie.partition(":")
    if not sep or prefix not in prefixes:
        return None
    return prefixes[prefix] + local


def compact(uri: str, prefixes: Dict[str, str]) -> str:
    for prefix, base in sorted(prefixes.items(), key=lambda kv: -len(kv[1])):
        if uri.startswith(base):
            return f"{prefix}:{uri[len(base):]}"
    return uri


# --- Schema index --------------------------------------------------------------------


def schema_prefixes(schema: dict) -> Dict[str, str]:
    prefixes = {}
    for key, val in (schema.get("prefixes") or {}).items():
        prefixes[key] = val["prefix_reference"] if isinstance(val, dict) else val
    return prefixes


def index_schemas(schema_dir: Path) -> Dict[str, List[Element]]:
    """Map the URI of every slot, class and enum to the element(s) defining it.

    Both the native URI (default_prefix + name) and any explicit slot_uri/class_uri
    are indexed.
    """
    index: Dict[str, List[Element]] = {}
    for path in sorted(schema_dir.glob("*.yaml")):
        sv = SchemaView(str(path))
        for section, elements in (
            ("slots", sv.schema.slots),
            ("classes", sv.schema.classes),
            ("enums", sv.schema.enums),
        ):
            for name in elements:
                elem = Element(path, section, name)
                schema_elem = sv.get_element(name)
                uris = {
                    sv.get_uri(schema_elem, expand=True, native=True),
                    sv.get_uri(schema_elem, expand=True),
                }
                for uri in uris:
                    index.setdefault(uri, []).append(elem)
    return index


def suggest(label: str, uri: str, index, prefixes) -> str:
    candidates = []
    if label:
        names = {e.name: uri for uri, elems in index.items() for e in elems}
        candidates += [names[n] for n in difflib.get_close_matches(label, names, n=3, cutoff=0.8)]
    candidates += difflib.get_close_matches(uri, index.keys(), n=3, cutoff=0.9)
    seen = []
    for uri in candidates:
        for elem in index[uri]:
            hint = f"{compact(uri, prefixes)} ({elem})"
            if hint not in seen:
                seen.append(hint)
    return f" Did you mean: {'; '.join(seen[:3])}?" if seen else ""


# --- Line-based YAML editing -----------------------------------------------------------


class YamlText:
    """A YAML file edited line by line, using PyYAML node positions to locate content."""

    def __init__(self, path: Path):
        self.path = path
        self.lines = path.read_text().splitlines(keepends=True)
        self.original = "".join(self.lines)

    @property
    def text(self) -> str:
        return "".join(self.lines)

    def root(self) -> MappingNode:
        return yaml.compose(self.text, Loader=yaml.SafeLoader)

    @staticmethod
    def get(node: Node, key: str) -> Tuple[Optional[ScalarNode], Optional[Node]]:
        if isinstance(node, MappingNode):
            for k, v in node.value:
                if k.value == key:
                    return k, v
        return None, None

    def last_line(self, node: Node) -> int:
        """0-based index of the last non-blank line belonging to node."""
        if isinstance(node, MappingNode) and node.value and not node.flow_style:
            return self.last_line(node.value[-1][1])
        if isinstance(node, SequenceNode) and node.value and not node.flow_style:
            return self.last_line(node.value[-1])
        end = node.end_mark
        line = end.line
        if end.column == 0 and line > node.start_mark.line:
            line -= 1
        while line > node.start_mark.line and not self.lines[line].strip():
            line -= 1
        return line

    def insert(self, index: int, new_lines: List[str]):
        if index > 0 and not self.lines[index - 1].endswith("\n"):
            self.lines[index - 1] += "\n"
        self.lines[index:index] = [line + "\n" for line in new_lines]

    def ensure_prefix(self, prefix: str, uri: str) -> bool:
        _, prefixes = self.get(self.root(), "prefixes")
        if not isinstance(prefixes, MappingNode) or prefixes.flow_style or not prefixes.value:
            raise MappingError(f"{self.path.name}: no block 'prefixes:' section to add {prefix} to")
        key, val = self.get(prefixes, prefix)
        if key is not None:
            existing = self.get(val, "prefix_reference")[1] if isinstance(val, MappingNode) else val
            if existing is None or existing.value != uri:
                raise MappingError(
                    f"{self.path.name}: prefix {prefix} is declared as "
                    f"{existing.value if existing else '?'}, but the mapping file uses {uri}"
                )
            return False
        indent = " " * prefixes.value[0][0].start_mark.column
        self.insert(self.last_line(prefixes) + 1, [f"{indent}{prefix}: {uri}"])
        return True

    def element_node(self, elem: Element) -> Tuple[ScalarNode, Node]:
        _, section = self.get(self.root(), elem.section)
        key, val = self.get(section, elem.name)
        if key is None:
            raise MappingError(f"{elem}: not found in file")
        if isinstance(val, MappingNode) and val.flow_style:
            raise MappingError(f"{elem}: flow-style mappings are not supported")
        return key, val

    def list_items(self, elem: Element, slot: str) -> List[str]:
        _, node = self.element_node(elem)
        _, val = self.get(node, slot)
        if val is None or (isinstance(val, ScalarNode) and val.value in ("", "null", "~")):
            return []
        if isinstance(val, ScalarNode):
            return [val.value]
        if isinstance(val, SequenceNode) and all(isinstance(i, ScalarNode) for i in val.value):
            return [i.value for i in val.value]
        raise MappingError(f"{elem}: {slot} must be a list of CURIEs")

    def set_list(self, elem: Element, slot: str, items: List[str]):
        """Make elem.slot equal to items, touching as few lines as possible."""
        current = self.list_items(elem, slot)
        if current == items:
            return
        key, node = self.element_node(elem)
        slot_key, val = self.get(node, slot)

        block_seq = isinstance(val, SequenceNode) and not val.flow_style and val.value
        kept = [i for i in current if i in items]
        if block_seq and kept and kept == [i for i in items if i in current]:
            # Only removals and appends: edit individual item lines
            for item in reversed(val.value):
                if item.value not in items:
                    del self.lines[item.start_mark.line : self.last_line(item) + 1]
            _, val = self.get(self.element_node(elem)[1], slot)
            last = val.value[-1]
            item_prefix = self.lines[last.start_mark.line][: last.start_mark.column]
            if not item_prefix.strip().startswith("-"):
                item_prefix = " " * (last.start_mark.column - 2) + "- "
            self.insert(
                self.last_line(last) + 1, [item_prefix + i for i in items if i not in current]
            )
            return

        # Otherwise (re)write the whole key
        if slot_key is not None:
            indent = " " * slot_key.start_mark.column
            start = slot_key.start_mark.line
            del self.lines[start : self.last_line(val) + 1]
        elif isinstance(node, MappingNode) and node.value:
            indent = " " * node.value[0][0].start_mark.column
            start = self.last_line(node) + 1
        else:
            # Element with no body, e.g. "  foo:"
            if not isinstance(node, ScalarNode) or node.value not in ("", "null", "~"):
                raise MappingError(f"{elem}: unexpected element body")
            line = self.lines[key.start_mark.line]
            self.lines[key.start_mark.line] = line[: line.index(":", key.start_mark.column) + 1] + "\n"
            indent = " " * (key.start_mark.column + 2)
            start = key.start_mark.line + 1
        if items:
            self.insert(start, [f"{indent}{slot}:"] + [f"{indent}  - {i}" for i in items])

    def write(self) -> bool:
        if self.text == self.original:
            return False
        self.path.write_text(self.text)
        return True


# --- Applying mappings -----------------------------------------------------------------


def apply_mapping_file(path, index, files: Dict[Path, YamlText], log) -> List[str]:
    """Apply one SSSOM file to the in-memory schema files. Returns a list of errors."""
    errors = []
    metadata, rows = read_sssom(path)
    sssom_prefixes = {**BUILTIN_PREFIXES, **(metadata.get("curie_map") or {})}

    # Resolve rows and group by OSC-EM element
    desired: Dict[Element, Dict[str, List[str]]] = {}
    external_prefixes: Dict[str, str] = {}  # prefixes of the external terms and see_also links
    for row in rows:
        where = f"{path.name}:{row.line}"
        predicate = expand(row.predicate_id, sssom_prefixes)
        if predicate not in PREDICATE_SLOTS:
            errors.append(f"{where}: unsupported predicate {row.predicate_id}")
            continue

        # Orient the row so that term_id is the OSC-EM side
        subject_uri = expand(row.subject_id, sssom_prefixes)
        object_uri = expand(row.object_id, sssom_prefixes)
        subject_is_oscem = (subject_uri or "").startswith(OSCEM_NAMESPACE)
        object_is_oscem = (object_uri or "").startswith(OSCEM_NAMESPACE)
        if subject_is_oscem == object_is_oscem:
            which = "both are" if subject_is_oscem else "neither is"
            errors.append(
                f"{where}: {row.subject_id} and {row.object_id}: {which} an OSC-EM term "
                f"(expected exactly one in {OSCEM_NAMESPACE})"
            )
            continue
        if subject_is_oscem:
            term_id, term_uri, term_label, mapped_id = row.subject_id, subject_uri, row.subject_label, row.object_id
        else:
            term_id, term_uri, term_label, mapped_id = row.object_id, object_uri, row.object_label, row.subject_id
            predicate = INVERSE_PREDICATES.get(predicate, predicate)

        mapped_prefix = mapped_id.partition(":")[0]
        if expand(mapped_id, sssom_prefixes) is None or "://" in mapped_id:
            errors.append(f"{where}: {mapped_id} is not a CURIE with a prefix in the curie_map")
            continue
        external_prefixes[mapped_prefix] = sssom_prefixes[mapped_prefix]

        links = []
        for link in row.see_also:
            curie = compact(link, sssom_prefixes) if "://" in link else link
            if "://" not in curie:
                prefix = curie.partition(":")[0]
                if prefix not in sssom_prefixes:
                    errors.append(f"{where}: see_also {link} has a prefix not in the curie_map")
                    continue
                external_prefixes[prefix] = sssom_prefixes[prefix]
            links.append(curie)

        elems = index.get(term_uri, [])
        if not elems:
            errors.append(
                f"{where}: {term_id} ({term_label}) not found in the schema."
                + suggest(term_label, term_uri, index, sssom_prefixes)
            )
            continue
        if len(elems) > 1:
            errors.append(f"{where}: {term_id} is ambiguous: {'; '.join(map(str, elems))}")
            continue
        elem = elems[0]

        slots = desired.setdefault(elem, {s: [] for s in MANAGED_SLOTS})
        if any(mapped_id in slots[s] for s in PREDICATE_SLOTS.values()):
            errors.append(f"{where}: {term_id} is mapped to {mapped_id} more than once")
            continue
        for link in links if row.see_also else [mapped_id]:
            if link not in slots["see_also"]:
                slots["see_also"].append(link)
        slots[PREDICATE_SLOTS[predicate]].append(mapped_id)

    if errors:
        return errors

    managed_bases = tuple(external_prefixes.values())

    # Apply to each element
    for elem, slots in desired.items():
        doc = files.setdefault(elem.path, YamlText(elem.path))
        for prefix, uri in external_prefixes.items():
            if any(i.startswith(prefix + ":") for items in slots.values() for i in items):
                if doc.ensure_prefix(prefix, uri):
                    log(f"{elem.path.name}: added prefix {prefix}: {uri}")
        file_prefixes = {**sssom_prefixes, **schema_prefixes(yaml.safe_load(doc.text))}

        def managed(curie):
            uri = expand(curie, file_prefixes)
            return uri is not None and uri.startswith(managed_bases)

        for slot in MANAGED_SLOTS:
            current = doc.list_items(elem, slot)
            wanted = slots[slot]
            wanted_uris = {expand(i, file_prefixes) for i in wanted}
            kept = [i for i in current if not managed(i) or expand(i, file_prefixes) in wanted_uris]
            kept_uris = {expand(i, file_prefixes) for i in kept}
            new = kept + [i for i in wanted if expand(i, file_prefixes) not in kept_uris]
            for i in current:
                if i not in new:
                    log(f"{elem}: {slot} - {i}")
            for i in new:
                if i not in current:
                    log(f"{elem}: {slot} + {i}")
            doc.set_list(elem, slot, new)

    # Report elements carrying managed mappings that the file doesn't mention
    for path_ in sorted({e.path for elems in index.values() for e in elems}):
        doc = files.get(path_) or YamlText(path_)
        data = yaml.safe_load(doc.text) or {}
        file_prefixes = {**sssom_prefixes, **schema_prefixes(data)}
        for section in SECTIONS:
            for name, body in (data.get(section) or {}).items():
                elem = Element(path_, section, name)
                if elem in desired or not isinstance(body, dict):
                    continue
                stale = [
                    i
                    for slot in MANAGED_SLOTS
                    for i in (body.get(slot) or [])
                    if (expand(str(i), file_prefixes) or "").startswith(managed_bases)
                ]
                if stale:
                    log(f"warning: {elem}: has {', '.join(stale)} but is not in {path.name}; left unchanged")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mapping", type=Path, help="SSSOM/TSV file to apply")
    parser.add_argument("--schema-dir", type=Path, default=SCHEMA_DIR, help="directory with the LinkML modules")
    parser.add_argument("--check", action="store_true", help="don't write; exit 1 if any file would change")
    args = parser.parse_args()

    index = index_schemas(args.schema_dir)
    files: Dict[Path, YamlText] = {}
    try:
        errors = apply_mapping_file(args.mapping, index, files, lambda msg: print(msg, file=sys.stderr))
    except MappingError as e:
        errors = [str(e)]

    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        print("No files were changed.", file=sys.stderr)
        return 2

    changed = [doc for doc in files.values() if doc.text != doc.original]
    for doc in changed:
        yaml.safe_load(doc.text)  # sanity check: edits must leave valid YAML
    if args.check:
        for doc in changed:
            print(f"would update {doc.path}", file=sys.stderr)
        return 1 if changed else 0
    for doc in changed:
        doc.write()
        print(f"updated {doc.path}", file=sys.stderr)
    if not changed:
        print("Schemas already match the mappings.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
