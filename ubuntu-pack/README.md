# Ubuntu live -lisäpaketti

45 Ubuntu-versiota: 4.10–26.10. Versiot 14.04 ja 14.10 käyttävät samaa
alkuperäistä oletuskuvaa mutta kumpikin löytyy omana valintanaan.

Alkuperäiset kuvat on koottu The Spacebarin artikkelista. Ne ovat Canonicalin
ja Ubuntu artwork -tekijöiden kuvitusta. Tämä on itsenäinen fanisovitus,
ei Canonicalin virallinen live-taustakuvapaketti. Alkuperäiset tekijämerkinnät,
lähdeosoitteet, tarkisteet ja saatavilla olevat lisenssitiedot säilytetään mukana.

Animaatio on pieni paikallinen muodonmuutos ja sulava siirtymä 16 avainkuvan
välillä. 48 sekunnin silmukka on jatkuva myös lopusta alkuun. Kuvan reunat ja
yleinen sommittelu pysyvät paikallaan. Tämä on rauhallinen graafinen animaatio,
ei video eläimen oikeista liikkeistä.

Rakennus: `python tools/build_ubuntu_pack.py --output outputs/ubuntu-pack`.
Työkalun riippuvuudet: Pillow ja NumPy; niitä ei tarvita sovelluksen käytössä.
Ladattavien alkuperäiskuvien SHA256-arvot tarkistetaan ennen renderöintiä.
