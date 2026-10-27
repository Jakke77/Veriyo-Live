# Projektin alkuperä

Veriyö Live kehitettiin alun perin Ajanlaskut ja Sää -projektin erilliseen
`live`-hakemistoon. Tämä repo kokoaa vain Veriyö Live -sovelluksen omaksi projektiksi.
Ajanlaskut ja Sää -repon muuta historiaa, muita sovelluksia tai henkilökohtaisia
asetuksia ei siirretä tähän repoon.

Siirretyn oman lähdekoodin vertailuversio on Veriyö Live 0.1.1,
Ajanlaskut ja Sää -repon commit `d1e82ec834ebd8fab04ac16c8f5f0c21ab77c72d`.
Tähtitieteellisen laskennan ja alkuperäisten teosten tekijämerkinnät säilyvät.

Sovelluksen ajonaikaiset Python-tiedostot, testit ja PyMeeus-lähdekirjasto on
säilytetty siirrossa muuttamattomina. Käyttöohjeet, paketointi ja GitHub Actions
on sovitettu itsenäiseen projektiin.

## Aiemmin tarkistetut paketit

Ubuntu 0.1.1:n Debian-paketin SHA256:
`75303f5071516236b0233d7f9a4acbfab2c53a736f073754b3e43c4057bf488a`

Windows 0.1.1:n ZIP-paketin SHA256:
`8f9d81f7884501f41832efb3ceb2549ac816cd5939c9fba3ad399943679f373f`

Windowsin alkuperäinen natiivitarkistus: Ajanlaskut ja Sää / GitHub Actions run
`40515482007`. Uusi repo rakentaa ja tarkistaa omat paketit oman lähdecommitinsa
perusteella. Niiden tarkisteet eroavat aiemmista paketeista käyttöohjeiden ja
paketointimetadatan muuttuessa.
