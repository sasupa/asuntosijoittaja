# Asuntosijoittajalaskuri

Yksinkertainen web-sovellus sijoitusasunnon kannattavuuden arviointiin 5, 10 ja 15 vuoden horisontilla. Vertaa sijoitusta yksityishenkilönä tai osakeyhtiön kautta.

## Ominaisuudet

- **Automaattiset markkinatiedot** – syötä osoite ja sovellus hakee alueen neliöhinnat ja vuokramarkkinahinnat suoraan Tilastokeskuksen avoimesta API:sta
- **Hintatrendi** – neliöhinta-badgessa näkyy alueen 5 vuoden hintakehitys (%/v), joka auttaa arvioimaan realistisen arvonnousu-oletuksen
- **Asuntotyyppikohtainen haku** – yksiö, kaksio, kolmio+ tai rivitalo ohjaa molemmat markkinatietohaut
- **Kaksi sijoitusmuotoa** – yksityishenkilö vs. osakeyhtiö verotuksineen rinnakkain
- **Remonttisuunnittelu** – lisää taloyhtiön ja omat remontit vuosikohtaisesti; valitse kertasuoritus, rahoitusvastike tai laina – kuukausierä lasketaan automaattisesti
- **Tulosvaihtoehto** – liukukytkimellä valitaan tarkastellaanko tuloksia yksityishenkilönä vai osakeyhtiönä; vuosikohtainen erittely valitulle sijoitusmuodolle
- **Kohteiden tallennus** – tallenna useita kohteita ja vertaile niitä rinnakkain

## Käyttö

### Asennus

```bash
git clone https://github.com/your-username/asuntosijoittaja.git
cd asuntosijoittaja
pip install -r requirements.txt
```

### Käynnistys

```bash
uvicorn main:app --reload
```

Avaa selaimessa: [http://localhost:8000](http://localhost:8000)

### Työnkulku

1. **Kohteen haku** – valitse asuntotyyppi, kirjoita osoite ja hae markkinatiedot
2. **Laskentatiedot** – täytä hinta, neliöt, oma pääoma, vuokra, lainaehdot ja vastike
3. **Remontit** – lisää tiedossa olevat taloyhtiön ja omat remontit; valitse kertasuoritus, rahoitusvastike tai laina
4. Paina **Laske sijoituksen tuotto** ja tarkastele tuloksia eri horisonteilla
5. Tallenna kohde sivupalkkiin ja vertaile useita kohteita rinnakkain

## Tietolähteet

| Lähde | Sisältö |
|---|---|
| [Tilastokeskus – ashi/13mt.px](https://pxdata.stat.fi) | Ostohinnat postinumeroalueittain (neljännesvuosittain) |
| [Tilastokeskus – asvu/15fa.px](https://pxdata.stat.fi) | Vapaarahoitteiset vuokrat kunnittain |
| [Nominatim / OpenStreetMap](https://nominatim.openstreetmap.org) | Osoitteen geokoodaus |

Kaikki tietolähteet ovat avoimia eikä API-avaimia tarvita.

## Tech stack

- **Backend:** Python 3.11+, FastAPI, uvicorn, httpx
- **Frontend:** Vanilla JS, yksittäinen HTML-tiedosto (ei ulkoisia skriptejä)
- **Tietokanta:** SQLite (stdlib `sqlite3`)

## Laskentaperiaatteet

### Yksityishenkilö

- Pääomatulovero 30 % (34 % yli 30 000 €/v vuokratuloista)
- Vähennykset: korkokulut, hoitovastike, remontit
- Myyntivoittovero: hankintameno-olettama 20 % (alle 10 v) tai 40 % (vähintään 10 v) – käytetään jos edullisempi kuin todellinen voitto
- Varainsiirtovero: 2 % (asunto-osake) tai 4 % (kiinteistö)

### Osakeyhtiö

- Yhtiöverokanta 20 %
- Vähennykset: kaikki kulut + rakennuspoistot (70 % hinnasta × 4 %/v)
- Myyntivoittovero 20 % + osinkojen nostosta ~12 % (optimaalinen osingonjako)
- Hallinto- ja kirjanpitokulut 1 500 €/v

### Laina

Annuiteettilaskenta: `P × r × (1+r)^n / ((1+r)^n − 1)`

## Lisenssi

MIT
