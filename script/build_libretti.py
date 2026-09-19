"""Compile sources/<slug>/{it,en,meta}.txt into libretto/<slug>.html, and
regenerate index.html's catalog from whichever operas exist under sources/.

Authoring grammar (see sources/*/it.txt, en.txt):
  ATTO ... / ACT ...      -> act header
  SCENA ... / SCENE ...   -> scene header
  ALL-CAPS line           -> character name
  (parenthesized line)    -> stage direction
  blank line              -> stanza break
  [[word|note text]]      -> inline translation-note trigger

sources/<slug>/meta.txt holds two lines: the opera's title, then its
composer.

it.txt/en.txt are independent hand-authored files, not a paired table:
for opera-guide.ch (the current Tosca source) the English text is a
free-flowing prose translation that doesn't follow the Italian's verse
line breaks, so individual dialogue lines aren't pairable 1:1. Each
speech (the run of lines between one act/character header and the next)
is therefore rendered as a single .original/.translation pair holding
that whole speech in both languages, stacked internally with <br>,
rather than one row per line. Act/character headers are still paired
positionally, and any mismatch there is printed as a warning.

Known limitation (sources/tosca): opera-guide.ch's English page also
reorders/splits *how many* speaking turns some exchanges have (not just
the line breaks within a turn), so from roughly the second half of Act 2
through all of Act 3, positional pairing puts some speeches next to the
wrong character/translation. Flagged here rather than hand-fixed for now
— see the warnings build_opera() prints; a real fix means hand-editing
sources/tosca/en.txt to match it.txt's turn sequence for that stretch.
"""
import html
import re
import sys
from itertools import zip_longest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT_DIR / 'sources'
LIBRETTO_DIR = ROOT_DIR / 'libretto'
INDEX_PATH = ROOT_DIR / 'index.html'

NOTE_RE = re.compile(r'\[\[([^|\]]+)\|([^\]]+)]]')

# Only act/character lines are treated as hard block boundaries for pairing.
# Scene headers ("SCENA .../SCENE ...") are excluded on purpose: opera-guide.ch's
# Italian page marks every scene but its English page doesn't, so using
# 'section' as a boundary desynced every block for the rest of the opera the
# moment one side lacked a scene marker the other had. Treating a lone
# 'section' line as a body-level entry (see extract_sections) keeps a missing
# scene header from drifting anything else out of alignment.
BOUNDARY_KINDS = {'act', 'character', 'section'}


def classify(line):
    """Classify one physical source line as (kind, text)."""
    stripped = line.strip()
    if not stripped:
        return 'gap', ''

    if stripped.startswith('(') and stripped.endswith(')'):
        return 'stage', stripped


    if stripped.startswith('<'):
        return 'html', stripped

    if stripped == stripped.upper() and any(c.isalpha() for c in stripped):
        upper = stripped.upper()
        if upper.startswith('ATTO') or upper.startswith('ACT '):
            return 'act', stripped
        if upper.startswith(('SCENA', 'SCENE')) or upper.endswith(('SCENE', 'SCENA')):
            return 'section', stripped
        return 'character', stripped

    return 'text', stripped


def render_inline(text):
    """Escape a line of source text, expanding [[word|note]] into a note-trigger span."""
    out, last = [], 0
    for m in NOTE_RE.finditer(text):
        out.append(html.escape(text[last:m.start()]))
        word, note = m.group(1), m.group(2)
        out.append(
            f'<span class="note-trigger" data-note="{html.escape(note)}">{html.escape(word)}</span>'
        )
        last = m.end()
    out.append(html.escape(text[last:]))
    return ''.join(out)


def render_image(text):
    """Render an image tag if present."""
    if text.startswith('<img:'):
        template = """<figure class="image-container">
  <div class="image-wrapper">
    <img src="{src}">
  </div>
  <figcaption>{caption}</figcaption>
</figure>"""
        img, caption = text[5:].split('|')
        return template.format(src=img, caption=caption)
    return text


def to_blocks(lines):
    """Split classified lines into blocks: a header (act/section/character) plus the body lines that follow it."""
    blocks = [{'kind': None, 'header': '', 'body': []}]
    for line in lines:
        kind, text = classify(line)
        if kind in BOUNDARY_KINDS:
            blocks.append({'kind': kind, 'header': text, 'body': []})
        else:
            blocks[-1]['body'].append((kind, text))

    if blocks[0]['kind'] is None and not blocks[0]['body']:
        blocks.pop(0)
    return blocks


def render_body(body):
    """Render one language's text/stage/gap lines as a single HTML blob for a speech.

    'section' entries are handled separately (see extract_sections) since a
    scene header is a full-width divider, not part of either language's
    spoken text.
    """
    parts = []
    for kind, text in body:
        if kind == 'section' or kind == "html":
            continue
        elif kind == 'gap':
            parts.append('')
        elif kind == 'stage':
            parts.append(f'<span class="stage-direction">{render_inline(text)}</span>')
        else:
            parts.append(render_inline(text))

    while parts and parts[0] == '':
        parts.pop(0)
    while parts and parts[-1] == '':
        parts.pop()

    return '<br>'.join(parts)


def extract_full_width_lines(body):
    return [(text, kind) for kind, text in body if kind in ('section', 'html')]


def build_rows(it_lines, en_lines, warn):
    it_blocks = to_blocks(it_lines)
    en_blocks = to_blocks(en_lines)

    if len(it_blocks) != len(en_blocks):
        warn(f'block count mismatch: it has {len(it_blocks)} block(s), en has {len(en_blocks)}')

    rows = []
    for idx, (it_block, en_block) in enumerate(zip_longest(it_blocks, en_blocks)):
        it_block = it_block or {'kind': None, 'header': '', 'body': []}
        en_block = en_block or {'kind': None, 'header': '', 'body': []}

        if it_block['kind'] and en_block['kind'] and it_block['kind'] != en_block['kind']:
            warn(
                f"block #{idx} kind mismatch: it={it_block['kind']!r} "
                f"({it_block['header']!r}) vs en={en_block['kind']!r} ({en_block['header']!r})"
            )
        elif (
            it_block['kind'] == 'character'
            and en_block['kind'] == 'character'
            and it_block['header'] != en_block['header']
        ):
            # Not necessarily wrong — group labels get translated (FOLLA/CHORUS,
            # TUTTI/ALL) — but proper names shouldn't differ, so flag every case
            # for a human to skim; a real desync (wrong character entirely) looks
            # like this too and won't be caught any other way.
            warn(f"block #{idx} character name differs: it={it_block['header']!r} vs en={en_block['header']!r}")

        kind = it_block['kind'] or en_block['kind']
        if kind:
            rows.append({'type': kind, 'it': render_inline(it_block['header']), 'en': render_inline(en_block['header'])})

        speech_it, speech_en = render_body(it_block['body']), render_body(en_block['body'])
        if speech_it or speech_en:
            rows.append({'type': 'speech', 'it': speech_it, 'en': speech_en})

        it_sections = extract_full_width_lines(it_block['body'])
        en_sections = extract_full_width_lines(en_block['body'])
        for it_text_kind, en_text_kind in zip_longest(it_sections, en_sections, fillvalue=''):
            it_text, it_kind = it_text_kind
            en_text, en_kind = en_text_kind
            if en_kind == 'html':
                rows.append({'type': en_kind, 'it': render_image(it_text)})
            else:
                rows.append({'type': en_kind, 'it': render_inline(it_text), 'en': render_inline(en_text)})

    return rows


ROW_TEMPLATES = {
    'act': '<div class="act-header">{it}<span class="alt">{en}</span></div>',
    'section': '<div class="section-header">{it}<span class="alt">{en}</span></div>',
    'character': '<div class="character-name">{it}<span class="alt">{en}</span></div>',
    'character-same': '<div class="character-name">{it}</div>',
    'html': '<div class="image-container">{it}</div>',
}


def render_rows_html(rows):
    parts = []
    for row in rows:
        if row['type'] == 'speech':
            parts.append(f'<div class="original">{row["it"]}</div>')
            parts.append(f'<div class="translation">{row["en"]}</div>')
        elif row['type'] == 'character':
            if row['it'] == row['en']:
                parts.append(ROW_TEMPLATES['character-same'].format(it=row['it']))
            else:
                parts.append(ROW_TEMPLATES['character'].format(it=row['it'], en=row['en']))
        elif row['type'] == 'html':
            parts.append(ROW_TEMPLATES['html'].format(it=row['it']))
        else:
            parts.append(ROW_TEMPLATES[row['type']].format(it=row['it'], en=row['en']))
    return '\n\n            '.join(parts)


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — Classical Libretto Translations</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;1,400&family=Playfair+Display:ital,wght@0,600;0,700;1,600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="../css/libretto.css">
    <script src="../js/libretto.js" defer></script>
</head>
<body>

    <header class="libretto-header">
        <h1 class="opera-title">{title}</h1>
        <h2 class="opera-composer">{composer}</h2>
        <p class="opera-note">
            Click on the <span class="note-trigger">highlighted words</span> to read translation notes.
        </p>
    </header>

    <main class="libretto-body">

        <div class="libretto-grid column-headers">
            <div class="original">Italiano (Originale)</div>
            <div class="translation">English (Translation)</div>
        </div>

        <div class="libretto-grid">

            {rows}

        </div>
    </main>

    <div id="tooltip" role="tooltip" aria-hidden="true"></div>

</body>
</html>
"""


def read_meta(opera_dir):
    lines = (opera_dir / 'meta.txt').read_text(encoding='utf-8').splitlines()
    title = lines[0].strip() if len(lines) > 0 else opera_dir.name
    composer = lines[1].strip() if len(lines) > 1 else ''
    return title, composer


def build_opera(slug):
    opera_dir = SOURCES_DIR / slug
    it_lines = (opera_dir / 'it.txt').read_text(encoding='utf-8').splitlines()
    en_lines = (opera_dir / 'en.txt').read_text(encoding='utf-8').splitlines()
    title, composer = read_meta(opera_dir)

    warnings = []
    rows = build_rows(it_lines, en_lines, warnings.append)

    LIBRETTO_DIR.mkdir(parents=True, exist_ok=True)
    out_path = LIBRETTO_DIR / f'{slug}.html'
    out_path.write_text(
        PAGE_TEMPLATE.format(title=html.escape(title), composer=html.escape(composer), rows=render_rows_html(rows)),
        encoding='utf-8',
    )

    print(f'{slug}: wrote {out_path} ({len(rows)} rows)')
    for warning in warnings:
        print(f'  WARNING: {warning}')
    return title, composer, len(warnings)


INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Opera Libretti Translations & Notes</title>
  <style>
    body {{
      font-family: 'Georgia', serif;
      max-width: 800px;
      margin: 40px auto;
      padding: 0 20px;
      line-height: 1.6;
      color: #2c2c2c;
      background-color: #fcfbfa;
    }}
    h1 {{
      border-bottom: 2px solid #8b0000;
      padding-bottom: 10px;
      color: #8b0000;
    }}
    .catalog-list {{
      list-style-type: none;
      padding: 0;
    }}
    .catalog-item {{
      background: #ffffff;
      border: 1px solid #e2ded9;
      border-radius: 8px;
      padding: 18px 24px;
      margin-bottom: 16px;
      transition: transform 0.2s, box-shadow 0.2s;
    }}
    .catalog-item:hover {{
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }}
    .catalog-item h2 {{
      margin: 0 0 6px 0;
      font-size: 1.3rem;
    }}
    .catalog-item a {{
      color: #8b0000;
      text-decoration: none;
    }}
    .catalog-item a:hover {{
      text-decoration: underline;
    }}
    .meta {{
      font-size: 0.9rem;
      color: #666;
      font-style: italic;
    }}
  </style>
</head>
<body>

  <h1>Libretti Translations & Notes</h1>
  <p>Line-by-line translations with commentary and annotations.</p>

  <ul class="catalog-list">
{items}
  </ul>

</body>
</html>
"""

INDEX_ITEM_TEMPLATE = """    <li class="catalog-item">
      <h2><a href="libretto/{slug}.html">{title}</a></h2>
      <div class="meta">{composer}</div>
    </li>"""


def build_index(operas):
    items = '\n'.join(
        INDEX_ITEM_TEMPLATE.format(slug=slug, title=html.escape(title), composer=html.escape(composer))
        for slug, title, composer in operas
    )
    INDEX_PATH.write_text(INDEX_TEMPLATE.format(items=items), encoding='utf-8')
    print(f'wrote {INDEX_PATH} ({len(operas)} opera(s))')


def main():
    slugs = sys.argv[1:] or sorted(p.name for p in SOURCES_DIR.iterdir() if p.is_dir())

    operas = []
    total_warnings = 0
    for slug in slugs:
        title, composer, warnings = build_opera(slug)
        operas.append((slug, title, composer))
        total_warnings += warnings

    build_index(operas)

    if total_warnings:
        print(f'\n{total_warnings} alignment warning(s) — review sources/*/{{it,en}}.txt for that opera.')


if __name__ == '__main__':
    main()
