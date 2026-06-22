from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import httpx
import time
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel

app = FastAPI(title="Asuntosijoittaja API")

DB_PATH = Path(__file__).parent / "kohteet.db"

def _db_init():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kohteet (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                nimi    TEXT    NOT NULL,
                luotu   TEXT    NOT NULL,
                params  TEXT    NOT NULL,
                tulokset TEXT   NOT NULL
            )
        """)

@app.on_event("startup")
def startup():
    _db_init()

class KohdeIn(BaseModel):
    nimi: str
    params: dict
    tulokset: dict

@app.post("/api/kohteet", status_code=201)
def tallenna_kohde(data: KohdeIn):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO kohteet (nimi, luotu, params, tulokset) VALUES (?, ?, ?, ?)",
            (data.nimi, datetime.now().isoformat(timespec="seconds"),
             json.dumps(data.params, ensure_ascii=False),
             json.dumps(data.tulokset, ensure_ascii=False))
        )
        conn.commit()
    return {"id": cur.lastrowid, "nimi": data.nimi}

@app.get("/api/kohteet")
def hae_kohteet():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, nimi, luotu, params, tulokset FROM kohteet ORDER BY luotu DESC"
        ).fetchall()
    return [
        {"id": r[0], "nimi": r[1], "luotu": r[2],
         "params": json.loads(r[3]), "tulokset": json.loads(r[4])}
        for r in rows
    ]

@app.put("/api/kohteet/{kohde_id}")
def paivita_kohde(kohde_id: int, data: KohdeIn):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE kohteet SET nimi=?, params=?, tulokset=? WHERE id=?",
            (data.nimi,
             json.dumps(data.params, ensure_ascii=False),
             json.dumps(data.tulokset, ensure_ascii=False),
             kohde_id)
        )
        conn.commit()
    return {"id": kohde_id, "nimi": data.nimi}

@app.delete("/api/kohteet/{kohde_id}")
def poista_kohde(kohde_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM kohteet WHERE id = ?", (kohde_id,))
        conn.commit()
    return {"ok": True}

_cache: dict = {}
CACHE_TTL = 3600

def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and time.time() - entry[1] < CACHE_TTL:
        return entry[0]
    return None

def _cache_set(key: str, value):
    _cache[key] = (value, time.time())

HEADERS = {"User-Agent": "asuntosijoittaja/1.0"}
ASHI_BASE = "https://pxdata.stat.fi/PxWeb/api/v1/fi/StatFin/ashi/"
ASVU_BASE = "https://pxdata.stat.fi/PxWeb/api/v1/fi/StatFin/asvu/"


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "frontend" / "index.html")


@app.get("/api/geocode")
async def geocode(address: str):
    key = f"geo:{address.lower().strip()}"
    if cached := _cache_get(key):
        return cached

    async with httpx.AsyncClient(headers=HEADERS, timeout=10.0) as c:
        r = await c.get(
            "https://nominatim.openstreetmap.org/search",
            params={"format": "json", "addressdetails": 1, "q": address, "countrycodes": "fi", "limit": 1},
        )

    data = r.json()
    if not data:
        raise HTTPException(status_code=404, detail="Osoitetta ei löydy")

    addr = data[0].get("address", {})
    postinumero = addr.get("postcode", "").replace(" ", "")
    if not postinumero:
        raise HTTPException(status_code=404, detail="Postinumeroa ei löydy tälle osoitteelle")

    result = {
        "postinumero": postinumero,
        "kaupunki": addr.get("city") or addr.get("town") or addr.get("municipality", ""),
        "katuosoite": data[0].get("display_name", "").split(",")[0].strip(),
    }
    _cache_set(key, result)
    return result


async def _px_meta(url: str) -> dict:
    key = f"meta:{url}"
    if cached := _cache_get(key):
        return cached
    async with httpx.AsyncClient(headers=HEADERS, timeout=30.0) as c:
        r = await c.get(url)
    r.raise_for_status()
    meta = r.json()
    _cache_set(key, meta)
    return meta


async def _px_query(url: str, query: dict) -> list:
    async with httpx.AsyncClient(headers=HEADERS, timeout=30.0) as c:
        r = await c.post(url, json=query)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Stat.fi vastasi {r.status_code}")
    return r.json().get("data", [])


def _find_var(variables: list, *hints: str) -> dict | None:
    for v in variables:
        combined = (v.get("code", "") + " " + v.get("text", "")).lower()
        if any(h.lower() in combined for h in hints):
            return v
    return None


TALOTYYPPI_NIMET = {
    "1": "Kerrostalo yksiöt",
    "2": "Kerrostalo kaksiot",
    "3": "Kerrostalo kolmiot+",
    "4": "Rivitalot yhteensä",
}


@app.get("/api/hinnat")
async def hinnat(postinumero: str, talotyyppi: str = "2"):
    key = f"hinnat:{postinumero}:{talotyyppi}"
    if cached := _cache_get(key):
        return cached

    url = ASHI_BASE + "13mt.px"
    meta = await _px_meta(url)
    vs = meta.get("variables", [])

    aika = _find_var(vs, "neljännes", "quarter", "vuosi")
    posti = _find_var(vs, "postinumero", "postal")
    tyyppi = _find_var(vs, "talotyyppi", "rakennustyyppi", "tyyppi")
    tiedot = _find_var(vs, "tiedot")

    if not all([aika, posti, tyyppi, tiedot]):
        raise HTTPException(status_code=500, detail="Muuttujia ei tunnistettu stat.fi-vastauksesta")

    if postinumero not in posti["values"]:
        raise HTTPException(status_code=404, detail=f"Postinumeroa {postinumero} ei löydy asuntohintatilastoista")

    if talotyyppi not in tyyppi["values"]:
        talotyyppi = tyyppi["values"][0]

    nelio_code = tiedot["values"][0]

    query = {
        "query": [
            {"code": aika["code"], "selection": {"filter": "top", "values": ["20"]}},
            {"code": posti["code"], "selection": {"filter": "item", "values": [postinumero]}},
            {"code": tyyppi["code"], "selection": {"filter": "item", "values": [talotyyppi]}},
            {"code": tiedot["code"], "selection": {"filter": "item", "values": [nelio_code]}},
        ],
        "response": {"format": "json"},
    }

    rows = await _px_query(url, query)
    if not rows:
        raise HTTPException(status_code=404, detail="Ei hintatietoja tälle alueelle")

    yearly: dict[str, list[float]] = {}
    for row in rows:
        kvartaali = row["key"][0]
        val = row["values"][0]
        if val and val.strip() not in (".", ""):
            try:
                year = kvartaali[:4]
                yearly.setdefault(year, []).append(float(val))
            except (ValueError, IndexError):
                pass

    historia = {y: round(sum(v) / len(v)) for y, v in sorted(yearly.items()) if v}

    viimeisin = None
    viimeisin_kvartaali = None
    for row in reversed(rows):
        val = row["values"][0]
        if val and val.strip() not in (".", ""):
            try:
                viimeisin = round(float(val))
                viimeisin_kvartaali = row["key"][0]
                break
            except ValueError:
                pass

    result = {
        "postinumero": postinumero,
        "talotyyppi": TALOTYYPPI_NIMET.get(talotyyppi, talotyyppi),
        "viimeisin_neliohinta": viimeisin,
        "kvartaali": viimeisin_kvartaali,
        "historia": historia,
    }
    _cache_set(key, result)
    return result


# 15fa.px käyttää kuntakoodia (ei postinumeroa) – kartoitus kaupungin nimestä
_KUNTAKOODI: dict[str, str] = {
    "helsinki": "091", "espoo": "049", "kauniainen": "049",
    "vantaa": "092", "tampere": "837", "turku": "853",
    "oulu": "564", "lahti": "398", "kuopio": "297",
    "jyväskylä": "179", "lappeenranta": "405", "joensuu": "167",
    "hämeenlinna": "109", "kotka": "285", "kouvola": "286",
    "pori": "609", "rauma": "684", "vaasa": "905",
    "rovaniemi": "698", "kajaani": "205", "kokkola": "272",
    "seinäjoki": "743", "mikkeli": "491", "riihimäki": "694",
    "porvoo": "638", "hyvinkää": "106", "järvenpää": "186", "kerava": "245",
}


@app.get("/api/vuokrat")
async def vuokrat(kaupunki: str, huoneluku: str = "2"):
    alue_koodi = _KUNTAKOODI.get(kaupunki.lower().strip(), "SSS")
    key = f"vuokrat:{alue_koodi}:{huoneluku}"
    if cached := _cache_get(key):
        return cached

    url = ASVU_BASE + "15fa.px"
    meta = await _px_meta(url)
    vs = meta.get("variables", [])

    alue = _find_var(vs, "alue")
    rahoitus = _find_var(vs, "rahoitus")
    huone = _find_var(vs, "huoneluku", "huone")
    aika = _find_var(vs, "neljännes", "quarter", "vuosi", "timeperiod")
    tiedot = _find_var(vs, "tiedot", "contentscode")

    if not all([alue, huone, aika, tiedot]):
        raise HTTPException(status_code=500, detail="Muuttujia ei tunnistettu vuokratilastoista")

    if alue_koodi not in alue["values"]:
        alue_koodi = "SSS"

    if huoneluku not in huone["values"]:
        huoneluku = "SSS"

    # keskineliovuokra on contentscode-listan 4. arvo
    vuokra_code = next(
        (v for v in tiedot["values"] if "keskineliovuokra" in v and "lkm" not in v and "_u" not in v),
        tiedot["values"][0],
    )

    query_parts = [
        {"code": alue["code"], "selection": {"filter": "item", "values": [alue_koodi]}},
        {"code": huone["code"], "selection": {"filter": "item", "values": [huoneluku]}},
        {"code": aika["code"], "selection": {"filter": "top", "values": ["4"]}},
        {"code": tiedot["code"], "selection": {"filter": "item", "values": [vuokra_code]}},
    ]
    if rahoitus:
        vapaa = "1" if "1" in rahoitus["values"] else rahoitus["values"][0]
        query_parts.insert(1, {"code": rahoitus["code"], "selection": {"filter": "item", "values": [vapaa]}})

    rows = await _px_query(url, {"query": query_parts, "response": {"format": "json"}})

    viimeisin = None
    for row in reversed(rows):
        val = row["values"][0]
        if val and val.strip() not in (".", ""):
            try:
                viimeisin = round(float(val), 1)
                break
            except ValueError:
                pass

    result = {"kaupunki": kaupunki, "alue_koodi": alue_koodi, "vuokra_per_m2_kk": viimeisin}
    _cache_set(key, result)
    return result
