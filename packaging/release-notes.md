**Tähtitaivaan suunta korjattu** teemoissa **Pohjantähden tähtitaivas** ja **Kuun kulkureitti**.

Näkymä katsoo nyt pohjoiseen: pohjoinen horisontti alhaalla, zeniitti ylhäällä, länsi vasemmalla ja itä oikealla. Tähdet, tähtikuvioiden yhdysviivat ja Kuun reitti käyttävät samaa stereografista projektiota kuin alkuperäinen Otava-tausta. Esimerkiksi Oulussa 28.10.2026 klo 20.24 Otava on Pohjantähden alapuolella, Alkaid lännen puolella.

Koko taivaan aiempi peilattu karttanäkymä on korvattu pohjoiseen avautuvalla näkymällä. Näkymän ulkopuolella olevat kohteet jätetään piirtämättä. Jos Kuu on horisontin yläpuolella mutta näkymän ulkopuolella, siitä kerrotaan erikseen. Kuunvaihe, suunta, korkeus sekä päivän arvioidut nousu- ja laskuajat näkyvät edelleen.

### Päivittäminen

1. Sulje vanha Veriyö Live ilmoitusalueen **Lopeta**-valinnalla.
2. Ubuntu: lataa `veriyo-live_0.4.1_all.deb` ja asenna `sudo apt install ./veriyo-live_0.4.1_all.deb`.
3. Windows: pura koko `Veriyo-Live-0.4.1-Windows-x64.zip` pysyvään kansioon ja avaa uusi `Veriyo-Live.exe`. Paina **Tallenna asetukset**, jos käytät kirjautumiskäynnistystä.
4. Valitse teema ja paina **Ota elävä tausta käyttöön**, jotta korjattu kuva tulee työpöydälle.

Maisemat, satunnaisvaihto, asetukset ja asennettu Ubuntu-kuvapaketti säilyvät. Uudet kuvat ja video: [käyttöohjeet](https://github.com/Jakke77/Veriyo-Live#readme). Lisäpakettia ei tarvitse asentaa uudelleen.

104 testin sarja sisältää ilmansuuntien ja zeniitin tarkistuksen, kuvakaappauksen Otavan asennon regression, vertailun riippumattomaan Astropy/ERFA-aineistoon sekä näkymän ulkopuolisten suuntien tarkistukset. Windows CI tarkistaa myös korjattujen taivasteemojen piirron natiivissa taustapinnassa.

Lukitusnäyttö on edelleen pysäytyskuva; Windows voi estää sen automaattisen vaihtamisen. Ubuntu-versioiden kuvat ovat taustakuvakokoelma, johon ei luvata havaittavaa animaatiota.
