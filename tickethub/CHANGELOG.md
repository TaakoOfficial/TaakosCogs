# Changelog

## Unreleased

- Delete the close-confirmation prompt when cancellation is selected instead of leaving a public "Close Cancelled" card in the ticket.
- Added a dashboard Ticket Desk for reading recent ticket conversations, sending attributed staff replies, managing members, and running ticket lifecycle actions without leaving the dashboard.
- Re-register imported AAA3A panel handlers after the AAA3A Tickets cog unloads, preventing existing panel buttons and dropdowns from returning "Interaction failed" after migration.
- Reorganized the dashboard into responsive Tickets, Profile Setup, Modal, Panels, and AAA3A Imports tabs that remain selected after form submissions.

## 1.16.1

- Renamed the repository package folder from `TicketHub` to `tickethub` to match Red cog naming standards.
- New installs should use `[p]cog install taakoscogs tickethub` and `[p]load tickethub`.
- Existing ticket profiles, panels, ticket records, and setup data are preserved because the cog's Config identifier did not change.

## 1.16.0

- Added Red-Web-Dashboard third-party integration for TicketHub.
- Added dashboard controls for global settings, profile management, channels, categories, roles, lifecycle behavior, control emojis, and modal questions, including explicit add/remove question workflows.
- Added dashboard workflows for posting, attaching, clearing, and managing single-profile and multi-profile panels.
- Added dashboard views and actions for tracked tickets, ticket creation, ticket recovery, transcripts, and AAA3A panel import records.

## 1.15.0

- Moved setup, role, automation, import, and export commands to the standalone `[p]ticketset` and `/ticketset` command tree.
- Grouped high-volume setup commands under `modal`, `multipanel`, `roles`, and `data` to stay within Discord's slash-command child limit.
- Added `[p]ticketset behavior closetimeout` to configure how long close requests wait before auto-closing.
- Added `[p]ticketset profile` commands to show, list, create, and delete profiles with confirmation for deletion.
- Grouped owner, lifecycle, transcript, and control settings under `[p]ticketset behavior` to keep `/ticketset` under Discord's child-command limit.
- Improved `[p]ticketset profile` output with cleaner sections for basics, destinations, lifecycle, permissions, and roles.

## 1.14.0

- Allowed TicketHub to load alongside another cog that already owns the `[p]ticket` command by temporarily using `[p]tickethub`.
- Imported AAA3A `buttons_dropdowns` panel routing so existing AAA3A buttons and dropdowns can open TicketHub tickets without editing the panel message.
- Added `[p]tickethub admin import-aaa3a-all` to import every AAA3A Tickets profile in one operation.
- Mapped AAA3A text-channel `forum_channel` settings to TicketHub thread mode during profile import.

## 1.13.0

- Added native application commands under `/ticket` without requiring SlashBridge.
- Organized setup commands under `/ticket config` and privileged maintenance commands under `/ticket admin`.
- Kept `tickethub` and `thub` as prefix aliases for the new `ticket` command group.

## 1.12.0

- Redesigned ticket cards with owner avatars, clear state indicators, structured request details, and richer timestamps.
- Redesigned lifecycle logs as complete ticket snapshots with consistent colors and jump-to-ticket buttons.
- Added polished transcript cards with owner, status, message count, generator, and attachment metadata.
- Improved the opening welcome layout and kept ticket recovery compatible with both legacy and redesigned cards.
- Changed bare `[p]tickethub` to show the help menu and moved the configuration overview to `[p]tickethub status`.

## 1.11.0

- Added Members controls with Discord user pickers and configurable owner add/remove permissions.
- Added closed-ticket Reopen and Delete controls plus a required reopen-reason modal.
- Added create-for, show, recovery, panel clearing, profile-role, ticket-role, owner-permission, close-on-leave, auto-delete, and control-emoji commands.
- Added speak-role access, ticket-role assignment, claimed/unclaimed list filters, and owner transcript access.
- Added restart-safe closed-ticket auto-delete and automatic closing when an owner leaves.
- Expanded AAA3A profile imports for member permissions, speak/ticket roles, close-on-leave, and control emojis.

## 1.10.0

- Added a support-only Lock button that changes to Unlock while active.
- Locked ticket owners and added members can no longer post until staff unlock the ticket.
- Added `[p]tickethub lock` and `[p]tickethub unlock` commands.
- Preserved lock restrictions across claim/unclaim, close/reopen, and bot restarts.
- Added lock lifecycle metadata to ticket records and CSV exports.

## 1.9.0

- Added a required close-reason modal to the ticket Close button.
- Added a red confirmation embed with the reason and Cancel/Close buttons.
- Added automatic closure after five minutes without a response.
- Added restart-safe pending confirmation state and requester-only modal launchers for prefix commands.
- Changed `[p]tickethub close` to use the same confirmation workflow.

## 1.8.0

- Changed the Claim button to Unclaim while a ticket is claimed.
- Added claim-time send locking so only the opener, claimer, and server administrators can send in channel tickets.
- Added private-thread claim locking by temporarily removing other members and restoring support/participants on unclaim.
- Applied the same permission transitions to claim/unclaim commands and newly added ticket participants.

## 1.7.0

- Added `[p]tickethub channelname` to show or set the channel-name template for a profile.
- Changed `{id}` in channel and ticket-message templates to an independently incrementing profile-local number.
- Added `{global_id}` for the existing guild-wide internal ticket ID.
- Added safe lazy initialization so upgraded profiles continue above their existing ticket numbers.

## 1.6.0

- Added persistent multi-profile panels.
- Added custom emoji, display name, and brief description fields for each profile option.
- Added commands to add/remove options, switch button/dropdown layouts, customize the dropdown placeholder, inspect configuration, and clear a multi-panel.

## 1.5.0

- Added persistent dropdown ticket panels as an alternative to buttons.
- Added `[p]tickethub attachpanel` to attach a panel to an existing message sent by the bot while preserving its content and embeds.
- Added panel style persistence to TicketHub profiles.

## 1.4.0

- Added native modal dropdowns for choice and boolean ticket questions on current Red installations.
- Retained the ephemeral step-form fallback for older Discord.py versions.

## 1.3.0

- Added dropdown and boolean ticket form questions.
- Preserved native Discord modals for text-only forms and added an ephemeral step form for mixed question types.
- Extended the modal wizard and add command to configure typed questions.

## 1.2.0

- Added `[p]tickethub modal` commands to show, build, add, remove, reset, and clear profile modal questions.
- Added a guided modal builder for custom panel-open forms.

## 1.1.0

- Added imported modal form support for panel-created tickets.
- Copied AAA3A Tickets `creating_modal` fields and default reason modal behavior during profile import.
- Stored submitted modal answers on ticket records and displayed them in ticket embeds.

## 1.0.0

- Initial TicketHub cog.
- Added ticket panels, private ticket channels, claim/unclaim, close/reopen/delete, add/remove member, ticket lists, CSV export, AAA3A Tickets profile import preview/apply, and self-contained HTML/text transcripts.
