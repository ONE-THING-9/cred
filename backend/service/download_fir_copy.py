import requests
from bs4 import BeautifulSoup
import re
import urllib.parse
import os
import time
import json # Although not strictly used in the final regex, good to have if needed later

# --- Configuration ---
# Search parameters (customize as needed)
import requests
from bs4 import BeautifulSoup
import re # Import regular expressions for more robust parsing if needed

# Setup basic logging
from logger import logger

# --- Constants ---
BASE_URL = "https://haryanapolice.gov.in/ViewFIR/FIRStatusSearch"
# The 'From' parameter seems necessary, keep it as observed
PARAMS = {'From': 'LFhlihlx/W49VSlBvdGc4w=='}

HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Accept-Language': 'en-US,en;q=0.9',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
    'Host': 'haryanapolice.gov.in',
    'Origin': 'https://haryanapolice.gov.in',
    'Referer': f"{BASE_URL}?From=LFhlihlx/W49VSlBvdGc4w==", # Referer is important for POST
    'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"', # Example, update if needed
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36' # Example, update if needed
}

# Use a session object to handle cookies automatically
session = requests.Session()
session.headers.update(HEADERS)

# --- Helper Functions ---

def get_initial_page_data():
    """Fetches the initial page and extracts districts and hidden form fields."""
    logger.info(f"Fetching initial page: {BASE_URL}")
    try:
        response = session.get(BASE_URL, params=PARAMS, timeout=20)
        response.raise_for_status()  # Raise an exception for bad status codes
        logger.info("Initial page fetched successfully.")

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract hidden fields needed for POST
        form_data = {}
        hidden_tags = soup.select('input[type="hidden"]')
        for tag in hidden_tags:
            if tag.get('name'):
                form_data[tag['name']] = tag.get('value', '')
        logger.debug(f"Extracted hidden fields: {list(form_data.keys())}")

        # Extract other input/select fields to build the base payload
        input_tags = soup.select('input:not([type="hidden"]):not([type="submit"]):not([type="image"])')
        for tag in input_tags:
             if tag.get('name'):
                form_data[tag['name']] = tag.get('value', '')

        select_tags = soup.select('select')
        for tag in select_tags:
             if tag.get('name'):
                 selected_option = tag.find('option', selected=True)
                 form_data[tag['name']] = selected_option['value'] if selected_option else tag.find('option')['value'] # Default to first option if none selected

        logger.debug(f"Extracted initial form fields (sample): { {k: v for i, (k, v) in enumerate(form_data.items()) if i < 5} }...") # Log only a sample

        # Extract districts
        district_dropdown = soup.find('select', {'id': 'ContentPlaceHolder1_ddlDistrict'})
        districts = {}
        if district_dropdown:
            options = district_dropdown.find_all('option')
            for option in options:
                value = option.get('value')
                text = option.text.strip()
                if value:  # Ignore the "Select" option with empty value
                    districts[text] = value
            logger.info(f"Found {len(districts)} districts.")
        else:
            logger.error("District dropdown not found!")
            return None, None

        return districts, form_data

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching initial page: {e}")
        return None, None
    except Exception as e:
        logger.error(f"Error parsing initial page: {e}")
        return None, None

def get_police_stations(district_code, initial_form_data):
    """Performs the POST request to get police stations for a selected district."""
    if not district_code or not initial_form_data:
        logger.error("Missing district code or initial form data for POST request.")
        return None

    post_data = initial_form_data.copy() # Start with base form data

    # --- Crucial ASP.NET fields for triggering the update ---
    post_data['__EVENTTARGET'] = 'ctl00$ContentPlaceHolder1$ddlDistrict' # The control that caused the postback
    post_data['__EVENTARGUMENT'] = '' # Usually empty for dropdown changes
    # --- Update the selected district value ---
    post_data['ctl00$ContentPlaceHolder1$ddlDistrict'] = district_code
    # --- Ensure the police station is reset to 'Select' as it would be in the browser ---
    # Find the actual 'Select' value if possible, otherwise guess common values
    post_data['ctl00$ContentPlaceHolder1$ddlPoliceStation'] = initial_form_data.get('ctl00$ContentPlaceHolder1$ddlPoliceStation', 'Select') # Use initial or default


    # Remove potential problematic button values if they exist in initial scrape
    post_data.pop('ctl00$ContentPlaceHolder1$btnStatusSearch', None)
    post_data.pop('ctl00$ContentPlaceHolder1$btnMainClose', None)
    post_data.pop('ctl00$ContentPlaceHolder1$btnClearAll', None)
    post_data.pop('ctl00$btnDefaultButton', None)


    logger.info(f"Performing POST request for district code: {district_code}")
    logger.debug(f"POST Data (sample): __EVENTTARGET={post_data.get('__EVENTTARGET')}, district={post_data.get('ctl00$ContentPlaceHolder1$ddlDistrict')}, viewstate_len={len(post_data.get('__VIEWSTATE', ''))}")

    try:
        response = session.post(BASE_URL, params=PARAMS, data=post_data, timeout=30)
        response.raise_for_status()
        logger.info("POST request successful.")

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract police stations from the *updated* dropdown in the response
        ps_dropdown = soup.find('select', {'id': 'ContentPlaceHolder1_ddlPoliceStation'})
        police_stations = {}
        if ps_dropdown:
            options = ps_dropdown.find_all('option')
            for option in options:
                value = option.get('value')
                # Use title attribute if available (often cleaner), fallback to text
                text = option.get('title', option.text).strip()
                if value: # Ignore the "Select" option
                    police_stations[text] = value
            logger.info(f"Found {len(police_stations)} police stations for district {district_code}.")
        else:
            logger.warning(f"Police Station dropdown not found in POST response for district {district_code}. Check response HTML.")
            # logger.debug(f"Response HTML snippet:\n{response.text[:2000]}") # Log start of HTML for debugging
            return None

        return police_stations

    except requests.exceptions.RequestException as e:
        logger.error(f"Error during POST request: {e}")
        # Log response details if available
        if hasattr(e, 'response') and e.response is not None:
             logger.error(f"Response status: {e.response.status_code}")
             # logger.error(f"Response content: {e.response.text[:500]}") # Be careful logging large responses
        return None
    except Exception as e:
        logger.error(f"Error parsing POST response: {e}")
        return None


# --- Main Function ---

# Cache initial data to avoid refetching districts and form state on every call
DISTRICTS_CACHE = None
INITIAL_FORM_DATA_CACHE = None
POLICE_STATION_CACHE = {} # Cache police stations per district code: {district_code: {ps_name: ps_code}}

def get_codes(district_name, police_station_name):
    """
    Gets the codes for a given district and police station name.

    Args:
        district_name (str): The exact name of the district (e.g., "AMBALA").
        police_station_name (str): The exact name of the police station (e.g., "AMBALA CANTT").

    Returns:
        tuple: (district_code, police_station_code) or (None, None) if not found.
    """
    global DISTRICTS_CACHE, INITIAL_FORM_DATA_CACHE, POLICE_STATION_CACHE

    district_name_upper = district_name.upper()
    # Handle variations in PS naming (e.g., extra spaces, case)
    # Normalize the input police station name
    police_station_name_normalized = ' '.join(police_station_name.strip().upper().split())


    # 1. Get initial data if not cached
    if DISTRICTS_CACHE is None or INITIAL_FORM_DATA_CACHE is None:
        logger.info("Fetching initial page data (not cached)...")
        districts, form_data = get_initial_page_data()
        if districts is None or form_data is None:
            return None, None
        DISTRICTS_CACHE = {k.upper(): v for k, v in districts.items()} # Store keys in upper case
        INITIAL_FORM_DATA_CACHE = form_data
    else:
        logger.info("Using cached initial page data.")

    # 2. Find District Code
    district_code = DISTRICTS_CACHE.get(district_name_upper)
    if not district_code:
        logger.error(f"District '{district_name}' not found in cache. Available: {list(DISTRICTS_CACHE.keys())}")
        return None, None
    logger.info(f"Found District Code for '{district_name}': {district_code}")

    # 3. Get Police Stations for the district (use cache if available)
    if district_code not in POLICE_STATION_CACHE:
        logger.info(f"Fetching police stations for district {district_code} (not cached)...")
        police_stations = get_police_stations(district_code, INITIAL_FORM_DATA_CACHE)
        if police_stations is None:
             logger.error(f"Failed to retrieve police stations for district code {district_code}")
             return district_code, None # Return district code even if PS fails
        # Normalize keys in the cache
        POLICE_STATION_CACHE[district_code] = {' '.join(k.strip().upper().split()): v for k, v in police_stations.items()}
    else:
        logger.info(f"Using cached police stations for district {district_code}.")

    # 4. Find Police Station Code
    # Normalize the keys from the cache for comparison
    cached_ps_normalized_keys = POLICE_STATION_CACHE.get(district_code, {})

    police_station_code = cached_ps_normalized_keys.get(police_station_name_normalized)

    if not police_station_code:
        logger.error(f"Police Station '{police_station_name}' (normalized: '{police_station_name_normalized}') not found for district '{district_name}'.")
        logger.warning(f"Available police stations for district {district_code}: {list(cached_ps_normalized_keys.keys())}")
        return district_code, None

    logger.info(f"Found Police Station Code for '{police_station_name}': {police_station_code}")
    return district_code, police_station_code



# --- Helper Functions ---

def parse_ajax_response(response_text):
    """
    Parses the ASP.NET AJAX pipe-delimited response using regex.
    Focuses on extracting VIEWSTATE and specific updatePanel content.
    """
    logger.debug("Parsing AJAX response...")
    updates = {}
    # Regex for __VIEWSTATE
    match_vs = re.search(r"\|hiddenField\|__VIEWSTATE\|([^|]+)\|", response_text)
    if match_vs:
        updates['__VIEWSTATE'] = match_vs.group(1)
        logger.debug(f"Extracted __VIEWSTATE (length: {len(updates['__VIEWSTATE'])})")
    else:
        logger.warning("Could not extract __VIEWSTATE from AJAX response.")

    # Regex for __VIEWSTATEGENERATOR (optional but good to have)
    match_vsg = re.search(r"\|hiddenField\|__VIEWSTATEGENERATOR\|([^|]+)\|", response_text)
    if match_vsg:
        updates['__VIEWSTATEGENERATOR'] = match_vsg.group(1)
        logger.debug("Extracted __VIEWSTATEGENERATOR")
    else:
        logger.debug("NOTE: __VIEWSTATEGENERATOR not found in AJAX response.")


    # Regex for __PREVIOUSPAGE (optional)
    match_pp = re.search(r"\|hiddenField\|__PREVIOUSPAGE\|([^|]+)\|", response_text)
    if match_pp:
         updates['__PREVIOUSPAGE'] = match_pp.group(1)
         logger.debug("Extracted __PREVIOUSPAGE")
    else:
         logger.debug("NOTE: __PREVIOUSPAGE not found in AJAX response.")


    # Regex for the specific update panel content (results table)
    # Looks for |updatePanel|ID|content... until the next pipe-length prefix
    # Using [\s\S]*? for non-greedy matching of any character including newlines
    match_panel = re.search(r"\|updatePanel\|ContentPlaceHolder1_updStatusSearch\|([\s\S]*?)(?=\|\d+\|)", response_text)
    if match_panel:
         panel_content = match_panel.group(1)
         # The content often starts with length|type|id| for nested elements, remove if present
         # Let's assume the actual HTML starts after the ID for simplicity here.
         # We might need more robust parsing if structure varies.
         # Crude check: if content starts like 'length|type|id|', skip it
         if re.match(r"^\d+\|[^|]+\|[^|]+\|", panel_content):
             logger.debug("Skipping potential prefix in UpdatePanel content.")
             # This part is heuristic, might need adjustment
         updates['ContentPlaceHolder1_updStatusSearch'] = panel_content
         logger.debug(f"Extracted UpdatePanel 'ContentPlaceHolder1_updStatusSearch' content (length: {len(panel_content)})")
    else:
        logger.warning("Could not extract 'ContentPlaceHolder1_updStatusSearch' content from AJAX response.")

    if not updates:
         logger.error("No relevant data extracted from AJAX response.")

    return updates


def extract_export_url_base(html_content):
    """
    Extracts the ExportUrlBase from the ReportViewer initialization script
    using regular expressions.
    """
    logger.debug("Searching for ReportViewer initialization script...")
    # Regex to find the $create call for _InternalReportViewer and capture its options object
    # Making it more general to find the options block
    match = re.search(
        r'\$create\(\s*Microsoft\.Reporting\.WebFormsClient\._InternalReportViewer\s*,\s*({.*?})\s*,\s*null,\s*null',
        html_content,
        re.DOTALL | re.IGNORECASE
    )
    if not match:
        logger.error("Could not find ReportViewer initialization script marker.")
        return None

    options_str = match.group(1)
    logger.debug(f"Found potential options object string (length: {len(options_str)}).")

    # --- Safer Regex directly targeting ExportUrlBase within the options string ---
    export_match = re.search(r'"ExportUrlBase"\s*:\s*"([^"]+)"', options_str, re.IGNORECASE)
    if export_match:
        export_url_base_relative = export_match.group(1)
        # Decode any potential unicode escape sequences like \u0026 for &
        try:
            export_url_base_relative = export_url_base_relative.encode('latin-1', 'backslashreplace').decode('unicode-escape')
            logger.debug(f"Successfully extracted and decoded ExportUrlBase: {export_url_base_relative}")
            return export_url_base_relative
        except Exception as decode_err:
            logger.error(f"Could not decode ExportUrlBase string: {decode_err}")
            logger.error(f"Raw ExportUrlBase string: {export_match.group(1)}")
            return None # Return None if decoding fails
    else:
        logger.error("Could not extract ExportUrlBase key/value from the options object using regex.")
        logger.debug(f"Options String Snippet: {options_str[:600]}...") # Log snippet for debugging
        return None


# --- Main Script ---
def get_user_fir(fir_year, district, police_station, fir_number):
    """
    Searches for and downloads a FIR PDF based on the provided parameters.
    
    Args:
        fir_year (str): The year of the FIR
        district (str): The district name
        police_station (str): The police station name
        fir_number (str): The FIR number
        
    Returns:
        str: Path to the downloaded PDF file on success
        None: If the download fails for any reason
    """
    logger.info(f"Starting FIR search and download for FIR #{fir_number} ({fir_year}) at {police_station}, {district}")
    
    try:
        district_code, police_station_code = get_codes(district, police_station)
        if not district_code:
            logger.error(f"Could not find district code for '{district}'")
            return None
        if not police_station_code:
            logger.error(f"Could not find police station code for '{police_station}' in district '{district}'")
            return None
            
        logger.info(f"Using district code: {district_code}, police station code: {police_station_code}")

        # Target URLs
        base_url = "https://haryanapolice.gov.in"
        search_page_relative = "/ViewFIR/FIRStatusSearch"
        from_param_value = "LFhlihlx/W49VSlBvdGc4w=="
        search_url_with_param = f"{base_url}{search_page_relative}?From={urllib.parse.quote_plus(from_param_value)}"

        # Download directory
        pdf_download_dir = "fir_pdfs"

        # Request Headers (Base set, will be modified per request type)
        base_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Origin': base_url,
            'Sec-Ch-Ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Site': 'same-origin',
        }
        
        # Create download directory if it doesn't exist
        if not os.path.exists(pdf_download_dir):
            try:
                os.makedirs(pdf_download_dir)
                logger.info(f"Created download directory: {pdf_download_dir}")
            except OSError as e:
                logger.error(f"Could not create directory '{pdf_download_dir}': {e}")
                return None

        # Use a session object to automatically handle cookies
        session = requests.Session()
        session.headers.update(base_headers) # Set default headers for the session

        # 1. Initial GET request to get cookies and dynamic form fields
        logger.info(f"Sending GET request to: {search_url_with_param}")
        get_headers = session.headers.copy()
        get_headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Referer': base_url # Initial referer might just be the base
        })
        get_response = session.get(search_url_with_param, headers=get_headers, timeout=30)
        get_response.raise_for_status()  # Raise exception for bad status codes
        logger.info(f"GET request successful (Status: {get_response.status_code})")
        logger.debug(f"Initial Cookies received: {session.cookies.get_dict()}")

        # Parse the initial HTML to find dynamic fields
        soup_initial = BeautifulSoup(get_response.text, 'html.parser')
        viewstate_input = soup_initial.find('input', {'name': '__VIEWSTATE'})
        vsg_input = soup_initial.find('input', {'name': '__VIEWSTATEGENERATOR'})
        pp_input = soup_initial.find('input', {'name': '__PREVIOUSPAGE'})

        if not viewstate_input:
            logger.error("Could not find __VIEWSTATE in initial page HTML. Aborting.")
            return None
            
        initial_viewstate = viewstate_input['value']
        initial_vsg = vsg_input['value'] if vsg_input else ''
        initial_pp = pp_input['value'] if pp_input else ''

        logger.debug(f"Initial __VIEWSTATE (length): {len(initial_viewstate)}")
        logger.debug(f"Initial __VIEWSTATEGENERATOR: {initial_vsg}")
        logger.debug(f"Initial __PREVIOUSPAGE: {initial_pp}")

        # 2. POST 1: Simulate District Selection (AJAX)
        logger.info(f"Sending POST 1: Simulate District Selection ({district_code})")
        payload_district = {
            '__EVENTTARGET': 'ctl00$ContentPlaceHolder1$ddlDistrict',
            '__EVENTARGUMENT': '',
            '__LASTFOCUS': '',
            '__VIEWSTATE': initial_viewstate,
            '__VIEWSTATEGENERATOR': initial_vsg,
            '__PREVIOUSPAGE': initial_pp,
            # --- Include current form values known so far ---
            'ctl00$ContentPlaceHolder1$ddFIRYear': fir_year,
            'ctl00$ContentPlaceHolder1$ddlDistrict': district_code, # The selected district
            'ctl00$ContentPlaceHolder1$txtRegistrationNumber': '', # Not entered yet
            'ctl00$ContentPlaceHolder1$ddlPoliceStation': '', # Key: This should be empty or default before update
            'ctl00$ContentPlaceHolder1$txtStatusSearchFromDate': '',
            'ctl00$ContentPlaceHolder1$meeStatusSearchFromDate_ClientState': '',
            'ctl00$ContentPlaceHolder1$txtStatusSearchToDate': '',
            'ctl00$ContentPlaceHolder1$meeStatusSearchToDate_ClientState': '',
            # --- ASP.NET AJAX Specific ---
            'ctl00$ScriptManager1': f'ctl00$ContentPlaceHolder1$updStatusSearch|ctl00$ContentPlaceHolder1$ddlDistrict',
            '__ASYNCPOST': 'true',
        }
        ajax_headers = session.headers.copy()
        ajax_headers.update({
            'Accept': '*/*',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Referer': search_url_with_param # Referer is the page where the action occurs
        })
        # Remove Sec-Fetch-User and Upgrade-Insecure-Requests for AJAX
        ajax_headers.pop('Sec-Fetch-User', None)
        ajax_headers.pop('Upgrade-Insecure-Requests', None)

        post1_response = session.post(search_url_with_param, data=payload_district, headers=ajax_headers, timeout=30)
        post1_response.raise_for_status()
        logger.info(f"POST 1 (District Select) successful (Status: {post1_response.status_code})")

        # 3. Parse AJAX Response from POST 1 to get updated state
        logger.info("Parsing AJAX response from POST 1...")
        ajax_updates_1 = parse_ajax_response(post1_response.text)
        updated_viewstate = ajax_updates_1.get('__VIEWSTATE')
        if not updated_viewstate:
            logger.error("Failed to extract updated __VIEWSTATE after district selection. Aborting.")
            return None
            
        # Use updated values if found, otherwise keep initial ones (especially for VSG/PP)
        updated_vsg = ajax_updates_1.get('__VIEWSTATEGENERATOR', initial_vsg)
        updated_pp = ajax_updates_1.get('__PREVIOUSPAGE', initial_pp)
        logger.info("State updated for next request.")

        # 4. POST 2: Simulate Search Button Click (AJAX)
        logger.info(f"Sending POST 2: Simulate Search Click (FIR: {fir_number}, PS: {police_station_code})")
        payload_search = {
            '__EVENTTARGET': 'ctl00$ContentPlaceHolder1$btnStatusSearch',
            '__EVENTARGUMENT': '',
            '__LASTFOCUS': '',
            # --- Use Updated State Variables ---
            '__VIEWSTATE': updated_viewstate,
            '__VIEWSTATEGENERATOR': updated_vsg,
            '__PREVIOUSPAGE': updated_pp,
            # --- Include ALL final form values ---
            'ctl00$ContentPlaceHolder1$ddFIRYear': fir_year,
            'ctl00$ContentPlaceHolder1$ddlDistrict': district_code,
            'ctl00$ContentPlaceHolder1$txtRegistrationNumber': fir_number,
            'ctl00$ContentPlaceHolder1$ddlPoliceStation': police_station_code, # Include selected police station
            'ctl00$ContentPlaceHolder1$txtStatusSearchFromDate': '',
            'ctl00$ContentPlaceHolder1$meeStatusSearchFromDate_ClientState': '',
            'ctl00$ContentPlaceHolder1$txtStatusSearchToDate': '',
            'ctl00$ContentPlaceHolder1$meeStatusSearchToDate_ClientState': '',
            # --- ASP.NET AJAX Specific ---
            'ctl00$ScriptManager1': f'ctl00$ContentPlaceHolder1$updStatusSearch|ctl00$ContentPlaceHolder1$btnStatusSearch',
            '__ASYNCPOST': 'true',
            # Add the button value itself, like a browser form submission
            'ctl00$ContentPlaceHolder1$btnStatusSearch': 'Search',
        }
        # Headers remain the same as the previous AJAX request
        post2_response = session.post(search_url_with_param, data=payload_search, headers=ajax_headers, timeout=40) # Slightly longer timeout
        post2_response.raise_for_status()
        logger.info(f"POST 2 (Search) successful (Status: {post2_response.status_code})")

        # 5. Process the FINAL Search response
        logger.info("Processing final search response...")
        ajax_updates_2 = parse_ajax_response(post2_response.text)
        results_html = ajax_updates_2.get('ContentPlaceHolder1_updStatusSearch')

        if results_html:
            logger.info("Extracted Search Results HTML Fragment.")
            results_soup = BeautifulSoup(results_html, 'html.parser')
            results_table = results_soup.find('table', id='tblDisplayRecords')

            if results_table:
                logger.info("Found results table (tblDisplayRecords). Processing rows...")
                rows = results_table.find_all('tr')
                data_rows_found = 0
                if len(rows) <= 1: # Only header row or empty message
                     no_record_msg = results_table.find('td')
                     if no_record_msg:
                         logger.warning(f"Message from table: {no_record_msg.text.strip()}")
                     else:
                         logger.warning("No data rows found in the table.")
                     return None

                for i, row in enumerate(rows[1:]): # Skip header row
                    cols = row.find_all('td')
                    if len(cols) >= 5:
                        data_rows_found += 1
                        s_no = cols[0].text.strip()
                        fir_no_display = cols[1].text.strip() # Use for display/logging
                        fir_no_for_file = fir_number # Use original input for filename consistency
                        fir_date_display = cols[2].text.strip()
                        fir_date_for_file = fir_date_display.replace('/', '-') # Sanitize for filename
                        chargesheet_date = cols[3].text.strip()
                        view_link_tag = cols[4].find('a')
                        view_action = view_link_tag['onclick'] if view_link_tag and view_link_tag.get('onclick') else None

                        logger.info(f"Processing Result {i+1}: S.No: {s_no}, FIR No: {fir_no_display}, FIR Date: {fir_date_display}")

                        # --- Fetch FIR Detail Page ---
                        if view_action:
                            match = re.search(r"f_open_window_max\('([^']+)'", view_action)
                            if match:
                                detail_url_relative = match.group(1)
                                base_url_for_relative = post2_response.url # URL of the search page context
                                detail_url_absolute = urllib.parse.urljoin(base_url_for_relative, detail_url_relative)
                                logger.info(f"Requesting Detail Page URL: {detail_url_absolute}")

                                try:
                                    # Update headers for HTML page request
                                    detail_headers = session.headers.copy()
                                    detail_headers.update({
                                        'Referer': base_url_for_relative,
                                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                                        'Sec-Fetch-Dest': 'document',
                                        'Sec-Fetch-Mode': 'navigate',
                                        'Upgrade-Insecure-Requests': '1'
                                    })
                                    detail_headers.pop('X-Requested-With', None)
                                    detail_headers.pop('Content-Type', None) # GET request has no body content-type

                                    detail_response = session.get(detail_url_absolute, headers=detail_headers, timeout=30)
                                    detail_response.raise_for_status()
                                    logger.info(f"Detail Page GET successful (Status: {detail_response.status_code}).")

                                    # --- Attempt to Extract and Download PDF ---
                                    logger.info(f"Attempting PDF Extraction/Download...")
                                    export_url_base_relative = extract_export_url_base(detail_response.text)

                                    if export_url_base_relative:
                                        # Construct the final PDF export URL
                                        pdf_export_url_relative = export_url_base_relative + "PDF"
                                        pdf_export_url_absolute = urllib.parse.urljoin(detail_response.url, pdf_export_url_relative)
                                        logger.info(f"Constructed PDF Export URL: {pdf_export_url_absolute}")

                                        try:
                                            # Update headers for PDF request
                                            pdf_headers = session.headers.copy()
                                            pdf_headers.update({
                                                'Referer': detail_response.url, # Referer is the detail page itself
                                                'Accept': 'application/pdf,application/octet-stream,*/*;q=0.8', # Prioritize PDF
                                                'Sec-Fetch-Dest': 'empty', # Or 'document' might also work
                                                'Sec-Fetch-Mode': 'navigate', # Browser often navigates to download
                                            })
                                            pdf_headers.pop('X-Requested-With', None)
                                            pdf_headers.pop('Content-Type', None)
                                            pdf_headers.pop('Upgrade-Insecure-Requests', None)

                                            logger.info("Sending GET request for PDF...")
                                            pdf_response = session.get(pdf_export_url_absolute, headers=pdf_headers, timeout=90, stream=True) # Longer timeout for download, stream=True
                                            pdf_response.raise_for_status()
                                            logger.info(f"PDF GET successful (Status: {pdf_response.status_code}).")

                                            # Check content type
                                            content_type = pdf_response.headers.get('Content-Type', '').lower()
                                            logger.info(f"Response Content-Type: {content_type}")

                                            if 'application/pdf' in content_type:
                                                # Construct filename
                                                pdf_filename = None
                                                content_disposition = pdf_response.headers.get('Content-Disposition')
                                                if content_disposition:
                                                    fname_match = re.search(r'filename\*?=(?:"([^"]+)"|([^;]+))', content_disposition, re.IGNORECASE)
                                                    if fname_match:
                                                        # Use the first non-None group (handles quoted and unquoted)
                                                        raw_filename = fname_match.group(1) or fname_match.group(2)
                                                        if raw_filename:
                                                            pdf_filename = urllib.parse.unquote(raw_filename.strip())
                                                            logger.info(f"Filename from header: {pdf_filename}")

                                                if not pdf_filename:
                                                    pdf_filename = f"FIR_{fir_year}_{district_code}_{fir_no_for_file}_{fir_date_for_file}.pdf"
                                                    logger.info(f"Using default filename: {pdf_filename}")

                                                # Sanitize filename slightly
                                                pdf_filename = pdf_filename.replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '').replace('*', '')
                                                full_pdf_path = os.path.join(pdf_download_dir, pdf_filename)

                                                # Save the PDF content
                                                logger.info(f"Saving PDF to: {full_pdf_path}")
                                                try:
                                                    with open(full_pdf_path, 'wb') as f:
                                                        file_size = 0
                                                        for chunk in pdf_response.iter_content(chunk_size=8192):
                                                            f.write(chunk)
                                                            file_size += len(chunk)
                                                    logger.info(f"Successfully saved PDF ({file_size / 1024:.2f} KB).")
                                                    return full_pdf_path
                                                except IOError as save_err:
                                                    logger.error(f"ERROR saving PDF file: {save_err}")
                                                    return None

                                            else:
                                                logger.error(f"Response Content-Type is not PDF. Skipping download.")
                                                logger.debug(f"Response text (first 200 chars): {pdf_response.text[:200]}...")
                                                return None

                                        except requests.exceptions.RequestException as pdf_err:
                                            logger.error(f"Error during PDF download request: {pdf_err}")
                                            if pdf_err.response is not None:
                                                 logger.error(f"PDF Response Status: {pdf_err.response.status_code}")
                                                 logger.debug(f"PDF Response Text: {pdf_err.response.text[:200]}...")
                                            return None
                                        except Exception as general_pdf_err:
                                             logger.error(f"Unexpected error saving/processing PDF: {general_pdf_err}")
                                             return None

                                    else:
                                         logger.error("Could not extract ExportUrlBase to download PDF.")
                                         return None

                                except requests.exceptions.RequestException as detail_err:
                                    logger.error(f"Error fetching FIR detail page: {detail_err}")
                                    if detail_err.response is not None:
                                        logger.error(f"Detail Page Response Status: {detail_err.response.status_code}")
                                        logger.debug(f"Detail Page Response Text: {detail_err.response.text[:200]}...")
                                    return None
                                except Exception as general_detail_err:
                                     logger.error(f"Unexpected error processing FIR detail: {general_detail_err}")
                                     return None
                            else:
                                logger.error("Could not extract detail URL from view_action string.")
                                return None
                        else:
                            logger.error("No view action link found for this result.")
                            return None

                    elif len(cols) == 1: # Handle messages like "No records found" spanning the row
                         logger.warning(f"Message from table: {cols[0].text.strip()}")
                # End of processing a row

                if data_rows_found == 0 and len(rows) > 1: # If header existed but no valid data rows matched
                     logger.warning("No valid data rows found in the results table.")
                     return None

            else:
                logger.error("Could not find results table (id='tblDisplayRecords') in the search results HTML fragment.")
                logger.debug(f"Results HTML Fragment Start: {results_html[:500]}")
                # Check for potential error messages within the results_html if table missing
                error_span = results_soup.find('span', id='spanErrorMessage')
                if error_span and error_span.text.strip():
                    logger.error(f"Server Error Message found in UpdatePanel: {error_span.text.strip()}")
                return None

        else:
            logger.error("Failed to extract search results HTML fragment from the final AJAX response.")
            logger.debug(f"Raw Final Response (POST 2): {post2_response.text[:1000]}")
            return None

    # --- Global Error Handling ---
    except requests.exceptions.Timeout as e:
        logger.error(f"Request timed out: {e}")
        return None
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred: {e}")
        if e.response is not None:
            logger.error(f"Response Status: {e.response.status_code}")
            logger.error(f"Response URL: {e.response.url}")
            logger.debug(f"Response Text: {e.response.text[:500]}...")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"An HTTP request error occurred: {e}")
        return None
    except KeyError as e:
        logger.error(f"Failed to find a required element/key (e.g., __VIEWSTATE or attribute): {e}")
        return None
    except AttributeError as e:
         logger.error(f"Tried to access attribute on None (likely parsing failed): {e}")
         return None
    except Exception as e:
        import traceback
        logger.error(f"An unexpected error occurred: {e}")
        logger.error(traceback.format_exc()) # Log full traceback for unexpected errors
        return None
    finally:
        logger.info("FIR search and download process completed")
        
    # If we reach here without returning a path, it means no PDF was found/downloaded
    return None

# --- Run the main function ---