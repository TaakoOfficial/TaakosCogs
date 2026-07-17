# Third-Party Notices

This file centralizes attribution for artwork, projects that inspired parts of the
repository, compatibility targets, and separately installed dependencies. Unless a
notice says otherwise, these projects are not bundled into this repository and keep
their own licenses and copyrights.

## Twemoji graphics

Weather, moon-phase, calendar, logging, and book thumbnails use unmodified PNG
graphics from [Twemoji v17.0.3](https://github.com/jdecked/twemoji/tree/v17.0.3),
served by jsDelivr. The graphics are licensed under the
[Creative Commons Attribution 4.0 International license](https://creativecommons.org/licenses/by/4.0/).

Copyright (c) 2022-present Jason Sofonia and Justine De Caires  
Copyright (c) 2014-2021 Twitter

No endorsement by the Twemoji authors or contributors is implied.

## Merlin Fuchs' Embed Generator

MessageStudio's visual editor is inspired by the component-card workflow and split
editor/preview layout of Merlin Fuchs'
[Embed Generator](https://github.com/merlinfuchs/embed-generator). MessageStudio is
a self-contained implementation for Red-Web-Dashboard. The complete upstream MIT
notice is preserved below in case any portion is considered copied or adapted:

```text
MIT License

Copyright (c) 2023 Merlin Fuchs

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Compatibility and reference projects

The following projects or services are named because cogs provide migration,
configuration, command-surface, transcript, or documented-workflow compatibility.
These acknowledgements do not imply endorsement or affiliation.

- [AAA3A-cogs EmbedUtils](https://github.com/AAA3A-AAA3A/AAA3A-cogs/tree/main/embedutils)
  and [Phen's historical EmbedUtils](https://github.com/phenom4n4n/phen-cogs/tree/master/embedutils):
  MessageStudio supports compatible commands and stored-embed migration.
- [AAA3A-cogs Tickets](https://github.com/AAA3A-AAA3A/AAA3A-cogs/tree/main/tickets):
  TicketHub supports migration of compatible ticket profiles and panel mappings.
- [TrustyJAID RoleTools](https://github.com/TrustyJAID/Trusty-cogs/tree/master/roletools):
  RoleManager supports compatible configuration migration.
- [Seina RoleUtils](https://github.com/japandotorg/Seina-Cogs/tree/master/roleutils):
  RoleManager supports compatible configuration migration.
- [DiscordChatExporterPy](https://github.com/mahtoid/DiscordChatExporterPy):
  TicketHub can use the separately installed `chat-exporter` package for HTML
  transcripts. That dependency is licensed by its authors under GPLv3 and is not
  vendored here.
- [ReviewHub](https://reviewhubs.info/documentation): the local ReviewHub cog is an
  independent implementation inspired by the service's publicly documented Discord
  workflow. It does not connect to or represent the external service.

Python dependencies declared in cog metadata are installed separately by Red's
Downloader. Their source and license texts are not redistributed by this repository.
