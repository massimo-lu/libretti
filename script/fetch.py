import requests
from bs4 import BeautifulSoup

def fetch_and_generate(url, output_filename):
    print(f"Fetching {url}...")
    
    # 1. Fetch the web page
    headers = {'User-Agent': 'Mozilla/5.0'} # Helps prevent being blocked by the server
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Failed to retrieve page. Status code: {response.status_code}")
        return

    # 2. Parse the HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 3. Find the side-by-side text
    # Note: Most side-by-side libretti are laid out in tables. 
    # If the site uses divs instead, you will need to change 'tr' and 'td' below.
    rows = soup.find_all('tr')
    
    if not rows:
        print("No table rows (<tr>) found. The website might use <div> tags for layout instead.")
        return
        
    libretto_html_content = ""
    
    # Loop through each row and extract the original and translated text
    for row in rows:
        columns = row.find_all(['td', 'th'])
        
        # We only want rows that have at least 2 columns (Original and Translation)
        if len(columns) >= 2:
            # .get_text(strip=True) removes messy whitespace/HTML tags
            original_text = columns[0].get_text(strip=True)
            translation_text = columns[1].get_text(strip=True)
            
            # Skip empty rows
            if not original_text and not translation_text:
                continue

            # 4. Wrap the scraped text in YOUR custom HTML structure
            libretto_html_content += f"""
      <div class="line-row">
        <div class="original">
          {original_text}
        </div>
        <div class="translation">
          {translation_text}
        </div>
      </div>"""

    # 5. Build the final HTML document with your CSS/JS links
    final_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Imported Libretto</title>
  
  <!-- Links to the shared styles in your GitHub repo -->
  <link rel="stylesheet" href="../css/libretto.css">
  <script src="../js/libretto.js" defer></script>
</head>
<body>

  <div class="libretto-container">
{libretto_html_content}
  </div>

</body>
</html>
"""

    # 6. Save it to a file you can upload to GitHub
    with open(output_filename, 'w', encoding='utf-8') as file:
        file.write(final_html)
        
    print(f"Success! {len(rows)} rows processed. Saved to '{output_filename}'.")
    print("You can now open this file, add your popup <span class='popup-trigger'> tags manually, and upload it to GitHub.")

# --- Run the script ---
target_url = "https://www.librettoarchive.com/Tosca_libretto_Italian_English"
output_file = "tosca.html"

fetch_and_generate(target_url, output_file)
