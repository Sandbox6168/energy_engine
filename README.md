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
engine in Home Assistant. The core engine itself lives at
`custom_components/energy_engine/core/` — HACS only ever ships the `custom_components/` folder,
so the core engine is developed there directly rather than as a separate package that needs
syncing in.
