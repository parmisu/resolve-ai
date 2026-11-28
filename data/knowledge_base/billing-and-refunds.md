---
document_id: TF-BIL-001
version: "1.0.0"
title: TaskFlow Billing and Refunds
effective_from: "2026-11-28"
status: active
owner: Billing Operations
source_path: data/knowledge_base/billing-and-refunds.md
---

# TaskFlow Billing and Refunds

## Billing model

Paid subscriptions are billed monthly in USD, per workspace.
Current prices and plan limits are listed in TF-SUB-001.

Invoices are issued at the beginning of each billing period.
Applicable taxes are shown separately. Published plan prices exclude tax.

Annual billing, promotional discounts, and custom enterprise pricing
are not offered in this demo.

## Invoices

Workspace owners can open Settings → Billing → Invoices to download
available invoices. Members and viewers cannot access billing settings.

If an invoice is missing, collect the invoice period and workspace name.
An agent must investigate; the AI must not invent an invoice or charge.

## Failed payments

A failed payment changes the subscription to past_due.
The workspace receives a seven-day grace period with its existing access.

If payment remains unsuccessful after the grace period, the workspace
becomes read-only. Successful payment restores access.

The AI must use verified account information before claiming that a
specific customer's payment failed or access was restored.

## Refund requests

Customers may request review of a charge within 14 calendar days of
its invoice date. This is a review window, not an automatic entitlement
to a refund.

Duplicate charges and billing errors require investigation. Requests
outside the review window must also be escalated for a human decision.

Collect the invoice identifier and reason for the request.
Never request complete card details.

Only authorized billing staff may approve or execute refunds.
The AI must not promise eligibility, an amount, or a processing date.

## Cancellation and refunds

Cancellation does not automatically generate a refund.
For cancellation timing, see TF-SUB-001.