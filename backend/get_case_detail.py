import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json # For pretty printing the dictionary

# 1. Create a Session object to persist cookies
session = requests.Session()

# 2. Define Base URL and Target URL for POST
BASE_URL = "https://www.phhc.gov.in/"
post_url = urljoin(BASE_URL, "home.php?search_param=case") # Construct full POST URL

# 3. Request Headers for the initial POST (Mimicking the browser)
# REMOVED hardcoded 'Cookie'. Session object will handle cookies.
post_headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
    'Content-Type': 'application/x-www-form-urlencoded',
    # 'Cookie': 'PHPSESSID=kuamakdt9j47bg55bn2ur8i926', # REMOVED - Let session handle this
    'Host': 'www.phhc.gov.in', # Often optional with requests, but kept for mimicry
    'Origin': 'https://www.phhc.gov.in',
    'Referer': post_url, # Referer for the POST is often the page itself or where the form was
    'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
}

# 4. Form Data (Payload)
payload = {
    't_case_type': 'CWP',
    't_case_no': '10239',
    't_case_year': '2022',
    'submit': 'Search Case'
}

# --- Make the FIRST request (POST) using the session ---
try:
    print(f"Making POST request to: {post_url}")
    # Use the session object here
    first_page_response = session.post(post_url, headers=post_headers, data=payload, timeout=30) # Increased timeout
    first_page_response.raise_for_status() # Check for HTTP errors

    print("POST Request successful!")
    print(f"Status Code: {first_page_response.status_code}")
    # Optional: See cookies set by the server and stored in the session
    print(f"Session cookies after POST: {session.cookies.get_dict()}")
    # print("\nResponse Content (first 500 characters):")
    # print(first_page_response.text[:500]) # Optional: print start of response

except requests.exceptions.RequestException as e:
    print(f"Error during initial POST request: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Response Status Code: {e.response.status_code}")
        print(f"Response Body Preview: {e.response.text[:500]}...")
    exit() # Stop script if the first step fails


# --- Extraction Functions (Keep as they were, ensure they use the correct response) ---
def extract_table_to_dict(html_content):
    """Extracts data from the first data row of table#tables11 into a dictionary."""
    soup = BeautifulSoup(html_content, 'lxml')
    data_dict = None
    table_tag = soup.find('table', id='tables11')
    if not table_tag:
        print("Error: Table with id='tables11' not found.")
        return None

    all_rows = table_tag.find_all('tr')
    if len(all_rows) < 3:
        print(f"Error: Expected at least 3 rows in table 'tables11', found {len(all_rows)}.")
        return None

    header_row = all_rows[1]
    headers = [th.get_text(strip=True) for th in header_row.find_all('th')]
    if not headers:
        print("Error: Could not find header cells (<th>) in the second row.")
        return None

    data_row = all_rows[2] # Assuming data is in the third row
    values_cells = data_row.find_all('td')
    values = [td.get_text(strip=True) for td in values_cells]

    if len(headers) == len(values):
        data_dict = dict(zip(headers, values))
    else:
        print(f"Warning: Mismatch between header count ({len(headers)}) and data cell count ({len(values)}). Cannot create reliable dictionary.")
        return None
    return data_dict

def extract_link_from_table(html_content):
    """Extracts the href from the first link in the first data cell of table#tables11."""
    soup = BeautifulSoup(html_content, 'lxml')
    extracted_link = None
    table_tag = soup.find('table', id='tables11')
    if not table_tag:
        print("Error: Table with id='tables11' not found for link extraction.")
        return None

    all_rows = table_tag.find_all('tr')
    if len(all_rows) < 3:
        print(f"Error: Not enough rows in table 'tables11' for link extraction.")
        return None

    data_row = all_rows[2] # Assuming data (and link) is in the third row
    first_cell = data_row.find('td')
    if first_cell:
        link_tag = first_cell.find('a', href=True) # Find 'a' tag with an href attribute
        if link_tag:
            extracted_link = link_tag.get('href')
            print(f"Found link tag: {link_tag}") # Debug print
        else:
            print("Error: No 'a' tag with href found in the first data cell.")
            print(f"First data cell content: {first_cell}") # Debug print
    else:
        print("Error: No 'td' cells found in the data row.")
        print(f"Data row content: {data_row}") # Debug print

    return extracted_link

# --- Extract data and link from the first response ---
first_page_html = first_page_response.text
case_data_dictionary = extract_table_to_dict(first_page_html)
link = extract_link_from_table(first_page_html)

print("\n--- Extraction Results ---")
if case_data_dictionary:
    print("\nExtracted Table Data as Dictionary:")
    print(json.dumps(case_data_dictionary, indent=4))
else:
    print("\nCould not extract table data into a dictionary.")

print("-" * 40)

if not link:
    print("\nError: Could not extract the link. Exiting.")
    # Optional: Print more of the HTML to debug link extraction failure
    # print("\n--- HTML Content (for debugging link extraction) ---")
    # print(first_page_html[:2000])
    exit()
else:
    print(f"\nExtracted relative link: {link}")

# --- Make the SECOND request (GET) for the extracted link using the SAME session ---
full_url = urljoin(BASE_URL, link.strip()) # Use urljoin and strip whitespace from link
print(f"Making GET request to: {full_url}")

# Headers for the second request (GET) - User-Agent and Referer are often important
get_headers = {
    'User-Agent': post_headers['User-Agent'], # Use the same User-Agent
    'Referer': post_url, # Indicate we came from the search results page
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
}

try:
    # Use the session object again - it will automatically send the necessary cookies
    linked_page_response = session.get(full_url, headers=get_headers, timeout=30) # Increased timeout
    linked_page_response.raise_for_status() # Check for HTTP errors

    print(f"\nSuccessfully fetched content for linked page: {full_url}")
    print(f"Status Code: {linked_page_response.status_code}")
    linked_page_html = linked_page_response.text

    # Optional: Check if the URL is what we expected (no unexpected redirects)
    if linked_page_response.url != full_url:
        print(f"Note: Final URL is {linked_page_response.url} (might indicate a redirect)")

    print("\n--- Linked Page Content (first 1000 characters) ---")
    print(linked_page_html)
    print("-" * 40)

    # Now you can parse linked_page_html with BeautifulSoup if needed
    # soup_linked_page = BeautifulSoup(linked_page_html, 'lxml')
    # ... find elements in the linked page ...

except requests.exceptions.RequestException as e:
    print(f"\nError during GET request for linked page {full_url}: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Response Status Code: {e.response.status_code}")
        # Check if we were perhaps redirected back to the homepage
        if 'home.php' in str(e.response.url) or e.response.is_redirect:
             print("It seems we might have been redirected, possibly back to the homepage. The session might not be working as expected or the link requires more parameters.")
        print(f"Response Body Preview: {e.response.text[:500]}...")