---
document_id: TF-TRB-001
version: "1.0.0"
title: TaskFlow Troubleshooting
effective_from: "2026-11-28"
status: active
owner: Technical Support
source_path: data/knowledge_base/troubleshooting.md
---

# TaskFlow Troubleshooting

## Project page keeps loading

1. Copy any unsaved text before refreshing.
2. Refresh the page and check the network connection.
3. Try a private browser window to check whether browser state is involved.
4. If appropriate, temporarily disable extensions for TaskFlow and retry.
5. Collect the browser version, approximate UTC time, affected project
   identifier, and any visible error message.

If the problem persists, escalate to technical support.
Do not claim there is a service outage without verified incident evidence.

## Invitation email not received

Ask the owner to confirm the recipient address and check pending
invitations under Settings → Members.

The recipient should check spam or junk folders.
An expired invitation must be revoked and replaced by the owner.
Invitation expiry and capacity rules are documented in TF-PRD-001.

Do not ask the customer to share the invitation link or token.

## Cannot edit a project

Check whether the user's product role is viewer and whether the workspace
is read-only.

Possible causes include trial expiry, completed cancellation, or an
unresolved payment failure after its grace period. These are possibilities,
not confirmed diagnoses.

Use verified subscription data and relevant documentation before
attributing the restriction to billing.

## Password reset

Use Forgot password on the sign-in page.
Reset links expire after 30 minutes; requesting another link invalidates
the previous one.

Never ask the user to send a password, reset link, or one-time code.
Escalate if the user cannot access their registered email address.

## Suspected account compromise

Treat reports of unfamiliar access, unauthorized account changes, or
exposed credentials as security cases requiring human escalation.

Direct the customer to the official password-reset flow.
Do not change ownership, disable security controls, or promise that the
account is secure.

## Tool failures

If an account lookup times out or returns an error, state that the account
information could not be verified. Do not guess its contents.

Preserve the case for a human investigation when the missing information
prevents a reliable answer.