# Asuntosijoittaja – projektin ohjeet Claude CLI:lle

## Projektin tavoite

Yksinkertainen web-sovellus, joka arvioi asuntosijoituksen kannattavuutta 5/10/15 vuoden horisontilla. Käyttäjä syöttää kohteen osoitteen → sovellus hakee automaattisesti postinumeron ja alueen markkinahintatiedot Tilastokeskuksen API:sta → näyttää laskennan vertailuna yksityishenkilönä tai osakeyhtiön kautta.

## Tech stack

- **Backend:** FastAPI (Python 3.11+)
- **Frontend:** Yksittäinen `index.html` – vanilla JS, Chart.js CDN, ei build-steppiä
- **Tietokanta:** SQLite (`kohteet.db`), Python stdlib `sqlite3`
- **Riippuvuudet:** `fastapi`, `uvicorn[standard]`, `httpx`, `requests`

## Rakenne

```
asuntosijoittaja/
├── CLAUDE.md
├── main.py           # FastAPI-palvelin + API-endpointit
├── requirements.txt
├── kohteet.db        # SQLite, luodaan automaattisesti käynnistyksessä
└── frontend/
    └── index.html    # Koko UI tässä tiedostossa
```

Backend servaa `frontend/index.html`:n juuripolusta (`/`). Kaikki ulkoiset API-kutsut (stat.fi, Nominatim) tehdään backendin kautta – ei CORS-ongelmia frontendissä.

## Backend-endpointit (main.py)

### GET /api/geocode

Muuntaa osoitteen postinumeroksi Nominatim-geokoodauksen avulla.

- **Parametrit:** `address` (str)
- **Vastaus:** `{ postinumero, kaupunki, katuosoite }`
- **Toteutus:** `https://nominatim.openstreetmap.org/search` – User-Agent: `asuntosijoittaja/1.0` vaaditaan

### GET /api/hinnat

Hakee alueen keskimääräiset ostohinnat Tilastokeskuksen PxWeb-API:sta (taulu `ashi/13mt.px`).

- **Parametrit:** `postinumero` (str), `talotyyppi` (str: `"1"`=yksiöt, `"2"`=kaksiot, `"3"`=kolmiot+, `"4"`=rivitalot)
- **Vastaus:** `{ postinumero, talotyyppi, viimeisin_neliohinta, kvartaali, historia }`
- **Toteutus:** Hae metadata dynaamisesti GET-kutsulla → POST query. Aggregoi kvartaaleittain vuosittain.

### GET /api/vuokrat

Hakee alueen vuokramarkkinahinnat (taulu `asvu/15fa.px`, vapaarahoitteiset).

- **Parametrit:** `kaupunki` (str, esim. `"Helsinki"`), `huoneluku` (str: `"1"`, `"2"`, `"3"`)
- **Vastaus:** `{ kaupunki, alue_koodi, vuokra_per_m2_kk }`
- **Huom:** `15fa.px` käyttää kuntakoodia, ei postinumeroa. `_KUNTAKOODI`-hakutaulu (main.py) muuntaa kaupunginnimet → koodit. Tuntematon kaupunki → `"SSS"` (koko maa).

### POST /api/kohteet

Tallenna kohde. Body: `{ nimi: str, params: dict, tulokset: dict }` (Pydantic `KohdeIn`).

### GET /api/kohteet

Hae kaikki kohteet uusimmasta vanhimpaan. Vastaus: lista `{ id, nimi, luotu, params, tulokset }`.

### PUT /api/kohteet/{id}

Päivitä tallennettu kohde. Sama body kuin POST.

### DELETE /api/kohteet/{id}

Poista kohde.

## Frontend (frontend/index.html)

Yksisivuinen laskuri. Kaikki CSS ja JS tässä tiedostossa. Chart.js ladataan CDN:stä.

**Layout:** `.app-layout` CSS Grid, `grid-template-columns: 1fr 2fr`. Vasen on `<aside class="sidebar">` (sticky). Ei responsiivisia breakpointteja – sovellus on optimoitu lg-näytölle.

### Käyttäjävirta

**1. Kohteen haku:**
- Pudotusvalikko `#hakuTyyppi`: Yksiö / Kaksio / Kolmio+ / Rivitalo (ohjaa molemmat API-kutsut)
- Osoitekenttä → "Hae markkinatiedot" → `GET /api/geocode` → `GET /api/hinnat` + `GET /api/vuokrat`
- Market-badget näyttävät alueen neliöhinnan ja keskivuokran

**2. Laskentatiedot:**
- Velaton hinta, neliöt, oma pääoma, vuokra/kk, laina-aika, korko, hoitovastike, remonttivara, arvonnousu
- Asuntotyyppi-toggle: Asunto-osake (2 %) | Kiinteistö (4 %) – ohjaa varainsiirtoveroa

**3. Remontit:**
- Lista kertaluonteisista remonteista: kuvaus, vuosi (1–15), summa (€), tyyppi (taloyhtiö/oma)
- Lisätään `totalRepairs = p.repairs + remoSum` ko. vuodelle – vaikuttaa kassavirtaan ja veroon

**Tulokset (5 / 10 / 15 v):**
- KPI-kortit: kassavirta/kk, oma pääoma, myyntivoitto, vuosituotto p.a.
- Vertailutaulukko yksityinen vs. osakeyhtiö
- Kassavirtakaavio (Chart.js bar) ja varallisuuskehityskaavio (Chart.js line)
- Vuosikohtainen erittely (yksityishenkilö)

### Tärkeät JS-funktiot

| Funktio | Kuvaus |
|---|---|
| `val(id)` | `parseFloat(...)` – siivoaa välilyönnit, muuntaa pilkun pisteeksi |
| `simulate(p, mode)` | Laskentamoottori, palauttaa `{ yearly, horizons }` |
| `calculate()` | Validoi kentät, kutsuu simulaatioita, näyttää tulokset |
| `fetchMarket()` | Geocode → hinnat + vuokrat, käyttää `hakuTyyppi`-valintaa |
| `loadKohde(id)` | Täyttää lomakkeen, palauttaa markkinatiedot + remontit |
| `clearForm()` | Tyhjentää kaiken, nollaa `activeKohdeId` |
| `addRemontti()` / `renderRemontit()` | Remontit-listan hallinta |
| `h_(k, mode, field)` | Lukee horizons-objektin avaimella string tai number |

### State-muuttujat

```javascript
let mkt = {};           // { geo, hinnat, vuokrat } – haettu markkinatieto
let res = null;         // { ind, comp, p } – viimeisin laskentatulos
let horizon = 5;        // aktiivinen horisontti (5/10/15)
let assetType = 'osake';
let activeKohdeId = null;
let remontit = [];      // [{ id, nimi, vuosi, summa, tyyppi }]
let _rId = 0;           // remontit-id-laskuri
let savedKohteet = [];
let compH = 5;          // vertailutaulukon horisontti
```

## Verotuslogiikka (JavaScript)

### Yksityishenkilö

- Vuokratulo: pääomatulovero 30 % (34 % yli 30 000 €/v)
- Vähennykset: korkokulut, hoitovastike, remonttivara + kertaluonteiset remontit
- Myyntivoitto: `Math.min(todellinen voitto, propVal × (1 − acq)) × 0.30`
  - `acq` = 0.20 (omistus < 10 v) tai 0.40 (≥ 10 v) – hankintameno-olettama
- Varainsiirtovero hankinnassa: 2 % (asunto-osake) tai 4 % (kiinteistö)

### Osakeyhtiö

- Yhtiöverokanta: 20 %
- Vähennykset: kaikki kulut + poistot rakennuksesta (70 % hinnasta × 4 %/v)
- Myyntivoitto: 20 % yhtiövero → osinkojen nosto ~12 % lisäverotus (yhteensä ~30 %)
- Hallinto- ja kirjanpitokulut: 1 500 €/v

## Lainan laskenta

**Annuiteetti:** `P × r × (1+r)^n / ((1+r)^n − 1)` jossa `r = vuosikorko/12`, `n = kuukaudet`

## Tietokanta (kohteet.db)

SQLite, luodaan automaattisesti käynnistyksessä.

**Taulu `kohteet`:** `id, nimi, luotu (ISO), params (JSON), tulokset (JSON)`

**params-kentät:** `price, sqm, equity, rent, loanYears, rate, maintenance, repairs, appreciation, assetType, address, hakuTyyppi, geo, hinnat, vuokrat, remontit`

**tulokset-rakenne:** `{ ind: { yearly, horizons }, comp: { yearly, horizons } }`

**Huom:** `horizons`-objektin avaimet ovat JSON-kierroksen jälkeen merkkijonoja (`"5"`, `"10"`, `"15"`). `h_()`-apufunktio osaa hakea kummallakin tavalla.

## Kehityksen aloitus

```bash
pip install fastapi uvicorn httpx requests
uvicorn main:app --reload
# Frontend: http://localhost:8000
```

## Tärkeää

- **Nominatim:** käytä aina `User-Agent`-headeria, rate limit 1 req/s
- **Stat.fi PxWeb:** hae metadata dynaamisesti GET-kutsulla – älä hardkoodaa muuttujakoodeja
- **Cache:** `_cache`-dict + TTL 3600 s – stat.fi on hidas eikä data muutu usein
- **Euromäärät:** kokonaislukuina ilman senttejä (`Math.round`)
- **UI:** suomenkielinen läpi linjan
- **Desimaalierotin:** piste (`3.5`), ei pilkku – kerrottu käyttäjälle otsikossa. `val()`-funktio muuntaa automaattisesti.

## CLAUDE.md:n ylläpito

Päivitä tätä tiedostoa **samassa commitissa** kuin koodimuutos:

- Uusi endpoint tai parametri → Backend-endpointit-osio
- Uusi riippuvuus → Tech stack + requirements.txt
- Muutos hakemistorakenteeseen → Rakenne-osio
- Muutos verotuslogiikkaan → Verotuslogiikka-osio
- Uusi state-muuttuja tai apufunktio → Frontend-osio
- Muutos params-kenttiin → Tietokanta-osio
