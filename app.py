import os
from time import sleep
from functools import wraps
from threading import Thread
from db import Database
from flask import Flask, request, render_template
from dotenv import load_dotenv
from scraper import Scraper
from scraper_amazon import ScraperAmazon
from scraper_ebay import ScraperEbay
from scraper_walmart import ScraperWalmart

app = Flask(__name__)

# Load env variables
load_dotenv ()
DB_HOST = os.getenv ("DB_HOST")
DB_USER = os.getenv ("DB_USER")
DB_PASSWORD = os.getenv ("DB_PASSWORD")
DB_NAME = os.getenv ("DB_NAME")
USE_THREADING = os.getenv ("USE_THREADING") == "True"

# Connect with database
db = Database(DB_HOST, DB_NAME, DB_USER, DB_PASSWORD)

log_origin = "api"

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
        db.save_log (f"keyword: {keyword}, request_id: {request_id}, error: {str (error)}", log_origin, id_request=request_id)
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

def wrapper_validate_api_key(function):
    @wraps(function)
    def wrap(*args, **kwargs):
        # Get json data
        json_data = request.get_json ()
        api_key = json_data.get ("api-key", "")
        
        # Validate required data
        if not api_key:
            
            db.save_log ("Api-key is required", log_origin, api_key=api_key[0:5])
            
            return ({
                "status": "error",
                "message": "Api-key is required",
                "data": {}
            }, 400)
        
        # Validate if token exist in db
        api_key_valid = db.validate_token (api_key)
        if not api_key_valid:
            
            db.save_log ("Invalid api-key", log_origin, api_key=api_key)
            
            return ({
                "status": "error",
                "message": "Invalid api-key",
                "data": {}
            }, 401)
            
        return function(*args, **kwargs)
    
    return wrap

def wrapper_validate_request_id(function):
    @wraps(function)
    def wrap(*args, **kwargs):
        # Get json data
        json_data = request.get_json ()
        request_id = json_data.get ("request-id", "")
        
        # Validate required data
        if not request_id:
            
            db.save_log ("Request-id is required", log_origin, request_id=request_id)
            
            return ({
                "status": "error",
                "message": "Request-id is required",
                "data": {}
            }, 400)
        
        # Get request status
        request_status = db.get_request_status (request_id)
        
        if not request_status:
            
            db.save_log ("Invalid request-id", log_origin, request_id=request_id)
            
            return ({
                "status": "error",
                "message": "Invalid request-id",
                "data": {}
            }, 404)
            
        return function(*args, **kwargs)
    
    return wrap

@app.post ('/keyword/')
@wrapper_validate_api_key
def keyword ():
    """ Initilize scraper in background """
    
    # Get json data
    json_data = request.get_json ()
    keyword = json_data.get ("keyword", "")
    api_key = json_data.get ("api-key", "")
    
    # Validate required data
    if not keyword:
        
        db.save_log ("Keyword is required", log_origin, api_key=api_key)
        
        return ({
            "status": "error",
            "message": "Keyword is required",
            "data": {}
        }, 400)
    
    # save request in db
    request_id = db.create_new_request (api_key)
    
    # initialize web scraper in background
    thread_scrapers = Thread (target=start_scrapers, args=(keyword, request_id))
    thread_scrapers.start ()
    
    db.save_log ("Scraper started in background", log_origin, api_key=api_key, id_request=request_id)
    
    return {
        "status": "success",
        "message": "Scraper started in background",
        "data": {
            "request-id": request_id
        }
    }

@app.get ('/status/')
@wrapper_validate_api_key
@wrapper_validate_request_id
def status ():
    """ Get request status """
    
    # Get json data
    json_data = request.get_json ()
    request_id = json_data.get ("request-id", "")
    
    # Get request status
    request_status = db.get_request_status (request_id)
    
    db.save_log ("Request status", log_origin, request_id=request_id)
    
    return ({
        "status": "success",
        "message": "Request status",
        "data": {
            "status": request_status
        }
    })
        
@app.get ('/results/')
@wrapper_validate_api_key
@wrapper_validate_request_id
def results ():
    
    # Get json data
    json_data = request.get_json ()
    request_id = json_data.get ("request-id", "")

    # Get products from db
    products = db.get_products (request_id)
    
    db.save_log ("Products found", log_origin, request_id=request_id)
    
    return ({
        "status": "success",
        "message": "Products found",
        "data": {
            "products": products
        }
    })
    
@app.get ('/preview/')
def preview ():    
    """ Render basic preview products page """
    
    # Get url variables
    api_token = request.args.get ("api-token", "")
    request_id = request.args.get ("request-id", "")
    
    valid_token = db.validate_token (api_token)
    valid_request_id = db.get_request_status (request_id)
    
    if not valid_token or not valid_request_id:
        
        db.save_log ("Invalid api token or request id", log_origin, api_token=api_token, request_id=request_id)
        
        return ({
            "status": "error",
            "message": "invalid api token or request id",
            "data": []
        }, 401)
    
    # Get products from db
    products_categories = db.get_products (request_id)
    
    db.save_log ("Products rendered", log_origin, request_id=request_id)
    
    return render_template ("preview.html", products_categories=products_categories)
    
if __name__ == "__main__":
    app.run(debug=True)