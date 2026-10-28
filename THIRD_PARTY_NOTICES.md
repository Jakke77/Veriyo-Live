# Aineistot ja riippuvuudet

Veriyö Live on Jakke77:n itsenäinen sovellus. Oma Python- ja C-koodi on MIT-lisensoitu
(LICENSE). Ajanlaskut ja Sää 1.12.3:n Veri Ajan säännöt ja tähtimalli ovat sen pohjana.

Seitsemän tähden J2000-paikat, magnitudit ja ominaisliikkeet ovat Yale Bright Star
Catalogue 5th Revised Ed. -luettelosta (Hoffleit & Warren, CDS V/50), HR 4301,
4295, 4554, 4660, 4905, 5054 ja 5191. Dokumentaatio:
https://cdsarc.cds.unistra.fr/ftp/V/50/ReadMe

PyMeeus 0.5.12 toimitetaan muuttamattomana Python-lähdekoodina `vendor/pymeeus`.
Dagoberto Salazar ja muut tekijät; LGPLv3. Täydet GPLv3- ja LGPLv3-lisenssit:
`vendor/pymeeus-0.5.12.dist-info/licenses/`.
Kirjaston lähde: https://github.com/architest/pymeeus
Kirjaston voi korvata omalla versiolla; sitä ei sulauteta suljettuun binääriin.

Numeerinen testiaineisto `tests/otava-astropy.json` on Ajanlaskut ja Sää -projektin
Astropy 7.1 / ERFA -vertailuaineisto. Astropya ei tarvita käytössä tai testeissä.
Uuden Kuu-teeman `tests/moon-astropy.json` on laskettu erikseen Astropy 7.1:n
sisäisellä ephemeridillä ilman verkkolatauksia, ilman ilmakehän taittumaa ja
merenpinnan korkeudelle. Sovellus käyttää PyMeeusin kuusarjoja.

## Uusien teemojen tähtiluettelo ja kuvitus

`veriyo_live/assets/bright-stars.json` on David Nashin / Astronexuksen HYG Database
4.1 -aineiston muokattu 634 tähden otos. HYG yhdistää Hipparcos-, Yale Bright Star-
ja Gliese-luetteloita. Valinta: HIP-tähdet magnitudiin 4.2 asti ja Pienen karhun
lisätähdet; valitut kentät, rektaskensio muunnettu tunneista asteiksi.
Otos säilyy **CC BY-SA 4.0** -lisenssillä. Lähteen tarkka commit-osoite ja SHA256
ovat JSON-tiedostossa; alkuperäinen lisenssimerkintä on `docs/HYG-LICENSE.txt`.
https://github.com/astronexus/HYG-Database · https://creativecommons.org/licenses/by-sa/4.0/

Uusien teemojen metsät, maisemat, kivikappaleet, kuun havainnollinen pintatekstuuri,
sumut ja koneiston merkit piirretään projektin omalla ohjelmakoodilla. Kuun tekstuuri
ei ole kraatterikartta. Avaruusmaisema ja Veri Ajan koneisto ovat kuvitusta.
Myös puron, kasvihuoneen, ruusujen, majakan ja vieraan maailman maisemien kuvitus
piirretään projektin omalla ohjelmakoodilla. Niiden päivärytmi perustuu valitun
aikavyöhykkeen paikallisiin kellonaikoihin.

Taustakuvapohjat `otava.png` ja `hiillos.png` on tehty 27.10.2026 kuvanmuokkauksella
projektin alkuperäisistä 24.10.2026 luoduista Veriyö-kuvista. Alkuperäisen kuvan
staattinen Otava ja Otava-kuvan kaaviokehät poistettiin, jotta ohjelma voi piirtää
seitsemän todellista tähteä vain kerran. Metsä ja muu tähtitausta ovat kuvitusta,
eivät valokuva kyseisen paikan oikeasta horisontista tai kattava tähtikartta.
Kuvat ovat projektin omaa kuvitusta; niille ei tällä muuteta alkuperäistä
jakelulisenssiä. Alkuperäiset kuvat säilyvät Ajanlaskut ja Sää -sovelluksessa.

PyQt6: Riverbank Computing, GPLv3 tai kaupallinen lisenssi.
https://www.riverbankcomputing.com/software/pyqt/
Qt6: The Qt Company ja muut tekijät; moduulikohtaiset GPL/LGPL-lisenssit.
https://www.qt.io/licensing/
Windows-paketti sisältää wheel-pakettien lisenssit ja metadatahakemistot sekä
muokattavan sovelluslähdekoodin. Ubuntu-paketti käyttää jakelun Qt/PyQt-paketteja.
Näiden riippuvuuksien lisenssit säilyvät voimassa oman koodin MIT-lisenssistä riippumatta.
Qt-lähteet: https://download.qt.io/archive/qt/6.8/6.8.2/submodules/
PyQt6-lähteet: https://pypi.org/project/PyQt6/6.8.1/#files

Windowsin yksityinen Python 3.12.10 -ajoympäristö: Python Software Foundation,
PSF-lisenssi; runtime/LICENSE.txt ja https://www.python.org/ftp/python/3.12.10/
Mukana oleva tzdata-wheel: Python Software Foundation / IANA-aikavyöhyketiedot;
sen dist-info sisältää alkuperäiset lisenssit ja lähdetiedot.

## Ubuntu live -lisäpaketti

45 Ubuntu-version alkuperäiset oletuskuvat ovat Canonical Ltd:n ja Ubuntu artwork -tekijöiden kuvitusta. Version ja kuvan yhdistämisen lähde on Corbin Davenportin The Spacebar -artikkeli (16.10.2026): https://www.spacebar.news/ubuntu-linux-default-wallpapers/ . Artikkelin tekstiä ei kopioida pakettiin.

Kuvakohtaiset lähdeosoitteet ja alkuperäisten SHA256-arvot ovat `veriyo_live/assets/ubuntu_catalog.json`-tiedostossa. Alkuperäiset lähdepakettien copyright-tiedostot ja niiden osoitteet ovat `ubuntu-pack/LICENSES`-kansiossa ja asennetun lisäpaketin mukana. Sovelluskoodin MIT-lisenssi ei muuta kuvituksen lisenssejä.

Muutokset: 1920×1080-sovitus, pieni paikallinen muodonmuutos ja rauhalliset siirtymät. Tämä on itsenäinen fanisovitus; Ubuntu ja sen tavaramerkit kuuluvat Canonicalille.
