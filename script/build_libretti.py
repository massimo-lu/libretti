"""Compile sources/<slug>/{it,en,meta}.txt into libretto/<slug>.html, and
regenerate index.html's catalog from whichever operas exist under sources/.

Authoring grammar (see sources/*/it.txt, en.txt):
  ATTO ... / ACT ...      -> act header
  SCENA ... / SCENE ...   -> scene header
  ALL-CAPS line           -> character name
  (parenthesized line)    -> stage direction
  <img:src|caption>       -> image, full width
  blank line              -> stanza break
  [[word|note text]]      -> inline translation-note trigger

sources/<slug>/meta.txt holds two lines: the opera's title, then its
composer.

it.txt/en.txt are paired line by line: line N of one must be the same
kind of line (both act headers, both character names, both gaps, ...)
as line N of the other. The moment a pair disagrees, that's logged as a
warning and the whole build stops there — no attempt is made to
resynchronize, since guessing how to skip/insert lines to realign two
independent translations is exactly what produced wrong pairings before.
Keeping it.txt/en.txt in lockstep is the author's job.
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

NOTE_RE = re.compile(r'\[\[?([^|\]]+)\|([^\]]+)]]?')


def classify(line):
    """Classify one physical source line as (kind, text)."""
    stripped = line.strip()
    if not stripped:
        return 'gap', ''

    if stripped.startswith('(') and stripped.endswith(')'):
        return 'stage', stripped

    if stripped.startswith('<img:'):
        return 'html', stripped

    if stripped == stripped.upper() and any(c.isalpha() for c in stripped):
        upper = stripped.upper()
        if upper.startswith('ATTO') or upper.startswith('ACT '):
            return 'act', stripped
        if upper.startswith(('SCENA', 'SCENE')) or upper.endswith(('SCENA', 'SCENE')):
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
    """Render a '<img:src|caption>' line as a figure, full width."""
    template = """<figure class="image-container">
  <div class="image-wrapper">
    <img src="{src}">
  </div>
  <figcaption>{caption}</figcaption>
</figure>"""
    src, caption = text[len('<img:'):].rstrip('>').split('|', 1)
    return template.format(src=src, caption=html.escape(caption))


def render_row(kind, it_text, en_text):
    """Render one paired line as the HTML for that row."""
    if kind == 'gap':
        return '<div class="line-gap"></div>'

    if kind == 'html':
        return render_image(it_text)

    it_html, en_html = render_inline(it_text), render_inline(en_text)

    if kind == 'act':
        return f'<div class="act-header">{it_html}<span class="alt">{en_html}</span></div>'

    if kind == 'section':
        return f'<div class="section-header">{it_html}<span class="alt">{en_html}</span></div>'

    if kind == 'character':
        if it_html == en_html:
            return f'<div class="character-name">{it_html}</div>'
        return f'<div class="character-name">{it_html}<span class="alt">{en_html}</span></div>'

    css_class = 'original stage-direction' if kind == 'stage' else 'original'
    translation_class = 'translation stage-direction' if kind == 'stage' else 'translation'
    return (
        f'<div class="{css_class}">{it_html}</div>\n\n'
        f'            <div class="{translation_class}">{en_html}</div>'
    )


def build_rows(it_lines, en_lines, warn):
    rows = []
    for idx, (it_line, en_line) in enumerate(zip_longest(it_lines, en_lines)):
        if it_line is None or en_line is None:
            warn(f'line {idx}: one file ran out of lines (it={it_line!r}, en={en_line!r}) — stopping here')
            break

        it_kind, it_text = classify(it_line)
        en_kind, en_text = classify(en_line)
        if it_kind != en_kind:
            warn(
                f"line {idx}: kind mismatch, it={it_kind!r} ({it_text!r}) vs "
                f"en={en_kind!r} ({en_text!r}) — stopping here"
            )
            break

        rows.append(render_row(it_kind, it_text, en_text))

    return rows


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
            Click on the <span class="note-trigger" data-note="Example  ">highlighted words</span> to read translation notes.
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
        PAGE_TEMPLATE.format(
            title=html.escape(title),
            composer=html.escape(composer),
            rows='\n\n            '.join(rows),
        ),
        encoding='utf-8',
    )

    print(f'{slug}: wrote {out_path} ({len(rows)} row(s))')
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
