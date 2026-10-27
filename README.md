# Veriyö Live

**Elävä Otavan tähtitaustakuva Windowsille ja Ubuntu GNOME:lle.**
Maisema pysyy paikallaan, Otava seuraa oikeaa tähtitaivasta. Mukana Veri Ajan
777 päivän ajanlasku, joka perustuu paikalliseen Suomen aikaan.

**[Lataa uusin julkaisu](https://github.com/Jakke77/Veriyo-Live/releases/latest)** ·
[Julkaisut](https://github.com/Jakke77/Veriyo-Live/releases) ·
[Ilmoita ongelmasta](https://github.com/Jakke77/Veriyo-Live/issues)

![Veriyö Live työpöydällä](screenshots/taustakuva.png)

## Versio 0.1.1

Oma taustakuvasovellus Windows 10/11:lle ja Ubuntu GNOME:lle. Maisema pysyy paikallaan,
seitsemän oikeaa Otavan tähteä liikkuu antamasi paikan tähtitaivaan mukana.
Ohjelma toimii kokonaan ilman verkkoyhteyttä ja ilman Ajanlaskut ja Sää -asennusta.

## Käyttö

1. Avaa **Veriyö Live** sovellusvalikosta (Ubuntu) tai **Veriyo-Live.exe** puretusta Windows-kansiosta.
2. Valitse **Otava ja järvi** tai **Hiillos**. Oletuspaikka on **65.071562, 25.507046**.
3. Kokeile halutessasi **Nopeutettu esikatselu**. Se ei muuta työpöytää tai vientikuvan aikaa.
4. Paina **Ota elävä tausta käyttöön**. Kuva päivittyy oletuksena minuutin välein.
5. Valitse **Päivämäärä**: **Piilossa**, **Veri Aika**, **Tavallinen päivämäärä** tai **Molemmat**. Valinta tallentuu heti ja päivittää myös käynnissä olevan taustakuvan.
6. **Pysäytä päivitys** jättää viimeisen kuvan. **Palauta aiempi tausta** palauttaa varmuuskopion.

Päivämäärän **Piilossa**-valinta poistaa kaikki päivämäärät ja kellonajan taustakuvasta; koordinaatit jäävät alareunaan. **Tavallinen päivämäärä** näyttää gregoriaanisen päivämäärän ja kellonajan Suomen ajassa. Esikatselun aikaleima sovelluksen sisällä säilyy näkyvissä. Vanhan version päivämäärävalinta säilytetään päivityksessä.

Otava käyttää oikeaa tähtiaikaa: yksi kierros kestää noin **23 h 56 min**. Veri Ajan
vuosi on erillinen 777 paikallisen päivän ajanlasku, joka alkaa 26.6.2026 klo
01:07:07 Suomen aikaa; uusi päivä ja viikko vaihtuvat klo 01:07:07 myös kesä-/talviajassa.
Otavaa ei keinotekoisesti nopeuteta 777 päivän kalenteriin. Liike näyttää myös oikean vuodenajan.

Kuva katsoo pohjoiseen stereografisessa projektiossa. **Länsi on vasemmalla, itä oikealla,
zeniitti ylhäällä.** Pohjoisen taivaannavan korkeus on havaintopaikan leveysaste,
oletuksena 65,071562°. Horisonttiviiva on havainnollinen; kuvan metsä ei mallinna
Oulun oikeaa maastoa. Alkaid, hännän viimeinen tähti, on ympyröity. Vain seitsemän
ohjelmalla piirrettyä tähteä edustavat laskettua taivasta; pohjakuvan sumut ja muut tähdet ovat kuvitusta.

## Ubuntu

Asenna ladattu paketti:

```bash
sudo apt install ./veriyo-live_0.1.1_all.deb
```

Sovellus löytyy nimellä **Veriyö Live**. Komento: `veriyo-live`.
Taustan vaihtaminen tarvitsee kirjautuneen GNOME-istunnon (Wayland tai X11).
KDE/Xfce eivät kuulu tähän ensimmäiseen versioon; kuvan tallennusta voi käyttää niissäkin.
GNOME käyttää yleensä työpöytäkuvan sumennettua versiota myös lukituksessa.
Valinnainen erillinen lukituskuva-asetus toimii vain, jos GNOME-versio tukee sitä;
aktiivinen Dia Wall 77 tai toinen taustakuvaohjelma voi ohittaa tämän kuvan.
Pidä vain yksi taustakuvaa vaihtava ohjelma kerrallaan käytössä.

## Windows

Pura **koko ZIP** pysyvään kansioon. Avaa **Veriyo-Live.exe**.
Pythonia tai järjestelmänvalvojan oikeuksia ei tarvita. **Luo-pikakuvakkeet.cmd**
tekee pikakuvakkeet vain tämän käyttäjän työpöydälle ja Käynnistä-valikkoon.
**Tarkista-toiminta.cmd** ajaa mukana tulevat testit muuttamatta taustakuvaa.

Windowsin työpöytä käyttää järjestelmän omaa taustakuvatoimintoa. Lukituskuvan
vaihto käyttää käyttäjäkohtaista Windows WinRT -toimintoa, jos Windows sallii sen.
Ennen ensimmäistä vaihtoa sovellus yrittää tallentaa nykyisen lukituskuvan; jos
varmuuskopiointi ei onnistu, vaihtoa ei tehdä. Spotlight- tai diaesitysvalintaa
sovellus ei voi palauttaa kuvatiedostosta: valitse se tarvittaessa Windowsin omista
**Mukauttaminen → Lukitusnäyttö** -asetuksista. Yrityskäytäntöjä ei ohiteta.

## Lukitusnäytön ja live-kuvan rajat

Tämä ensimmäinen versio on **ajastetusti päivittyvä taustakuva**, ei video eikä
60 FPS -animaatio. Tähtien todellinen hidas liike ei tarvitse videotoistoa.
Avoimen sovelluksen esikatselu päivittyy normaalisti kerran sekunnissa ja
nopeutettuna 10 kertaa sekunnissa; työpöytä päivittyy 1, 5 tai 26 minuutin välein.
Kumpikaan käyttöjärjestelmä ei takaa, että **jo näkyvissä oleva lukitusnäyttö**
lataa kuvan uudelleen. Sitä ei väitetä jatkuvasti animoiduksi. Tietokoneen
nukkuessa ei tehdä päivityksiä; herätessä asento korjataan.

Kaikki näytöt saavat saman kuvan päänäytön tarkkuudella. Erilliset näyttökohtaiset
sommittelut, vapaa sijaintialue ja sujuva videotausta voidaan tehdä myöhemmin.
Tämän sommittelun sijainti on rajattu leveysasteille 60–70° N. Tähtimalli tukee vuosia 1900–2100.

## Taustalla käyttö ja palautus

Valitse **Käynnistä elävä tausta kirjautuessani sisään** ja tallenna asetukset.
Suljettu ikkuna jää ilmoitusalueelle, kun tausta on käytössä ja ilmoitusalue on saatavilla.
Ilman ilmoitusaluetta ikkuna pidetään näkyvillä taustakäynnistyksessä. Ilmoitusalueen
**Lopeta** lopettaa sovelluksen jättäen viimeisen kuvan; palautuspainike on erillinen.

Aiempi tausta tallentuu ennen ensimmäistä muutosta ja säilyy myös ohjelman tai
koneen uudelleenkäynnistyksen yli. Käynnistys jatkaa samaa varmuuskopiota eikä
korvaa sitä omalla kuvallaan. Jos vaihdat työpöytäkuvaa muualla, palautus säilyttää
sen ja uusi automaattinen ajo pyytää ensin palautustoiminnon käyttöä. Lukituskuvan
valinnan muuttaminen kesken varmuuskopion vaatii ensin palautuksen.

Windowsissa ZIP-kansion siirron tai uuden version jälkeen avaa uusi sovellus ja
paina **Tallenna asetukset**; kirjautumiskäynnistyksen polku päivittyy tähän kansioon.
Asennuksen poisto ei poista henkilökohtaisia asetuksia tai varmuuskopiota. Palauta
aiempi tausta ja poista kirjautumiskäynnistys käytöstä ennen poistamista.

Tiedot ovat erillään Ajanlaskut ja Sää -asetuksista:

- Ubuntu: `~/.local/share/veriyo-live/` (tai XDG_DATA_HOME).
- Windows: `%LOCALAPPDATA%\VeriyoLive\`.

Vain kaksi vaihtuvaa JPEG-kuvaa säilytetään, joten päivitykset eivät kasvata
kuva-arkistoa loputtomasti. Viimeisin kuvatiedosto säilytetään lopetettaessa.

## Lähdekoodista ja kuvan viennistä

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
QT_QPA_PLATFORM=offscreen .venv/bin/python main.py --self-test
QT_QPA_PLATFORM=offscreen .venv/bin/python main.py --export veriyo.png --at 2026-10-27T21:00:00+02:00 --size 3840x2160
```

Windowsissa vastaavat komennot käyttävät `.venv\Scripts\python.exe`-ohjelmaa.
Jos ajat lähdekoodia ilman Windowsin mukana tulevaa tzdataa, asenna myös `pip install tzdata`.

## Päivitys versiosta 0.1.0

Windowsissa lopeta vanha Veriyö Live ilmoitusalueen **Lopeta**-valinnalla ja pura uusi ZIP omaan pysyvään kansioonsa. Avaa uusi **Veriyo-Live.exe**. Jos kirjautumiskäynnistys on valittu, paina uudessa versiossa **Tallenna asetukset**, jotta polku osoittaa uuteen kansioon. Ubuntu-paketti päivittää aiemman asennuksen; sulje vanha ohjelma ja avaa päivitetty sovellus.

## Tarkistukset

Tähtimallin tuloksia verrataan riippumattomaan Astropy/ERFA-aineistoon. Testit
kattavat päivärajan, DST:n, koko vuorokauden geometrian, molemmat kuvat,
päivityksen, pysäytyksen, uudelleenkäynnistyksen ja keskeytyneen muutoksen palautuksen.
Qt-käyttöliittymä ja pakattu Windows-ajoympäristö tarkistetaan erikseen.
Pilviympäristössä ei ole käyttäjän oikeaa Ubuntu- tai Windows-lukitusnäyttöä:
niiden näkyvä käyttäytyminen tarvitsee vielä kokeilun omalla koneella.


## Kehitys ja paketointi

Tämä repo on itsenäinen: tarvitut PyMeeus-lähdekoodit ja lisenssit sisältyvät
`vendor`-hakemistoon. Koko Ajanlaskut ja Sää -sovellusta ei tarvita.

```bash
python3 packaging/build.py ubuntu --output outputs/ubuntu
```

Windowsin rakentaja tarvitsee `packaging/downloads.json`-tiedoston tarkisteita
vastaavat ladatut riippuvuudet ja Zig 0.15.2:n. GitHub Actions tekee latauksen,
tarkistaa tarkisteet ja rakentaa paketit automaattisesti. Se ei pakkaa mukaan
henkilökohtaisia asetuksia, taustakuvan varmuuskopioita tai sovelluksen tietoja.

Päivityksen yhteydessä muuta `veriyo_live/__init__.py`-versionumero ja
`packaging/launcher.rc`-versionumerot. `main`-haaran päivitys ajaa testit ja
rakentaa paketit ladattaviksi Actionsin artefakteista. Version mukaisen tagin
(esimerkiksi `v0.1.1`) julkaisu rakentaa molemmat käyttöjärjestelmäpaketit ja
julkaisee ne yhdessä lähde-ZIP:n ja SHA256-tarkisteiden kanssa. Julkaisua ei
tehdä, jos kumman tahansa käyttöjärjestelmän tarkistus epäonnistuu.

## Lisenssit ja alkuperä

Oma ohjelmakoodi: [MIT](LICENSE). Riippuvuuksien ja kuvituksen ehdot sekä
tekijämerkinnät: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Julkinen repo ei muuta kolmansien osapuolten tai taustakuvien lisenssiehtoja.
[Projektin alkuperä](docs/ALKUPERA.md).
