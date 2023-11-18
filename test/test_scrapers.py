import os
from time import sleep
from threading import Thread
from database.db import Database
from dotenv import load_dotenv
from scraper.scraper import Scraper
from scraper_amazon import ScraperAmazon
from scraper_ebay import ScraperEbay
from scraper_walmart import ScraperWalmart

# Load env variables
load_dotenv ()
DB_HOST = os.getenv ("DB_HOST")
DB_USER = os.getenv ("DB_USER")
DB_PASSWORD = os.getenv ("DB_PASSWORD")
DB_NAME = os.getenv ("DB_NAME")
USE_THREADING = os.getenv ("USE_THREADING") == "True"

# Connect with database
db = Database(DB_HOST, DB_NAME, DB_USER, DB_PASSWORD)

log_origin = "scraper"

def start_scraper (scraper_class:Scraper, keyword:str, request_id:int):
    """ Start an specific scraper and extract data

    Args:
        scraper_class (Scraper): Scraper class
        keyword (str): keyword to search
        request_id (int): request id
    """
    
    scraper = scraper_class (keyword, db)
    
    try:
        scraper.get_results (request_id)
    except Exception as error:
        
        # Clean error message
        error = str (error).replace ("'", "").replace ("\"", "")
        
        # Save error in db
        error_message = f"store: {scraper.store}, keyword: {keyword}, error: {str (error)}"
        db.save_log (error_message, log_origin, id_request=request_id, log_type="error")
        quit ()
         
    # random_wait_time = random.randint (30, 60)
    # sleep (random_wait_time)

def start_scrapers (keyword:str, request_id:int):
    """ Start all scrapers

    Args:
        keyword (str): keyword to search
        request_id (int): request id
    """
    
    classes = [ScraperAmazon, ScraperEbay, ScraperWalmart]
    
    # Update request status to working
    db.update_request_status (request_id, "working")
    
    # Start scraping threads
    threads = []
    for class_elem in classes:
        
        # Run functions with and without threads
        if USE_THREADING:
            thread_scraper = Thread (target=start_scraper, args=(class_elem, keyword, request_id))
            thread_scraper.start ()
            threads.append (thread_scraper)
        else:
            start_scraper (class_elem, keyword)
                        
    # Wait for all threads to finish
    while True:
        
        alive_threads = list (filter (lambda thread: thread.is_alive (), threads))
        if not alive_threads:
            break
        
        else:
            sleep (2)
            
    # Update request status to done
    db.update_request_status (request_id, "done")

while True:
    start_scrapers ("plant based protein", 142)
    sleep (20)