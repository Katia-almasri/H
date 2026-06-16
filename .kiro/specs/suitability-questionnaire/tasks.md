# Implementation Plan: Suitability Questionnaire

> Convert the feature design into a series of prompts for a code-generation LLM that will implement each step with incremental progress. Make sure that each prompt builds on the previous prompts, and ends with wiring things together. There should be no hanging or orphaned code that isn't integrated into a previous step. Focus ONLY on tasks that involve writing, modifying, or testing code.

## Overview

Bottom-up implementation of `app/modules/suitability_questionnaire/` for the Harvest platform. Order: enums → models → migrations → repositories → pure scoring engine (with property-based tests) → schemas → services → router and dependency factories → KYC integration wiring → end-to-end tests. Every task uses Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 async, Pydantic v2, async-only, the `api_response` envelope, and `AppException` subclasses; every state-changing service writes to `audit_logs` inside its parent transaction; every read and write filters by the request's `tenant_id`.

## Tasks

- [x] 1. Define module enums
  - [x] 1.1 Add core lifecycle enums
    - Create `app/modules/suitability_questionnaire/enums/__init__.py`, `suitability_outcome.py` (`ELIGIBLE`, `ELIGIBLE_WITH_WARNING`, `NOT_SUITABLE`), `question_id.py` (`Q1`..`Q7`), `gate_decision_kind.py` (`ALLOW`, `SUITABILITY_REQUIRED`, `SUITABILITY_BLOCKED`, `SUITABILITY_ACK_REQUIRED`, `INVALID_SUBJECT`).
    - Use `StrEnum` so values match what is persisted in the DB.
    - _Requirements: 3.2, 8.2, 8.3, 8.4, 8.5, 8.6, 8.8_
  - [x] 1.2 Add per-question answer enums (Q1–Q7)
    - One enum per question following Appendix A: `net_worth_bracket.py`, `annual_income_bracket.py`, `allocation_bracket.py`, `liquidity_horizon.py`, `investment_experience.py`, `risk_response.py`, `investment_objective.py`.
    - Values must be the exact case-sensitive strings from Appendix A (e.g. `under_100k`, `between_2_5yr`, `buy_more`).
    - _Requirements: 2.1, 2.2_
  - [x] 1.3 Add warning, block, and audit enums
    - `warning_reason_code.py` (`SHORT_HORIZON`, `HIGH_CONCENTRATION`, `LOW_EXPERIENCE`).
    - Extend the shared `AuditAction` enum (in `app/modules/auth/enums/audit_action.py`) with `SUITABILITY_SUBMITTED`, `SUITABILITY_ACKNOWLEDGED`, `SUITABILITY_INVALIDATED`, `SUITABILITY_GATE_BLOCKED`.
    - Re-export every enum from `enums/__init__.py`.
    - _Requirements: 3.4, 3.10, 4.10, 7.4, 8.9_

- [x] 2. Define ORM models
  - [x] 2.1 Implement `InvestorSuitability` model
    - Create `app/modules/suitability_questionnaire/models/investor_suitability.py` with all columns from the design (`id`, `tenant_id`, `user_id`, `kyc_submission_id`, `answers` JSONB, `per_question_scores` JSONB, `total_score` SMALLINT, `outcome`, `warning_reasons` TEXT[], `block_reason`, `questionnaire_version`, `submission_ip` INET, `submission_user_agent`, `completed_at`, `expires_at`, `retake_allowed_at`, `superseded_by`, `created_at`).
    - Add CHECK constraints `total_score BETWEEN 0 AND 100`, `(outcome = 'NOT_SUITABLE') = (block_reason IS NOT NULL)`, `(outcome = 'NOT_SUITABLE') = (retake_allowed_at IS NOT NULL)`.
    - Add B-tree indexes `(tenant_id, user_id)` and `(tenant_id, expires_at)`.
    - _Requirements: 3.6, 3.7, 5.4, 6.1, 9.1_
  - [x] 2.2 Implement `SuitabilityAcknowledgement` model
    - Create `app/modules/suitability_questionnaire/models/suitability_acknowledgement.py` with `id`, `tenant_id`, `suitability_id`, `user_id`, `property_id`, `acknowledged_at`, `ip_address`, `user_agent`, `created_at`.
    - Add unique key on `(suitability_id, user_id, property_id, tenant_id)` to enable idempotent inserts.
    - Document at module level that the table is append-only and that the repository never exposes update or delete.
    - _Requirements: 4.3, 4.4, 4.5, 9.1_
  - [x] 2.3 Implement `SuitabilityCompletionMarker` model
    - Create `app/modules/suitability_questionnaire/models/suitability_completion_marker.py` with composite PK `(user_id, tenant_id)`, `kyc_submission_id`, `marked_at`.
    - _Requirements: 1.1, 1.2, 1.4_
  - [x] 2.4 Register models for Alembic autogenerate
    - Re-export the three models from `app/modules/suitability_questionnaire/models/__init__.py`.
    - Import them in `app/database.py` so Alembic detects them.
    - _Requirements: 9.6_

- [x] 3. Database migrations
  - [x] 3.1 Drop legacy `suitability_retake_requests` table
    - New Alembic revision under `migrations/versions/` with `op.drop_table("suitability_retake_requests")` in `upgrade()` and the corresponding recreate statement in `downgrade()` (mirror the original DDL from `aec47ab74cb0`).
    - _Requirements: 5.7 (the cool-off is now encoded by `retake_allowed_at` on the NOT_SUITABLE row, so the separate request table is redundant)_
  - [x] 3.2 Create `investor_suitability` table
    - New Alembic revision creating the table with all columns, CHECK constraints, and the two B-tree indexes from task 2.1.
    - _Requirements: 3.6, 3.7, 9.6_
  - [x] 3.3 Create `suitability_completion_markers` table
    - New Alembic revision creating the table with composite PK `(user_id, tenant_id)` and a B-tree index on `tenant_id`.
    - _Requirements: 1.1, 1.4_
  - [x] 3.4 Add `tenant_id` to `suitability_acknowledgements`
    - New Alembic revision: `op.add_column("suitability_acknowledgements", sa.Column("tenant_id", sa.Text(), nullable=False, server_default="harvest-uae"))`, then drop the server default after backfill, add an index on `tenant_id`, and add a unique key on `(suitability_id, user_id, property_id, tenant_id)`.
    - _Requirements: 4.5, 9.1, 9.6_
  - [x] 3.5 Add `unique_active_suitability` partial unique index
    - New Alembic revision creating the partial unique index `unique_active_suitability` on `investor_suitability(tenant_id, user_id) WHERE superseded_by IS NULL`. Use `op.create_index(..., postgresql_where=sa.text("superseded_by IS NULL"))`.
    - _Requirements: 3.9, 9.6, 9.7_
  - [x] 3.6 Add RLS policy denying UPDATE/DELETE on `suitability_acknowledgements`
    - New Alembic revision that enables RLS on `suitability_acknowledgements` and creates two restrictive policies that deny UPDATE and DELETE for all roles (mirror the pattern used by `audit_logs`, `governance_votes`, `user_agreements`).
    - Use raw `op.execute("ALTER TABLE ... ENABLE ROW LEVEL SECURITY; CREATE POLICY ...")` statements with matching `DROP POLICY` calls in `downgrade()`.
    - _Requirements: 4.4_

- [x] 4. Repositories
  - [x] 4.1 Implement `InvestorSuitabilityRepository`
    - Create `app/modules/suitability_questionnaire/repositories/investor_suitability_repository.py` with `get_active(user_id, tenant_id)`, `get_latest_not_suitable(user_id, tenant_id)`, `get_by_id(record_id, tenant_id)`, `supersede_and_insert(new_record, prior_active_id)` (atomic UPDATE prior + INSERT new under the outer transaction), `mark_expired_now(record_id, tenant_id)`, and a paged scan helper for renewal notifications keyed on `(tenant_id, expires_at)`.
    - Every method MUST filter by `tenant_id`.
    - _Requirements: 3.8, 3.9, 5.5, 5.7, 6.1, 6.2, 7.2, 8.2, 8.3, 9.3, 9.5_
  - [x] 4.2 Implement `SuitabilityAcknowledgementRepository`
    - Create `app/modules/suitability_questionnaire/repositories/suitability_acknowledgement_repository.py` with `get(suitability_id, user_id, property_id, tenant_id)` and `idempotent_create(record)` using `INSERT ... ON CONFLICT (suitability_id, user_id, property_id, tenant_id) DO NOTHING RETURNING *` followed by a SELECT fallback when nothing was returned.
    - Do not expose `update` or `delete` methods.
    - _Requirements: 4.3, 4.4, 4.5, 8.4, 8.6, 9.3, 9.5_
  - [x] 4.3 Implement `SuitabilityCompletionMarkerRepository`
    - Create `app/modules/suitability_questionnaire/repositories/suitability_completion_marker_repository.py` with `mark(user_id, tenant_id, kyc_submission_id)` using `ON CONFLICT (user_id, tenant_id) DO NOTHING`, `clear(user_id, tenant_id)`, and `exists(user_id, tenant_id)`.
    - Re-export all three repositories from `repositories/__init__.py`.
    - _Requirements: 1.1, 1.4_

- [x] 5. Pure scoring engine
  - [x] 5.1 Define `questionnaire_definition.py`
    - Create `app/modules/suitability_questionnaire/services/scoring_engine/questionnaire_definition.py` with `QUESTIONNAIRE_VERSION: int = 1`, frozen dataclass `QuestionDefinition(id: QuestionId, weight: float, answer_scores: Mapping[str, int])`, and the `QUESTION_DEFINITIONS` tuple containing all seven questions with weights and per-answer scores from Appendix A.1.
    - Verify at module import that `sum(weight) == 1.30` and that every answer enum value has an entry in `answer_scores`.
    - _Requirements: 2.1, 2.7, Appendix A.1_
  - [x] 5.2 Implement `scorer.py`
    - Create `app/modules/suitability_questionnaire/services/scoring_engine/scorer.py` with frozen dataclass `ScoringResult(total_score, per_question_scores, outcome, warning_reasons, block_reason)`.
    - Implement `score_submission(answers: dict[QuestionId, str]) -> ScoringResult` and `classify_outcome(total_score: int) -> SuitabilityOutcome` using thresholds from Appendix A.2 (`>= 65` → `ELIGIBLE`, `40..64` → `ELIGIBLE_WITH_WARNING`, `< 40` → `NOT_SUITABLE`).
    - The function must be pure: no DB, no `datetime.now()`, no I/O. Compute `raw = sum(answer_score * weight)`, `total = round(raw / sum(weights) * 100 / 100)` so the result lies in `[0, 100]`.
    - Re-export `score_submission` and `ScoringResult` from `services/scoring_engine/__init__.py`.
    - _Requirements: 3.1, 3.2, 3.3, 3.6_
  - [x] 5.3 Implement `warning_rules.py`
    - Create `compute_warning_reasons(answers, outcome, total_score) -> list[WarningReasonCode]` returning an empty list unless `outcome == ELIGIBLE_WITH_WARNING`. Encode the three rules from Appendix A.3 (`SHORT_HORIZON` when `Q4 == between_2_5yr` and `total_score < 65`, `HIGH_CONCENTRATION` when `Q3 == between_20_50pct`, `LOW_EXPERIENCE` when `Q5 in {none, stocks_bonds}`).
    - _Requirements: 3.4, 4.1, 4.8, 4.9_
  - [x] 5.4 Implement `block_rules.py`
    - Define module-level constants `BLOCK_REASON_SHORT_HORIZON`, `BLOCK_REASON_HIGH_CONCENTRATION`, `BLOCK_REASON_NO_EXPERIENCE`, `BLOCK_REASON_GENERIC` with the verbatim text from Appendix A.4.
    - Implement `compute_block_reason(answers, outcome) -> str | None` returning `None` unless `outcome == NOT_SUITABLE`, then selecting exactly one reason via the priority order in Appendix A.4 (Q4 → Q3 → Q5∧Q6 → generic).
    - Wire `compute_warning_reasons` and `compute_block_reason` into `score_submission` so `ScoringResult` carries both fields.
    - _Requirements: 3.5, 5.2, 5.3_
  - [ ]* 5.5 Property test — Determinism of `score_submission`
    - **Property 1: Determinism** — for any valid answers tuple, calling `score_submission` twice yields equal `ScoringResult`s.
    - Use Hypothesis strategies built from the question answer enums.
    - **Validates: Requirements 3.1, 3.3**
  - [ ]* 5.6 Property test — `total_score` bounded in `[0, 100]`
    - **Property 2: Bounded score** — for any valid answers, `0 <= total_score <= 100`.
    - **Validates: Requirements 3.1**
  - [ ]* 5.7 Property test — Outcome thresholds match Appendix A.2
    - **Property 3: Outcome partition** — `total_score >= 65 ⇒ ELIGIBLE`, `40 <= total_score <= 64 ⇒ ELIGIBLE_WITH_WARNING`, `total_score < 40 ⇒ NOT_SUITABLE`.
    - **Validates: Requirements 3.2**
  - [ ]* 5.8 Property test — Block-reason priority order (Appendix A.4)
    - **Property 4: Block-reason priority** — when `outcome == NOT_SUITABLE`, `block_reason` is non-null, equals one of the four module constants, and follows the priority `Q4=under_2yr` ≻ `Q3=over_50pct` ≻ `(Q5=none ∧ Q6=sell_immediately)` ≻ generic. When `outcome != NOT_SUITABLE`, `block_reason is None`.
    - **Validates: Requirements 3.5**
  - [ ]* 5.9 Property test — Idempotency of repeated scoring
    - **Property 5: Idempotency** — re-scoring the same answers tuple any number of times never changes the result; round-trip through `dataclasses.asdict` and back preserves equality.
    - **Validates: Requirements 3.3, 3.6**
  - [ ]* 5.10 Unit tests for warning rules and edge cases
    - Cover each warning code in isolation, the empty warning set when `outcome != ELIGIBLE_WITH_WARNING`, and the answer combinations on every threshold boundary (39/40, 64/65).
    - _Requirements: 3.2, 3.4_

- [ ] 6. Checkpoint
  - Ensure all scoring engine tests pass, ask the user if questions arise.

- [x] 7. Pydantic schemas
  - [x] 7.1 Request schemas
    - Create `schemas/requests/submit_questionnaire.py` (`SubmitQuestionnaireRequest` with `questionnaire_version: int (ge=1)` and `answers: dict[QuestionId, str]`) and `schemas/requests/acknowledge_warning.py` (empty body — `property_id` is the URL path parameter).
    - Use Pydantic v2 strict mode. Re-export from `schemas/requests/__init__.py`.
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.8_
  - [x] 7.2 Response schemas
    - Create one file each in `schemas/responses/`: `questionnaire.py` (questions + version + answer enumerations), `status.py` (`SuitabilityStatusResponse` with `state`, `can_invest`, `outcome`, `total_score`, `warning_reasons`, `block_reason`, `expires_at`, `renewal_due`, `renewal_required`, `retake_allowed_at`, `minimum_share_size_aed`, `questionnaire_version`, `message`), `submission_result.py`, `acknowledgement.py` (status and confirmation), `gate_decision.py` (mirrors the `GateDecision` dataclass).
    - Re-export from `schemas/responses/__init__.py`.
    - _Requirements: 1.2, 4.1, 4.8, 5.2, 5.3, 6.1, 6.3, 8.2, 8.3, 8.4, 8.5, 8.6_

- [ ] 8. Services
  - [-] 8.1 Implement `SuitabilityService` (orchestrator)
    - Create `app/modules/suitability_questionnaire/services/suitability_service.py` with `get_questionnaire`, `get_status`, and `submit_questionnaire`.
    - `submit_questionnaire` must run inside a single `async with self.db.begin()` block: verify approved KYC exists in tenant, verify `questionnaire_version` matches the engine's current version, verify the cool-off has elapsed if a prior `NOT_SUITABLE` record exists, call `score_submission`, supersede the prior active record + insert the new record via `InvestorSuitabilityRepository.supersede_and_insert`, clear the completion marker, and write a `SUITABILITY_SUBMITTED` audit log. Any failure must roll back the entire transaction.
    - Reject cross-tenant resource references with `AuthorizationException` and indistinguishable-from-not-found responses.
    - _Requirements: 1.4, 1.5, 1.6, 1.7, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 3.1, 3.6, 3.7, 3.8, 3.10, 3.11, 3.12, 5.4, 5.5, 5.6, 5.7, 6.5, 9.1, 9.2, 9.3, 9.4, 9.5, 9.7_
  - [-] 8.2 Implement `SuitabilityGateService`
    - Create `app/modules/suitability_questionnaire/services/suitability_gate_service.py` with `evaluate(user_id, tenant_id, property_id, ip_address, user_agent) -> GateDecision`.
    - Read at most twice (`get_active`, `get_acknowledgement`); never use cache (Sprint-1 rule). Map states to `GateDecisionKind`: missing/expired record → `SUITABILITY_REQUIRED` with `reason_indicator` `NO_RECORD`/`EXPIRED`; outcome `NOT_SUITABLE` → `SUITABILITY_BLOCKED` with `block_reason` and `retake_allowed_at`; outcome `ELIGIBLE_WITH_WARNING` without acknowledgement → `SUITABILITY_ACK_REQUIRED` with `warning_reasons` and `property_id`; with acknowledgement → `ALLOW`; outcome `ELIGIBLE` → `ALLOW`; cross-tenant subject → `INVALID_SUBJECT`.
    - On every blocking decision write a `SUITABILITY_GATE_BLOCKED` audit log (best effort, separate transaction or caller's transaction depending on call site).
    - Define `SuitabilityGateBlocked` exception in the module's `exceptions.py` for the future Investment module to raise.
    - _Requirements: 1.3, 4.2, 4.9, 5.1, 5.2, 6.2, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 9.3, 9.4, 9.5_
  - [-] 8.3 Implement `SuitabilityRenewalService`
    - Create `app/modules/suitability_questionnaire/services/suitability_renewal_service.py` with three methods:
      - `on_kyc_approved(user_id, tenant_id, kyc_submission_id)` — idempotent insert into `suitability_completion_markers`. Caller-driven transaction.
      - `on_material_kyc_change(user_id, tenant_id, field_name)` — fetch active record, set `expires_at = utcnow()` on it, write `SUITABILITY_INVALIDATED` audit log; no-op when no active record. Caller-driven transaction. Allowed `field_name` values: `nationality`, `source_of_funds`.
      - `enqueue_renewal_notifications()` — periodic worker scanning records due for renewal (within 30 days before or 30 days after `expires_at`); enforce at-most-once-per-24h-per-investor and at-most-four-per-record using Redis keys `sq:renewal:<suitability_id>:count` and `sq:renewal:<suitability_id>:last_at`; dispatch via the existing notification module.
    - _Requirements: 1.1, 1.4, 6.1, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
  - [ ] 8.4 Implement `SuitabilityAcknowledgementService`
    - Create `app/modules/suitability_questionnaire/services/suitability_acknowledgement_service.py` with `get_acknowledgement_status(user_id, tenant_id, property_id)` and `acknowledge(user_id, tenant_id, property_id, ip_address, user_agent)`.
    - `acknowledge` runs inside `async with self.db.begin()`: verify active record exists and outcome is `ELIGIBLE_WITH_WARNING`, idempotently insert via the repository, write a `SUITABILITY_ACKNOWLEDGED` audit log; rollback on any failure including audit failure.
    - Re-export every service from `services/__init__.py`.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.10, 4.11, 6.6, 9.1, 9.4_
  - [ ]* 8.5 Unit tests for services
    - Test each service against fakeredis and an in-memory SQLite or test Postgres fixture: happy paths, validation errors, cross-tenant rejection, transaction rollback when the audit write fails, idempotent acknowledgement, cool-off enforcement, version-mismatch rejection.
    - _Requirements: 1.6, 1.7, 2.8, 3.11, 4.5, 4.7, 5.5, 7.5, 9.4, 9.7_

- [ ] 9. Router and dependency injection
  - [ ] 9.1 Implement dependency factories
    - Create `app/modules/suitability_questionnaire/dependencies.py` with `get_suitability_service`, `get_suitability_gate_service`, `get_suitability_renewal_service`, `get_suitability_acknowledgement_service`, each receiving `Annotated[AsyncSession, Depends(get_db)]` and `Annotated[Redis, Depends(get_redis)]` where appropriate.
    - _Requirements: tech.md DI rule_
  - [ ] 9.2 Implement router endpoints
    - Create `app/modules/suitability_questionnaire/router.py` with the five routes from the design under `/suitability`: `GET /questionnaire`, `GET /status`, `POST /submit`, `GET /properties/{property_id}/acknowledgement`, `POST /properties/{property_id}/acknowledge`.
    - Apply `RoleChecker(allowed_roles=[UserRole.INVESTOR])`. Resolve `tenant_id` via `get_current_tenant()`. Pass `request.client.host` and `request.headers.get("user-agent")` into the service. Return every response via `api_response(...)`. Raise only `AppException` subclasses on failure.
    - _Requirements: 1.2, 1.7, 2.1, 4.1, 4.2, 4.8, 5.3, 8.1, 9.2, 9.4_
  - [ ] 9.3 Register the router
    - Import and `include_router(suitability_router)` in `app/api/v1/routes.py` so the routes are mounted under `/api/v1/suitability`.
    - _Requirements: API contract rule (`/api/v1/` prefix)_

- [ ] 10. KYC integration wiring
  - [ ] 10.1 Wire `on_kyc_approved` into KYC approval transaction
    - Modify `app/modules/kyc/services/kyc_service.py` `approve_kyc` (or equivalent approval method): inside the existing approval transaction, after the KYC submission row is updated and the approval audit log is written, call `await SuitabilityRenewalService(self.db).on_kyc_approved(user_id, tenant_id, submission.id)` so the completion marker write commits or rolls back atomically with the KYC approval.
    - _Requirements: 1.1, 1.4_
  - [ ] 10.2 Wire `on_material_kyc_change` into KYC change flow
    - In the same `kyc_service.py`, on every approved change to `nationality` or `source_of_funds`, call `await SuitabilityRenewalService(self.db).on_material_kyc_change(user_id, tenant_id, field_name)` inside the change transaction. Detect "material change" by comparing the prior persisted value to the new approved value before writing.
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
  - [ ]* 10.3 Integration tests for KYC → suitability hooks
    - First KYC approval inserts exactly one completion marker (idempotent on repeat).
    - Approved nationality change with an active record sets `expires_at = utcnow()` and writes `SUITABILITY_INVALIDATED`.
    - No-op when no active record exists.
    - Audit-write failure rolls back the entire KYC change transaction.
    - _Requirements: 1.1, 7.2, 7.3, 7.4, 7.5_

- [ ]* 11. End-to-end integration tests for endpoints
  - [ ]* 11.1 End-to-end tests via `httpx.AsyncClient`
    - Cover: questionnaire fetch returns the seven questions with current version; valid submission returns `ELIGIBLE` and clears the completion marker; submission with an invalid answer value returns 422; submission with stale version returns 422; submission within the 30-day cool-off after `NOT_SUITABLE` returns 422 with the `retake_allowed_at` timestamp; status endpoint reports `renewal_due` 30 days before expiry and `renewal_required` after; acknowledgement endpoint is idempotent; cross-tenant access returns the same response shape as not-found.
    - _Requirements: 1.2, 2.1, 2.5, 2.8, 3.2, 5.5, 6.1, 6.3, 4.5, 9.4_

- [ ] 12. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP. Core implementation tasks are never optional.
- Each task references the requirement clauses it satisfies for traceability.
- Property tests target the pure scoring engine because it is deterministic, isolated, and fully covered by Appendix A. Persistence and gating logic are validated by service-level and end-to-end tests.
- Every service write runs inside an explicit transaction (`async with self.db.begin()`) and writes the corresponding `audit_logs` entry in the same transaction; an audit-write failure rolls back the whole submission, acknowledgement, or invalidation per the audit rule.
- The legacy `suitability_retake_requests` table is removed (task 3.1) because the 30-day cool-off is fully encoded by `retake_allowed_at` on the `NOT_SUITABLE` record; keeping a separate table would create a second source of truth.
- All endpoints return the unified `api_response` envelope; all errors are `AppException` subclasses converted by the global handler.
- All code is async-only — no synchronous DB calls or blocking I/O in the request path.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1", "2.2", "2.3", "5.1", "7.1", "7.2"] },
    { "id": 2, "tasks": ["2.4", "3.1", "4.1", "4.2", "4.3", "5.2", "5.3", "5.4"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "5.5", "5.6", "5.7", "5.8", "5.9", "5.10", "8.1", "8.2", "8.3", "8.4"] },
    { "id": 4, "tasks": ["3.5", "3.6", "8.5", "9.1"] },
    { "id": 5, "tasks": ["9.2", "10.1"] },
    { "id": 6, "tasks": ["9.3", "10.2"] },
    { "id": 7, "tasks": ["10.3", "11.1"] }
  ]
}
```
