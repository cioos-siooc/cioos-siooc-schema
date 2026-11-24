"""Static checks on the files CKAN and the harvesters load from this repo.

No CKAN needed: ``uv run --with pytest --with shapely pytest tests``.
``test_schema_ckan.py`` checks the same schemas against a running CKAN.
"""

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
import shapely.validation
import shapely.wkt

ROOT = Path(__file__).resolve().parent.parent

# Schema file -> (type key, expected type, field-list keys)
SCHEMAS = {
    "cioos-siooc_schema.json": (
        "dataset_type",
        "dataset",
        ("dataset_fields", "resource_fields"),
    ),
    "organization.json": ("organization_type", "organization", ("fields",)),
    "group.json": ("group_type", "resorg", ("fields",)),
}
LANGUAGES = ["en", "fr"]
TRANSLATABLE_KEYS = ("label", "help_text", "form_placeholder", "repeating_label")


def load(name):
    with open(ROOT / name, encoding="utf-8") as f:
        return json.load(f)


def iter_fields(fields, path=""):
    """Yield (path, field) for every field, recursing into repeating subfields."""
    for field in fields:
        field_path = f"{path}{field.get('field_name')}"
        yield field_path, field
        yield from iter_fields(field.get("repeating_subfields", []), field_path + ".")


def iter_translatable(node, path=""):
    """Yield (path, value) for every translatable value, including choice labels."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in TRANSLATABLE_KEYS:
                yield f"{path}.{key}", value
            elif isinstance(value, (dict, list)):
                yield from iter_translatable(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            name = (
                value.get("field_name") or value.get("value")
                if isinstance(value, dict)
                else None
            )
            yield from iter_translatable(value, f"{path}[{name or i}]")


@pytest.fixture(params=sorted(SCHEMAS))
def schema(request):
    return request.param, load(request.param)


def test_schema_header(schema):
    name, data = schema
    type_key, expected_type, _ = SCHEMAS[name]
    assert data["scheming_version"] == 2
    assert data[type_key] == expected_type
    assert sorted(data["form_languages"]) == LANGUAGES


def test_field_names_unique(schema):
    name, data = schema
    for list_key in SCHEMAS[name][2]:
        lists = [data[list_key]] + [
            f["repeating_subfields"]
            for _, f in iter_fields(data[list_key])
            if "repeating_subfields" in f
        ]
        for fields in lists:
            assert all(f.get("field_name") for f in fields), (
                f"{list_key}: field without field_name"
            )
            dupes = [
                n for n, c in Counter(f["field_name"] for f in fields).items() if c > 1
            ]
            assert not dupes, f"{list_key}: duplicate field_name {dupes}"


def test_translations_complete(schema):
    """A translated label, help text or placeholder has every form language, non-empty."""
    _, data = schema
    bad = [
        f"{path}: {value!r}"
        for path, value in iter_translatable(data)
        if isinstance(value, dict)
        and (
            sorted(value) != LANGUAGES
            or not all(isinstance(v, str) and v.strip() for v in value.values())
        )
    ]
    assert not bad, "\n".join(bad)


def test_choices(schema):
    name, data = schema
    for list_key in SCHEMAS[name][2]:
        for path, field in iter_fields(data[list_key]):
            if "choices" not in field:
                continue
            choices = field["choices"]
            assert choices, f"{path}: empty choices"
            assert all(c.get("value") and c.get("label") for c in choices), (
                f"{path}: choice without value or label"
            )
            dupes = [
                v for v, c in Counter(c["value"] for c in choices).items() if c > 1
            ]
            assert not dupes, f"{path}: duplicate choice values {dupes}"


def test_licenses():
    licenses = load("ckan_license.json")
    for lic in licenses:
        assert lic.get("id") and lic.get("title"), lic
        assert "url" in lic, lic["id"]
    dupes = [i for i, c in Counter(lic["id"] for lic in licenses).items() if c > 1]
    assert not dupes, f"duplicate license ids {dupes}"
    # CKAN resolves a legacy id to the first license listing it.
    legacy = [i for lic in licenses for i in lic.get("legacy_ids", [])]
    dupes = [i for i, c in Counter(legacy).items() if c > 1]
    assert not dupes, f"legacy id listed by two licenses {dupes}"


@pytest.mark.parametrize(
    "wkt_file",
    [
        p.name
        if p.name != "saint_lawrence_RA.wkt"
        else pytest.param(
            p.name,
            marks=pytest.mark.xfail(
                strict=True, reason="ring self-intersection near -64.67 47.72"
            ),
        )
        for p in sorted(ROOT.glob("*.wkt"))
    ],
)
def test_wkt_is_valid_polygon(wkt_file):
    """WKT files are ckan_spatial ``spatial_filter_file``s, sent to Solr as Intersects() filters."""
    geom = shapely.wkt.loads((ROOT / wkt_file).read_text())
    assert geom.geom_type in ("Polygon", "MultiPolygon")
    assert not geom.is_empty
    assert geom.is_valid, shapely.validation.explain_validity(geom)
    minx, miny, maxx, maxy = geom.bounds
    assert -180 <= minx <= maxx <= 180 and -90 <= miny <= maxy <= 90, "not lon/lat"


def test_eov_choices_match_cioos_commons():
    """The eov choices are generated from cioos-commons/eov.json (synced from cioos-commons)."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "update_eovs.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
