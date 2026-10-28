# Ubuntun oletustaustakuvakokoelma

45 Ubuntu-versiota: 4.10–26.10. Versiot 14.04 ja 14.10 käyttävät samaa
alkuperäistä oletuskuvaa mutta kumpikin löytyy omana valintanaan.

Alkuperäiset kuvat on koottu The Spacebarin artikkelista. Ne ovat Canonicalin
ja Ubuntu artwork -tekijöiden kuvitusta. Tämä on itsenäinen fanisovitus,
ei Canonicalin virallinen taustakuvapaketti. Alkuperäiset tekijämerkinnät,
lähdeosoitteet, tarkisteet ja saatavilla olevat lisenssitiedot säilytetään mukana.

Kokoelmaan ei luvata havaittavaa animaatiota. Aiemman version esittely lupasi
hahmojen liikettä liian vahvasti, vaikka käyttäjän kokeilussa liike jäi huomaamatta.
Kuvat esitellään siksi taustakuvakokoelmana. Tiedostonimi
`Ubuntu-Live-Pack-1.0.0.zip` säilyy vanhojen asennusten yhteensopivuuden vuoksi.

Kehitysaineistossa on alkuperäisen kokeilun 16 avainkuvaa kutakin versiota kohti.
Tekninen siirtymäkokeilu ei ole lupaus käytännössä näkyvästä liikkeestä.

Rakennus: `python tools/build_ubuntu_pack.py --output outputs/ubuntu-pack`.
Työkalun riippuvuudet: Pillow ja NumPy; niitä ei tarvita sovelluksen käytössä.
Ladattavien alkuperäiskuvien SHA256-arvot tarkistetaan ennen renderöintiä.
