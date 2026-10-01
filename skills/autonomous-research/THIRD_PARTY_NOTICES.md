# Third-party notices

The workflow in this bundle is derived from OpenDraft:
https://github.com/federicodeponte/opendraft

`DERIVATION.json` maps it file by file: which upstream prompt or module each
agent and script came from, which upstream prompts were deliberately not
ported and why, and the six corrections made to the original engine.

OpenDraft is licensed under the MIT License:

> MIT License
>
> Copyright (c) 2025 SCAILE Technologies GmbH
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

## Fonts in assets/fonts

The journal export (`scripts/journal.py`) embeds two typefaces, shipped as
unmodified static instances of the upstream variable fonts:

- **STIX Two Text** (`STIX-400.ttf`, `STIX-600.ttf`, `STIX-700.ttf`,
  `STIXi-400.ttf`, `STIXi-600.ttf`). Copyright 2001-2021 The STIX Fonts
  Project Authors (https://github.com/stipub/stixfonts). Licensed under the
  SIL Open Font License, Version 1.1; the full text is in
  `assets/fonts/OFL-STIX-Two.txt`.
- **Source Sans 3** (`SS-400.ttf`, `SS-600.ttf`, `SS-700.ttf`,
  `SSi-400.ttf`). Copyright 2010-2024 Adobe (http://www.adobe.com/), with
  Reserved Font Name 'Source'. Licensed under the SIL Open Font License,
  Version 1.1; the full text is in `assets/fonts/OFL-Source-Sans-3.txt`.

The three equation images in `assets/` are drawings of the evidence-index
formulas rendered in the STIX glyphs and carry no third-party content.
