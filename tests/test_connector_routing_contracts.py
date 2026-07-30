"""Schema and contract validation tests for Slice 31 connector routing."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest

from lumina.connector_routing.router import (
    CapabilityRoute,
    CapabilityRoutePolicy,
    ConnectorRegistryEntry,
    resolve_connector,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
STANDARDS = REPO_ROOT / "standards"


def _schema(name: str) -> dict:
    return json.loads((STANDARDS / name).read_text(encoding="utf-8"))


SCHEMA_FILES = [
    STANDARDS / "connector-registry-entry-schema-v1.json",
    STANDARDS / "capability-route-policy-schema-v1.json",
    STANDARDS / "connector-resolution-result-schema-v1.json",
    STANDARDS / "business-operation-request-schema-v1.json",
]


def _store() -> dict[str, dict]:
    store: dict[str, dict] = {}
    for schema_path in SCHEMA_FILES:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        store[schema_path.name] = schema
        store[schema_path.resolve().as_uri()] = schema
        schema_id = schema.get("$id")
        if isinstance(schema_id, str) and schema_id:
            store[schema_id] = schema
    return store


STORE = _store()


def _validator(name: str) -> jsonschema.Draft202012Validator:
    schema_path = STANDARDS / name
    schema = _schema(name)
    resolver = jsonschema.RefResolver(
        base_uri=f"{schema_path.parent.as_uri()}/",
        referrer=schema,
        store=STORE,
    )
    return jsonschema.Draft202012Validator(
        schema,
        resolver=resolver,
        format_checker=jsonschema.FormatChecker(),
    )


@pytest.mark.unit
def test_registry_entry_schema_accepts_valid_payload() -> None:
    payload = {
        "organization_id": "org-a",
        "site_id": "site-a",
        "connector_instance_id": "conn-a",
        "provider_family": "erpnext",
        "capability_namespaces": ["service/work-order"],
        "supported_action_classes": ["query", "request_commit"],
        "enabled": True,
        "health_status": "healthy",
        "is_site_primary": True,
        "health_checked_utc": "2026-07-26T00:00:00Z",
        "metadata": {"notes": "stable"},
    }
    _validator("connector-registry-entry-schema-v1.json").validate(payload)


@pytest.mark.unit
def test_route_policy_schema_accepts_valid_payload() -> None:
    payload = {
        "policy_version": 1,
        "organization_id": "org-a",
        "site_id": "site-a",
        "organization_default_connector_id": "conn-default",
        "routes": [
            {
                "capability_namespace": "service/work-order",
                "connector_instance_id": "conn-a",
                "supported_action_classes": ["query"],
                "priority": 1,
            }
        ],
    }
    _validator("capability-route-policy-schema-v1.json").validate(payload)


@pytest.mark.unit
def test_result_schema_validates_router_record() -> None:
    policy = CapabilityRoutePolicy(
        policy_version=1,
        organization_id="org-a",
        site_id="site-a",
        routes=(CapabilityRoute("service/work-order", "conn-a", ("query",), 1),),
    )
    entries = [
        ConnectorRegistryEntry(
            organization_id="org-a",
            site_id="site-a",
            connector_instance_id="conn-a",
            capability_namespaces=("service/work-order",),
            supported_action_classes=("query",),
            enabled=True,
            health_status="healthy",
            is_site_primary=False,
        )
    ]
    result = resolve_connector(
        entries,
        policy,
        request_id="req-a",
        actor_id="actor-a",
        action_class="query",
        capability_namespace="service/work-order",
        resolution_id="resolution-a",
        evaluated_utc=datetime(2026, 7, 26, tzinfo=UTC),
    )
    record = result.as_record()
    _validator("connector-resolution-result-schema-v1.json").validate(record)


@pytest.mark.unit
def test_registry_entry_rejects_nested_secret_key() -> None:
    payload = {
        "organization_id": "org-a",
        "site_id": "site-a",
        "connector_instance_id": "conn-a",
        "capability_namespaces": ["service/work-order"],
        "supported_action_classes": ["query"],
        "enabled": True,
        "health_status": "healthy",
        "metadata": {"nested": {"token": "forbidden"}},
    }
    with pytest.raises(jsonschema.ValidationError):
        _validator("connector-registry-entry-schema-v1.json").validate(payload)


@pytest.mark.unit
def test_result_schema_rejects_unknown_reason_code() -> None:
    payload = {
        "schema_version": "1.0.0",
        "resolution_id": "resolution-a",
        "request_id": "req-a",
        "organization_id": "org-a",
        "site_id": "site-a",
        "actor_id": "actor-a",
        "action_class": "query",
        "capability_namespace": "service/work-order",
        "status": "error",
        "source": "no_route",
        "reason_code": "made_up_reason",
        "connector_instance_id": None,
        "idempotency_key": None,
        "correlation_id": None,
        "policy_version": 1,
        "candidate_connector_ids": [],
        "evaluated_utc": "2026-07-26T00:00:00Z",
    }
    with pytest.raises(jsonschema.ValidationError):
        _validator("connector-resolution-result-schema-v1.json").validate(payload)
