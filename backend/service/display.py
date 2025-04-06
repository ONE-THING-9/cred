import requests
from bs4 import BeautifulSoup

# The base URL (without the query string)
url = "https://www.phhc.gov.in/home.php"

# The query string parameters as a Python dictionary
# 'requests' will automatically format this into '?search_param=display'
params = {
    'search_param': 'display'
}

# Optional: Sometimes websites check headers like User-Agent.
# If the basic request fails or gets blocked, uncomment and potentially modify this.
# headers = {
#     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
#     'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
#     'Accept-Language': 'en-US,en;q=0.9',
#     # Add any other headers if you find they are necessary
# }
async def get_court_display_data(request):
    try:
        # Make the GET request using requests.get()
        # Pass the base URL and the parameters dictionary.
        # If using headers, add the argument: headers=headers
        response = requests.get(url, params=params) # add headers=headers here if needed

        # Check if the request was successful (status code 200)
        response.raise_for_status() # This will raise an HTTPError exception for bad responses (4xx or 5xx)

        print(f"Request successful!")
        print(f"Status Code: {response.status_code}")

        # The original 'content-type' was 'text/html', so access the content using response.text
        print("\nResponse Content (first 500 characters):")
        # print(response.text) # Displaying only the first 500 chars for brevity
        soup = BeautifulSoup(response.text, 'lxml') # Use 'lxml' for parsing

        court_data = {}
        print("55")

        # Find the main container table for the display board
        main_display_table = soup.find('table', id='tables_input1')
        # print(main_display_table)

        if main_display_table:
                # Find all the inner tables that contain the actual court/sr data
                inner_data_tables = main_display_table.select('td > table[border="1"][style*="border-collapse: collapse"]')

                for table in inner_data_tables:
                    # Find all rows within this inner table that have the class 'text_label'
                    # This selector should be specific enough, but we add checks below.
                    rows = table.find_all('tr', class_='text_label')

                    for row in rows:
                        cells = row.find_all('td')

                        # **** ROBUSTNESS CHECK ****
                        # Ensure we have *at least* two 'td' elements before proceeding
                        if len(cells) >= 2:
                            # Now it's safe to access cells[0] and cells[1]

                            # Check if it's a header row (contains 'td_head' class in the first cell)
                            is_header = cells[0].has_attr('class') and 'td_head' in cells[0].get('class', [])

                            # Only process if it's NOT a header row
                            if not is_header:
                                # Extract Court Number (usually inside an <a> tag)
                                court_no = ""
                                court_link = cells[0].find('a')
                                if court_link:
                                    court_no = court_link.get_text(strip=True)
                                else: # Fallback if no <a> tag
                                    court_no = cells[0].get_text(strip=True)

                                # Extract SR Number from the second cell
                                sr_no = cells[1].get_text(strip=True)

                                # Add to dictionary only if both values were successfully extracted
                                if court_no and sr_no:
                                    court_data[court_no] = sr_no
                                # else: # Optional: Debugging for rows that look like data but failed extraction
                                #    print(f"DEBUG: Failed to extract court/sr from row: {row}")

                        # else: # Optional: Debugging for rows that had the class but < 2 cells
                            # print(f"DEBUG: Skipping row with class 'text_label' but < 2 cells: {row}")

        else:
            print("Could not find the table with id='tables_input1'. Parsing failed.")

        print("\nExtracted Court Data:")
        return court_data

        # You can also inspect other parts of the response:
        # print("\nResponse Headers:")
        # print(response.headers)
        # print("\nFull URL Requested:")
        # print(response.url) # See the URL that requests actually built

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text}") # Show beginning of error response if any
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Connection error occurred: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        print(f"Timeout error occurred: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"An unexpected error occurred during the request: {req_err}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")