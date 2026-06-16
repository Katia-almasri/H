# Requirements Document

## Introduction

The Suitability Questionnaire is a regulatory feature of the Harvest platform (DFSA Crowdfunding, DIFC) that assesses each investor's financial capacity, investment horizon, experience, and risk tolerance before allowing fractional real estate investments. Per FR-INV-023 through FR-INV-027, the questionnaire is presented on first KYC approval, gates the first investment, and produces one of three outcomes (ELIGIBLE, ELIGIBLE_WITH_WARNING, NOT_SUITABLE) using the deterministic scoring logic defined in Appendix A. The questionnaire results are persisted alongside answers and timestamps, and they drive downstream investment-gating rules (per-property risk acknowledgement for warnings, hard block with a 30-day re-take window for non-suitable outcomes).

This feature lives in the `app/modules/suitability/` module and integrates with the KYC module (gating trigger), the Investment module (pre-purchase gate), the Audit Log module (state-change logging), and the Notification module (renewal reminders). All requirements are scoped per tenant and respect the platform's append-only audit and multi-tenancy rules.

## Glossary

- **Suitability_Service**: The application service in `app/modules/suitability/` that orchestrates submission, scoring, persistence, and gating decisions for the suitability questionnaire.
- **Scoring_Engine**: Pure-function module within Suitability_Service that computes the total score, outcome, warning reasons, and block reason from a set of answers without database access.
- **Investment_Gate**: The pre-purchase check exposed by Suitability_Service and invoked by the Investment module before any share purchase.
- **Investor**: An authenticated user with the investor role whose KYC submission has been approved.
- **Suitability_Record**: The persisted row representing a single completed questionnaire submission, including answers, per-question scores, total score, outcome, warning reasons, block reason, completion timestamp, expiry timestamp, and (for NOT_SUITABLE) re-take-allowed timestamp.
- **Active_Suitability_Record**: The non-superseded Suitability_Record for an Investor within a tenant (at most one).
- **Outcome**: One of `ELIGIBLE`, `ELIGIBLE_WITH_WARNING`, or `NOT_SUITABLE`, computed by the Scoring_Engine from the total score per Appendix A.
- **Warning_Acknowledgement**: An append-only record capturing that an Investor has explicitly acknowledged the risk warning for a specific property when their Outcome is `ELIGIBLE_WITH_WARNING`.
- **Re_Take_Window**: The 30-day cool-off period following a `NOT_SUITABLE` Outcome during which the Investor cannot resubmit the questionnaire.
- **Renewal_Period**: The 365-day validity window of an Active_Suitability_Record after which the questionnaire must be re-taken before the next investment.
- **Material_KYC_Change**: A change to an Investor's nationality or source-of-funds field on their KYC profile that invalidates the current Active_Suitability_Record.
- **Minimum_Share_Size**: The platform-defined minimum investment amount (AED 500 per the product steering) shown to NOT_SUITABLE investors as an informational alternative starting point.
- **Audit_Log**: The append-only `audit_logs` table where every state-changing action is recorded.
- **Tenant_Id**: The tenant discriminator read from the `X-Tenant-ID` header that scopes every query and write.

## Requirements

### Requirement 1: Questionnaire Gating on First KYC Approval

**User Story:** As an Investor, I want the suitability questionnaire to be presented to me after my KYC is approved, so that I understand the platform's risk profile before making my first investment.

#### Acceptance Criteria

1. WHEN an Investor's KYC submission transitions to the approved state for the first time within a Tenant_Id, THE Suitability_Service SHALL mark the Investor as requiring suitability completion within the same database transaction that records the KYC approval, and SHALL be idempotent so that subsequent approvals of the same KYC submission do not alter the existing requiring-completion marker or any existing Active_Suitability_Record.
2. WHEN an authenticated Investor with no Active_Suitability_Record for the current Tenant_Id requests the questionnaire status, THE Suitability_Service SHALL return a status response containing a required-state indicator equal to `SUITABILITY_REQUIRED`, a boolean `can_invest` field set to false, and a human-readable message indicating that questionnaire completion is required before investing.
3. WHILE an Investor has no Active_Suitability_Record for the current Tenant_Id, OR is marked as requiring suitability completion without a corresponding Active_Suitability_Record, THE Investment_Gate SHALL block every investment attempt by that Investor by returning a `SUITABILITY_REQUIRED` blocking decision and SHALL prevent any payment, escrow, or ledger operation from being initiated for that attempt.
4. WHEN an Investor with no Active_Suitability_Record successfully completes the questionnaire and the resulting Suitability_Record is persisted, THE Suitability_Service SHALL atomically, within the same database transaction, set the new Suitability_Record as the Active_Suitability_Record and clear the requiring-completion marker so that the next Investment_Gate evaluation for that Investor and Tenant_Id uses the new record without requiring any further action by the Investor.
5. WHEN an Investor submits the questionnaire, THE Suitability_Service SHALL verify, before persisting any data, that the Investor has at least one KYC submission in the approved state within the same Tenant_Id as the current request.
6. IF an Investor submits the questionnaire and no KYC submission in the approved state exists for that Investor within the current Tenant_Id, THEN THE Suitability_Service SHALL reject the submission with a validation error indicating that an approved KYC is required, SHALL NOT create or modify any Suitability_Record, and SHALL leave any existing requiring-completion marker unchanged.
7. IF the questionnaire status or submission request resolves to a Tenant_Id that differs from the Tenant_Id on the Investor's KYC submission or on any existing Suitability_Record for that Investor, THEN THE Suitability_Service SHALL reject the request with an authorisation error and SHALL NOT disclose data from the other tenant.

### Requirement 2: Questionnaire Composition

**User Story:** As an Investor, I want to answer a fixed set of questions about my finances, experience, and goals, so that the platform can assess whether the product is suitable for me.

#### Acceptance Criteria

1. WHEN an Investor requests the questionnaire, THE Suitability_Service SHALL return exactly seven questions per submission in the following fixed order: (1) net-worth bracket, (2) annual-income bracket, (3) investable-asset allocation percentage to the platform, (4) intended liquidity horizon, (5) prior investment experience, (6) risk-response scenario, (7) primary investment objective, together with the current questionnaire version identifier and, for each question, the complete enumerated answer set defined in Appendix A.
2. WHEN an Investor submits the questionnaire, THE Suitability_Service SHALL accept an answer for each question only if its value is exactly equal (case-sensitive string match) to one of the enumerated answer values defined for that question in Appendix A.
3. WHEN an Investor submits the questionnaire, THE Suitability_Service SHALL require exactly one answer for each of the seven questions in a single atomic submission, persisting the Suitability_Record only if all seven answers are valid and rolling back the entire submission transaction otherwise.
4. IF a submission is missing one or more of the seven required answers, THEN THE Suitability_Service SHALL reject the submission with a validation error that identifies every missing question by its question identifier and persist no Suitability_Record.
5. IF a submission contains, for any question, a value that is not in the enumerated answer set defined for that question in Appendix A, THEN THE Suitability_Service SHALL reject the submission with a validation error that identifies every invalid question by its question identifier and persist no Suitability_Record.
6. IF a submission contains any answer for a question identifier not in the seven defined questions, OR contains more than one answer for the same question, THEN THE Suitability_Service SHALL reject the submission with a validation error identifying the unexpected or duplicated question and persist no Suitability_Record.
7. WHEN a submission is accepted, THE Suitability_Service SHALL persist the questionnaire version identifier in effect at the time of submission on the resulting Suitability_Record, where the version identifier is a monotonically increasing positive integer that changes whenever the question set, enumerated answer values, weights, per-answer scores, or outcome thresholds in Appendix A change.
8. IF the questionnaire version identifier supplied by the client in a submission does not match the current questionnaire version identifier maintained by the Suitability_Service, THEN THE Suitability_Service SHALL reject the submission with a validation error indicating that the questionnaire version is out of date and persist no Suitability_Record.

### Requirement 3: Suitability Outcome Computation and Persistence

**User Story:** As the platform, I want to compute a deterministic suitability outcome from each set of answers and persist the result, so that downstream gating and regulatory audit are reliable.

#### Acceptance Criteria

1. WHEN the Suitability_Service receives a valid submission, THE Scoring_Engine SHALL compute a total score as an integer in the inclusive range 0 to 100 using the weighted scoring matrix and normalisation formula defined in Appendix A, returning the result within 200 milliseconds.
2. THE Scoring_Engine SHALL assign exactly one Outcome per submission as follows: a total score in the inclusive range 65 to 100 yields `ELIGIBLE`; a total score in the inclusive range 40 to 64 yields `ELIGIBLE_WITH_WARNING`; a total score in the inclusive range 0 to 39 yields `NOT_SUITABLE`.
3. THE Scoring_Engine SHALL be a pure function of the seven enumerated answers, producing identical outputs for identical inputs without any database, network, file system, or clock access.
4. WHEN the Outcome is `ELIGIBLE_WITH_WARNING`, THE Scoring_Engine SHALL compute the set of applicable warning reason codes per the rules in Appendix A section A.3, returning an empty set when no rule matches and at most three codes when all rules match.
5. WHEN the Outcome is `NOT_SUITABLE`, THE Scoring_Engine SHALL compute exactly one block reason selected by the first matching rule in the priority order defined in Appendix A section A.4, with the reason text drawn verbatim from that section.
6. WHEN a submission is accepted, THE Suitability_Service SHALL persist a Suitability_Record containing the raw answers for all seven questions, the per-question weighted scores, the total score, the Outcome, the warning reason codes (empty list when none apply), the block reason (null when Outcome is not `NOT_SUITABLE`), the questionnaire version, and the submission timestamp recorded in UTC with millisecond precision.
7. WHEN a Suitability_Record is created, THE Suitability_Service SHALL set its expiry timestamp to the submission timestamp plus exactly 365 calendar days, recorded in UTC.
8. WHEN a Suitability_Record is created and a previous Active_Suitability_Record exists for the same Investor and Tenant_Id, THE Suitability_Service SHALL mark the previous record as superseded by the new record's id within the same database transaction, so that either both writes commit or neither is persisted.
9. THE Suitability_Service SHALL maintain at most one Active_Suitability_Record per Investor per Tenant_Id at any time, enforced by a database uniqueness constraint on the (user_id, tenant_id, active) tuple.
10. WHEN a Suitability_Record is created, THE Suitability_Service SHALL write an entry to the Audit_Log with the action `SUITABILITY_SUBMITTED`, the Investor's user id, the submitter IP address, the user agent string truncated to 512 characters, the UTC timestamp with millisecond precision, and metadata containing the Outcome, total score, and superseded record id (null when none existed), within the same database transaction as the Suitability_Record write.
11. IF the Audit_Log write fails for any reason, THEN THE Suitability_Service SHALL roll back the entire submission transaction so that no Suitability_Record is persisted, no previous record is marked superseded, and the submission request returns an error response indicating that the submission could not be recorded.
12. THE Suitability_Service SHALL filter every read and write of suitability data by the Tenant_Id resolved from the current request, and IF a request references a Suitability_Record belonging to a different Tenant_Id, THEN THE Suitability_Service SHALL reject the request with an authorisation error and SHALL NOT disclose the existence of the record.

### Requirement 4: ELIGIBLE_WITH_WARNING Acknowledgement Flow

**User Story:** As an Investor with an ELIGIBLE_WITH_WARNING outcome, I want to see a clear risk warning and explicitly acknowledge it on the investment screen, so that I confirm I understand the risks before investing.

#### Acceptance Criteria

1. WHILE an Investor's Active_Suitability_Record has the Outcome `ELIGIBLE_WITH_WARNING`, THE Suitability_Service SHALL include the warning reason codes from that record in the questionnaire-status response so that the investment screen can display the corresponding risk warning text.
2. WHEN an Investor with `ELIGIBLE_WITH_WARNING` initiates investment in a property, THE Investment_Gate SHALL require a Warning_Acknowledgement scoped to the same Active_Suitability_Record id, the same user id, and the target property id, all within the current Tenant_Id, before allowing the investment to proceed.
3. WHEN an Investor submits a Warning_Acknowledgement for a property, THE Suitability_Service SHALL persist a Warning_Acknowledgement record containing the Active_Suitability_Record id, user id, property id, acknowledgement timestamp in UTC, IP address, user agent, and Tenant_Id in a single atomic database transaction.
4. THE Suitability_Service SHALL persist Warning_Acknowledgement records as append-only, rejecting any update attempt with an authorisation error and responding to any delete attempt with a success status while leaving the stored record unchanged and accessible for read by subsequent queries within the same Tenant_Id.
5. WHEN an Investor submits a Warning_Acknowledgement for a property where a record already exists for the same Active_Suitability_Record id, user id, property id, and Tenant_Id, THE Suitability_Service SHALL return the existing record without creating a duplicate row.
6. IF an Investor whose Active_Suitability_Record Outcome is not `ELIGIBLE_WITH_WARNING` submits a Warning_Acknowledgement, THEN THE Suitability_Service SHALL reject the submission with a validation error indicating that the current Outcome does not require acknowledgement, and SHALL NOT create any Warning_Acknowledgement record.
7. IF an Investor submits a Warning_Acknowledgement while they have no Active_Suitability_Record, or while their Active_Suitability_Record is superseded or has an expiry timestamp at or before the current UTC time, THEN THE Suitability_Service SHALL reject the submission with a validation error indicating that an active suitability record is required and SHALL NOT create any Warning_Acknowledgement record.
8. WHEN an Investor with `ELIGIBLE_WITH_WARNING` requests access to the investment screen for a property without a corresponding Warning_Acknowledgement, THE Suitability_Service SHALL return a response containing an acknowledgement-required indicator, the property id, and the warning reason codes, so the client can present the acknowledgement step before any investment input is collected.
9. WHEN an Investor with `ELIGIBLE_WITH_WARNING` attempts to invest in a property without a corresponding Warning_Acknowledgement, THE Investment_Gate SHALL block the investment and return a response containing an acknowledgement-required indicator, the property id, and the warning reason codes.
10. WHEN a Warning_Acknowledgement is persisted, THE Suitability_Service SHALL write an entry to the Audit_Log with the action `SUITABILITY_ACKNOWLEDGED`, the Investor's user id, IP address, user agent, UTC timestamp, and metadata containing the property id and Active_Suitability_Record id, within the same database transaction as the acknowledgement persistence.
11. IF the Audit_Log write for a Warning_Acknowledgement fails, THEN THE Suitability_Service SHALL roll back the entire transaction so that no Warning_Acknowledgement record is persisted.

### Requirement 5: NOT_SUITABLE Block, Disclosure, and Re-take Window

**User Story:** As an Investor with a NOT_SUITABLE outcome, I want a clear explanation of why I cannot invest and an alternative starting point, so that I can make an informed decision and re-attempt later.

#### Acceptance Criteria

1. WHILE an Investor's Active_Suitability_Record has the Outcome `NOT_SUITABLE`, THE Investment_Gate SHALL block every investment attempt by that Investor and signal a `SUITABILITY_BLOCKED` decision indicating that the Investor is not suitable to invest.
2. WHEN the Investment_Gate blocks an investment due to a `NOT_SUITABLE` Outcome, THE Suitability_Service SHALL return the block reason and the re-take-allowed timestamp from the Active_Suitability_Record so that the investment screen can display the explanation and the date on which re-take becomes available.
3. WHEN an Investor with Outcome `NOT_SUITABLE` requests the questionnaire status, THE Suitability_Service SHALL include the platform Minimum_Share_Size value in AED, the block reason, and the re-take-allowed timestamp in the response so the client can display the alternative starting point alongside the cool-off information.
4. WHEN a Suitability_Record with Outcome `NOT_SUITABLE` is created, THE Suitability_Service SHALL set its re-take-allowed timestamp to the submission timestamp plus exactly 30 calendar days, expressed in UTC.
5. IF an Investor submits a new questionnaire and the current UTC time is before the re-take-allowed timestamp of the Investor's most recent `NOT_SUITABLE` Suitability_Record, THEN THE Suitability_Service SHALL reject the submission with a validation error indicating the cool-off period is in effect and including the re-take-allowed timestamp in ISO 8601 UTC format.
6. WHEN the current UTC time reaches or exceeds the re-take-allowed timestamp of the Investor's most recent `NOT_SUITABLE` Suitability_Record, THE Suitability_Service SHALL accept a new submission from the Investor and process it per Requirement 3.
7. THE Suitability_Service SHALL retain every superseded Suitability_Record row for the Investor without deletion or modification so that the Investor's complete historical suitability assessments remain available for audit and regulatory review.

### Requirement 6: Annual Renewal of Suitability

**User Story:** As the platform, I want suitability assessments to expire after 365 days, so that an Investor's profile is re-confirmed periodically per regulatory expectations.

#### Acceptance Criteria

1. WHEN the current UTC time reaches or exceeds the expiry timestamp of an Active_Suitability_Record, THE Suitability_Service SHALL set a renewal-required flag to true in the questionnaire-status response for that Investor so that the client and the Investment_Gate observe a deterministic due-for-renewal state.
2. WHILE an Active_Suitability_Record is due for renewal, THE Investment_Gate SHALL block new investment attempts by that Investor with a `SUITABILITY_REQUIRED` blocking decision until a new Suitability_Record is persisted as the Active_Suitability_Record for that Investor and Tenant_Id.
3. WHILE the current UTC time is within the 30-day window ending at the expiry timestamp of an Active_Suitability_Record and has not yet reached that expiry timestamp, THE Suitability_Service SHALL include a boolean renewal-due indicator set to true in the questionnaire-status response for that Investor.
4. WHEN the current UTC time is within the 30-day window ending at the expiry timestamp of an Active_Suitability_Record, OR is at or after the expiry timestamp and no more than 30 days past it, THE Suitability_Service SHALL queue a renewal notification to the Investor through the Notification module at most once per rolling 24-hour period per Investor and at most four total notifications per Active_Suitability_Record.
5. WHEN an Investor submits a new questionnaire at or after the expiry timestamp of their previous Active_Suitability_Record, THE Suitability_Service SHALL process the submission per Requirement 3 and set the new record's expiry timestamp to the new submission timestamp plus 365 days.
6. WHEN a new Active_Suitability_Record is created as a result of renewal, THE Suitability_Service SHALL treat all Warning_Acknowledgement records associated with previous Active_Suitability_Records as invalid for the new Active_Suitability_Record so that an Investor with a renewed `ELIGIBLE_WITH_WARNING` Outcome must submit a new Warning_Acknowledgement per property before the Investment_Gate allows an investment in that property.

### Requirement 7: KYC-Triggered Suitability Invalidation

**User Story:** As the platform, I want suitability to be re-taken when an Investor's KYC profile changes materially, so that the assessment remains aligned with the Investor's current circumstances.

#### Acceptance Criteria

1. THE Suitability_Service SHALL define a Material_KYC_Change as any approved change to the Investor's nationality value or source-of-funds value on the KYC profile, where "approved change" means the new value differs from the prior persisted value and the KYC update has transitioned to the approved state within the same Tenant_Id.
2. WHEN a Material_KYC_Change is recorded for an Investor with an Active_Suitability_Record within the same Tenant_Id, THE Suitability_Service SHALL set the expiry timestamp of that Active_Suitability_Record to the current UTC time within the same database transaction as the KYC change so that the Investment_Gate treats it as due for renewal on the next investment attempt.
3. IF an Investor has no Active_Suitability_Record within the same Tenant_Id when a Material_KYC_Change is recorded, THEN THE Suitability_Service SHALL take no invalidation action and SHALL record no error.
4. WHEN the Suitability_Service invalidates an Active_Suitability_Record due to a Material_KYC_Change, THE Suitability_Service SHALL write an entry to the Audit_Log with the action `SUITABILITY_INVALIDATED`, the Investor's user id, the UTC timestamp, the Tenant_Id, and metadata identifying the KYC field name (`nationality` or `source_of_funds`) that triggered invalidation, in the same database transaction as the invalidation.
5. IF the Audit_Log write for a Material_KYC_Change invalidation fails, THEN THE Suitability_Service SHALL roll back the entire invalidation transaction so that the Active_Suitability_Record's expiry timestamp is not modified.
6. WHILE an Active_Suitability_Record is invalidated by a Material_KYC_Change, THE Suitability_Service SHALL NOT trigger any reversal, cancellation, refund, or modification of the Investor's existing investment, ownership ledger, or distribution records as a consequence of the invalidation.

### Requirement 8: Investment Gate Enforcement

**User Story:** As the platform, I want every investment attempt to pass the Investment_Gate, so that suitability rules are enforced uniformly regardless of the calling endpoint.

#### Acceptance Criteria

1. WHEN the Investment module receives a request to create an investment, THE Investment module SHALL invoke the Investment_Gate synchronously for the Investor id and target property id and SHALL NOT perform any payment authorisation, escrow movement, or ledger write unless the Investment_Gate returns an allow decision.
2. IF the Investor has no Active_Suitability_Record for the request's Tenant_Id, OR the Active_Suitability_Record's expiry timestamp is less than or equal to the current UTC time, THEN THE Investment_Gate SHALL return a `SUITABILITY_REQUIRED` blocking decision containing the Investor id and the reason indicator (`NO_RECORD` or `EXPIRED`).
3. IF the Active_Suitability_Record's Outcome is `NOT_SUITABLE`, THEN THE Investment_Gate SHALL return a `SUITABILITY_BLOCKED` decision containing the block reason text from the Active_Suitability_Record and the re-take-allowed timestamp in UTC.
4. IF the Active_Suitability_Record's Outcome is `ELIGIBLE_WITH_WARNING` AND no Warning_Acknowledgement exists for the same Active_Suitability_Record id, Investor id, target property id, and Tenant_Id, THEN THE Investment_Gate SHALL return a `SUITABILITY_ACK_REQUIRED` decision containing the target property id and the complete list of warning reason codes from the Active_Suitability_Record.
5. WHEN the Active_Suitability_Record's Outcome is `ELIGIBLE`, THE Investment_Gate SHALL return an allow decision containing the Active_Suitability_Record id.
6. WHEN the Active_Suitability_Record's Outcome is `ELIGIBLE_WITH_WARNING` AND a Warning_Acknowledgement exists for the same Active_Suitability_Record id, Investor id, target property id, and Tenant_Id, THE Investment_Gate SHALL return an allow decision containing the Active_Suitability_Record id and the Warning_Acknowledgement id.
7. THE Investment_Gate SHALL evaluate every decision against the primary database (not from any cached value) using the Investor id, target property id, current UTC time, and persisted records scoped to the request's Tenant_Id, so that two consecutive evaluations with no intervening state change produce identical decisions.
8. IF the Investor id does not resolve to an Investor within the request's Tenant_Id, OR the target property id does not resolve to a property within the request's Tenant_Id, THEN THE Investment_Gate SHALL return a blocking decision with reason indicator `INVALID_SUBJECT` and SHALL NOT disclose suitability data of any other tenant.
9. WHEN the Investment_Gate returns any blocking decision (`SUITABILITY_REQUIRED`, `SUITABILITY_BLOCKED`, `SUITABILITY_ACK_REQUIRED`, `INVALID_SUBJECT`), THE Suitability_Service SHALL write an entry to the Audit_Log with the action identifying the gate block, the Investor's user id, the target property id, the reason indicator, IP address, user agent, UTC timestamp, and Tenant_Id.

### Requirement 9: Multi-Tenancy Isolation

**User Story:** As the platform, I want suitability data to be scoped per tenant, so that no Investor's data is visible across tenant boundaries.

#### Acceptance Criteria

1. WHEN a Suitability_Record or Warning_Acknowledgement is created, THE Suitability_Service SHALL persist the Tenant_Id resolved from the `X-Tenant-ID` header on the new row in the same database transaction as the row insert.
2. IF the `X-Tenant-ID` header is missing, empty, or contains a value not matching the regex `^[a-z0-9-]{1,64}$`, THEN THE Suitability_Service SHALL reject the request with an authorisation error and SHALL NOT execute any read or write of suitability data.
3. WHEN the Suitability_Service executes any read query against Suitability_Record or Warning_Acknowledgement, THE Suitability_Service SHALL include an equality filter on Tenant_Id matching the request's Tenant_Id, so that rows belonging to any other Tenant_Id are excluded from the result set.
4. IF a request supplies an Investor identifier, Suitability_Record identifier, Warning_Acknowledgement identifier, or property identifier whose persisted Tenant_Id differs from the request's Tenant_Id, THEN THE Suitability_Service SHALL reject the request with an authorisation error indicating cross-tenant access is denied, SHALL NOT modify any persisted data, and SHALL return an outcome indistinguishable from the resource not existing so that tenant membership is not disclosed.
5. WHEN the Suitability_Service executes any write to Suitability_Record or Warning_Acknowledgement, THE Suitability_Service SHALL include an equality predicate on Tenant_Id matching the request's Tenant_Id in the write statement so that rows belonging to any other Tenant_Id cannot be modified.
6. THE database schema SHALL enforce, via a unique constraint on the (user id, Tenant_Id) pair restricted to non-superseded rows, that at most one Active_Suitability_Record exists per Investor per Tenant_Id, and SHALL reject any insert or update violating this constraint with a database constraint error.
7. IF a database constraint violation occurs on the (user id, Tenant_Id) uniqueness rule during a submission, THEN THE Suitability_Service SHALL roll back the entire submission transaction, SHALL NOT persist the new Suitability_Record, and SHALL return a conflict error to the caller.

## Appendix A: Suitability Outcome Logic (Authoritative)

This appendix is the source of truth for the Scoring_Engine. Any change to the matrix or thresholds requires a new questionnaire version number per Requirement 2.7.

### A.1 Question set, enumerated answers, weights, and per-answer scores

Total score = round(sum over all 7 questions of `answer_score × weight`). Weights sum to 1.00. Per-answer scores are integers in [0, 100].

| # | Question topic | Weight | Enumerated answers and scores |
|---|---|---|---|
| Q1 | Net worth bracket (excluding primary residence) | 0.10 | `under_100k` = 0, `between_100k_500k` = 50, `over_500k` = 100 |
| Q2 | Annual income bracket | 0.10 | `under_50k` = 0, `between_50k_200k` = 50, `over_200k` = 100 |
| Q3 | Investable-asset allocation to this platform | 0.25 | `over_50pct` = 0, `between_20_50pct` = 50, `under_20pct` = 100 |
| Q4 | Intended liquidity horizon | 0.30 | `under_2yr` = 0, `between_2_5yr` = 50, `over_5yr` = 100 |
| Q5 | Prior investment experience | 0.20 | `none` = 0, `stocks_bonds` = 60, `real_estate` = 100 |
| Q6 | Risk-response scenario (30% drop) | 0.25 | `sell_immediately` = 0, `wait_and_monitor` = 60, `buy_more` = 100 |
| Q7 | Primary investment objective | 0.10 | `income` = 100, `capital_growth` = 80, `both` = 100 |

Note: Weights sum to 1.30 across the seven questions because Q3, Q4, Q5, and Q6 are emphasised. The Scoring_Engine SHALL normalise the total by the weight sum so the final score remains in `[0, 100]`. Equivalently, total score = round((sum of `answer_score × weight`) × (100 / sum of weights × 100)). The exact normalised formula is fixed by the implementation and validated by the property tests in the design phase. If, in implementation, the weights are adjusted to sum exactly to 1.00, this appendix will be updated accordingly under a new questionnaire version.

### A.2 Outcome thresholds

- `ELIGIBLE` when total score ≥ 65
- `ELIGIBLE_WITH_WARNING` when 40 ≤ total score ≤ 64
- `NOT_SUITABLE` when total score < 40

### A.3 Warning reason codes (only emitted when Outcome is `ELIGIBLE_WITH_WARNING`)

The Scoring_Engine emits zero or more of the following codes:

- `SHORT_HORIZON` when Q4 = `between_2_5yr` AND total score < 65
- `HIGH_CONCENTRATION` when Q3 = `between_20_50pct`
- `LOW_EXPERIENCE` when Q5 ∈ { `none`, `stocks_bonds` }

### A.4 Block reason (only emitted when Outcome is `NOT_SUITABLE`)

Exactly one block reason is emitted, chosen by the first matching rule in this priority order:

1. IF Q4 = `under_2yr`, THEN block reason = "Your investment horizon is too short for illiquid real estate assets."
2. ELSE IF Q3 = `over_50pct`, THEN block reason = "Allocating over 50% of your investable assets to one platform poses significant concentration risk."
3. ELSE IF Q5 = `none` AND Q6 = `sell_immediately`, THEN block reason = "This product requires risk tolerance and prior investment experience."
4. ELSE block reason = "Your current financial profile does not meet the risk requirements for this product."
