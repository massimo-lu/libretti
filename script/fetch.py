import requests
from bs4 import BeautifulSoup, Tag
from itertools import zip_longest


def split_cell(td):
    """Split a libretto <td> into (character_name, [line_html, ...]).

    A dialogue cell looks like:
        <b>Angelotti</b><br />
        Ah! Finalmente!<br />
        <i>(stage direction on its own line)</i><br />
        <br />
        Next stanza...

    The leading <b> (if any) is the speaker's name; the rest of the
    cell is a series of lines separated by <br> tags.
    """
    contents = list(td.contents)

    character = None
    if contents and isinstance(contents[0], Tag) and contents[0].name == 'b':
        character = contents[0].get_text(strip=True)
        contents = contents[1:]
        # Drop the <br> (and any stray whitespace) right after the name
        while contents and (
            (isinstance(contents[0], Tag) and contents[0].name == 'br')
            or (isinstance(contents[0], str) and not contents[0].strip())
        ):
            contents = contents[1:]

    lines, current = [], []
    for node in contents:
        if isinstance(node, Tag) and node.name == 'br':
            lines.append(current)
            current = []
        else:
            current.append(node)
    lines.append(current)

    line_html = [''.join(str(n) for n in group).strip() for group in lines]
    return character, line_html


def line_kind(line_html):
    """Classify a single line as ('gap', None), ('stage', text) or ('text', html)."""
    if not line_html:
        return 'gap', None

    fragment = BeautifulSoup(line_html, 'html.parser')
    nodes = [n for n in fragment.contents if not (isinstance(n, str) and not n.strip())]

    # A line that is *entirely* a single <i>...</i> is a stage direction,
    # e.g. "<i>(Torna a guardare intorno a sé.)</i>". The direction itself
    # can wrap across several source lines with <br> tags nested inside
    # the <i> — collapse those to spaces rather than leaking raw markup.
    if len(nodes) == 1 and isinstance(nodes[0], Tag) and nodes[0].name == 'i':
        return 'stage', nodes[0].get_text(separator=' ', strip=True)

    return 'text', line_html


def render_row(css_class, original, translation):
    extra = f' {css_class}' if css_class else ''
    return f'''
            <div class="original{extra}">{original}</div>
            <div class="translation{extra}">{translation}</div>'''


def render_character(name_it, name_en):
    alt = f'<span class="alt">{name_en}</span>' if name_en and name_en != name_it else ''
    return f'''
            <div class="character-name">{name_it}{alt}</div>'''


def render_act(text_it, text_en):
    alt = f'<span class="alt">{text_en}</span>' if text_en and text_en != text_it else ''
    return f'''
            <div class="act-header">{text_it}{alt}</div>'''


def render_gap():
    return '''
            <div class="line-gap"></div>'''


def convert_table(table):
    """Walk the source <table class="lc-wrap"> and build the libretto-grid body."""
    html = ''
    last_was_gap = True  # avoid a leading/duplicated gap

    for row in table.find_all('tr'):
        cells = row.find_all(['td', 'th'], recursive=False)
        if len(cells) < 2:
            continue

        orig_td, trans_td = cells[0], cells[1]

        # The page's own footer (e.g. the "libretto by ..." credits row)
        # wraps its content in a <div>, unlike any genuine libretto row.
        if orig_td.find('div') or trans_td.find('div'):
            continue

        row_classes = set(row.get('class', [])) | set(orig_td.get('class', []))

        # Act / section headings, e.g. <tr class="lc-act"> ... "ATTO PRIMO" / "ACT ONE"
        if 'lc-act' in row_classes:
            text_it = orig_td.get_text(strip=True)
            text_en = trans_td.get_text(strip=True)
            if not text_it and not text_en:
                continue
            html += render_act(text_it, text_en)
            last_was_gap = True
            continue

        # Whole-cell stage direction, e.g. the scene-setting description
        if 'lc-stage' in row_classes:
            text_it = ' '.join(orig_td.get_text(separator=' ', strip=True).split())
            text_en = ' '.join(trans_td.get_text(separator=' ', strip=True).split())
            if not text_it and not text_en:
                continue
            html += render_row('stage-direction', text_it, text_en)
            last_was_gap = False
            continue

        # Regular dialogue cell: leading <b>Name</b> plus <br>-separated lines
        char_it, lines_it = split_cell(orig_td)
        char_en, lines_en = split_cell(trans_td)

        if not any(lines_it) and not any(lines_en) and not char_it and not char_en:
            continue

        if char_it or char_en:
            html += render_character(char_it or char_en, char_en)
            last_was_gap = True

        for line_it, line_en in zip_longest(lines_it, lines_en, fillvalue=''):
            kind_it, text_it = line_kind(line_it)
            kind_en, text_en = line_kind(line_en)

            if kind_it == 'gap' and kind_en == 'gap':
                if not last_was_gap:
                    html += render_gap()
                last_was_gap = True
                continue

            if kind_it == 'stage' or kind_en == 'stage':
                html += render_row('stage-direction', text_it or '', text_en or '')
            else:
                html += render_row('', text_it or '', text_en or '')
            last_was_gap = False

    return html


def fetch_and_generate(url, output_filename, css_path='../css/libretto.css', js_path='../js/libretto.js'):
    print(f"Fetching {url}...")

    # 1. Fetch the web page
    headers = {'User-Agent': 'Mozilla/5.0'}  # Helps prevent being blocked by the server
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to retrieve page. Status code: {response.status_code}")
        return

    # 2. Parse the HTML
    soup = BeautifulSoup(response.text, 'html.parser')

    # 3. Find the side-by-side table
    # librettoarchive.com lays its side-by-side text out as <table class="lc-wrap">,
    # with act/section headers marked by class "lc-act" and the speaker's name given
    # simply as a leading <b> inside the line-carrying <td>.
    table = soup.find('table', class_='lc-wrap')

    if table is None:
        print("No <table class=\"lc-wrap\"> found. The website's markup may have changed.")
        return

    # 4. Opera title & composer, from the page's own heading
    h1 = soup.find('h1')
    opera_title = h1.get_text(strip=True).strip('“”"') if h1 else 'Imported Libretto'

    h2 = soup.find('h2')
    composer = ''
    if h2:
        composer_link = h2.find('a')
        composer = composer_link.get_text(strip=True) if composer_link else h2.get_text(strip=True)

    # 5. Build the libretto grid rows
    grid_rows = convert_table(table)

    # 6. Build the final HTML document with your CSS/JS links
    final_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{opera_title} - Libretto Translation</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;1,400&family=Playfair+Display:ital,wght@0,600;0,700;1,600&display=swap" rel="stylesheet">
    <!-- Links to the shared styles/scripts in your GitHub repo -->
    <link rel="stylesheet" href="{css_path}">
    <script src="{js_path}" defer></script>
</head>
<body>

    <header class="libretto-header">
        <h1 class="opera-title">{opera_title}</h1>
        <h2 class="opera-composer">{composer}</h2>
        <p class="opera-note">
            Click on the <span class="note-trigger">highlighted words</span> to read translation notes.
        </p>
    </header>

    <main class="libretto-body">

        <!-- Column Headers -->
        <div class="libretto-grid column-headers">
            <div class="original">Italiano (Originale)</div>
            <div class="translation">English (Translation)</div>
        </div>

        <div class="libretto-grid">{grid_rows}
        </div>
    </main>

    <div id="tooltip" role="tooltip" aria-hidden="true"></div>

</body>
</html>
"""

    # 7. Save it to a file you can upload to GitHub
    with open(output_filename, 'w', encoding='utf-8') as file:
        file.write(final_html)

    print(f"Success! Saved to '{output_filename}'.")
    print("You can now open this file, add your popup <span class='note-trigger'> tags manually, and upload it to GitHub.")


# --- Run the script ---
if __name__ == '__main__':
    target_url = "https://www.librettoarchive.com/Tosca_libretto_Italian_English"
    # NB: "_tosca.html" (leading underscore) is the hand-crafted reference
    # template for the libretto-grid markup/CSS classes; generated pages go
    # to the un-prefixed filename instead so they never overwrite it.
    output_file = "../libretto/tosca.html"

    fetch_and_generate(target_url, output_file)
