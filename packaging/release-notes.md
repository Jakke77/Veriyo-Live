Kolme uutta maisemaa **Taustakuvan tyyli** -valikossa:

- **Metsien puro:** virtaavaa vettä, metsämaisema, kevyesti liikkuvaa kasvillisuutta, sumua ja yöllä tulikärpäsiä.
- **Varjoruusujen puutarha:** goottilainen kasvihuone vieraalla planeetalla, hitaasti avautuvia ruusuja, leijuvia terälehtiä ja sumussa häilyvä hahmo.
- **Viimeinen majakka:** kiertävä valokeila, rauhallinen meri, rengasplaneetta ja horisontissa vähitellen näkyvä suuri varjo.

Valaistus seuraa valitsemasi aikavyöhykkeen paikallista kellonaikaa. Aamu, päivä, ilta ja yö vaihtuvat vähitellen. **Nopeutettu esikatselu** näyttää vuorokauden minuutissa; työpöytä käyttää oikeaa aikaa. Teemat sisältyvät sovellukseen ja toimivat ilman lisäpakettia tai verkkoyhteyttä.

[Katso 16 sekunnin video normaalinopeudella](https://github.com/Jakke77/Veriyo-Live/blob/main/screenshots/landscape-scenes-demo.mp4) · [Kuvat ja käyttöohjeet](https://github.com/Jakke77/Veriyo-Live#readme)

### Satunnaisvaihto

**Vaihda satunnainen tausta nyt** vaihtaa käynnissä olevan taustan, pysäytettynä vain esikatselun. **Valitse mukaan tulevat taustat…** avaa rastitettavan luettelon. Voit valita maisemat, taivasteemat, vanhat Otava-kuvat tai asennetun Ubuntu-kuvapaketin versiot.

**Vaihda taustaa satunnaisesti** ottaa automaattisen vaihdon käyttöön, kun tausta on käynnistetty. Aikavälit ovat 1, 5, 15, 26 tai 60 minuuttia. Nykyinen tausta ohitetaan seuraavassa arvonnassa; jatkuva vaihtelu tarvitsee vähintään kaksi käytettävissä olevaa valintaa. Valinnat tallentuvat. Pysäytys pysäyttää myös satunnaisvaihdon, ja palautus säilyttää ensimmäisen alkuperäisen taustan.

### Päivittäminen

1. Sulje vanha Veriyö Live ilmoitusalueen **Lopeta**-valinnalla.
2. Windows: pura koko `Veriyo-Live-0.4.0-Windows-x64.zip` pysyvään kansioon ja avaa uusi `Veriyo-Live.exe`. Paina **Tallenna asetukset**, jos käytät kirjautumiskäynnistystä.
3. Ubuntu: asenna `veriyo-live_0.4.0_all.deb` komennolla `sudo apt install ./veriyo-live_0.4.0_all.deb`.
4. Valitse teema ja aikavyöhyke sekä paina **Ota elävä tausta käyttöön**. GNOMEssa valaistus virkistyy valitulla 1, 5 tai 26 minuutin välillä; 1 minuutti antaa tiheimmän päivityksen.

Aiemmat teemat, asetukset ja asennettu Ubuntu-kuvapaketti säilyvät. Ubuntu-kuvat esitellään taustakuvakokoelmana, johon ei luvata havaittavaa animaatiota. Niiden vanha tiedostonimi `Ubuntu-Live-Pack-1.0.0.zip` säilyy yhteensopivuuden vuoksi.

Windows käyttää Explorerin WorkerW-taustapintaa ja tauottaa liikkeen lukituksen ajaksi. GNOME käyttää sulavia taustakuvasiirtymiä. Lukitusnäyttö on pysäytyskuva; Windows voi edelleen hylätä sen automaattisen vaihtamisen.

98 testin sarja kattaa valaistuksen, aikavyöhykkeet, kesä-/talviajan, liikkeen jatkuvuuden, satunnaisvalintojen rajauksen, jonotetut vaihdot, automaattisen ja käsin tehdyn vaihdon sekä ensimmäisen taustan palautuksen. Windows CI tarkistaa myös kolmen uuden maiseman liikkeen natiivissa taustapinnassa ja fokuksen säilymisen. Käyttäjän oman työpöytäistunnon näkyvä toiminta tarvitsee kokeilun omalla koneella.
