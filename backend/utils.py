import requests
import os
import psutil
from urllib.parse import urlparse, unquote
from logger import logger
import tempfile
import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from config import PATHS
import shutil

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def get_pdf_link_only(year, district, police_station, fir_number):
    """
    Downloads a PDF file from the Haryana Police website by filling a form and navigating through pages.
    
    Args:
        year (int): The year of the FIR.
        district (str): The district name.
        police_station (str): The police station name.
        fir_number (int): The FIR number.
    
    Returns:
        str: The file path where the PDF is saved, or the expected path if download fails.
    
    Raises:
        Exception: If all retry attempts fail to download the PDF.
    """
    # Convert inputs to strings for consistency
    year = str(year)
    fir_number = str(fir_number)
    url = "https://haryanapolice.gov.in/ViewFIR/FIRStatusSearch?From=LFhlihlx/W49VSlBvdGc4w=="
    download_dir = PATHS["downloads"]
    expected_file_path = os.path.join(download_dir, f"{fir_number}-{year}-{district}-{police_station}.pdf")
    print("---------------", expected_file_path)

    # Ensure download directory exists
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        logger.debug(f"Created download directory: {download_dir}")

    logger.info(f"Starting PDF download: Year={year}, District={district}, Police Station={police_station}, FIR={fir_number}")
    logger.info(f"Expected file path: {expected_file_path}")

    # Set up Chrome options
    chrome_options = webdriver.ChromeOptions()
    # Uncomment the next line for production to run without a visible browser
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Use a temporary user data directory
    temp_user_data_dir = tempfile.mkdtemp()
    chrome_options.add_argument(f"--user-data-dir={temp_user_data_dir}")

    # Configure download preferences
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    }
    chrome_options.add_experimental_option("prefs", prefs)

    max_retries = 3
    driver = None

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries}")
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(60)
            driver.set_script_timeout(60)

            # Step 1: Navigate to the page and fill the form
            logger.debug(f"Navigating to {url}")
            driver.get(url)

            # it will wait until 30 second for selection of this year dropdown and Select Year
            year_select = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_ddFIRYear"))
            )
            Select(year_select).select_by_value(year)
            logger.debug(f"Selected year: {year}")

            # Select District
            district_select = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_ddlDistrict"))
            )
            Select(district_select).select_by_visible_text(district)
            logger.debug(f"Selected district: {district}")

            # Wait for Police Station options and select
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located(
                    (By.XPATH, f"//select[@id='ContentPlaceHolder1_ddlPoliceStation']/option[text()='{police_station}']")
                )
            )
            police_station_select = driver.find_element(By.ID, "ContentPlaceHolder1_ddlPoliceStation")
            Select(police_station_select).select_by_visible_text(police_station)
            logger.debug(f"Selected police station: {police_station}")

            # Enter FIR Number
            fir_input = driver.find_element(By.ID, "ContentPlaceHolder1_txtRegistrationNumber")
            fir_input.send_keys(fir_number)
            logger.debug(f"Entered FIR number: {fir_number}")

            # Click Search Button
            search_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_btnStatusSearch"))
            )
            search_button.click()
            logger.debug("Clicked search button")

            # Step 2: Click "View FIR" link
            view_fir_link = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "View FIR"))
            )
            #store all tab/window opened by selenium
            initial_handles = driver.window_handles
            main_window = initial_handles[0]
            view_fir_link.click()
            logger.debug("Clicked 'View FIR' link")

            # Wait for new window and switch to it
            #This waits until a new window/tab appears after clicking the "View FIR" link (from your previous snippet)
            WebDriverWait(driver, 30).until(lambda d: len(d.window_handles) > len(initial_handles))
            #Identifies the handle of the new window/tab
            new_window = [handle for handle in driver.window_handles if handle not in initial_handles][0]
            #Switches the WebDriver’s focus to the new window/tab
            driver.switch_to.window(new_window)
            logger.debug(f"Switched to new window: {new_window}")

            # Wait for the new page to fully load
            #This is typically used to ensure a webpage has at least started loading before performing further actions
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            WebDriverWait(driver, 60).until(
                EC.invisibility_of_element_located((By.ID, "RptView_AsyncWait"))
            )
            export_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.ID, "RptView_ctl06_ctl04_ctl00_ButtonLink"))
            )
            while "ExportDisabled.gif" in export_button.get_attribute("outerHTML"):
                print("dis")
                if time.time() - start_time > max_wait_time:
                    logger.warning("Export button did not enable after waiting.")
                    break  # Exit the loop if time exceeds max_wait_time
                logger.info("Export button is disabled, waiting...")
                time.sleep(1)  # Wait for 1 second before checking again
                export_button = driver.find_element(By.ID, "RptView_ctl06_ctl04_ctl00_ButtonLink")  # Refresh the element

            logger.debug("Report has finished loading")

            # Find and click the Export button using a precise locator
            
            driver.execute_script("arguments[0].click();", export_button)
            logger.debug("Clicked export button")

            # Find and click the PDF option using a specific locator
            pdf_option = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@id='RptView_ctl06_ctl04_ctl00_Menu']//a[text()='PDF']"))
            )
            driver.execute_script("arguments[0].click();", pdf_option)

            # Step 3: Find and click the Export button
            # Note: Replace with actual locator after inspecting the website
            # export_button = WebDriverWait(driver, 30).until(
            #         EC.element_to_be_clickable((By.XPATH, "//table[@title='Export']//a"))
            #     )
            # # export_button = WebDriverWait(driver, 30).until(
            # #        EC.element_to_be_clickable((By.ID, "RptView_ctl06_ctl04_ctl00_ButtonLink"))
            # #   )
            # driver.execute_script("arguments[0].click();", export_button)
            # logger.debug("Clicked export button")

            # # Step 4: Find and click the PDF option
            # # Note: Replace with actual locator after inspecting the website
            # pdf_option = WebDriverWait(driver, 30).until(
            #     EC.element_to_be_clickable((By.XPATH, "//*[text()='PDF']"))
            # )
            # # pdf_option = WebDriverWait(driver, 10).until(
            # #         EC.element_to_be_clickable((By.XPATH, "//div[@id='RptView_ctl06_ctl04_ctl00_Menu']//a[text()='PDF']"))
            # #     )
            # driver.execute_script("arguments[0].click();", pdf_option)
            # logger.debug("Clicked PDF option")


            # Step 5: Verify the download
            print("done pdf")
            max_wait_time = 120
            start_time = time.time()
            while time.time() - start_time < max_wait_time:
                if os.path.exists(expected_file_path) and os.path.getsize(expected_file_path) > 0:
                    logger.info(f"PDF downloaded successfully to {expected_file_path}")
                    return expected_file_path
                time.sleep(1)
            time.sleep(3)
            print("done sleep")
        except Exception as e:
            logger.error(f"Unexpected error in attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise
        
        finally:
            print("done finally")
            if driver:
                for handle in driver.window_handles:
                        if handle != main_window:
                            driver.switch_to.window(handle)
                            driver.close()
                # Switch back to the main window and quit
                driver.switch_to.window(main_window)
                driver.quit()
                logger.debug("WebDriver closed")
            print("done driver quit")
            if os.path.exists(temp_user_data_dir):
                try:
                    shutil.rmtree(temp_user_data_dir)
                    logger.debug(f"Deleted temp directory: {temp_user_data_dir}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp directory: {str(e)}")

    logger.warning(f"All retries completed, returning expected path: {expected_file_path}")
    return expected_file_path
