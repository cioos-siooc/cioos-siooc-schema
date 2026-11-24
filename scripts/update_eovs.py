"""Rewrite the eov field's choices in cioos-siooc_schema.json from cioos-commons.

cioos-commons/eov.json is synced from cioos-commons (eovs/eov.json) by its
sync-repos workflow; edit the vocabulary there, not here. Run after it changes:

    python scripts/update_eovs.py          # rewrite the schema
    python scripts/update_eovs.py --check  # exit 1 if the schema is out of date
    python scripts/update_eovs.py --report base.json report.md  # PR summary
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "cioos-siooc_schema.json"
EOVS = ROOT / "cioos-commons" / "eov.json"

# Copied as-is when set: keyword aliases matched by cioos_clean_and_populate_eovs,
# and the lifecycle flags (deprecated choices stay so existing datasets validate).
OPTIONAL_KEYS = ("alternative_ids", "emerging", "deprecated", "replacedBy")


def eov_choices(eovs):
    """Map cioos-commons EOV records to ckanext-scheming choices."""
    choices = []
    for eov in eovs:
        choice = {
            "category": eov["category"],
            "value": eov["value"],
            "label": {"en": eov["label EN"], "fr": eov["label FR"]},
            "icon": eov["icon"],
        }
        choice.update({k: eov[k] for k in OPTIONAL_KEYS if eov.get(k)})
        choices.append(choice)
    return choices


def render(schema_text, eovs):
    """Return the schema text with only the eov field's choices array replaced.

    The rest of the file is left byte-for-byte, so its hand formatting (inline
    arrays, unescaped accents) survives.
    """
    field_start = schema_text.index('"field_name": "eov"')
    key = '"choices": '
    start = schema_text.index(key, field_start) + len(key)
    _, end = json.JSONDecoder().raw_decode(schema_text, start)
    indent = "\n" + " " * 6  # the choices key sits at 6 spaces in dataset_fields
    choices = json.dumps(eov_choices(eovs), indent=2, ensure_ascii=False)
    return schema_text[:start] + choices.replace("\n", indent) + schema_text[end:]


def schema_choices(schema_text):
    """The eov field's choices in a schema, keyed by value."""
    schema = json.loads(schema_text)
    (field,) = [f for f in schema["dataset_fields"] if f["field_name"] == "eov"]
    return {c["value"]: c for c in field["choices"]}


def change_report(old_text, new_text):
    """Markdown summary of eov choice changes between two schema versions.

    Returns (markdown, breaking); markdown is "" when nothing changed. Removing
    a value is breaking: datasets that use it fail validation on their next
    edit or harvest.
    """
    old, new = schema_choices(old_text), schema_choices(new_text)
    removed = [v for v in old if v not in new]
    added = [v for v in new if v not in old]
    changed = {
        v: [
            k
            for k in sorted(set(old[v]) | set(new[v]))
            if old[v].get(k) != new[v].get(k)
        ]
        for v in old
        if v in new and old[v] != new[v]
    }
    if not (removed or added or changed):
        return "", False

    def label(choice):
        return choice["label"]["en"]

    def show(value):
        return "—" if value is None else f"`{json.dumps(value, ensure_ascii=False)}`"

    lines = ["## EOV changes from cioos-commons", ""]
    if removed:
        lines += [
            "### ⚠️ Breaking: EOVs removed",
            "",
            "Datasets tagged with these values will fail validation on their next "
            "edit or harvest. Deprecate them in cioos-commons instead "
            '(`"deprecated": true`, plus `replacedBy`) unless no dataset uses them.',
            "",
        ]
        lines += [f"- `{v}` ({label(old[v])})" for v in removed]
        lines.append("")
    if added:
        lines += ["### Added", ""]
        lines += [f"- `{v}` ({label(new[v])})" for v in added]
        lines.append("")
    if changed:
        lines += [
            "### Changed",
            "",
            "| EOV | Key | Before | After |",
            "|---|---|---|---|",
        ]
        lines += [
            f"| `{v}` | {k} | {show(old[v].get(k))} | {show(new[v].get(k))} |"
            for v, keys in changed.items()
            for k in keys
        ]
        lines.append("")
    return "\n".join(lines), bool(removed)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="fail if the schema is out of date"
    )
    parser.add_argument(
        "--report",
        nargs=2,
        metavar=("BASE_SCHEMA", "OUT"),
        help="write a Markdown summary of eov changes since BASE_SCHEMA to OUT; "
        "exit 2 when an EOV was removed",
    )
    args = parser.parse_args()

    current = SCHEMA.read_text(encoding="utf-8")
    updated = render(current, json.loads(EOVS.read_text(encoding="utf-8")))
    if args.report:
        base, out = (Path(p) for p in args.report)
        report, breaking = change_report(base.read_text(encoding="utf-8"), updated)
        out.write_text(report, encoding="utf-8")
        return 2 if breaking else 0
    if current == updated:
        return 0
    if args.check:
        print(
            f"{SCHEMA.name} eov choices differ from {EOVS.relative_to(ROOT)}; "
            "run python scripts/update_eovs.py",
            file=sys.stderr,
        )
        return 1
    SCHEMA.write_text(updated, encoding="utf-8")
    print(f"updated {SCHEMA.name} eov choices from {EOVS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
