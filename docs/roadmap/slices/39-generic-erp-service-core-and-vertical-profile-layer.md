---
title: "Slice 39 — Generic ERP Service Core and Vertical Profile Layer"
slice: 39
status: planned
version: 0.1.1
last_updated: 2026-08-04
---

## Purpose

Lock the reusable ERP integration direction by defining one canonical service workflow core that supports multiple vertical presentations (for example towing and retail-delivery) without forcing core runtime changes.

## Scope

- Define profile-driven vertical variation over a shared canonical service operation graph.
- Keep canonical capability namespaces and action classes stable across profiles.
- Isolate ERP provider specifics to thin mapping adapters.
- Define optional low-change customization hooks (for example custom doctype/table mappings) that do not alter canonical contracts.
- Define parity expectations across at least ERPNext and Odoo for identical canonical operations.

## 2026-08-04 Alignment Addendum

- Canonical service-core flow remains host-generic while domain profile orchestration (including DAG/task dependency handling) stays in the domain/profile layer.
- `task_ready_for_execution` semantics are node/task readiness only and must not be overloaded as workflow-terminal state.
- Profile parity evidence should include linkage metadata that groups similar decisions and tracks entity state transitions across profiles/providers.

## Out of Scope

- Rewriting core engine flow in `src/lumina/`.
- Provider-specific schema promotion into canonical request/result contracts.
- Full provider feature parity across all ERP modules.

## Required Changes

- Add profile contract documentation for vertical presentation/configuration overlays.
- Add mapping-boundary guidance for provider-specific object translation.
- Add portability/conformance scenarios for at least towing and retail-delivery profiles.
- Add evidence requirements showing cross-provider canonical parity.

## New/Changed Contracts

- New profile contract: `service_vertical_profile_v1`.
- New mapping-extension contract: `provider_custom_mapping_hook_v1`.
- Extended portability evidence requirement over existing connector conformance artifacts.

## Files Likely Touched

- `docs/7-concepts/business-system-capability-taxonomy.md`
- `docs/7-concepts/domain-adapter-pattern.md`
- `src/lumina/business_ops/connectors/*/mapping.py`
- `src/lumina/business_ops/connectors/conformance.py`
- `src/lumina/business_ops/replay.py`
- `tests/test_connector_*_manifest.py`
- `tests/test_business_ops_replay_service.py`
- `docs/roadmap/slices/39-generic-erp-service-core-and-vertical-profile-layer.md`

## Acceptance Criteria

- A single canonical service action graph supports both towing and retail-delivery profile variants.
- Profile differences are limited to configuration/presentation overlays and do not change canonical payload shape.
- ERPNext and Odoo both pass shared conformance and replay parity scenarios for both profiles.
- Optional provider customization path (for example custom doctype mapping) is demonstrated without changing canonical contracts.

## Tests

- Cross-profile conformance suite for canonical service actions.
- Cross-provider replay parity suite for towing and retail-delivery profiles.
- Negative tests proving profile-specific fields are rejected from canonical payload keys.
- Compose CI parity validation before push.

## Ledger/Governance Impact

- Keeps multi-vertical ERP integration decisions auditable and contract-driven.
- Prevents uncontrolled drift into provider- or vertical-specific forks of core runtime semantics.

## Follow-Up Slices

- Slice 36 execution and hardening must preserve this slice's invariants.
- Future vertical slices should extend profile overlays before proposing core workflow changes.

## Implementation-Ready PR Description Template

### Title

Slice 39: generic ERP service core with profile-layer variance

### PR Scope

- Introduce/clarify canonical service-core plus profile-layer contracts.
- Add mapping-boundary and low-change customization guidance.
- Add cross-provider and cross-profile parity evidence.

### Acceptance Criteria

- Canonical action graph parity is proven across target profiles/providers.
- Provider customization path is low-change and contract-safe.
- No core-engine fork is required for vertical variation.

### Test Checklist

- [ ] `./scripts/compose-ci.ps1 -Target backend`
- [ ] `pytest tests/test_connector_erpnext_manifest.py tests/test_connector_odoo_manifest.py tests/test_business_ops_replay_service.py -q`
- [ ] `python -m lumina.systools.verify_repo`
- [ ] `python -m lumina.systools.manifest_integrity check`

### Out of Scope Confirmations

- No broad ERP feature-completeness work in this slice.
- No auth transition implementation from Slice 37/38 in this slice.
