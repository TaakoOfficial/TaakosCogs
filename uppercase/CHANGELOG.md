# Changelog

## 1.1.4

- Renamed the repository package folder from `Uppercase` to `uppercase` to match Red cog naming standards.
- New installs should use `[p]cog install taakoscogs uppercase` and `[p]load uppercase`.
- Existing behavior is unchanged; this cog does not store persistent setup data.

## 1.1.3

- Restored bold sans uppercase formatting because Discord lowercases normal ASCII channel names.

## 1.1.2

- Changed channel formatting to use plain uppercase text for the requested name.

## 1.1.1

- Changed uppercase channel formatting from fullwidth letters to bold sans uppercase letters for a cleaner Discord appearance.

## 1.1.0

- Updated `[p]create-channel` and `/create-channel` to accept a category before the channel name.

## 1.0.0

- Added `/create-channel` and `[p]create-channel`.
- Added `/rename-channel` and `[p]rename-channel`.
- Added uppercase-style text channel name formatting.
