---
document_id: TF-SUB-001
version: "1.0.0"
title: TaskFlow Subscription Plans
effective_from: "2026-11-28"
status: active
owner: Product Operations
source_path: data/knowledge_base/subscription-plans.md
---

# TaskFlow Subscription Plans

## Available plans

Prices are monthly, in USD, per workspace, excluding applicable taxes.
Members include the owner and accepted workspace users.

| Plan code | Plan | Monthly price | Member limit | Active project limit |
|---|---|---:|---:|---:|
| starter | Starter | $12 | 3 | 5 |
| team | Team | $39 | 15 | 50 |

Tasks are unlimited on both plans, subject to normal service availability.
Archived projects do not count toward the active project limit.

These prices apply from this document's effective date.
Do not use them to infer the amount of an earlier invoice.

## Trial

A new workspace may receive one 14-day trial with Starter limits.
No payment card is required to start the trial.

If no paid subscription is activated when the trial ends, the workspace
becomes read-only. Trial expiry does not itself delete workspace data.

## Plan changes

Only the workspace owner can request a plan change.
Support must verify ownership before processing it.

Approved upgrades and downgrades take effect at the next billing-period
boundary. There are no mid-period plan changes or prorated charges
in this demo.

Before a downgrade, the workspace must fit within the target plan's
member and active-project limits. Otherwise the change remains pending
human review.

The AI may explain the process but must not change the subscription.

## Cancellation

An owner may request cancellation at the end of the current billing period.
Until then, the current plan remains available.

A scheduled cancellation may still have status active and
cancel_at_period_end=true. It must not be described as already cancelled.

At the period boundary, the subscription becomes cancelled and the
workspace becomes read-only. Data deletion is a separate account request.

## Account-specific answers

Use the subscription lookup tool to check a customer's actual plan,
status, billing period, and cancellation flag.

A missing record or failed lookup does not mean the customer is on
Starter, has cancelled, or has no subscription.