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
