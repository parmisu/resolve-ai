---
document_id: TF-PRD-001
version: "1.0.0"
title: TaskFlow Product Guide
effective_from: "2026-11-28"
status: active
owner: Product Support
source_path: data/knowledge_base/product-guide.md
---

# TaskFlow Product Guide

## Workspace roles

TaskFlow product roles are owner, member, and viewer.

Owners manage workspace settings, invitations, billing, and projects.
Members create and edit projects and tasks.
Viewers can read projects shared with them but cannot change them.

These product roles are separate from ResolveAI support roles:
customer, support_agent, and administrator.
Being a support administrator does not establish workspace ownership.

## Create a project

Open Projects → New project, enter a name, and select Create.
Owners and members can create projects within the plan's active-project
limit. If the limit is reached, archive an unused project or ask the owner
to review the subscription.

## Create and assign a task

Open a project and select Add task.
Enter a title, optional description, and optional due date.
Choose an existing workspace member as the assignee.

An invitation must be accepted before that person can receive tasks.

## Invite teammates

The owner opens Settings → Members → Invite member, enters an email
address, selects a role, and sends the invitation.

Invitation links expire after 72 hours.
Pending invitations reserve member slots until accepted or revoked.

To replace an expired invitation, revoke it and send a new one.
If capacity is reached, remove unused access or review the plan limits
in TF-SUB-001.

## Archive a project

Owners and members can open a project's menu and select Archive.
Archiving preserves its tasks and removes it from the active-project count.

Restoring an archived project requires an available active-project slot.

## Feature boundaries

This demo supports projects, tasks, assignments, invitations, and billing.
Native mobile apps, SSO, and third-party integrations are not supported.

Feature requests can be recorded, but support must not promise a release
date or claim that a requested feature already exists.