"""Seed sources/<slug>/{it,en}.txt from opera-guide.ch libretto pages.

opera-guide.ch renders each libretto as a single flowing <p> (after a
<hr> that separates it from the cast list), with individual lines
separated by <br>, <b> for act headers and <i> for stage directions.
This script converts that markup into the project's plain-text authoring
grammar (see the Jekyll migration plan): ATTO/ACT and SCENA/SCENE headers
and all-caps character names pass through unchanged, stage directions are
wrapped in parentheses, and blank lines become stanza breaks.

It only *seeds* the two files — it/en line counts are not guaranteed to
line up (opera-guide.ch's two language pages are independent flowing
translations, not a paired table like the old librettoarchive.com
source), so expect to hand-edit sources/<slug>/{it,en}.txt afterwards to
tighten the line-by-line alignment the two-column layout depends on.
"""
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

HEADERS = {'User-Agent': 'Mozilla/5.0'}
SOURCES_DIR = Path(__file__).resolve().parent.parent / 'sources'


def fetch_body_lines(url):
    """Return the <br>-delimited top-level line nodes of a libretto page, past the cast-list <hr>."""
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    container = soup.select_one('div.col-lg-7 p')
    if container is None:
        raise RuntimeError(f'Could not find the libretto text container at {url}')

    contents = list(container.contents)
    for i, node in enumerate(contents):
        if isinstance(node, Tag) and node.name == 'hr':
            contents = contents[i + 1:]
            break

    lines, current = [], []
    for node in contents:
        if isinstance(node, Tag) and node.name == 'br':
            lines.append(current)
            current = []
        else:
            current.append(node)
    if current:
        lines.append(current)
    return lines


def classify_line(nodes):
    """Render one <br>-delimited line as a line of sources/*.txt."""
    real = [n for n in nodes if not (isinstance(n, NavigableString) and not n.strip())]
    if not real:
        return ''

    # A line that is *entirely* a single <i>...</i> is a stage direction.
    # It may itself span several source lines via <br> nested inside the
    # <i> — collapse those to spaces and wrap in parens per the grammar.
    if len(real) == 1 and isinstance(real[0], Tag) and real[0].name == 'i':
        text = ' '.join(real[0].get_text(separator=' ', strip=True).split())
        return f'({text})' if text else ''

    text = ''.join(
        n.get_text(separator=' ', strip=True) if isinstance(n, Tag) else str(n)
        for n in real
    )
    return ' '.join(text.split())


def fetch_libretto_text(url):
    lines = fetch_body_lines(url)
    rendered = [classify_line(line) for line in lines]

    # Collapse runs of multiple blank lines into a single stanza break
    out = []
    for line in rendered:
        if line == '' and out and out[-1] == '':
            continue
        out.append(line)
    while out and out[0] == '':
        out.pop(0)
    while out and out[-1] == '':
        out.pop()

    return '\n'.join(out) + '\n'


def seed_opera(slug, it_url, en_url):
    opera_dir = SOURCES_DIR / slug
    opera_dir.mkdir(parents=True, exist_ok=True)

    for lang, url in (('it', it_url), ('en', en_url)):
        print(f'Fetching {lang} from {url}...')
        text = fetch_libretto_text(url)
        out_path = opera_dir / f'{lang}.txt'
        out_path.write_text(text, encoding='utf-8')
        print(f'  wrote {out_path} ({text.count(chr(10))} lines)')


if __name__ == '__main__':
    seed_opera(
        'tosca',
        it_url='https://opera-guide.ch/en/operas/tosca/libretto/it/',
        en_url='https://opera-guide.ch/en/operas/tosca/libretto/en/',
    )
