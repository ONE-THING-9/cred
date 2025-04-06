import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote, parse_qs, urlparse
import json
import re
import os
import logging
import time # <--- Already imported, needed for sleep
import tempfile
import shutil
from fastapi import HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse
import base64
import os
from google import genai
from google.genai import types
from concurrent.futures import ThreadPoolExecutor, as_completed # Import necessary modules


from schema import GetCaseDetailsResponse, GetCaseFileRequest
# --- Configure Logging --- (Keep as is)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants --- (Keep as is)
BASE_URL = "https://www.phhc.gov.in/"
DOWNLOAD_DIR = "downloaded_files"

# --- Helper Functions --- (Keep as is - clean_text, extract_onclick_link)
def clean_text(element):
    """Helper function to get stripped text from a BS4 element."""
    if element:
        return element.get_text(strip=True).replace('\xa0', ' ').strip()
    return ""

def extract_onclick_link(tag):
    """Extracts the URL part from an OnClick javascript link."""
    if tag and tag.has_attr('onclick'):
        onclick_attr = tag['onclick']
        match = re.search(r"window\.open\('([^']+)'\)", onclick_attr)
        if match:
            link = match.group(1)
            if link.startswith('download_file.php'):
                return link
            return link
    return None

# --- Parsing Function --- (Keep as is - parse_case_details_page)
def parse_case_details_page(html_content):
    # ... (rest of the implementation remains unchanged) ...
    soup = BeautifulSoup(html_content, 'lxml')

    main_table = soup.find('table', id='table1')
    if not main_table:
        logger.error("Error: Main table with id='table1' not found.")
        return None

    all_data = {
        "case_details": {},
        "related_cases": [],
        "case_listing": [],
        "copy_petitions": [],
        "judgment_details": []
    }
    # Reset these for each parse
    case_listing_headers = []
    copy_petition_headers = []
    judgment_details_headers = []
    current_section = None
    rows = main_table.find_all('tr', recursive=False)

    # Use enumerate to easily access the next row for header capture
    for i, row in enumerate(rows):
        # Find potential headers
        header_cell = row.find('th', class_='case_header')
        section_header_cell = row.find('th', {'colspan': '4'})
        sub_header_cells = row.find_all('th', class_='header_sub_text') # Headers for case listing
        copy_petition_sub_headers = row.find_all('th', align='left', width='25%') # Headers for copy petition
        judgment_sub_headers = row.find_all('th', recursive=False) # Headers for judgments (more general)

        # --- Identify Section Headers ---
        is_section_header = False
        if header_cell:
            section_title = clean_text(header_cell)
            if "Case Details For Case" in section_title:
                current_section = "case_details"
                all_data["case_details"]["Section Title"] = section_title
                is_section_header = True

        # Check for general section headers ONLY if not already identified as the main case header
        if not is_section_header and section_header_cell and section_header_cell.get('class') != ['case_header']:
            section_title = clean_text(section_header_cell)
            if "Related Cases/Miscellaneous Applications" in section_title:
                current_section = "related_cases"
                all_data["related_cases_title"] = section_title
                is_section_header = True
            elif "Case Listing Details" in section_title:
                current_section = "case_listing"
                all_data["case_listing_title"] = section_title
                if i + 1 < len(rows):
                    potential_headers = rows[i+1].find_all('th', class_='header_sub_text')
                    if potential_headers: # Only update if we find the specific class
                       case_listing_headers = [clean_text(th) for th in potential_headers]
                       logger.debug(f"Captured Case Listing Headers: {case_listing_headers}")
                is_section_header = True
            elif "Details of Copy Petition Applied" in section_title:
                current_section = "copy_petitions"
                all_data["copy_petitions_title"] = section_title
                if i + 1 < len(rows):
                     th_tags = rows[i+1].find_all('th')
                     if len(th_tags) == 4:
                         copy_petition_headers = [clean_text(th) for th in th_tags]
                         logger.debug(f"Captured Copy Petition Headers: {copy_petition_headers}")
                is_section_header = True
            elif "Judgment Details For Case" in section_title:
                current_section = "judgment_details"
                all_data["judgment_details_title"] = section_title
                if i + 1 < len(rows):
                     th_tags = rows[i+1].find_all('th')
                     if len(th_tags) == 4:
                         judgment_details_headers = [clean_text(th) for th in th_tags]
                         logger.debug(f"Captured Judgment Headers: {judgment_details_headers}")
                is_section_header = True

        if is_section_header:
             logger.debug(f"--- Identified Section: {current_section} ---")
             continue # Skip processing the rest of the loop for header rows

        # --- Skip Specific Header Rows for Multi-Row Tables ---
        if current_section == "case_listing" and sub_header_cells and len(sub_header_cells) == len(case_listing_headers) and case_listing_headers:
             logger.debug(f"Skipping case listing sub-header row: {[clean_text(th) for th in sub_header_cells]}")
             continue
        if current_section == "copy_petitions" and len(copy_petition_sub_headers) == len(copy_petition_headers) and copy_petition_headers:
             logger.debug(f"Skipping copy petition sub-header row: {[clean_text(th) for th in copy_petition_sub_headers]}")
             continue
        th_in_row = row.find_all('th', recursive=False)
        if current_section == "judgment_details" and len(th_in_row) == len(judgment_details_headers) and judgment_details_headers and not row.find('td', recursive=False):
             logger.debug(f"Skipping judgment details sub-header row: {[clean_text(th) for th in th_in_row]}")
             continue

        # --- Process Data Rows based on Current Section ---
        cells = row.find_all('td', recursive=False) # Find direct children td
        logger.debug(f"Processing Row in section '{current_section}': {len(cells)} cells")

        # --- Case Details Processing ---
        if current_section == "case_details" and len(cells) > 0:
            if len(cells) == 4:
                key1 = clean_text(cells[0])
                val1 = clean_text(cells[1])
                key2 = clean_text(cells[2])
                val2 = clean_text(cells[3])
                if key1: all_data["case_details"][key1] = val1
                if key2: all_data["case_details"][key2] = val2
            elif len(cells) == 2:
                 key1_cell = cells[0]
                 val1_cell = cells[1]
                 key1 = clean_text(key1_cell)
                 val1 = clean_text(val1_cell)
                 blink_tag = val1_cell.find('blink')
                 if blink_tag:
                     val1 = clean_text(blink_tag)
                 if key1_cell.get('class') == ['header_text'] or key1_cell.find('strong'):
                    if key1: all_data["case_details"][key1] = val1
                 elif 'Advocate Name' in all_data["case_details"] and 'Respondent Advocate Name' not in all_data["case_details"]:
                     if not key1 and val1: # If first cell is blank, assume it's Respondent Advocate value
                          prev_key_cell = row.find_previous('td', class_='header_text')
                          if prev_key_cell and 'Advocate Name' in clean_text(prev_key_cell):
                              all_data["case_details"]['Respondent Advocate Name'] = val1
                          else:
                              all_data["case_details"]['Respondent Advocate Name'] = val1
                 elif key1:
                    all_data["case_details"][key1] = val1

        # --- Related Cases Processing ---
        elif current_section == "related_cases" and len(cells) >= 1:
            item_data = {}
            cell1 = cells[0]
            cell2 = cells[1] if len(cells) > 1 else None

            links = cell1.find_all('a')
            item_data['Case Links'] = []
            link_texts = []
            for link in links:
                link_info = {
                    "Text": clean_text(link),
                    "HREF": link.get('href'),
                    "OnClickLink": extract_onclick_link(link)
                }
                if link_info["OnClickLink"] or (not link_info["OnClickLink"] and link_info["Text"]):
                    item_data['Case Links'].append(link_info)
                    link_texts.append(link_info["Text"])

            desc_text = clean_text(cell1)
            for lt in link_texts:
                desc_text = desc_text.replace(lt, "", 1)
            item_data['Description'] = desc_text.strip()
            item_data['Context'] = clean_text(cell2)

            if item_data['Case Links'] or item_data['Description'] or item_data['Context']:
                 if not (len(cells)==1 and cells[0].has_attr('colspan') and not clean_text(cells[0])):
                    all_data["related_cases"].append(item_data)

        # --- Case Listing Processing ---
        elif current_section == "case_listing":
            cells = row.find_all('td', recursive=False)
            if cells and case_listing_headers and len(case_listing_headers) > 0:
                item_data = {}
                header_idx = 0
                cell_idx = 0
                while header_idx < len(case_listing_headers) and cell_idx < len(cells):
                    header = case_listing_headers[header_idx]
                    cell = cells[cell_idx]
                    item_data[header] = clean_text(cell)
                    colspan = cell.get('colspan')
                    increment = 1
                    if colspan:
                        try: increment = int(colspan)
                        except (ValueError, TypeError): increment = 1
                    header_idx += increment
                    cell_idx += 1
                if any(item_data.values()):
                    all_data["case_listing"].append(item_data)
                    logger.debug(f"Added Case Listing Item: {item_data}")

        # --- Copy Petitions Processing ---
        elif current_section == "copy_petitions":
             cells = row.find_all('td', recursive=False)
             if cells and copy_petition_headers and len(cells) == len(copy_petition_headers):
                item_data = {}
                for h_idx, header in enumerate(copy_petition_headers):
                    cell = cells[h_idx]
                    item_data[header] = clean_text(cell)
                    if h_idx == 0:
                        link_tag = cell.find('a')
                        if link_tag:
                            item_data[f"{header} Link HREF"] = link_tag.get('href')
                            item_data[f"{header} Link OnClick"] = extract_onclick_link(link_tag)
                if any(item_data.values()):
                    all_data["copy_petitions"].append(item_data)

        # --- Judgment Details Processing ---
        elif current_section == "judgment_details":
             cells = row.find_all('td', recursive=False)
             if cells and judgment_details_headers and len(cells) == len(judgment_details_headers):
                item_data = {}
                for h_idx, header in enumerate(judgment_details_headers):
                    cell = cells[h_idx]
                    cell_text = clean_text(cell)
                    item_data[header] = cell_text
                    link_tag = cell.find('a')
                    if link_tag :
                        onclick_link = extract_onclick_link(link_tag)
                        if onclick_link and 'download_file.php' in onclick_link:
                             item_data["Judgment Link OnClick Link"] = onclick_link
                if any(item_data.values()):
                    all_data["judgment_details"].append(item_data)

    return all_data

# --- Page Fetching Functions --- (Keep as is - get_first_page_content, extract_table_to_dict, extract_link_from_table, get_second_page)
def get_first_page_content(year, court, case_type, case_number, session):
    # ... (rest of the implementation remains unchanged) ...
    post_url = urljoin(BASE_URL, "home.php?search_param=case")
    post_headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Host': 'www.phhc.gov.in',
        'Origin': BASE_URL.rstrip('/'),
        'Referer': post_url,
        'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'User-Agent': session.headers.get('User-Agent', 'Mozilla/5.0')
    }
    payload = {
        't_case_type': case_type,
        't_case_no': case_number,
        't_case_year': year,
        'submit': 'Search Case'
    }
    logger.info(f"Payload for POST: {payload}")

    try:
        logger.info(f"Making POST request to: {post_url}")
        first_page_response = session.post(post_url, headers=post_headers, data=payload, timeout=45)
        first_page_response.raise_for_status()
        logger.info("POST Request successful!")
        logger.info(f"Status Code: {first_page_response.status_code}")
        logger.debug(f"Session cookies after POST: {session.cookies.get_dict()}")
        return first_page_response.text, post_headers, post_url

    except requests.exceptions.RequestException as e:
        logger.error(f"Error during initial POST request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response Status Code: {e.response.status_code}")
            logger.error(f"Response Body Preview: {e.response.text[:500]}...")
        raise e

def extract_table_to_dict(html_content):
    # ... (rest of the implementation remains unchanged) ...
    soup = BeautifulSoup(html_content, 'lxml')
    table_tag = soup.find('table', id='tables11')
    if not table_tag:
        logger.warning("Warning: Table with id='tables11' not found in first page.")
        return None
    all_rows = table_tag.find_all('tr')
    if len(all_rows) < 3: return None
    header_row = all_rows[1]
    headers = [th.get_text(strip=True) for th in header_row.find_all('th')]
    if not headers: return None
    data_row = all_rows[2]
    values_cells = data_row.find_all('td')
    values = [td.get_text(strip=True) for td in values_cells]
    if len(headers) == len(values): return dict(zip(headers, values))
    else: return None

def extract_link_from_table(html_content):
    # ... (rest of the implementation remains unchanged) ...
    soup = BeautifulSoup(html_content, 'lxml')
    table_tag = soup.find('table', id='tables11')
    if not table_tag: return None
    all_rows = table_tag.find_all('tr')
    if len(all_rows) < 3: return None
    data_row = all_rows[2]
    first_cell = data_row.find('td')
    if first_cell:
        link_tag = first_cell.find('a', href=True)
        if link_tag:
            extracted_link = link_tag.get('href')
            logger.info(f"Found link tag in first table: {link_tag}")
            return extracted_link
    return None

def get_second_page(session, post_headers, post_url, link):
    # ... (rest of the implementation remains unchanged) ...
    full_url = urljoin(BASE_URL, link.strip())
    logger.info(f"Making GET request to: {full_url}")
    get_headers = {
        'User-Agent': session.headers.get('User-Agent', 'Mozilla/5.0'),
        'Referer': post_url,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    try:
        linked_page_response = session.get(full_url, headers=get_headers, timeout=45)
        linked_page_response.raise_for_status()
        logger.info(f"Successfully fetched content for linked page: {full_url}")
        logger.info(f"Status Code: {linked_page_response.status_code}")
        if linked_page_response.url != full_url:
            logger.warning(f"Note: Final URL is {linked_page_response.url} (redirect occurred)")
        return linked_page_response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"\nError during GET request for linked page {full_url}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response Status Code: {e.response.status_code}")
            if 'home.php' in str(e.response.url) or e.response.is_redirect:
                logger.warning("Redirect detected, possibly back to homepage. Session/link validity issue?")
            logger.error(f"Response Body Preview: {e.response.text[:500]}...")
        raise e

# --- Post Processing Function --- (Keep as is - post_process_case_result)
def post_process_case_result(data, case_number):
    # ... (rest of the implementation remains unchanged) ...
    final_data = {}
    final_data['case_number'] = case_number

    # --- Case Details ---
    case_details_raw = data.get('case_details', {})
    final_data['case_details'] = {
        'section_title': case_details_raw.get("Section Title", ""),
        'diary_number': case_details_raw.get('Diary Number', '---'),
        'registration_date': case_details_raw.get('Registration Date', '---'),
        'category': case_details_raw.get('Category', '---'),
        'main_case_detail': case_details_raw.get('Main Case Detail', '---'),
        'party_detail': case_details_raw.get('Party Detail', '---'),
        'district': case_details_raw.get('District', '---'),
        'advocate_name': case_details_raw.get('Advocate Name', '---'),
        'list_type': case_details_raw.get('List Type', '---'),
        'respondent_advocate_name': case_details_raw.get('Respondent Advocate Name', '---'),
        'status': case_details_raw.get('Status', '---'),
        'next_date': case_details_raw.get('Next date', '---')
    }

    # --- Related Cases ---
    related_cases = []
    for case in data.get('related_cases', []):
        r_case = {}
        case_num_link = next((link for link in case.get('Case Links', []) if not link.get('OnClickLink') and link.get('Text')), None)
        r_case['case_number'] = case_num_link['Text'] if case_num_link else case.get('Description', '').split(' ')[0]
        order_link_info = next((link for link in case.get('Case Links', []) if link.get('OnClickLink') and 'download_file.php' in link.get('OnClickLink')), None)
        if order_link_info:
            r_case['view_order'] = "view order"
            r_case['view_order_link'] = order_link_info.get('OnClickLink')
        else:
            r_case['view_order'] = None
            r_case['view_order_link'] = None
        r_case['description'] = case.get('Context', '') or case.get('Description', '')
        related_cases.append(r_case)
    final_data['related_cases'] = related_cases

    # --- Case Listing ---
    case_listing = []
    for case in data.get('case_listing', []):
        l_case = {'cause_list_date': case.get("Cause List Date", ""), 'list_type_sr_no': case.get("List Type:Sr. No.", ""), 'bench': case.get('Bench', "")}
        case_listing.append(l_case)
    final_data["case_listing"] = case_listing

    # --- Copy Petitions ---
    copy_petitions = []
    for case in data.get('copy_petitions', []):
        c_case = {
            'petition_type_no': case.get("Petition Type/No", ""),
            'petition_date': case.get("Petition Date", ""),
            'applied_by': case.get("Applied By", ""),
            'petition_status': case.get("Petition Status", ""),
            'link': (case.get("Petition Type/No Link OnClick") if case.get("Petition Type/No Link OnClick") and 'download_file.php' in case.get("Petition Type/No Link OnClick") else None) or case.get("Petition Type/No Link HREF") or "None"
        }
        copy_petitions.append(c_case)
    final_data['copy_petitions'] = copy_petitions

    # --- Judgment Details ---
    judgment_details = []
    for case in data.get('judgment_details', []):
        j_case = {
            'order_date': case.get("Order Date", ""),
            'order_and_case_id': case.get("Order and Case-ID", ""),
            'bench': case.get('Bench', ""),
            'view_order': "view order" if case.get("Judgment Link OnClick Link") else None,
            'order_link': case.get("Judgment Link OnClick Link")
        }
        judgment_details.append(j_case)
    final_data['judgment_details'] = judgment_details

    return final_data

def generate(file_path):
    logger.info(f"File path: {file_path}")
    client = genai.Client(
        api_key="AIzaSyBWqzsaywJ3pkzysv14BuV_7Bs-az5TBTA",
    )

    files = [
        # Please ensure that the file is available in local system working direrctory or change the file path.
        client.files.upload(file=file_path),
    ]
    model = "gemini-2.0-flash"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_uri(
                    file_uri=files[0].uri,
                    mime_type=files[0].mime_type,
                ),
                types.Part.from_text(text="""give me what is the text in the image. dont return anything else just give me text in image. """),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        response_mime_type="text/plain",
    )
    #     from google import genai

    # client = genai.Client()

    # response = client.models.generate_content(
    #     model='gemini-2.0-flash', 
    #     contents='Tell me a story in 300 words.'
    # )

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config,
    )
    return response.text

# --- MODIFIED Download Function with CAPTCHA Handling and Retry ---
def download_file_with_captcha(session, relative_url, save_dir, filename_prefix="file", max_retries=3):
    """
    Downloads a file protected by a CAPTCHA from phhc.gov.in, with retries.

    Args:
        session: The requests.Session object with necessary cookies.
        relative_url: The relative URL like 'download_file.php?auth=...'.
        save_dir: The directory to save the downloaded file.
        filename_prefix: A prefix to use for the downloaded filename.
        max_retries (int): Maximum number of download attempts.

    Returns:
        The full path to the downloaded file, or None if download fails after all retries.
    """
    if not relative_url or not isinstance(relative_url, str) or 'download_file.php' not in relative_url:
        logger.warning(f"Invalid or non-download relative_url provided: {relative_url}")
        return None

    full_url = urljoin(BASE_URL, relative_url.strip())
    parsed_url = urlparse(full_url)
    query_params = parse_qs(parsed_url.query)
    auth_param = query_params.get('auth', [None])[0]

    if not auth_param:
        logger.error(f"Could not extract 'auth' parameter from URL: {full_url}")
        return None

    logger.info(f"Attempting CAPTCHA download from: {full_url} (Max Retries: {max_retries})")
    os.makedirs(save_dir, exist_ok=True)

    for attempt in range(max_retries):
        logger.info(f"--- Download Attempt {attempt + 1} of {max_retries} for {filename_prefix} ---")
        temp_captcha_path = None  # Reset path for each attempt

        try:
            # --- 1. Initial GET to fetch the CAPTCHA page ---
            logger.info("Step 1: Fetching CAPTCHA page...")
            get_headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'en-US,en;q=0.9',
                'Connection': 'keep-alive',
                'Referer': BASE_URL, # Referer might be the main page or previous case page
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
                'User-Agent': session.headers.get('User-Agent', 'Mozilla/5.0')
            }
            captcha_page_response = session.get(full_url, headers=get_headers, timeout=30)
            captcha_page_response.raise_for_status()

            # --- 2. Parse HTML to find CAPTCHA image URL ---
            logger.info("Step 2: Parsing CAPTCHA page HTML...")
            soup = BeautifulSoup(captcha_page_response.text, 'html.parser')
            captcha_img_tag = soup.find('img', {'id': 'captchaimg'})
            if not captcha_img_tag:
                logger.error("Could not find CAPTCHA image tag (id='captchaimg') on the page.")
                # No point retrying if the page structure is wrong
                return None # Exit function if fundamental structure issue

            relative_captcha_url = captcha_img_tag.get('src')
            if not relative_captcha_url:
                logger.error("Found CAPTCHA img tag but it has no 'src' attribute.")
                 # No point retrying if the page structure is wrong
                return None # Exit function if fundamental structure issue

            # --- 3. Download the CAPTCHA Image ---
            logger.info("Step 3: Downloading CAPTCHA image...")
            captcha_image_url = urljoin(captcha_page_response.url, relative_captcha_url)
            logger.debug(f"CAPTCHA Image URL: {captcha_image_url}")

            image_headers = get_headers.copy()
            image_headers['Accept'] = 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
            image_headers['Referer'] = full_url
            image_headers['Sec-Fetch-Dest'] = 'image'
            if 'Upgrade-Insecure-Requests' in image_headers: del image_headers['Upgrade-Insecure-Requests']
            if 'Sec-Fetch-User' in image_headers: del image_headers['Sec-Fetch-User']

            response_image = session.get(captcha_image_url, headers=image_headers, stream=True, timeout=20)
            response_image.raise_for_status()

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                temp_captcha_path = tmp_file.name
                for chunk in response_image.iter_content(chunk_size=8192):
                    if chunk: tmp_file.write(chunk)
            logger.info(f"CAPTCHA image saved temporarily to: {temp_captcha_path}")

            # # --- 4. Prompt User for CAPTCHA Code ---
            # print("-" * 50)
            # print(f"CAPTCHA required for: {filename_prefix} (Attempt {attempt + 1}/{max_retries})")
            # try:
            #     print(f"Please open this image file: {os.path.abspath(temp_captcha_path)}")
            # except Exception:
            #     print(f"Please find the CAPTCHA image at: {temp_captcha_path}")
            # time.sleep(1)
            captcha_code = generate(temp_captcha_path)

            if not captcha_code:
                logger.warning("No CAPTCHA code entered for this attempt.")
                # Continue to the next retry attempt
                # Clean up the temp file for *this* attempt before continuing
                if temp_captcha_path and os.path.exists(temp_captcha_path):
                    try: os.remove(temp_captcha_path)
                    except OSError as e: logger.warning(f"Could not delete temp CAPTCHA file {temp_captcha_path}: {e}")
                # Add delay before next attempt only if not the last one
                if attempt < max_retries - 1:
                    logger.info(f"Waiting 5 seconds before next attempt...")
                    time.sleep(5)
                continue # Skip to the next iteration of the loop


            # --- 5. Submit CAPTCHA Code via POST ---
            logger.info(f"Step 4: Submitting CAPTCHA code '{captcha_code}'...")
            post_data = {
                'auth': auth_param,
                'vercode': captcha_code,
                'submit': 'Submit'
            }
            post_headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'max-age=0',
                'Connection': 'keep-alive',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': BASE_URL.rstrip('/'),
                'Referer': full_url,
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
                'User-Agent': session.headers.get('User-Agent', 'Mozilla/5.0')
            }

            response_file = session.post(full_url, headers=post_headers, data=post_data, stream=True, timeout=60)
            response_file.raise_for_status()

            # --- 6. Check Response and Save File ---
            logger.debug(f"POST submission Status Code: {response_file.status_code}")
            content_type = response_file.headers.get('Content-Type', '').lower()
            content_disposition = response_file.headers.get('Content-Disposition')

            # Check if CAPTCHA failed (returns HTML)
            if 'text/html' in content_type:
                logger.error(f"CAPTCHA submission failed on attempt {attempt + 1}. Received HTML page.")
                fail_soup = BeautifulSoup(response_file.text, 'html.parser')
                error_msg = fail_soup.find(style=lambda s: s and 'color: red' in s.lower())
                if error_msg:
                    logger.error(f"Error message found: {clean_text(error_msg)}")
                # Let the loop continue for retry
                # Clean up the temp file for *this* attempt before continuing
                if temp_captcha_path and os.path.exists(temp_captcha_path):
                    try: os.remove(temp_captcha_path)
                    except OSError as e: logger.warning(f"Could not delete temp CAPTCHA file {temp_captcha_path}: {e}")
                # Add delay before next attempt only if not the last one
                if attempt < max_retries - 1:
                    logger.info(f"Waiting 5 seconds before next attempt...")
                    time.sleep(5)
                continue # Skip to the next iteration

            # --- Success Case ---
            logger.info(f"Step 5: Saving the downloaded file (Attempt {attempt + 1})...")
            filename = None
            if content_disposition:
                filename_match = re.search(r'filename="?([^"]+)"?', content_disposition)
                if filename_match:
                    filename = unquote(filename_match.group(1))
                    filename = re.sub(r'[\\/*?:"<>|]', "_", filename)

            if not filename:
                safe_prefix = re.sub(r'[\\/*?:"<>|]', "_", filename_prefix)
                extension = ".pdf"
                if 'pdf' in content_type: extension = ".pdf"
                elif 'zip' in content_type: extension = ".zip"
                else: extension = ".bin"
                filename = f"{safe_prefix}_captcha_download{extension}"
                logger.info(f"No Content-Disposition filename. Generated: {filename}")

            save_path = os.path.join(save_dir, filename)
            logger.info(f"Saving file to: {save_path}")

            with open(save_path, 'wb') as f:
                for chunk in response_file.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)

            logger.info(f"Successfully downloaded and saved: {save_path} on attempt {attempt + 1}")
            # Clean up temp file on success
            if temp_captcha_path and os.path.exists(temp_captcha_path):
                try: os.remove(temp_captcha_path)
                except OSError as e: logger.warning(f"Could not delete temp CAPTCHA file {temp_captcha_path}: {e}")
            return save_path # <<< SUCCESS: Exit loop and function

        except requests.exceptions.RequestException as e:
            logger.error(f"Error during download attempt {attempt + 1}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response Status Code: {e.response.status_code}")
                resp_content_type = e.response.headers.get('content-type', '').lower()
                if 'text' in resp_content_type or 'json' in resp_content_type:
                    logger.error(f"Response Body Preview: {e.response.text[:500]}...")
            # Let the loop continue for retry

        except IOError as e:
            logger.error(f"Error saving file on attempt {attempt + 1}: {e}")
            # Let the loop continue for retry (though unlikely to succeed if disk is full)

        except Exception as e:
            logger.exception(f"An unexpected error occurred during download attempt {attempt + 1}: {e}")
            # Let the loop continue for retry

        finally:
             # Ensure temp file for *this attempt* is cleaned up if it exists,
             # especially if an error happened after creation but before explicit cleanup.
            if temp_captcha_path and os.path.exists(temp_captcha_path):
                try:
                    os.remove(temp_captcha_path)
                    logger.debug(f"Cleaned up temp CAPTCHA file from attempt {attempt+1}: {temp_captcha_path}")
                except OSError as e:
                    logger.warning(f"Could not delete temp CAPTCHA file {temp_captcha_path} after attempt {attempt+1}: {e}")

        # --- Add delay before next attempt if not the last one ---
        if attempt < max_retries - 1:
            logger.info(f"Waiting 5 seconds before next attempt...")
            time.sleep(5) # Wait 5 seconds between retries

    # --- If loop finishes without returning, all retries failed ---
    logger.error(f"Download failed for {filename_prefix} after {max_retries} attempts.")
    return None


# --- Main Function --- (Modified to check DB first and use background tasks for downloads)
async def get_case_details(request: Request, background_tasks: BackgroundTasks, year, court, case_type, case_number):
    session = None
    try:
        case_id_str = f"{case_type}-{case_number}-{year}"
        logger.info(f"Starting case details retrieval for: {case_id_str}")
        
        # First check if this case already exists in the database
        db = request.state.case_db
        collection = db[case_id_str]
        existing_case = await collection.find_one({"case_number": case_id_str})
        
        if existing_case:
            logger.info(f"Case {case_id_str} found in database, returning cached data")
            # Remove MongoDB _id field which is not JSON serializable
            if '_id' in existing_case:
                del existing_case['_id']
            # Return as proper response class
            return GetCaseDetailsResponse(**existing_case)
        
        # Case not in DB, proceed with fetching from website
        logger.info(f"Case {case_id_str} not found in database, fetching from website")
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
        })

        # 1. Get first page
        first_html_page_content, post_headers, post_url = get_first_page_content(year, court, case_type, case_number, session)
        logger.info("First page content retrieved successfully")

        # 2. Extract link
        second_page_url = extract_link_from_table(first_html_page_content)
        if not second_page_url:
            logger.error("Failed to extract second page URL from the first table.")
            raise ValueError("Could not find the case details link (second page URL).")

        # 3. Get second page
        linked_html_page = get_second_page(session, post_headers, post_url, second_page_url)
        logger.info("Second page content retrieved successfully")

        # 4. Parse details
        structured_data = parse_case_details_page(linked_html_page)
        if not structured_data:
             logger.error("Failed to parse structured data from the second page.")
             raise ValueError("Could not parse case details from the second page.")

        structured_data['case_number'] = case_id_str

        # 5. Post-process
        response_data = post_process_case_result(structured_data, case_id_str)
        
        # 6. Schedule background download tasks and DB update
        background_tasks.add_task(
            download_files_and_update_db, 
            session.cookies.get_dict(),
            response_data,
            case_id_str,
        )
        
        logger.info("Case details retrieved successfully, file downloads and DB update scheduled in background")
        return GetCaseDetailsResponse(**response_data)

    except Exception as e:
        logger.exception(f"An error occurred in get_case_details: {str(e)}")
        return {"error": str(e), "case_number": f"{case_type}-{case_number}-{year}"}
    finally:
        if session:
            session.close()
            logger.debug("Requests session closed.")

# New combined background task function to handle downloads and DB update
def _download_task_wrapper(initial_cookies, download_url, save_dir, file_prefix, item_index, item_type, max_retries=3):
    """
    Creates a session, downloads a file, and returns results for thread pool.
    """
    # Create a NEW session for this thread
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36' # Or get from main thread if needed
    })
    # Restore cookies for this specific session
    for key, value in initial_cookies.items():
        session.cookies.set(key, value)

    logger.info(f"Thread started for: {file_prefix} (Index: {item_index}, Type: {item_type})")
    downloaded_path = None
    try:
        downloaded_path = download_file_with_captcha(
            session,
            download_url,
            save_dir,
            file_prefix,
            max_retries
        )
        logger.info(f"Thread finished for {file_prefix}. Result: {'Success' if downloaded_path else 'Failed'}")
        # Return necessary info to map back to the original data structure
        return {
            'type': item_type,
            'index': item_index,
            'file_path': downloaded_path,
            'success': downloaded_path is not None
        }
    except Exception as e:
        logger.exception(f"Error within thread executing download for {file_prefix}: {e}")
        return {
            'type': item_type,
            'index': item_index,
            'file_path': None,
            'success': False,
            'error': str(e)
        }
    finally:
        session.close() # Close the session specific to this thread


# --- Modified background task function ---
def download_files_and_update_db(cookies, response_data, case_id_str):
    """
    Background task to download files in parallel and then update the database.
    """
    download_results = [] # Store results from threads
    tasks_to_submit = []
    max_concurrent_downloads = 1 # Limit concurrent downloads to avoid overwhelming the server/network

    try:
        logger.info(f"Starting parallel background file downloads for case: {case_id_str}")
        case_download_dir = os.path.join(DOWNLOAD_DIR, case_id_str)
        os.makedirs(case_download_dir, exist_ok=True) # Ensure dir exists before tasks run

        # --- 1. Prepare download tasks ---
        if 'related_cases' in response_data:
            for i, r_case in enumerate(response_data['related_cases']):
                link_to_download = r_case.get('view_order_link')
                if link_to_download:
                    related_case_num_safe = re.sub(r'[\\/*?:"<>|]', "_", r_case.get('case_number', f'related_{i+1}'))
                    file_prefix = f"{case_id_str}_related_{related_case_num_safe}"
                    tasks_to_submit.append({
                        'url': link_to_download,
                        'prefix': file_prefix,
                        'index': i,
                        'type': 'related_cases'
                    })
                    logger.info(f"Prepared download task for related case: {related_case_num_safe}")

        if 'judgment_details' in response_data:
             for i, j_detail in enumerate(response_data['judgment_details']):
                link_to_download = j_detail.get('order_link')
                if link_to_download:
                    order_date_safe = re.sub(r'[\\/*?:"<>|]', "_", j_detail.get('order_date', f'order_{i+1}'))
                    file_prefix = f"{case_id_str}_order_{order_date_safe}"
                    tasks_to_submit.append({
                        'url': link_to_download,
                        'prefix': file_prefix,
                        'index': i,
                        'type': 'judgment_details'
                    })
                    logger.info(f"Prepared download task for judgment/order: {order_date_safe}")

        if not tasks_to_submit:
             logger.info(f"No files found to download for case: {case_id_str}")
             # Still proceed to DB update logic if needed, maybe with empty download info
        else:
            logger.info(f"Submitting {len(tasks_to_submit)} download tasks to thread pool (max_workers={max_concurrent_downloads})...")
            # --- 2. Execute tasks in parallel ---
            with ThreadPoolExecutor(max_workers=max_concurrent_downloads) as executor:
                # Submit tasks using the wrapper function
                future_to_task = {
                    executor.submit(
                        _download_task_wrapper,
                        cookies, # Pass the initial cookies
                        task['url'],
                        case_download_dir,
                        task['prefix'],
                        task['index'],
                        task['type'],
                        max_retries=3 # Pass max_retries if needed
                    ): task
                    for task in tasks_to_submit
                }

                # Process results as they complete
                for future in as_completed(future_to_task):
                    task_info = future_to_task[future]
                    try:
                        result = future.result() # Get the dictionary returned by the wrapper
                        download_results.append(result)
                        logger.info(f"Completed task for {task_info['prefix']}: Success={result['success']}")
                    except Exception as exc:
                        logger.error(f"Task {task_info['prefix']} generated an exception: {exc}")
                        # Record failure
                        download_results.append({
                            'type': task_info['type'],
                            'index': task_info['index'],
                            'file_path': None,
                            'success': False,
                            'error': str(exc)
                        })

            logger.info(f"All {len(tasks_to_submit)} download tasks finished processing.")

        # --- 3. Update response_data with results ---
        downloaded_files_summary = {
            'related_cases': [],
            'judgment_details': []
        }

        for result in download_results:
            if result['success']:
                 item_type = result['type']
                 idx = result['index']
                 file_path = result['file_path']

                 if item_type == 'related_cases':
                     if idx < len(response_data.get('related_cases', [])):
                         response_data['related_cases'][idx]['downloaded_file_path'] = file_path
                         downloaded_files_summary['related_cases'].append({
                             'index': idx,
                             'case_number': response_data['related_cases'][idx].get('case_number', ''),
                             'file_path': file_path
                         })
                 elif item_type == 'judgment_details':
                     if idx < len(response_data.get('judgment_details', [])):
                         response_data['judgment_details'][idx]['downloaded_file_path'] = file_path
                         downloaded_files_summary['judgment_details'].append({
                             'index': idx,
                              'order_date': response_data['judgment_details'][idx].get('order_date', ''),
                              'file_path': file_path
                          })

        # Add a summary of downloaded files
        response_data['downloaded_files_summary'] = {
            'related_cases_count': len(downloaded_files_summary['related_cases']),
            'judgment_details_count': len(downloaded_files_summary['judgment_details']),
            'total_files_attempted': len(tasks_to_submit),
            'total_files_succeeded': len(downloaded_files_summary['related_cases']) + len(downloaded_files_summary['judgment_details'])
        }

        logger.info(f"Background file processing complete for case {case_id_str}. "
                    f"Attempted: {response_data['downloaded_files_summary']['total_files_attempted']}, "
                    f"Succeeded: {response_data['downloaded_files_summary']['total_files_succeeded']}")

        # --- 4. Update the database ---
        logger.info(f"Preparing to update database for case {case_id_str}")

        # Use the synchronous motor API pattern (new loop) as in the original code
        # Create a new event loop for this background task's async DB operation
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Create a new client within this loop context
        client = None # Define client outside try block
        try:
            import motor.motor_asyncio

            client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017", io_loop=loop)
            bg_db = client["case_db"]
            collection = bg_db[case_id_str] # Assuming collection name is case_id_str

            async def update_db_async():
                # Ensure response_data has an identifier if upserting
                if "case_number" not in response_data:
                     response_data["case_number"] = case_id_str # Add if missing

                # Use update_one with upsert=True
                # Filter by a unique identifier, e.g., case_number
                result = await collection.update_one(
                    {"case_number": case_id_str},
                    {"$set": response_data},
                    upsert=True
                )
                logger.info(f"Database update result for case {case_id_str}: "
                            f"Matched: {result.matched_count}, Modified: {result.modified_count}, UpsertedId: {result.upserted_id}")
                return result

            # Run the async function in the new loop
            loop.run_until_complete(update_db_async())
            logger.info(f"Database update process finished for case {case_id_str}")

        except Exception as db_exc:
             logger.exception(f"Error during database update for case {case_id_str}: {db_exc}")
        finally:
            if client:
                client.close()
                logger.debug(f"Motor client closed for case {case_id_str}.")
            loop.close()
            logger.debug(f"Async event loop closed for case {case_id_str}.")

    except Exception as e:
        # Catch errors in the main task setup/processing phase
        logger.exception(f"Error in overall background download/DB task for case {case_id_str}: {str(e)}")

    finally:
        # No session object is created at this top level anymore
        logger.info(f"Background task function finished for case: {case_id_str}")



async def get_case_file(request, get_file_request: GetCaseFileRequest):
    db = request.state.case_db
    collection = db[get_file_request.case_number]
    existing_case = await collection.find_one({"case_number": get_file_request.case_number})
    if not existing_case:
        logger.error(f"Case {get_file_request.case_number} not found in database.")
        return {"error": "Case not found in database."}
    
    if get_file_request.table_name == "related_cases":
        table = existing_case[get_file_request.table_name]

        for case in table:
            if case['case_number'] == get_file_request.row_value:
                file_path = case.get('downloaded_file_path')
                if file_path and os.path.exists(file_path):
                    return FileResponse(file_path)
                else:
                    return {"error": "File not found."}
    elif get_file_request.table_name == "judgment_details":
        table = existing_case[get_file_request.table_name]

        for case in table:
            if case['order_date'] == get_file_request.row_value:
                file_path = case.get('downloaded_file_path')
                if file_path and os.path.exists(file_path):
                    return FileResponse(file_path)
                else:
                    return {"error": "File not found."}

