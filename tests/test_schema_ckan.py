"""Load the schemas through ckanext-scheming and resolve what they reference.

A misspelt or removed validator or snippet only fails when a form is saved or a
page rendered; this fails it here. Needs CKAN with the CIOOS plugins:
``pytest tests --ckan-ini=/srv/app/ckan.ini`` in the ckan container (``just test-schema``).
"""

import pytest

pytest.importorskip("ckan")

import ckan.plugins.toolkit as tk  # noqa: E402
from ckanext.scheming.validation import validators_from_string  # noqa: E402
from jinja2 import TemplateNotFound  # noqa: E402

VALIDATOR_KEYS = ("validators", "output_validators", "tag_validators")
SNIPPET_KEYS = {"display_snippet": "display_snippets", "form_snippet": "form_snippets"}


def expanded_schemas():
    """The schemas as scheming serves them: presets applied."""
    h = tk.h
    dataset = h.scheming_get_dataset_schema("dataset")
    return {
        "dataset": dataset["dataset_fields"],
        "resource": dataset["resource_fields"],
        "organization": h.scheming_get_organization_schema("organization")["fields"],
        "resorg": h.scheming_get_group_schema("resorg")["fields"],
    }, dataset


def iter_fields(fields, path=""):
    for field in fields:
        field_path = f"{path}{field['field_name']}"
        yield field_path, field
        yield from iter_fields(field.get("repeating_subfields", []), field_path + ".")


@pytest.mark.usefixtures("with_plugins")
def test_validators_resolve():
    schemas, dataset = expanded_schemas()
    errors = []
    for kind, fields in schemas.items():
        for path, field in iter_fields(fields):
            for key in VALIDATOR_KEYS:
                if field.get(key):
                    # An unknown name raises SchemingException ("validator/converter not found")
                    try:
                        validators_from_string(field[key], field, dataset)
                    except Exception as e:
                        errors.append(f"{kind}:{path}.{key}: {e!r}")
    assert not errors, "\n".join(errors)


@pytest.mark.usefixtures("with_plugins")
def test_snippets_exist(app):
    env = app.flask_app.jinja_env
    schemas, _ = expanded_schemas()
    missing = []
    for kind, fields in schemas.items():
        for path, field in iter_fields(fields):
            for key, folder in SNIPPET_KEYS.items():
                if field.get(key):
                    try:
                        env.get_template(f"scheming/{folder}/{field[key]}")
                    except TemplateNotFound:
                        missing.append(f"{kind}:{path}.{key}: {field[key]}")
    assert not missing, "\n".join(missing)
