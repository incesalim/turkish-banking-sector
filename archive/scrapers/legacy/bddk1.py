import requests
import pandas as pd
import os
import time

# ================= CONFIGURATION =================
START_YEAR = 2020
START_MONTH = 1
END_YEAR = 2025
END_MONTH = 8

BASE_OUTPUT_FOLDER = "BDDK_Full_Extracts"
# We fetch Tables 1 to 20 to cover everything (Balance Sheet, Credits, P&L, etc.)
TABLE_IDS = list(range(1, 21))  

# COMPLETE SECTOR LIST (10 Types)
SECTORS = [
    {"code": "10001", "name": "Sektör (Toplam)"},
    {"code": "10002", "name": "Mevduat Bankaları"},
    {"code": "10003", "name": "Katılım Bankaları"},
    {"code": "10004", "name": "Kalkınma ve Yatırım Bankaları"},
    {"code": "10005", "name": "Yerli Özel (Tüm)"},
    {"code": "10006", "name": "Kamu (Tüm)"},
    {"code": "10007", "name": "Yabancı (Tüm)"},
    {"code": "10008", "name": "Mevduat - Yerli Özel"},
    {"code": "10009", "name": "Mevduat - Kamu"},
    {"code": "10010", "name": "Mevduat - Yabancı"}
]

URL = "https://www.bddk.org.tr/BultenAylik/tr/Home/BasitRaporGetir"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}
# =================================================

def clean_value(val):
    """Converts BDDK formatting to standard data types"""
    if val is None: return None
    s_val = str(val).strip()
    if s_val == '' or s_val == '-': return None
    
    # Try converting to float (1.234,56 -> 1234.56)
    try:
        clean_s = s_val.replace('.', '').replace(',', '.')
        return float(clean_s)
    except:
        return s_val # Return as text if it's not a number

def run_scraper():
    if not os.path.exists(BASE_OUTPUT_FOLDER):
        os.makedirs(BASE_OUTPUT_FOLDER)

    print(f"Starting Full Extraction: {START_YEAR}-{START_MONTH:02d} to {END_YEAR}-{END_MONTH:02d}")
    print(f"Covering {len(SECTORS)} Sectors and {len(TABLE_IDS)} Tables.")

    for year in range(START_YEAR, END_YEAR + 1):
        s_m = START_MONTH if year == START_YEAR else 1
        e_m = END_MONTH if year == END_YEAR else 12

        for month in range(s_m, e_m + 1):
            date_str = f"{year}-{month:02d}"
            print(f"\nProcessing Date: {date_str}")

            for table_id in TABLE_IDS:
                table_rows = []
                headers_captured = False
                final_columns = []

                for sector in SECTORS:
                    payload = {
                        "tabloNo": str(table_id),
                        "yil": str(year),
                        "ay": str(month),
                        "paraBirimi": "TL",
                        "taraf[0]": sector["code"]
                    }

                    try:
                        resp = requests.post(URL, data=payload, headers=HEADERS, timeout=10)
                        if resp.status_code != 200: continue
                        
                        data_json = resp.json()
                        if "Json" not in data_json or "data" not in data_json["Json"]:
                            continue

                        grid = data_json["Json"]
                        rows = grid["data"]["rows"]
                        
                        if not rows: continue

                        # --- HEADER LOGIC (Capture once per table) ---
                        if not headers_captured:
                            raw_headers = grid.get("colNames", [])
                            col_models = grid.get("colModels", [])
                            
                            # Standard columns for Power BI
                            final_columns = ["Date", "Year", "Month", "Sector_Code", "Sector_Name"]
                            
                            for idx, h in enumerate(raw_headers):
                                header_name = h.strip() if h else col_models[idx]['name']
                                
                                # Standardize key names
                                if header_name in ['BasitSira', 'Sira']: header_name = "Item_Number"
                                if header_name in ['Ad', 'BankaAdi']: header_name = "Item_Name"
                                
                                # Handle duplicate header names (e.g. TP, TP) by appending index
                                if header_name in final_columns:
                                    header_name = f"{header_name}_{idx}"
                                    
                                final_columns.append(header_name)
                            
                            headers_captured = True

                        # --- ROW DATA ---
                        for r in rows:
                            cells = r["cell"]
                            
                            row_data = [
                                f"{year}-{month:02d}-01", 
                                year, 
                                month, 
                                sector["code"], 
                                sector["name"]
                            ]
                            
                            cleaned_cells = [clean_value(c) for c in cells]
                            
                            # Align data length with header length
                            needed = len(final_columns) - len(row_data)
                            current = len(cleaned_cells)
                            
                            if current < needed:
                                cleaned_cells += [None] * (needed - current)
                            elif current > needed:
                                cleaned_cells = cleaned_cells[:needed]
                                
                            row_data.extend(cleaned_cells)
                            table_rows.append(row_data)

                    except Exception as e:
                        # Fail silently on individual sector errors to keep the loop running
                        pass

                # --- SAVE TO DISK ---
                if table_rows:
                    # Folder: BDDK_Full_Extracts / Table_01
                    table_folder = os.path.join(BASE_OUTPUT_FOLDER, f"Table_{table_id:02d}")
                    if not os.path.exists(table_folder):
                        os.makedirs(table_folder)
                    
                    # File: 2024_09.csv
                    df = pd.DataFrame(table_rows, columns=final_columns)
                    filename = os.path.join(table_folder, f"{year}_{month:02d}.csv")
                    
                    df.to_csv(filename, index=False, encoding="utf-8-sig")
                    print(f"  -> Table {table_id}: Saved {len(df)} rows (All Sectors)")

if __name__ == "__main__":
    run_scraper()