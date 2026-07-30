"""Deterministic connector-routing precedence tests for Slice 31."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lumina.connector_routing.router import (
    CapabilityRoute,
    CapabilityRoutePolicy,
    ConnectorRegistryEntry,
    resolve_connector,
)


def _entry(
    connector_id: str,
    *,
    enabled: bool = True,
    health_status: str = "healthy",
    is_site_primary: bool = False,
    capabilities: tuple[str, ...] = ("service/work-order", "inventory"),
    actions: tuple[str, ...] = ("query", "request_commit"),
) -> ConnectorRegistryEntry:
    return ConnectorRegistryEntry(
        organization_id="org-a",
        site_id="site-a",
        connector_instance_id=connector_id,
        capability_namespaces=capabilities,
        supported_action_classes=actions,  # type: ignore[arg-type]
        enabled=enabled,
        health_status=health_status,  # type: ignore[arg-type]
        is_site_primary=is_site_primary,
    )


def _policy(
    routes: tuple[CapabilityRoute, ...] = (),
    *,
    default_id: str | None = None,
) -> CapabilityRoutePolicy:
    return CapabilityRoutePolicy(
        policy_version=1,
        organization_id="org-a",
        site_id="site-a",
        routes=routes,
        organization_default_connector_id=default_id,
    )


@pytest.mark.unit
def test_operation_override_has_highest_precedence() -> None:
    result = resolve_connector(
        [_entry("conn-a"), _entry("conn-b", is_site_primary=True)],
        _policy(routes=(CapabilityRoute("service/work-order", "conn-b", ("query",), 10),)),
        request_id="req-1",
        actor_id="actor-a",
        action_class="query",
        capability_namespace="service/work-order",
        operation_override_connector_id="conn-a",
    )

    assert result.status == "resolved"
    assert result.source == "operation_override"
    assert result.connector_instance_id == "conn-a"


@pytest.mark.unit
def test_requires_idempotency_key_for_mutation_actions() -> None:
    result = resolve_connector(
        [_entry("conn-a", actions=("request_commit",))],
        _policy(),
        request_id="req-2",
        actor_id="actor-a",
        action_class="request_commit",
        capability_namespace="service/work-order",
    )

    assert result.status == "error"
    assert result.reason_code == "missing_idempotency_key"


@pytest.mark.unit
def test_capability_route_used_before_site_primary() -> None:
    result = resolve_connector(
        [_entry("conn-primary", is_site_primary=True), _entry("conn-cap")],
        _policy(routes=(CapabilityRoute("service/work-order", "conn-cap", ("query",), 1),)),
        request_id="req-3",
        actor_id="actor-a",
        action_class="query",
        capability_namespace="service/work-order",
    )

    assert result.status == "resolved"
    assert result.source == "capability_route"
    assert result.connector_instance_id == "conn-cap"


@pytest.mark.unit
def test_capability_namespace_is_normalized_for_matching() -> None:
    result = resolve_connector(
        [_entry("conn-cap", capabilities=(" service/work-order ",))],
        _policy(routes=(CapabilityRoute(" service/work-order ", "conn-cap", ("query",), 1),)),
        request_id="req-3b",
        actor_id="actor-a",
        action_class="query",
        capability_namespace="  service/work-order  ",
    )

    assert result.status == "resolved"
    assert result.source == "capability_route"
    assert result.connector_instance_id == "conn-cap"


@pytest.mark.unit
def test_ambiguous_capability_route_is_error() -> None:
    result = resolve_connector(
        [_entry("conn-a"), _entry("conn-b")],
        _policy(
            routes=(
                CapabilityRoute("service/work-order", "conn-a", ("query",), 1),
                CapabilityRoute("service/work-order", "conn-b", ("query",), 1),
            ),
        ),
        request_id="req-4",
        actor_id="actor-a",
        action_class="query",
        capability_namespace="service/work-order",
    )

    assert result.status == "error"
    assert result.reason_code == "ambiguous_route"
    assert result.source == "capability_route"


@pytest.mark.unit
def test_site_primary_used_when_no_route() -> None:
    result = resolve_connector(
        [_entry("conn-primary", is_site_primary=True)],
        _policy(),
        request_id="req-5",
        actor_id="actor-a",
        action_class="query",
        capability_namespace="service/work-order",
    )

    assert result.status == "resolved"
    assert result.source == "site_primary"
    assert result.connector_instance_id == "conn-primary"


@pytest.mark.unit
def test_org_default_used_after_site_primary() -> None:
    result = resolve_connector(
        [_entry("conn-default")],
        _policy(default_id="conn-default"),
        request_id="req-6",
        actor_id="actor-a",
        action_class="query",
        capability_namespace="service/work-order",
    )

    assert result.status == "resolved"
    assert result.source == "organization_default"
    assert result.connector_instance_id == "conn-default"


@pytest.mark.unit
def test_unhealthy_connector_returns_structured_error() -> None:
    result = resolve_connector(
        [_entry("conn-a", health_status="unhealthy", is_site_primary=True)],
        _policy(),
        request_id="req-7",
        actor_id="actor-a",
        action_class="query",
        capability_namespace="service/work-order",
    )

    assert result.status == "error"
    assert result.reason_code == "no_eligible_connector"


@pytest.mark.unit
def test_result_record_is_stable_and_transcript_free() -> None:
    result = resolve_connector(
        [_entry("conn-a", is_site_primary=True)],
        _policy(),
        request_id="req-8",
        actor_id="actor-a",
        action_class="query",
        capability_namespace="service/work-order",
        resolution_id="resolution-1",
        evaluated_utc=datetime(2026, 7, 26, tzinfo=UTC),
    )

    record = result.as_record()
    assert record["resolution_id"] == "resolution-1"
    assert record["evaluated_utc"] == "2026-07-26T00:00:00Z"
    assert "transcript" not in str(record).lower()
