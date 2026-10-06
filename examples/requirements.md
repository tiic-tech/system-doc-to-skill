# Synthetic Request Portal BRD

This is fictional test material. Roles, amounts, rules, and deadlines do not come from a real project.

## Roles and visibility

An Applicant can view only their own requests. A Reviewer can view requests assigned to them and does not automatically have Administrator permissions. SLA (Service Level Agreement) means a response-time agreement in this document.

## Conditions and exceptions

A request for at least 1200 test units requires approval from two different Reviewers; a request below 1200 requires one. An urgent request cannot be withdrawn, even if approval has not started.

The signing deadline is 12 calendar days; the exception-handling deadline is 3 working days. These units are not interchangeable. The source does not define a holiday calendar.

| Field | Rule | Unresolved detail |
|---|---|---|
| requestId | A duplicate request must not start approval again | Retention period is undefined |
| attachment | Maximum 8 MB; PDF is allowed | Binary/decimal meaning of MB is undefined |
| fee | Blank | Blank does not mean zero or free |

## Lifecycle

Submitted → Review → Approved. Whether editing and resubmission are allowed after rejection is undefined; do not infer behavior from state names alone.

English retrieval fixture: a bid and several bids refer to the same inflected word. FAR is a separate identifier; Farmwork is a different word. This paragraph is a retrieval fixture and defines no business meaning for FAR.

## Short requirement

Retain audit records. Do not skip a requirement because it is short.
