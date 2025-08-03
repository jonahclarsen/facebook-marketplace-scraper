import random
import streamlit as st
import streamlit.components.v1 as stcomponents
import time
import json 
import requests
from datetime import datetime
from PIL import Image


def ding():
  unique_id = f'dingSound_{time.time()}_{random.randint(1, 1000)}'
  audio_html = f'<audio id="{unique_id}" autoplay><source src="app/static/ding.mp3"></audio>'
  stcomponents.html(audio_html)

def crawl():
  global max_price
  global city
  global query

  # Workaround to hide the ugly iframe that the new results alert component gets rendered in
  st.markdown(
    """
    <style>
        iframe {
            display: none;  /* Hide the iframe */
        }
    </style>
    """,
    unsafe_allow_html=True
  )
  
  if "," in max_price:
      max_price = max_price.replace(",", "")
  elif "$" in max_price:
      max_price = max_price.replace("$", "")
  else:
      pass

  # Convert the response from json into a Python list.
  try:
    api_url = f"http://127.0.0.1:8000/crawl_facebook_marketplace?city={city}&sortBy=creation_time_descend&query={query}&max_price={str(int(max_price) * 100)}&max_results_per_query={max_listings}"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Making API request: {api_url}")
    
    res = requests.get(api_url)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] API Response Status: {res.status_code}")
    
    if res.status_code == 200:
      results = res.json()
      print(f"[{datetime.now().strftime('%H:%M:%S')}] API returned {len(results)} results")
      if len(results) > 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] First result: {results[0]}")
      else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] No results returned from API")
    else:
      print(f"[{datetime.now().strftime('%H:%M:%S')}] API Error: {res.status_code} - {res.text}")
      results = []
  except Exception as e:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Exception during API call: {e}")
    results = []

  # Display the length of the results list.
  if len(results) > 0:
    # Determine if there are new results and log an alert if so
    latest = [json.dumps(item["title"]) for item in results] # TODO: index on url instead of title in case of dupes
    diff = [item for item in latest if item not in st.session_state.current_latest]
    if len(diff) > 0:
      # Reset the latest list
      st.session_state.current_latest = latest
      latest_string = "\\n\\n".join(diff)
      # TODO: still getting repeat alerts. perhaps when random login prompt?
      alert_js=f"alert('New listings!!\\n\\n{latest_string}')"
      alert_html = f"<script>{alert_js}</script>"

      stcomponents.html(alert_html)
      ding()

  last_ran_formatted = datetime.now().time().strftime("%I:%M:%S %p")
  results_message.markdown(f"*Showing latest {max_listings} listings (per query) since last scrape at **{last_ran_formatted}***")

  # Clear previous results
  results_container.empty()

  # Iterate over the results list to display each item.
  # TODO: new! badge. query headings
  with results_container.container():
    for item in results:
        st.header(item["title"])
        img_url = item["image"] # TODO: make the whole row clickable link to listing
        st.image(img_url, width=200)
        st.write(f"https://www.facebook.com{item['link']}")
        st.write("----")

# End of private functions

# Initialize session state
if 'current_latest' not in st.session_state:
    st.session_state.current_latest = []

# Create a title for the web app.
st.title("DingBot™ Facebook Scraper")
st.subheader("Brought to you by Passivebot + WordForest")

# Add a list of supported cities.
supported_cities = ["Hamilton", "Barrie", "Toronto"] # TODO: more oNTARIO cities

# Take user input for the city, query, and max price.
city = st.selectbox("City", supported_cities, 0)
query = st.text_input("Query (comma,between,multiple,queries)", "Horror VHS,Digimon")
# TODO: don't scrape until there is an input. Ensure that subsequent auto scrapes use the input
max_price = st.text_input("Max Price ($)", "1000")
# This value should be calibrated to your queries. Facebook sometimes is very lax about what they think
# is related to your search query.
max_listings = st.text_input("Max Latest Listings", "8")
# TODO: auto scrape every 3, 5, 10, 30 minutes select

countdown_message = st.empty()

# TODO: shouldn't clear results
submit = st.button("Force Scrape Now!")

results_message = st.empty()
results_container = st.empty()

# If the button is clicked
if submit:
  countdown_message.text("Scraping...")
  crawl()

# Add refresh button for updating the page
col1, col2 = st.columns(2)
with col1:
    refresh_page = st.button("🔄 Refresh Page")
with col2:
    auto_scrape_interval = st.selectbox("Auto-scrape interval", 
                                       ["Disabled", "1 minute", "3 minutes", "5 minutes", "10 minutes"], 
                                       index=3)

# Initialize timing
if 'last_manual_scrape' not in st.session_state:
    st.session_state.last_manual_scrape = None

# Convert interval to seconds
interval_seconds = {
    "Disabled": 0,
    "1 minute": 60,
    "3 minutes": 180,
    "5 minutes": 300,
    "10 minutes": 600
}[auto_scrape_interval]

# Auto-scrape logic (only if enabled)
if interval_seconds > 0:
    if 'last_auto_scrape' not in st.session_state:
        st.session_state.last_auto_scrape = time.time()
    
    current_time = time.time()
    time_since_last_scrape = current_time - st.session_state.last_auto_scrape
    
    if time_since_last_scrape >= interval_seconds:
        st.session_state.last_auto_scrape = current_time
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Auto-scraping triggered (interval: {auto_scrape_interval})")
        countdown_message.text("Auto-scraping...")
        crawl()
    else:
        # Show time until next auto-scrape
        time_until_next = interval_seconds - time_since_last_scrape
        mins, secs = divmod(int(time_until_next), 60)
        countdown_message.text(f"Auto-scrape in: {mins:02d}:{secs:02d} (interval: {auto_scrape_interval})")
else:
    countdown_message.text("Auto-scraping disabled. Use 'Force Scrape Now!' to scrape manually.")

# Handle manual refresh
if refresh_page:
    st.rerun()

# Allow running the GUI directly with python gui.py
if __name__ == "__main__":
    import subprocess
    import sys
    import os
    
    print("Starting Streamlit server...")
    print("You can view console output here!")
    print("=" * 50)
    
    # Run streamlit with the current file
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", __file__,
        "--server.address", "localhost",
        "--server.port", "8501",
        "--browser.gatherUsageStats", "false"
    ])