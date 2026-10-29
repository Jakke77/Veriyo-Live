**Korjaa Ubuntun GNOME-taustojen sekoittumisen.** Satunnaisvaihdon jälkeen GNOME saattoi näyttää edellisen ja uuden teeman kuvia vuorotellen muutaman sekunnin välein, vaikka vaihtoväliksi oli valittu esimerkiksi 26 minuuttia.

Syynä olivat samoihin osoitteisiin uudelleen kirjoitetut kuvat ja GNOMEn URI-välimuisti. Uusi kuvasarja tehdään nyt kokonaan uusiin tiedostoihin ennen käyttöönottoa. Nykyinen ja edellinen 16 kuvan sarja säilytetään; vanhemmat siivotaan onnistuneen vaihdon jälkeen. Alkuperäisen taustan varmuuskopio ja siihen kuuluvat kuvat säilyvät. Epäonnistunut piirto tai käyttöönotto ei poista nykyistä taustaa.

**Satunnaisvaihdon aikaväli** määrää teeman vaihtamisen. Tavallinen päivitysväli päivittää saman teeman taivasta tai valaistusta; animaation kuvasarjan eteneminen ei vaihda teemaa. 26 minuutin vaihdon raja on tarkistettu erillisellä kellotestillä.

### Päivittäminen

1. Sulje vanha Veriyö Live ilmoitusalueen **Lopeta**-valinnalla. Pelkkä ikkunan sulkeminen voi jättää sen käyntiin.
2. Ubuntu: lataa `veriyo-live_0.4.2_all.deb` ja asenna `sudo apt install ./veriyo-live_0.4.2_all.deb`.
3. Windows: pura koko `Veriyo-Live-0.4.2-Windows-x64.zip` pysyvään kansioon ja avaa uusi `Veriyo-Live.exe`. Tämä korjaus koskee GNOMEa; Windows käyttää edelleen natiivia taustapintaa. Tallenna asetukset, jos käytät kirjautumiskäynnistystä.
4. Paina **Ota elävä tausta käyttöön**, jotta vanha kuvasarja korvautuu korjatulla.

Asetukset, satunnaisvaihdon valinnat ja Ubuntu-kuvapaketti säilyvät. Niitä ei tarvitse poistaa tai asentaa uudelleen. Mukana on myös version 0.4.1 pohjoiseen katsovan tähtitaivaan suuntakorjaus.

110 testin sarja sisältää URI-välimuistin jäljittelyn, kuvasarjojen muuttumattomuuden, peräkkäiset teemavaihdot, rajatun kuvatiedostojen määrän, vanhan version siivouksen, alkuperäisen taustan palautuksen sekä epäonnistuneet päivitykset. Linuxin ja pakatun Windows-ohjelman testit sekä Windowsin natiivin taustapinnan tarkistus ajetaan julkaisua varten.

Lukitusnäyttö on edelleen pysäytyskuva; Windows voi estää sen automaattisen vaihtamisen. Ubuntu-versioiden oletuskuvat ovat taustakuvakokoelma, johon ei luvata havaittavaa animaatiota.
