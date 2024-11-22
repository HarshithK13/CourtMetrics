from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import schedule
import time
import json
import re
from pymongo import MongoClient
import os

month_map = {
    1: 'january',
    2: 'february',
    3: 'march',
    4: 'april',
    5: 'may',
    6: 'june',
    7: 'july',
    8: 'august',
    9: 'september',
    10: 'october',
    11: 'november',
    12: 'december'
}

def scrape_data():
    current_day = datetime.now().day
    current_month = datetime.now().month
    driver = webdriver.Chrome()
    year = 2025
    month = month_map[current_month]
    driver.get('https://www.basketball-reference.com/leagues/NBA_'+str(year)+'_games-'+month+'.html')

    # Wait for the page to load completely
    time.sleep(5)  # or use WebDriverWait to ensure the content is loaded

    # Once the content is loaded, extract the page source
    html = driver.page_source

    # Use BeautifulSoup to parse the page source
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')

    driver.quit()

    table = soup.find_all('table',class_='suppress_glossary sortable stats_table now_sortable sticky_table eq1 re1 le1')

    if len(table) == 0:
        table = soup.find_all('table',class_='suppress_glossary sortable stats_table now_sortable')

    count=0
    headers = [header.text.strip() for header in table[0].find_all('thead')[0].find_all('th')]

    for row in table[0].find_all('tr')[1:]:
        try:
            temp = {}
            date = row.find_all('th')[0].text.strip()
            present_date = current_day
            print(current_day)
            pattern = rf"\b{str(present_date)}\b"
            pattern2 = rf"\b{str(present_date-1)}\b"
            if re.search(pattern, date):
                break
            if re.search(pattern2,date):
                temp['Date'] = row.find_all('th')[0].text.strip()
                for j in range(1,len(headers)):
                    key = headers[j]
                    value = row.find_all('td')[j-1].text.strip()
                    # temp[headers[j]] = row.find_all('td')[j-1].text.strip()
                    if key in temp:
                        if key == 'PTS':
                            key = 'Home_PTS'
                            temp[key] = value
                        if key == "":
                            key = 'no. of OT'
                            temp[key] = value
                    else:
                        temp[key] = value
                count+=1
                
                with open('c://Users//manis//Desktop//daily_data//Scores_of_'+str(present_date-1)+'_'+month+'.json', 'a') as json_file:
                    json.dump(temp, json_file)
                print('Data for '+str(present_date-1)+'_'+month+' saved successfully')
        except:
            print('missed data for row: ',str(count))
        
    with open('c://Users//manis//Desktop//daily_data//Scores_of_'+str(present_date-1)+'_'+month+'.json', 'r') as json_file:
        raw_data = json_file.read()

    # Fix the format by adding square brackets and commas
    fixed_data = "[" + raw_data.replace("}{", "},{") + "]"

    # Parse the corrected JSON format
    try:
        data = json.loads(fixed_data)
        print("JSON data for "+str(present_date-1) +" loaded successfully.")
    except json.JSONDecodeError as e:
        print(f"Failed to load JSON: {e}")

    # If you want, you can save the corrected JSON format to a new file
    with open('c://Users//manis//Desktop//daily_data//Scores_of_'+str(present_date-1)+'_'+month+'.json', 'w') as fixed_file:
        json.dump(data, fixed_file, indent=4)

    with open('c://Users//manis//Desktop//daily_data//Scores_of_'+str(present_date-1)+'_'+month+'.json', 'r') as json_file:
        data = json.load(json_file)

    # Step 2: Connect to MongoDB
    # Replace the URI with your MongoDB server's URI, for example, "mongodb://localhost:27017/"
    client = MongoClient("mongodb+srv://court-metrics:k2vCw0PaWW2v7k7N@cluster0.tqzmo.mongodb.net/")

    # Access the database and collection you want to use
    db = client['courtmetrics_db']  # Replace with your database name
    collection = db['past_matches']  # Replace with your collection name

    # Step 3: Insert JSON data into the collection
    # If `data` is a list of JSON objects, use insert_many; if it's a single JSON object, use insert_one
    if isinstance(data, list):
        collection.insert_many(data)
    else:
        collection.insert_one(data)

    print("Data for date "+str(present_date-1) +" successfully added to MongoDB.")


schedule.every().day.at("01:00").do(scrape_data)

print("Scheduler is running. Press Ctrl+C to stop.")

# Keep the script running
while True:
    schedule.run_pending()
    time.sleep(20)  # Sleep for 1 second to avoid high CPU usage
