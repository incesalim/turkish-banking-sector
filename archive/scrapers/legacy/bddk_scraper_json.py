import requests
import json
import os
from datetime import datetime

# SET THE DATE RANGE MANUALLY
start_year = 2010  # Change this to your desired start year
start_month = 5     # Change this to your desired start month (1 = January, 12 = December)
end_year = 2016     # Change this to your desired end year
end_month = 1     # Change this to your desired end month

# List of table numbers to fetch
table_numbers = list(range(1, 18))  # Fetch all tables from 1 to 17

# API URL
url = "https://www.bddk.org.tr/BultenAylik/tr/Home/BasitRaporGetir"

# Headers to mimic a real browser
headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
}

# Create output directory
output_dir = "bddk_reports"
os.makedirs(output_dir, exist_ok=True)

# Iterate over the selected date range
current_year, current_month = start_year, start_month

while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
    monthly_data = {"month": f"{current_year}-{current_month:02d}", "tables": {}}

    for table_no in table_numbers:  # Loop through each table number
        # API parameters for each selected month & table
        payload = {
            "tabloNo": str(table_no),  # Table Number (1-17)
            "yil": str(current_year),  # Year
            "ay": str(current_month),  # Month (1-12)
            "paraBirimi": "TL",        # Currency: "TL" or "USD"
            "taraf[0]": "10001"        # Institution Type (10001 = Sektör, 10002 = Mevduat, etc.)
        }

        try:
            # Send POST request to fetch data
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()  # Raise an exception for HTTP errors

            # Convert response to JSON and store in the dictionary
            monthly_data["tables"][table_no] = response.json()

            print(f"✅ Data for {current_year}-{current_month:02d}, Table {table_no} fetched.")

        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to retrieve data for {current_year}-{current_month:02d}, Table {table_no}. Error: {e}")
            monthly_data["tables"][table_no] = None  # Mark missing data as None

    # Save the full month’s data in a single JSON file
    file_path = os.path.join(output_dir, f"bddk_{current_year}_{current_month:02d}.json")
    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(monthly_data, json_file, ensure_ascii=False, indent=4)

    print(f"📁 Saved full dataset for {current_year}-{current_month:02d} in {file_path}")

    # Move to the next month
    if current_month == 12:
        current_month = 1
        current_year += 1
    else:
        current_month += 1

print("✅ All selected data retrieved and saved successfully!")
