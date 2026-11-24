# cioos-siooc-schema

cioos-siooc Schema definition and templates for use in the ckanext-scheming
extension. This is a subset of the full CIOOS-SIOOC metadata standard and fields
included here are intended to support data discovery. For the full metadata
please see the metadata xml records assosiated with each dataset.

# Dependencies
This schema depends on the following ckan extensions. They must be isntalled, configured and added to the plugins list for the schema to work
* [ckanext-scheming](https://github.com/cioos-siooc/ckanext-scheming)
* [ckanext-spatial](https://github.com/cioos-siooc/ckanext-spatial)
* [ckanext-repeating](https://github.com/open-data/ckanext-repeating)
* [ckanext-composite](https://github.com/EnviDat/ckanext-composite)
* [ckanext-fluent](https://github.com/ckan/ckanext-fluent)

# EOV choices
The `eov` field's choices are generated from the
[cioos-commons](https://github.com/cioos-siooc/cioos-commons) EOV vocabulary;
do not edit them in `cioos-siooc_schema.json`. cioos-ckan-docker-base's
`Sync cioos-commons` workflow copies `eovs/eov.json` to `cioos-commons/eov.json`
here, runs `scripts/update_eovs.py` to regenerate the choices, and opens the PR
with a summary of the EOV changes (labelled `breaking change` when an EOV was
removed). Run the script yourself after a manual change; `--check` reports
drift, as the tests do.
Change EOVs, their labels, categories, icons or keyword aliases
(`alternative_ids`) in cioos-commons; deprecate an EOV rather than delete it, so
datasets that use it still validate.

# Tests
`tests/test_schema_files.py` checks the schema, license and WKT files
(`uv run --no-project --with pytest --with shapely pytest tests`).
`tests/test_schema_ckan.py` loads the schemas through ckanext-scheming and checks
every validator and snippet they reference resolves; it runs in
[cioos-ckan-docker-base](https://github.com/cioos-siooc/cioos-ckan-docker-base)
with `just test-schema` (part of `just test` in CI).
