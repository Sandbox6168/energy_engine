"""Constants for the Energy Engine integration."""

from __future__ import annotations

DOMAIN = "energy_engine"

# Config entry data: the single, shared Data Source (Energy Profile) for this installation.
CONF_IMPORT_ENTITY = "import_entity_id"
CONF_EXPORT_ENTITY = "export_entity_id"

# Options entry: named Scenarios, each with its own Tariff Provider entity mapping.
CONF_SCENARIOS = "scenarios"
CONF_SCENARIO_NAME = "name"
CONF_IMPORT_RATE_ENTITY = "import_rate_entity_id"
CONF_EXPORT_RATE_ENTITY = "export_rate_entity_id"
CONF_STANDING_CHARGE_ENTITY = "standing_charge_entity_id"

SERVICE_RUN_SCENARIO = "run_scenario"
SERVICE_RUN_COMPARISON = "run_comparison"
SERVICE_VERIFY_ENTITIES = "verify_entities"

ATTR_START_DATE = "start_date"
ATTR_END_DATE = "end_date"

# Recorder statistics/short-term-statistics retention boundary this integration relies
# on for the precision-caveat decision (ADR-0001 / ADR-0002) - kept as a constant so the
# caveat message and the actual query logic can't drift out of sync.
SHORT_TERM_STATS_RETENTION_DAYS = 10
