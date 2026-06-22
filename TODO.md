# Asuntosijoittaja – kehitystodo

## Bugikorjaukset (tehty 2026-06-22)
- [x] Oy ei saa tehdä poistoja asunto-osakkeesta (vain kiinteistöt)
- [x] Rahoitusvastike: lisätty rahastoitu/tuloutettu-valinta remontteihin
  - Rahastoitu → ei vähennyskelpoinen vuosittain, lisätään hankintamenoon myyntivoiton laskennassa
  - Tuloutettu → vähennyskelpoinen kaikilla (vero.fi)

---

## Sijoituslogiikka – prioriteetti 1

### Tyhjyysriski
- Lisää kenttä "Tyhjyys (%/v tai kk/v)" syöttöosioon
- Vähentää vuositason vuokratulosta ennen kaikkia laskelmia
- Oletusarvo voisi olla 0 mutta hint "esim. 1 kk = 8 %"

### Tappiontilanne ja alijäämähyvitys
- Jos yksityishenkilön vuokratulo < kulut → syntyy tappio
- Tappiosta 30 % vähennetään ansiotuloveroista (alijäämähyvitys, max 1 400 €/v)
- Tällä hetkellä näytetään vain negatiivinen kassavirta ilman tätä verohyötyä
- Vaikuttaa erityisesti isojen remonttivuosien laskelmiin

### Vuokra- ja kuluinflaatio
- Lisää kenttä "Vuokran kasvu (%/v)" – käytetään `rent * (1 + g/100)^yr` vuosittain
- Optio myös hoitovastikkeen kasvulle (%/v)
- 15 v laskelmassa vakiovuokra on epärealistinen

---

## Sijoituslogiikka – prioriteetti 2

### Oma perusparannus – jaksotus
- Nykyinen `repairs`-kenttä on tasainen kuukausivara, ei erittele vuosikorjausta vs. perusparannusta
- Vero.fi: oma perusparannus jaksotetaan 10 vuodelle (1/10 per vuosi) tai vähennetään myynnissä
- Remontti-listaan voisi lisätä "Perusparannus"-tyyppi joka jaksottaa automaattisesti

### Sensitiivisyysanalyysi
- "Mitä jos korko +2 %?" / "Mitä jos vuokra −10 %?" / "Mitä jos tyhjää 2 kk/v?"
- Toteutus: kolme nappia jotka muuttavat parametreja ±X ja laskevat uudelleen
- Tai erillinen herkkyystaulukko

### Vertailu vaihtoehtoiseen sijoitukseen
- "Jos laittaisit saman pääoman indeksirahastoon 7 %/v → X € horisontilla Y"
- Yksinkertainen laskelma joka näkyy tulososiossa rinnalla

---

## Koodilaatuparannukset

### Yksikkötestit laskentamoottorille
- `simulate()`-funktio on pitkä ja kriittinen – bugikorjaukset paljastivat ettei virheitä huomata
- Erota verotuslogiikka omaksi `calcTax(mode, params)`-funktioksi
- Node.js-testit (esim. `test.js`) tärkeimmille skenaarioille:
  - negatiivinen kassavirta
  - rahastoitu vs. tuloutettu rahoitusvastike
  - poiston käyttäytyminen asunto-osake vs. kiinteistö

### simulate()-refaktorointi
- Jaa: `calcYearlyRepairs()`, `calcTax()`, `calcSaleNet()` → helpompi lukea ja testata
- `yearly`-taulukko kasvaa kentillä, dokumentoi rakenne CLAUDE.md:hen

---

## UI-parannukset

- Tulossivulla näkyy vain aktiivinen viewMode (ind/comp) – harkitse rinnakkainen pikataulukko
- Mobiilinäkymä ei toimi (intentionaalinen, mutta voisi lisätä breakpointin)
- Tallennetun kohteen vertailu toiseen kohteeseen (ei priorisoitu)
