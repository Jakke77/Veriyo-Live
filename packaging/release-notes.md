Neljä uutta teemaa **Taustakuvan tyyli** -valikossa:

- **Pohjantähden tähtitaivas:** 634 kirkkaan tähden luettelo, sijainnin ja ajan mukainen taivas sekä hitaasti kiertävät valokehät.
- **Kuun kulkureitti:** oikea kuunvaihe ja nykyinen sijainti, päivän reitti sekä arvioidut nousu- ja laskuajat. Reitillä kulkee koristeellinen valopulssi.
- **Veri Ajan taivaankoneisto:** seitsemän kehää ja kiertävät sinetit, joiden hehku ja ulkokehän eteneminen seuraavat 777 päivän vuotta.
- **Hiljainen avaruus:** kuvitteellinen planeetta, leijuvia kivikappaleita ja rauhallisesti liikkuvaa sumua.

Teemat sisältyvät sovellukseen ja toimivat ilman verkkoyhteyttä tai lisäpakettia. Tähtikartta ja Kuu tukevat koko maapallon koordinaatteja; valitse myös sijaintisi aikavyöhyke. Veri Ajan päiväraja pysyy Suomen ajassa. Kuun nousu- ja laskuajat ovat arvioita tasaiselle horisontille.

[Katso 16 sekunnin video normaalinopeudella](https://github.com/Jakke77/Veriyo-Live/blob/main/screenshots/four-scenes-demo.mp4) · [Kuvakooste ja käyttöohjeet](https://github.com/Jakke77/Veriyo-Live#readme)

**Ubuntu-kuvien esittely on korjattu.** 45 Ubuntu-version kuvat esitellään taustakuvakokoelmana, johon ei luvata havaittavaa animaatiota. Tiedostonimi `Ubuntu-Live-Pack-1.0.0.zip` säilyy yhteensopivuuden vuoksi. Jo asennettua kuvapakettia ei tarvitse ladata uudelleen. `Ubuntu-Live-Originals-1.0.0.zip` on kehitysaineistoa.

### Päivittäminen

1. Sulje vanha Veriyö Live ilmoitusalueen **Lopeta**-valinnalla.
2. Windows: pura koko `Veriyo-Live-0.3.0-Windows-x64.zip` pysyvään kansioon ja avaa uusi `Veriyo-Live.exe`. Paina **Tallenna asetukset**, jos käytät kirjautumiskäynnistystä.
3. Ubuntu: asenna `veriyo-live_0.3.0_all.deb` komennolla `sudo apt install ./veriyo-live_0.3.0_all.deb`.
4. Valitse uusi teema, tarvittaessa sijainti ja aikavyöhyke, ja paina **Ota elävä tausta käyttöön**. Teemaa vaihtaessa pysäytä vanha tausta ensin.

Windows käyttää Explorerin WorkerW-taustapintaa. GNOME käyttää sulavia taustakuvasiirtymiä; tähtitieteelliset tiedot päivittyvät valitulla aikavälillä. **Pysäytä päivitys** jättää pysäytyskuvan, **Palauta aiempi tausta** palauttaa varmuuskopion. Lukitusnäytölle tehdään pysäytyskuva. Windows voi edelleen hylätä automaattisen lukituskuvan vaihdon; työpöytä jatkaa tällöin toimintaansa.

78 testin sarja kattaa myös riippumattomat Astropy/ERFA-vertailut, Pohjantähden suunnan, Kuun topocentrisen sijainnin ja vaiheen, kesä-/talviajan, havaittavan koristeellisen liikkeen, asetusten yhteensopivuuden sekä pysäytyksen ja palautuksen. Windows CI tarkistaa uuden ohjelmallisesti piirretyn teeman natiivissa taustapinnassa. Käyttäjän oman työpöytäistunnon näkyvä toiminta kannattaa kokeilla.

HYG-tähtiluettelon muokattu otos on CC BY-SA 4.0; tekijämerkinnät ja lähdetiedot ovat mukana. Muut lisenssit: `THIRD_PARTY_NOTICES.md`.
