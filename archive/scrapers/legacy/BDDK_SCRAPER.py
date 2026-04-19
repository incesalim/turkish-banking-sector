# BDDK BasitRaporGetir → Folder per TABLE (1..17), file per MONTH (YYYY-MM.csv)
# - Folder: table number "1".."17"
# - File:   "YYYY-MM.csv" per month inside that folder
# - Preserves Turkish labels; exposes row labels as "Kalem" by locating the "Ad"/"Banka Adı" column via colModels
# - Merges colNames with colModels.name for robust headers (colNames may have blanks)
# - Pads rows/headers, converts numerics by position to avoid duplicate-name issues

import os
import requests
import pandas as pd

# ---------------- Parameters ----------------
start_year, start_month = 2025, 8
end_year,   end_month   = 2025, 8

table_numbers = list(range(1, 18))  # 1..17

taraf_types = [
    {"code": "10001", "name": "Sektör"},
    {"code": "10002", "name": "Mevduat"},
    {"code": "10008", "name": "Mevduat-Yerli Özel"},
    {"code": "10009", "name": "Mevduat-Kamu"},
    {"code": "10010", "name": "Mevduat-Yabancı"},
    {"code": "10003", "name": "Katılım"},
    {"code": "10004", "name": "Kalkınma ve Yatırım"},
    {"code": "10005", "name": "Yerli Özel"},
    {"code": "10006", "name": "Kamu"},
    {"code": "10007", "name": "Yabancı"},
]

url = "https://www.bddk.org.tr/BultenAylik/tr/Home/BasitRaporGetir"
headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Mozilla/5.0",
}

# ---------------- Normalizer ----------------
def normalize_table(taraf_name: str, table_no: int, node: dict, month_str: str):
    """
    One BDDK JSON node → DataFrame, returning (df, caption).
    Header is built by merging colNames with colModels.name.
    The column whose colModels.name is 'Ad' or 'BankaAdi' is renamed to 'Kalem'.
    """
    j = node.get("Json", {}) if isinstance(node, dict) else {}

    col_models = j.get("colModels", []) or []
    col_names  = j.get("colNames", []) or []

    # Start with colNames; fill blanks with colModels.name to keep Turkish labels where present.
    header = list(col_names)  # copy
    # ensure header length matches col_models
    if len(header) < len(col_models):
        header += [None] * (len(col_models) - len(header))

    # Merge: fill empty entries from colModels.name
    for i, cm in enumerate(col_models):
        if header[i] is None or str(header[i]).strip() == "":
            header[i] = cm.get("name")

    # Find the index of the row-label column (technical name 'Ad' or 'BankaAdi')
    ad_idx = None
    for i, cm in enumerate(col_models):
        nm = (cm.get("name") or "").strip()
        if nm in ("Ad", "BankaAdi", "Banka Adı"):
            ad_idx = i
            break
    if ad_idx is not None:
        header[ad_idx] = "Kalem"  # visible row label

    # Rows → records
    rows = (j.get("data", {}) or {}).get("rows", []) or []
    records = [r.get("cell", []) for r in rows]

    # Harmonize lengths between records and header
    if records:
        max_len = max(len(r) for r in records)
        target_len = max(max_len, len(header))
        # pad records
        records = [r + [None] * (target_len - len(r)) for r in records]
        # pad header if needed
        if target_len > len(header):
            header += [f"_col{i}" for i in range(len(header), target_len)]

    df = pd.DataFrame(records, columns=header if records else header)

    # Meta columns at front (Turkish kept as-is)
    caption = j.get("caption") or f"Tablo {table_no}"
    df.insert(0, "Taraf", taraf_name)
    df.insert(1, "Month", month_str)
    df.insert(2, "TableNo", str(table_no))
    df.insert(3, "Caption", caption)

    # Convert numeric-like columns by POSITION (avoid duplicate label issues)
    skip = {"Taraf", "Month", "TableNo", "Caption", "Kalem", "Banka Adı", "Ad", "BasitFont"}
    for i, col in enumerate(df.columns):
        if col in skip:
            continue
        df.iloc[:, i] = pd.to_numeric(df.iloc[:, i], errors="coerce")

    return df, caption

# ---------------- Main ----------------
base_out = "bddk_tables"  # root folder
os.makedirs(base_out, exist_ok=True)

y, m = start_year, start_month
while (y < end_year) or (y == end_year and m <= end_month):
    month_str = f"{y}-{m:02d}"

    for t_no in table_numbers:
        month_frames = []

        for taraf in taraf_types:
            payload = {
                "tabloNo": str(t_no),
                "yil": str(y),
                "ay": str(m),
                "paraBirimi": "TL",
                "taraf[0]": taraf["code"],
            }
            try:
                resp = requests.post(url, headers=headers, data=payload, timeout=60)
                resp.raise_for_status()
                node = resp.json()
                if not isinstance(node, dict) or "Json" not in node:
                    continue

                df, _ = normalize_table(taraf["name"], t_no, node, month_str)
                if not df.empty:
                    month_frames.append(df)
            except requests.RequestException:
                continue  # skip quietly

        if month_frames:
            folder_path = os.path.join(base_out, str(t_no))  # e.g., bddk_tables/1
            os.makedirs(folder_path, exist_ok=True)

            out_path = os.path.join(folder_path, f"{month_str}.csv")  # e.g., 2025-05.csv
            pd.concat(month_frames, ignore_index=True).to_csv(out_path, index=False, encoding="utf-8-sig")
            print(f"Saved {out_path}")

    # next month
    if m == 12:
        y += 1
        m = 1
    else:
        m += 1
