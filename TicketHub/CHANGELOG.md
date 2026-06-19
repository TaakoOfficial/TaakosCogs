# Changelog

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
