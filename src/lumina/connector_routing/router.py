"""Pure, deterministic connector routing decisions for Slice 31."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

ActionClass = Literal[
    "query",
    "create_draft",
    "update_draft",
    "request_commit",
    "request_cancel",
    "sync_event",
]
ResolutionSource = Literal[
    "operation_override",
    "capability_route",
    "site_primary",
    "organization_default",
    "no_route",
]
ResolutionStatus = Literal["resolved", "error"]
ReasonCode = Literal[
    "ok",
    "missing_idempotency_key",
    "override_not_found",
    "override_ineligible",
    "ambiguous_route",
    "capability_route_not_found",
    "site_primary_not_found",
    "organization_default_not_found",
    "unsupported_capability",
    "unsupported_action",
    "connector_unhealthy",
    "no_eligible_connector",
]
HealthStatus = Literal["healthy", "degraded", "unhealthy"]

_MUTATION_ACTIONS = frozenset({
    "create_draft",
    "update_draft",
    "request_commit",
    "request_cancel",
    "sync_event",
})


@dataclass(frozen=True)
class ConnectorRegistryEntry:
    organization_id: str
    site_id: str
    connector_instance_id: str
    capability_namespaces: tuple[str, ...]
    supported_action_classes: tuple[ActionClass, ...]
    enabled: bool
    health_status: HealthStatus
    is_site_primary: bool = False


@dataclass(frozen=True)
class CapabilityRoute:
    capability_namespace: str
    connector_instance_id: str
    supported_action_classes: tuple[ActionClass, ...] = ()
    priority: int = 100


@dataclass(frozen=True)
class CapabilityRoutePolicy:
    policy_version: int
    organization_id: str
    site_id: str
    routes: tuple[CapabilityRoute, ...]
    organization_default_connector_id: str | None = None


@dataclass(frozen=True)
class ConnectorResolutionResult:
    resolution_id: str
    request_id: str
    organization_id: str
    site_id: str
    actor_id: str
    action_class: ActionClass
    capability_namespace: str
    status: ResolutionStatus
    source: ResolutionSource
    reason_code: ReasonCode
    connector_instance_id: str | None
    idempotency_key: str | None
    correlation_id: str | None
    policy_version: int
    candidate_connector_ids: tuple[str, ...]
    evaluated_utc: str

    def as_record(self) -> dict[str, object]:
        return {
            "schema_version": "1.0.0",
            "resolution_id": self.resolution_id,
            "request_id": self.request_id,
            "organization_id": self.organization_id,
            "site_id": self.site_id,
            "actor_id": self.actor_id,
            "action_class": self.action_class,
            "capability_namespace": self.capability_namespace,
            "status": self.status,
            "source": self.source,
            "reason_code": self.reason_code,
            "connector_instance_id": self.connector_instance_id,
            "idempotency_key": self.idempotency_key,
            "correlation_id": self.correlation_id,
            "policy_version": self.policy_version,
            "candidate_connector_ids": list(self.candidate_connector_ids),
            "evaluated_utc": self.evaluated_utc,
        }


def _require_scope(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"connector routing requires {field_name}")
    return value.strip()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _is_entry_eligible(
    entry: ConnectorRegistryEntry,
    *,
    action_class: ActionClass,
    capability_namespace: str,
) -> tuple[bool, ReasonCode]:
    normalized_capabilities = {
        capability.strip() for capability in entry.capability_namespaces if capability and capability.strip()
    }
    if not entry.enabled:
        return False, "no_eligible_connector"
    if entry.health_status == "unhealthy":
        return False, "connector_unhealthy"
    if capability_namespace not in normalized_capabilities:
        return False, "unsupported_capability"
    if action_class not in entry.supported_action_classes:
        return False, "unsupported_action"
    return True, "ok"


def _result(
    *,
    request_id: str,
    organization_id: str,
    site_id: str,
    actor_id: str,
    action_class: ActionClass,
    capability_namespace: str,
    status: ResolutionStatus,
    source: ResolutionSource,
    reason_code: ReasonCode,
    connector_instance_id: str | None,
    idempotency_key: str | None,
    correlation_id: str | None,
    policy_version: int,
    candidate_connector_ids: tuple[str, ...],
    resolution_id: str | None,
    evaluated_utc: datetime | None,
) -> ConnectorResolutionResult:
    return ConnectorResolutionResult(
        resolution_id=resolution_id or str(uuid.uuid4()),
        request_id=request_id,
        organization_id=organization_id,
        site_id=site_id,
        actor_id=actor_id,
        action_class=action_class,
        capability_namespace=capability_namespace,
        status=status,
        source=source,
        reason_code=reason_code,
        connector_instance_id=connector_instance_id,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        policy_version=policy_version,
        candidate_connector_ids=tuple(sorted(candidate_connector_ids)),
        evaluated_utc=(
            evaluated_utc.isoformat().replace("+00:00", "Z") if evaluated_utc is not None else _utc_now()
        ),
    )


def resolve_connector(
    entries: list[ConnectorRegistryEntry],
    policy: CapabilityRoutePolicy,
    *,
    request_id: str,
    actor_id: str,
    action_class: ActionClass,
    capability_namespace: str,
    operation_override_connector_id: str | None = None,
    idempotency_key: str | None = None,
    correlation_id: str | None = None,
    resolution_id: str | None = None,
    evaluated_utc: datetime | None = None,
) -> ConnectorResolutionResult:
    """Resolve one connector deterministically without side effects."""
    request_id = _require_scope(request_id, "request_id")
    actor_id = _require_scope(actor_id, "actor_id")
    capability_namespace = _require_scope(capability_namespace, "capability_namespace")
    organization_id = _require_scope(policy.organization_id, "organization_id")
    site_id = _require_scope(policy.site_id, "site_id")
    operation_override_connector_id = _normalize_optional(operation_override_connector_id)
    idempotency_key = _normalize_optional(idempotency_key)
    correlation_id = _normalize_optional(correlation_id)

    scoped_entries = [
        entry
        for entry in entries
        if entry.organization_id == organization_id and entry.site_id == site_id
    ]
    scoped_entries.sort(key=lambda item: item.connector_instance_id)
    candidate_ids = tuple(entry.connector_instance_id for entry in scoped_entries)

    if action_class in _MUTATION_ACTIONS and not idempotency_key:
        return _result(
            request_id=request_id,
            organization_id=organization_id,
            site_id=site_id,
            actor_id=actor_id,
            action_class=action_class,
            capability_namespace=capability_namespace,
            status="error",
            source="no_route",
            reason_code="missing_idempotency_key",
            connector_instance_id=None,
            idempotency_key=None,
            correlation_id=correlation_id,
            policy_version=policy.policy_version,
            candidate_connector_ids=candidate_ids,
            resolution_id=resolution_id,
            evaluated_utc=evaluated_utc,
        )

    if operation_override_connector_id is not None:
        override = next(
            (entry for entry in scoped_entries if entry.connector_instance_id == operation_override_connector_id),
            None,
        )
        if override is None:
            return _result(
                request_id=request_id,
                organization_id=organization_id,
                site_id=site_id,
                actor_id=actor_id,
                action_class=action_class,
                capability_namespace=capability_namespace,
                status="error",
                source="operation_override",
                reason_code="override_not_found",
                connector_instance_id=None,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                policy_version=policy.policy_version,
                candidate_connector_ids=candidate_ids,
                resolution_id=resolution_id,
                evaluated_utc=evaluated_utc,
            )
        eligible, reason = _is_entry_eligible(
            override,
            action_class=action_class,
            capability_namespace=capability_namespace,
        )
        if not eligible:
            return _result(
                request_id=request_id,
                organization_id=organization_id,
                site_id=site_id,
                actor_id=actor_id,
                action_class=action_class,
                capability_namespace=capability_namespace,
                status="error",
                source="operation_override",
                reason_code="override_ineligible" if reason != "connector_unhealthy" else "connector_unhealthy",
                connector_instance_id=None,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                policy_version=policy.policy_version,
                candidate_connector_ids=candidate_ids,
                resolution_id=resolution_id,
                evaluated_utc=evaluated_utc,
            )
        return _result(
            request_id=request_id,
            organization_id=organization_id,
            site_id=site_id,
            actor_id=actor_id,
            action_class=action_class,
            capability_namespace=capability_namespace,
            status="resolved",
            source="operation_override",
            reason_code="ok",
            connector_instance_id=override.connector_instance_id,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            policy_version=policy.policy_version,
            candidate_connector_ids=candidate_ids,
            resolution_id=resolution_id,
            evaluated_utc=evaluated_utc,
        )

    matching_routes = [
        route
        for route in policy.routes
        if route.capability_namespace.strip() == capability_namespace
        and (not route.supported_action_classes or action_class in route.supported_action_classes)
    ]
    matching_routes.sort(key=lambda route: (route.priority, route.connector_instance_id))

    if matching_routes:
        best_priority = matching_routes[0].priority
        top_routes = [route for route in matching_routes if route.priority == best_priority]
        route_ids = {route.connector_instance_id for route in top_routes}
        if len(route_ids) > 1:
            return _result(
                request_id=request_id,
                organization_id=organization_id,
                site_id=site_id,
                actor_id=actor_id,
                action_class=action_class,
                capability_namespace=capability_namespace,
                status="error",
                source="capability_route",
                reason_code="ambiguous_route",
                connector_instance_id=None,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                policy_version=policy.policy_version,
                candidate_connector_ids=tuple(sorted(route_ids)),
                resolution_id=resolution_id,
                evaluated_utc=evaluated_utc,
            )

        routed_id = top_routes[0].connector_instance_id
        routed_entry = next((entry for entry in scoped_entries if entry.connector_instance_id == routed_id), None)
        if routed_entry:
            eligible, reason = _is_entry_eligible(
                routed_entry,
                action_class=action_class,
                capability_namespace=capability_namespace,
            )
            if eligible:
                return _result(
                    request_id=request_id,
                    organization_id=organization_id,
                    site_id=site_id,
                    actor_id=actor_id,
                    action_class=action_class,
                    capability_namespace=capability_namespace,
                    status="resolved",
                    source="capability_route",
                    reason_code="ok",
                    connector_instance_id=routed_entry.connector_instance_id,
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                    policy_version=policy.policy_version,
                    candidate_connector_ids=candidate_ids,
                    resolution_id=resolution_id,
                    evaluated_utc=evaluated_utc,
                )
            if reason == "connector_unhealthy":
                return _result(
                    request_id=request_id,
                    organization_id=organization_id,
                    site_id=site_id,
                    actor_id=actor_id,
                    action_class=action_class,
                    capability_namespace=capability_namespace,
                    status="error",
                    source="capability_route",
                    reason_code="connector_unhealthy",
                    connector_instance_id=None,
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                    policy_version=policy.policy_version,
                    candidate_connector_ids=candidate_ids,
                    resolution_id=resolution_id,
                    evaluated_utc=evaluated_utc,
                )

    primaries = [
        entry
        for entry in scoped_entries
        if entry.is_site_primary
    ]
    primaries.sort(key=lambda item: item.connector_instance_id)
    eligible_primaries = [
        entry for entry in primaries
        if _is_entry_eligible(entry, action_class=action_class, capability_namespace=capability_namespace)[0]
    ]
    if len(eligible_primaries) == 1:
        selected = eligible_primaries[0]
        return _result(
            request_id=request_id,
            organization_id=organization_id,
            site_id=site_id,
            actor_id=actor_id,
            action_class=action_class,
            capability_namespace=capability_namespace,
            status="resolved",
            source="site_primary",
            reason_code="ok",
            connector_instance_id=selected.connector_instance_id,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            policy_version=policy.policy_version,
            candidate_connector_ids=candidate_ids,
            resolution_id=resolution_id,
            evaluated_utc=evaluated_utc,
        )
    if len(eligible_primaries) > 1:
        return _result(
            request_id=request_id,
            organization_id=organization_id,
            site_id=site_id,
            actor_id=actor_id,
            action_class=action_class,
            capability_namespace=capability_namespace,
            status="error",
            source="site_primary",
            reason_code="ambiguous_route",
            connector_instance_id=None,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            policy_version=policy.policy_version,
            candidate_connector_ids=tuple(entry.connector_instance_id for entry in eligible_primaries),
            resolution_id=resolution_id,
            evaluated_utc=evaluated_utc,
        )

    if policy.organization_default_connector_id:
        default_entry = next(
            (entry for entry in scoped_entries if entry.connector_instance_id == policy.organization_default_connector_id),
            None,
        )
        if default_entry:
            eligible, reason = _is_entry_eligible(
                default_entry,
                action_class=action_class,
                capability_namespace=capability_namespace,
            )
            if eligible:
                return _result(
                    request_id=request_id,
                    organization_id=organization_id,
                    site_id=site_id,
                    actor_id=actor_id,
                    action_class=action_class,
                    capability_namespace=capability_namespace,
                    status="resolved",
                    source="organization_default",
                    reason_code="ok",
                    connector_instance_id=default_entry.connector_instance_id,
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                    policy_version=policy.policy_version,
                    candidate_connector_ids=candidate_ids,
                    resolution_id=resolution_id,
                    evaluated_utc=evaluated_utc,
                )
            if reason == "connector_unhealthy":
                return _result(
                    request_id=request_id,
                    organization_id=organization_id,
                    site_id=site_id,
                    actor_id=actor_id,
                    action_class=action_class,
                    capability_namespace=capability_namespace,
                    status="error",
                    source="organization_default",
                    reason_code="connector_unhealthy",
                    connector_instance_id=None,
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                    policy_version=policy.policy_version,
                    candidate_connector_ids=candidate_ids,
                    resolution_id=resolution_id,
                    evaluated_utc=evaluated_utc,
                )

    return _result(
        request_id=request_id,
        organization_id=organization_id,
        site_id=site_id,
        actor_id=actor_id,
        action_class=action_class,
        capability_namespace=capability_namespace,
        status="error",
        source="no_route",
        reason_code="no_eligible_connector",
        connector_instance_id=None,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        policy_version=policy.policy_version,
        candidate_connector_ids=candidate_ids,
        resolution_id=resolution_id,
        evaluated_utc=evaluated_utc,
    )
