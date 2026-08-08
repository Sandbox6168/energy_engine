# Energy Engine

A core engine (usable independently of Home Assistant) that prices energy usage against UK electricity tariffs, plus a Home Assistant integration that surfaces it. The engine is built around a plugin architecture so data sources, tariffs, and (later) optimisers can be swapped without touching the core.

## Language

**Settlement Period**:
A fixed 30-minute UK billing window aligned to :00/:30, the atomic unit of time the engine reasons about. Matches how Octopus and the wider GB electricity market actually bill.
_Avoid_: time slot, interval, half-hour (as a noun)

**Energy Profile**:
A timeline of import/export kWh, one value per Settlement Period, over some date range. The core's unit of "usage" — produced by a Data Source, consumed and re-emitted by Transforms.
_Avoid_: usage timeline, usage data

**Data Source** _(plugin category)_:
Produces an initial Energy Profile for a date range. v1 scope: net grid import/export only — solar generation and battery charge/discharge are not modelled as separate series yet.

**Transform** _(plugin category)_:
Takes an Energy Profile (and the Scenario's Tariff Provider, for tariff-aware decisions) and returns a new Energy Profile — e.g. moving a dishwasher's load to a different Settlement Period, or shifting when a battery imports/exports. Like every plugin, a Transform never mutates the Energy Profile it's given; it returns a new one. The seam where future behavioural changes (an optimiser's decisions, a manual "what-if I'd run this at 2am" override) plug in. v1 ships with zero real Transforms (a Simulation with no Transforms is a straight replay of the source Energy Profile) — but the pipeline is shaped to carry them from the start.

**Tariff Provider** _(plugin category)_:
Supplies the import rate, export rate, and standing charge applicable to a given Settlement Period. Covers Agile, Go, and Fixed tariffs. Import and export are queried as distinct underlying products/tariff codes, not two fields of one lookup.

**Simulation**:
The core operation: run an Energy Profile through zero or more Transforms, then price the result against a Tariff Provider, producing a Simulation Result. The engine's only real verb — replay, "what-if I moved the dishwasher," and tariff comparison are all the same Simulation shape with different inputs.

**Simulation Result**:
The priced output of a Simulation — the transformed Energy Profile plus its total cost (including standing charge) for the period. Must be able to carry a precision caveat (e.g. "Settlement Periods before 2026-07-29 priced from hourly-averaged rates, not true half-hourly data") when an underlying plugin had to degrade precision — see [ADR-0001](docs/adr/0001-ha-tariff-provider-entity-only.md) and [ADR-0002](docs/adr/0002-ha-data-source-entity-only.md). A Simulation Result is never silently less precise than it claims to be — a precision caveat is only for genuinely coarser data (e.g. hourly instead of half-hourly); a Settlement Period with no data at all is a failure, not a caveat.

**Scenario**:
A named, reusable configuration of inputs to a Simulation — which Data Source/Energy Profile, which Transforms, which Tariff Provider. Built either from actual/historical data or hypothetical overrides; the Simulation doesn't distinguish which.

**Comparison**:
Running two or more **independent** Scenarios and presenting their Simulation Results side by side. Each Scenario carries its own Energy Profile source and Transform chain as well as its own Tariff Provider — a Comparison must not assume they share a starting Energy Profile, because a different tariff can legitimately imply different Transforms (e.g. switching to Octopus Go would shift your dishwasher/immersion Transforms to run overnight, which Agile's Scenario wouldn't apply). In v1, with zero real Transforms, every Scenario's Energy Profile happens to be identical regardless of tariff — so v1 Comparisons look like "same usage, different tariff" — but that's a v1 simplification, not the definition. Triggered on-demand for a chosen date range and tariff set, not a continuously recomputed sensor.

## Deferred concepts (named now, out of scope for v1)

**Battery Optimiser** _(plugin category, not yet built)_:
Would decide battery charge/discharge behaviour given a tariff. Excluded from v1 — no battery modelling at all yet.

**Device/Load Optimiser** _(plugin category, not yet built)_:
Would decide when a schedulable load (dishwasher, immersion heater, EV charger — EV is just another load instance, not its own category) runs given a tariff. Excluded from v1.

## Notes

- **Plugins are immutable — input in, new data out, never a mutation.** Applies across every plugin category (Data Source, Transform, Tariff Provider, and later Battery/Device Optimisers): none of them modify the Energy Profile or other data they're handed, they only ever return a new value derived from it. This is what makes chaining Transforms in a Simulation safe to reason about, and is why the Simulation itself can be a pure function — it's composing pure, side-effect-free pieces.
- **The core Simulation is a pure function.** No I/O, no HA dependency, deterministic given its inputs (Energy Profile, Transforms, Tariff Provider). How a Simulation Result gets surfaced — a service-call response, a persisted "last result" entity, both — is entirely a Home Assistant-layer presentation decision, not something the core knows or cares about.
- The engine must remain usable without Home Assistant. Home Assistant is a Data Source plugin implementation plus a UI/dashboard layer (a HACS custom_component **integration**, not a Supervisor add-on) — never a dependency of the core engine.
- **The core is provenance-agnostic by design.** Scenario, Cost Calculator, Comparison, etc. operate purely on the abstract Data Source / Tariff Provider contracts (usage and rates bucketed into Settlement Periods) and never know or care whether the numbers came from a live HA entity, an Octopus API call, or a CSV. Correctness questions like "should this return real historical rates for a past date" are properties of a *specific plugin's contract*, not the core — a Tariff Provider that claims to answer for a past Settlement Period must answer truthfully for that period, whatever its backing source. Re-bucketing raw source data (5-minute, hourly, whatever) into Settlement Periods is a plugin's responsibility, not the core's.
- There may legitimately be more than one plugin implementation per category even within the HA integration itself — e.g. grid import/export could be sourced from a Solax inverter integration's entities or from the Octopus HA add-on's entities; which one is authoritative is a per-installation config choice, not something the engine infers.
- The HA Tariff Provider is **entity-only**: it reads rate data (current value and history) from whatever HA integration is already installed for that purpose (e.g. the community Octopus Energy integration's sensors) — it never calls Octopus's API directly itself. See [ADR-0001](docs/adr/0001-ha-tariff-provider-entity-only.md) for why, including the historical-granularity trade-off this implies.
- The HA Data Source is **entity-only** too, for the same reason: it reads grid import/export energy data from whatever entities the installation designates via HA's own recorder/statistics, never a separate historical store — inheriting the same short-term/long-term precision trade-off as the HA Tariff Provider. See [ADR-0002](docs/adr/0002-ha-data-source-entity-only.md).
- A Home Assistant installation has a single Data Source (one Energy Profile), but can define multiple named Scenarios on top of it that vary by Tariff Provider — the concrete case of the v1 simplification noted under **Comparison** above, where every Scenario's Energy Profile is identical regardless of tariff.
- **Future idea, explicitly out of scope for now**: hooking the HA Data Source into Home Assistant's built-in Energy Dashboard configuration (if the user has one set up), instead of requiring separate explicit entity selection. Worth remembering, not designing yet.
