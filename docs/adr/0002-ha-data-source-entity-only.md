# HA Data Source reads energy data only from existing HA entities/statistics, mirroring ADR-0001's trade-off

The HA-side Data Source (grid import/export Energy Profile) reads exclusively from entities/statistics already present in Home Assistant — e.g. a Solax inverter's or a utility meter's energy sensors — via HA's recorder, rather than the energy-engine integration polling or storing usage data itself.

**Why**: keeps the HA integration a strict consumer of HA's own data model, symmetric with the Tariff Provider's entity-only design ([ADR-0001](0001-ha-tariff-provider-entity-only.md)) — one story ("HA plugins read HA's own history") instead of two different mechanisms for usage vs. rates.

**Trade-off accepted**: inherits the same precision ceiling as ADR-0001 — 5-minute short-term statistics are purged after ~10 days, and long-term statistics beyond that are hourly aggregates only. Simulations over older date ranges get hourly-averaged usage rather than true half-hourly, carried as a precision caveat on the Simulation Result. Considered and rejected: a Data Source that reads from an external time-series store (e.g. InfluxDB) to preserve full historical precision, which would reintroduce a second, HA-independent data dependency the integration would have to set up and maintain.
