---
title: "Slice 37 — ERP Identity Authority and Claim Contract"
slice: 37
status: active
version: 0.1.1
last_updated: 2026-08-04
---

## Purpose

Establish ERP as the single source of truth (SSOT) for non-system identity and authorization context, and define the canonical JWT claim contract Lumina must accept and enforce.

## Scope

- Define ERP ownership boundaries for domain/user identity lifecycle and organization/site membership.
- Preserve a separate Lumina-owned system JWT track for framework developers/system administrators (`root`, `super_admin`).
- Define canonical ERP-issued JWT claim schema used by Lumina runtime.
- Define issuer, audience, expiry, and key-rotation contract requirements.
- Define required role/context mapping from ERP claims into Lumina authorization checks.
- Define break-glass and outage posture for temporary fallback and audit requirements.

## 2026-08-04 Alignment Addendum

- Claim contracts should preserve sufficient scoped linkage fields to connect identity decisions with institutional-memory decision groups and entity state traces.
- Authorization outcomes should distinguish denied-from-policy vs missing-information-required routing for deterministic follow-up behavior.

## Out of Scope

- Full middleware implementation for ERP token verification.
- Removal of system-track bootstrap auth (`root`, `super_admin`) in this slice.
- Enterprise IdP federation architecture beyond ERP-issued token contract.

## Required Changes

- Add new concept/standards documentation for ERP identity authority boundaries.
- Add canonical claim contract with required and optional fields.
- Add rejection rules for malformed or unauthorized ERP claims.
- Add migration notes describing legacy Lumina domain/user auth compatibility window.

## New/Changed Contracts

- New contract: `erp_identity_authority_v1` (domain/user actor authority model).
- New contract: `erp_jwt_claim_contract_v1` including:
  - Required: `iss`, `aud`, `sub`, `exp`, `iat`, `jti`, `role`, `organization_id`, `site_id`
  - Optional: `domain_roles`, `governed_modules`, `device_id`, `site_role`
- New contract: `erp_auth_fallback_policy_v1` (time-bound fallback and audit constraints).

## Files Likely Touched

- `docs/7-concepts/parallel-authority-tracks.md`
- `docs/8-admin/air-gapped-admin-architecture.md`
- `docs/8-admin/secrets-and-runtime-config.md`
- `docs/5-standards/rbac-spec.md`
- `docs/3-functions/auth.md`
- `docs/roadmap/slices/37-erp-identity-authority-and-claim-contract.md`

## Acceptance Criteria

- ERP is explicitly declared SSOT for domain/user identity and membership context.
- System/developer control-plane authentication remains on a distinct Lumina-issued JWT track.
- Canonical ERP JWT claim schema is complete and unambiguous.
- Issuer/audience/expiry requirements and deny behavior are documented.
- Break-glass behavior is explicitly bounded, auditable, and non-default.

## Tests

- Contract test scenarios (documentation-level in this slice):
  - Valid token accepted when all required claims and issuer/audience constraints pass.
  - Token rejected for missing required claims (`organization_id`, `site_id`, `role`, `jti`).
  - Token rejected for invalid issuer or audience.
  - Token rejected when expired or with invalid time claims.
- Repository integrity checks:
  - `python -m lumina.systools.verify_repo`
  - `python -m lumina.systools.manifest_integrity check`

## Ledger/Governance Impact

- Auth denials and fallback activations become explicit governance/audit events.
- Identity truth moves to ERP for non-system actors; Lumina remains policy enforcement runtime and retains system-track token authority.

## Follow-Up Slices

- Slice 38: ERP JWT verification gateway and auth endpoint transition.

## Implementation-Ready PR Description Template

### Title

Slice 37: ERP identity authority and JWT claim contract

### PR Scope

- Define ERP as SSOT for domain/user identities.
- Define canonical JWT claim contract and validation rules.
- Define bounded fallback posture and audit obligations.

### Acceptance Criteria

- Claim contract is explicit and internally consistent with RBAC docs.
- Invalid/missing-claim denial behavior is documented.
- Migration dependency to Slice 38 is explicit.

### Test Checklist

- [ ] Contract validation scenarios documented (valid/invalid issuer, audience, required claims, expiry).
- [ ] Deny-path and fallback governance behavior documented.
- [ ] Repo integrity checks pass.

### Out of Scope Confirmations

- No middleware/runtime code migration in this slice.
- No removal of system-track bootstrap auth in this slice.
