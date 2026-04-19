import os, re, time
import requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin

BASE = "https://www.bddk.org.tr"
HOME_PATH = "/BultenHaftalik/"
DONEM_PATH = "/BultenHaftalik/tr/Home/DonemDegistir"
TARAF_PATH = "/BultenHaftalik/tr/Home/TarafSec"

TABLO_ID = 289        # yalnızca 289
TARAF_KODU = "10001"  # Sektör
YIL = 2025
HAFTA_NO = 41         # 41. Hafta
OUT_DIR = "bddk_weekly"

HEADERS = {"User-Agent": "Mozilla/5.0"}

def trnum_to_float(s):
    if s is None: return None
    s = str(s).strip()
    if s == "" or s == "-": return None
    # "1.234.567,89" -> 1234567.89
    s = s.replace(".", "").replace(",", ".")
    try: return float(s)
    except: return None

def extract_tokens(html):
    """Sayfadaki üç formun token'ını ve Donem seçeneklerini döndürür."""
    soup = BeautifulSoup(html, "html.parser")
    def _tok(action):
        f = soup.find("form", {"action": action})
        if not f: return None
        inp = f.find("input", {"name": "__RequestVerificationToken"})
        return inp["value"] if inp else None

    tok_donem = _tok(DONEM_PATH)
    tok_tablo = _tok(HOME_PATH)   # tablo seçimi formu ana path'e post ediyor
    tok_taraf = _tok(TARAF_PATH)

    # Donem seçenekleri
    donem_select = soup.find("select", {"id": "Donem"})
    donemlar = []
    if donem_select:
        for opt in donem_select.find_all("option"):
            donemlar.append({"donemId": opt.get("value"), "label": opt.get_text(strip=True)})
    return tok_donem, tok_tablo, tok_taraf, donemlar

def find_donem_id_for_week(donemlar, hafta_no:int):
    """
    option label'ı tipik olarak 'Ekim/10 (41. Hafta)' gibi.
    41 sayısını parantez içinden yakalayıp donemId'yi döndürür.
    """
    for d in donemlar:
        m = re.search(r"\((\d+)\. *Hafta\)", d["label"])
        if m and int(m.group(1)) == hafta_no:
            return d["donemId"], d["label"]
    return None, None

def parse_table(html):
    """Temel tabloda görünen No | Kalem | TP | YP | TOPLAM'ı DataFrame olarak döndürür."""
    soup = BeautifulSoup(html, "html.parser")
    # aktif tablo adını sol menüde activatedItem'dan yakala (opsiyonel)
    aktif = soup.find("td", class_="tabloListesiItem activatedItem")
    tablo_adi = aktif.get_text(strip=True) if aktif else ""

    table = soup.find("table", {"id": "TabloExcel"}) or soup.find("table", {"id": "TabloExcel2"})
    if table is None:
        # responsive-table fallback
        cand = soup.select("div.col-sm-8 table.responsive-table")
        table = cand[0] if cand else None
    if table is None:
        return tablo_adi, pd.DataFrame()

    rows = []
    for tr in table.find_all("tr"):
        tds = tr.find_all(["td","th"])
        if len(tds) >= 5:
            no = tds[0].get_text(strip=True)
            kalem = " ".join(tds[1].stripped_strings)
            tp = trnum_to_float(tds[2].get_text(strip=True))
            yp = trnum_to_float(tds[3].get_text(strip=True))
            toplam = trnum_to_float(tds[4].get_text(strip=True))
            # No sütunu bazı başlık satırlarında boş olabilir; yine de al
            rows.append([no, kalem, tp, yp, toplam])

    df = pd.DataFrame(rows, columns=["No","Kalem","TP","YP","TOPLAM"])
    # Bazı satırlar tamamen boşsa ayıkla (en azından Kalem dolu olanları tut)
    df = df[df["Kalem"].astype(str).str.strip() != ""].reset_index(drop=True)
    return tablo_adi, df

def main():
    os.makedirs(os.path.join(OUT_DIR, str(TABLO_ID)), exist_ok=True)
    s = requests.Session()
    s.headers.update(HEADERS)

    # 1) açılış: token'ları ve donem seçeneklerini al
    r = s.get(urljoin(BASE, HOME_PATH), timeout=60)
    r.raise_for_status()
    tok_donem, tok_tablo, tok_taraf, donemlar = extract_tokens(r.text)

    # 2) 2025 yılı ve 41. hafta için donemId'yi bul
    donemId, donem_label = find_donem_id_for_week(donemlar, HAFTA_NO)
    if not donemId:
        raise RuntimeError(f"41. hafta için DonemId bulunamadı. Mevcut etiketler: {[d['label'] for d in donemlar[:6]]} ...")

    # 3) dönemi seç (yil + donemId) -> token'lar yenilenebilir; her adım sonrası tokenları tekrar çek
    r = s.post(urljoin(BASE, DONEM_PATH),
               data={"yil": str(YIL), "donemId": str(donemId), "__RequestVerificationToken": tok_donem},
               timeout=60)
    r.raise_for_status()
    tok_donem, tok_tablo, tok_taraf, _ = extract_tokens(r.text)  # yenile

    # 4) tarafı seç (Sektör=10001)
    r = s.post(urljoin(BASE, TARAF_PATH),
               data={"tarafKodu": TARAF_KODU, "__RequestVerificationToken": tok_taraf},
               timeout=60)
    r.raise_for_status()
    tok_donem, tok_tablo, tok_taraf, _ = extract_tokens(r.text)  # yenile

    # 5) tabloyu seç (289)
    r = s.post(urljoin(BASE, HOME_PATH),
               data={"tabloId": str(TABLO_ID), "__RequestVerificationToken": tok_tablo},
               timeout=60)
    r.raise_for_status()

    tablo_adi, df = parse_table(r.text)
    if df.empty:
        raise RuntimeError("Tablo boş geldi veya parse edilemedi (Tablo 289, Sektör, 2025/41).")

    # 6) meta sütunları ve yazım
    df.insert(0, "Taraf", "Sektör")
    df.insert(1, "Yil", YIL)
    df.insert(2, "Hafta", HAFTA_NO)
    df.insert(3, "TabloId", str(TABLO_ID))
    df.insert(4, "TabloAdi", tablo_adi)

    out_path = os.path.join(OUT_DIR, str(TABLO_ID), f"{YIL}-{HAFTA_NO:02d}.csv")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[yazıldı] {out_path}")
    print(df.head(10).to_string(index=False))

if __name__ == "__main__":
    main()
