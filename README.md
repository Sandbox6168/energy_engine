# energy-engine

Core engine that prices energy usage against UK electricity tariffs, independent of Home Assistant.
See [CONTEXT.md](CONTEXT.md) for the domain model.

## Development

```sh
uv sync
uv run pytest
uv run ruff check .
```

## Home Assistant integration

`custom_components/energy_engine/` is a HACS-installable integration that surfaces the core
engine in Home Assistant. It vendors the core engine under `custom_components/energy_engine/core/`
(HACS only ever ships the `custom_components/` folder, not `src/` — see
[ADR-0002](docs/adr/0002-ha-data-source-entity-only.md)), so after changing anything under
`src/energy_engine/`, re-sync the vendored copy before committing or tagging a release:

```sh
uv run python scripts/sync_vendored_core.py
```
