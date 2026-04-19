import os, re, requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin

BASE   = "https://www.bddk.org.tr"
HOME   = "/BultenHaftalik/"
DONEM  = "/BultenHaftalik/tr/Home/DonemDegistir"
TARAF  = "/BultenHaftalik/tr/Home/TarafSec"

YIL        = 2025
HAFTA_NO   = 41
TABLO_ID   = 289
TARAF_KODU = "10001"  # Sektör
OUT        = os.path.join("bddk_weekly", str(TABLO_ID), f"{YIL}-{HAFTA_NO:02d}.csv")

HDRS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://www.bddk.org.tr",
    "Referer": "https://www.bddk.org.tr/BultenHaftalik/",
}

def trnum(s):
    s = (s or "").replace("\xa0"," ").strip()
    if not s or s == "-": return None
    return float(s.replace(".","").replace(",", "."))

def token_for(soup, action_suffix):
    for f in soup.find_all("form"):
        act = (f.get("action") or "").strip()
        if act.endswith(action_suffix):
            i = f.find("input", {"name":"__RequestVerificationToken"})
            if i and i.get("value"): return i["value"]
    return None

def read_state(html):
    soup = BeautifulSoup(html, "html.parser")
    tok_donem = token_for(soup, "/BultenHaftalik/tr/Home/DonemDegistir")
    tok_tablo = token_for(soup, "/BultenHaftalik/")
    tok_taraf = token_for(soup, "/BultenHaftalik/tr/Home/TarafSec")

    def get_sel(id_):
        sel = soup.find("select", {"id": id_})
        items, chosen_val, chosen_txt = [], None, None
        if sel:
            for o in sel.find_all("option"):
                items.append((o.get("value","").strip(), o.get_text(strip=True), bool(o.get("selected"))))
            ch = next((x for x in items if x[2]), None)
            if ch: chosen_val, chosen_txt = ch[0], ch[1]
        return items, chosen_val, chosen_txt

    y_list, y_val, y_txt = get_sel("Yil")
    d_list, d_val, d_txt = get_sel("Donem")
    return tok_donem, tok_tablo, tok_taraf, y_list, d_list, y_val, y_txt, d_val, d_txt

def pick_week_id(d_list, hafta):
    for val, txt, _ in d_list:
        if re.search(rf"\(\s*{hafta}\.\s*Hafta\s*\)", txt or "", flags=re.I):
            return val, txt
    return None, None

def parse_rows(html):
    soup = BeautifulSoup(html, "html.parser")
    data = []
    for tr in soup.select("tr.satir"):
        tds = tr.find_all("td")
        if len(tds) < 5: continue
        data.append([
            tds[0].get_text(strip=True),
            " ".join(tds[1].stripped_strings),
            trnum(tds[2].get_text(strip=True)),
            trnum(tds[3].get_text(strip=True)),
            trnum(tds[4].get_text(strip=True)),
        ])
    return pd.DataFrame(data, columns=["No","Kalem","TP","YP","TOPLAM"])

def main():
    s = requests.Session(); s.headers.update(HDRS)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    # 1) Home (tam sayfa)
    r = s.get(urljoin(BASE, HOME), timeout=30); r.raise_for_status()
    tok_donem, tok_tablo, tok_taraf, y_list, d_list, y_val, y_txt, d_val, d_txt = read_state(r.text)
    if not (tok_donem and tok_tablo and tok_taraf):
        raise RuntimeError("Token bulunamadı.")

    # 2) Yıl 2025 seçili değilse: herhangi bir mevcut donemId ile YIL=2025'e POST ET → SONRA tekrar HOME GET
    if not (y_txt and "2025" in y_txt):
        any_donem = d_val or (d_list[0][0] if d_list else "")
        r = s.post(urljoin(BASE, DONEM),
                   data={"yil": str(YIL), "donemId": str(any_donem), "__RequestVerificationToken": tok_donem},
                   timeout=30)
        r.raise_for_status()
        # **KRİTİK**: her POST'tan SONRA mutlaka HOME'u GET et
        r = s.get(urljoin(BASE, HOME), timeout=30); r.raise_for_status()
        tok_donem, tok_tablo, tok_taraf, y_list, d_list, y_val, y_txt, d_val, d_txt = read_state(r.text)
        if not (y_txt and "2025" in y_txt):
            raise RuntimeError(f"Yıl 2025 seçilemedi. Görünen yıl: {y_txt or '(yok)'}")

    # 3) 41. haftanın donemId'sini bu sayfadaki Donem select'inden bul
    donem_id, donem_label = pick_week_id(d_list, HAFTA_NO)
    if not donem_id:
        raise RuntimeError(f"41. hafta bulunamadı. İlk 3: {[x[1] for x in d_list[:3]]}")

    # 4) 41. haftayı POST et → SONRA HOME GET ile doğrula
    r = s.post(urljoin(BASE, DONEM),
               data={"yil": str(YIL), "donemId": str(donem_id), "__RequestVerificationToken": tok_donem},
               timeout=30)
    r.raise_for_status()
    r = s.get(urljoin(BASE, HOME), timeout=30); r.raise_for_status()
    tok_donem, tok_tablo, tok_taraf, y_list, d_list, y_val, y_txt, d_val, d_txt = read_state(r.text)
    if not (d_txt and f"{HAFTA_NO}. Hafta" in d_txt):
        raise RuntimeError(f"41. hafta seçilemedi. Görünen dönem: {d_txt or '(yok)'}")

    # 5) Taraf = Sektör → POST, sonra token yenilemek için HOME GET
    r = s.post(urljoin(BASE, TARAF),
               data={"tarafKodu": TARAF_KODU, "__RequestVerificationToken": tok_taraf},
               timeout=30)
    r.raise_for_status()
    r = s.get(urljoin(BASE, HOME), timeout=30); r.raise_for_status()
    tok_donem, tok_tablo, tok_taraf, *_ = read_state(r.text)

    # 6) Tablo = 289 → POST
    r = s.post(urljoin(BASE, HOME),
               data={"tabloId": str(TABLO_ID), "__RequestVerificationToken": tok_tablo},
               timeout=30)
    r.raise_for_status()

    # 7) Parse
    df = parse_rows(r.text)
    if df.empty:
        raise RuntimeError("Tablo boş veya parse edilemedi (289/Sektör/2025-41).")

    df.insert(0, "Taraf", "Sektör")
    df.insert(1, "Yil", YIL)
    df.insert(2, "Hafta", HAFTA_NO)
    df.insert(3, "TabloId", str(TABLO_ID))
    df.insert(4, "TabloAdi", "Krediler")
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print("[yazıldı]", OUT)
    print(df.head(5).to_string(index=False))

if __name__ == "__main__":
    main()
