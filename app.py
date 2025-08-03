# Description: This file contains the code for Passivebot's x WordForest's Facebook Marketplace Scraper API. This code was initially authored by Harminder Nijjar and modified by Tanya Da Costa to fit custom Marketplace needs.
# Date: 2024-01-24
# Author: Harminder Nijjar, Tanya Da Costa
# Version: 2.0.0.
# Usage: python app.py

# TODO: favicon

# Import the necessary libraries.
# Playwright is used to crawl the Facebook Marketplace.
from playwright.async_api import async_playwright, Page
# The os library is used to get the environment variables.
import os
# The time library is used to add a delay to the script.
import time
# The BeautifulSoup library is used to parse the HTML.
from bs4 import BeautifulSoup
# The FastAPI library is used to create the API.
from fastapi import HTTPException, FastAPI
# The JSON library is used to convert the data to JSON.
import json
# The uvicorn library is used to run the API.
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
# Import logging for debugging
import logging
# Import asyncio for async operations
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
                 
# Create an instance of the FastAPI class.
app = FastAPI()
# Configure CORS
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Global variables for the browser and page
browser = None
page = None
playwright_instance = None

async def initialize_browser():
    global browser, page, playwright_instance
    try:
      if browser is None:
          playwright_instance = await async_playwright().start()
          browser = await playwright_instance.chromium.launch(headless=False, args=['--enable-logging', '--v=1'])
          page = await browser.new_page()
    except Exception as e:
      logger.error(f"Error initializing browser: {e}")
      await restart_browser()

async def login_and_goto_marketplace(initial_url, marketplace_url):
    global page
    await page.goto(initial_url)
    await page.wait_for_timeout(2000)
    try:
      # If url does not contain "login", we assume we are logged in and redirect to marketplace
      if "login" not in page.url:
          await page.goto(marketplace_url)
          return
      # If not logged in, go to Facebook homepage and wait for manual login
      await page.goto("https://www.facebook.com")
      await wait_for_user_login(page)
      
      # After login, navigate to marketplace
      await page.goto(marketplace_url)
      await page.wait_for_timeout(5000)  # Wait for marketplace to load
        
    except Exception as e:
      logger.error(f"Login error: {e}")
      await restart_browser()

async def wait_for_user_login(page):
    print("Please login manually in the browser window...")

    # Wait for navigation after form submission
    async with page.expect_navigation(timeout=600_000):  # wait up to 10 minutes
        # Wait for the login button to appear
        await page.wait_for_selector('button[name="login"]')
        print("Login button is available. Waiting for user to submit the form...")

        # Optionally: Wait until button is actually clicked
        await page.locator('button[name="login"]').wait_for(state="detached", timeout=600_000)

    print("Login detected, proceeding with scraping...")
    # TODO: this is not automatically going to marketplace, have to hit force run again.
    # If we can't get it auto redirecting we should just have a separate login button
 
async def goto_marketplace(marketplace_url):
    await page.goto(marketplace_url)

async def restart_browser():
    global browser, page, playwright_instance
    logger.warning("Restarting the browser due to crash or failure...")
    if browser:
        await browser.close()
    if playwright_instance:
        await playwright_instance.stop()
    browser = None
    page = None
    playwright_instance = None
    await initialize_browser()


# Create a route to the root endpoint.
@app.get("/")
# Define a function to be executed when the endpoint is called.
def root():
    # Return a message.
    return {"message": "Welcome to Passivebot's Facebook Marketplace API. Documentation is currently being worked on along with the API. Some planned features currently in the pipeline are a ReactJS frontend, MongoDB database, and Google Authentication."}

# Create a route to the return_data endpoint.
@app.get("/crawl_facebook_marketplace")
# Define a function to be executed when the endpoint is called.
# Add a description to the function.
# TODO: days since listed input
async def crawl_facebook_marketplace(city: str, query: str, max_price: int, max_results_per_query: int):
    print(f"[API] Received request: city={city}, query={query}, max_price={max_price}, max_results={max_results_per_query}")
    
    # Define dictionary of cities from the facebook marketplace directory for United States.
    # https://m.facebook.com/marketplace/directory/US/?_se_imp=0oey5sMRMSl7wluQZ
    cities = {
        'Hamilton': 'hamilton',  # TODO: more Ontario cities
        'Barrie': 'barrie',
        'Toronto': 'toronto'
    }
    # If the city is in the cities dictionary...
    if city in cities:
        # Get the city location id from the cities dictionary.
        city = cities[city]
    # If the city is not in the cities dictionary...
    else:
        # Exit the script if the city is not in the cities dictionary.
        # Capitalize only the first letter of the city.
        city = city.capitalize()
        # Raise an HTTPException.
        raise HTTPException (404, f'{city} is not a city we are currently supporting on the Facebook Marketplace. Please reach out to us to add this city in our directory.')
        
    # Define the URL to scrape.
    results = []
    # Split the query into a list
    query_list = query.split(',')
    print(f"[API] Processing {len(query_list)} queries: {query_list}")
    
    for query in query_list:
      try:
        print(f"[API] Crawling query: '{query}'")
        # TODO: umm it seems to only consider the query the first time around? Or is that because im not signing in anymore?
        recent_query_results = await crawl_query(city, query.strip(), max_price, max_results_per_query, False)
        suggested_results = await crawl_query(city, query.strip(), max_price, max_results_per_query, True)
        
        print(f"[API] Query '{query}' - Recent: {len(recent_query_results)}, Suggested: {len(suggested_results)}")
      except Exception as e:
        print(f"[API] Error crawling query '{query}': {e}")
        recent_query_results = []
        suggested_results = []

      recent_query_results_urls = [item["link"] for item in recent_query_results]
      suggested_results_urls = [item["link"] for item in suggested_results]

      # If the items appear in both recent and suggested, put them in the top of the list
      common_items = set(recent_query_results_urls) & set(suggested_results_urls)

      consolidated_query_result_urls = list(common_items) + [item for item in recent_query_results_urls + suggested_results_urls if item not in list(common_items)]
      consolidated_query_results = [item for item in recent_query_results + suggested_results if item["link"] in consolidated_query_result_urls]

      results.extend(consolidated_query_results)

    print(f"[API] Total results returning: {len(results)}")
    return results

if __name__ == "__main__":

    # Run the app.
    uvicorn.run(
        # Specify the app as the FastAPI app.
        'app:app',
        host='127.0.0.1',
        port=8000
    )

async def crawl_query(city: str, query: str, max_price: int, max_results: int, suggested: bool):
  global page
  try:
    scrape_type = "suggested" if suggested else "recent"
    marketplace_url = f'https://www.facebook.com/marketplace/{city}/search?query={query}&maxPrice={max_price}&daysSinceListed=1&sortBy=creation_time_descend'
    initial_url = "https://www.facebook.com/login/device-based/regular/login/"
    if suggested:
      marketplace_url = f'https://www.facebook.com/marketplace/{city}/search?query={query}&maxPrice={max_price}&daysSinceListed=3'

    print(f"[CRAWL] {scrape_type.upper()}: {marketplace_url}")

    # Initialize browser if not already initialized
    await initialize_browser()

    # await login_and_goto_marketplace(initial_url, marketplace_url)
    await goto_marketplace(marketplace_url) # TODO: if login captcha locked.. comment above and uncomment this

    # Get listings of particular item in a particular city for a particular price.
    # Wait for the page to load.
    await page.wait_for_timeout(5000)
    html = await page.content()
    soup = BeautifulSoup(html, 'html.parser')
    parsed = []
    listings = soup.find_all('div', class_='x9f619 x78zum5 x1r8uery xdt5ytf x1iyjqo2 xs83m0k x135b78x x11lfxj5 x1iorvi4 xjkvuk6 xnpuxes x1cjf5ee x17dddeq')
    
    print(f"[CRAWL] {scrape_type.upper()}: Found {len(listings)} listing divs on page")

    for listing in listings:
      # Get the item image.
      image = listing.find('img', class_='x15mokao x1ga7v0g x16uus16 xbiv7yw xt7dq6l xl1xv1r x6ikm8r x10wlt62 xh8yej3')
      if image is not None:
        image = image['src']

      # TODO: better way to grab these or move these classes to config. They change sometimes
      # Get the item title from span.
      title = listing.find('span', 'x1lliihq x6ikm8r x10wlt62 x1n2onr6')
      if title is not None:
        title = title.text

      # Get the item URL.
      post_url = listing.find('a', class_='x1i10hfl xjbqb8w x1ejq31n x18oe1m7 x1sy0etr xstzfhl x972fbf x10w94by x1qhh985 x14e42zd x9f619 x1ypdohk xt0psk2 xe8uvvx xdj266r x14z9mp xat24cr x1lziwak xexx8yu xyri2b x18d9i69 x1c1uobl x16tdsg8 x1hl2dhg xggy1nq x1a2a7pz x1heor9g xkrqix3 x1sur9pj x1s688f x1lku1pv')
      if post_url is not None:
        post_url = post_url['href']

      # Only add the item if the title includes any of the query terms
      query_parts = query.split(' ')
      if title is not None and post_url is not None and image is not None:
        matches_query = any(part.lower() in title.lower() for part in query_parts)
        if matches_query:
          # Append the parsed data to the list.
          parsed.append({
              'image': image,
              # 'location': location,
              'title': title,
              # 'price': price,
              'post_url': post_url
          })
          print(f"[CRAWL] {scrape_type.upper()}: Added item: {title}")
        else:
          print(f"[CRAWL] {scrape_type.upper()}: Skipped item (no query match): {title}")
      else:
        missing = []
        if title is None: missing.append("title")
        if post_url is None: missing.append("url")
        if image is None: missing.append("image")
        print(f"[CRAWL] {scrape_type.upper()}: Skipped item (missing {', '.join(missing)})")

    # Return the parsed data as a JSON.
    # TODO: put in a dict for query headings
    result = []
    # Grab only max results amount
    parsed = parsed[:max_results]
    for item in parsed:
        result.append({
            'name': item['title'],
            # 'price': item['price'],
            # 'location': item['location'],
            'title': item['title'],
            'image': item['image'],
            'link': item['post_url']
        })

    return result
  except Exception as e:
    logger.error(f"Error during crawl: {e}")
    # await restart_browser()  # Restart on failure

