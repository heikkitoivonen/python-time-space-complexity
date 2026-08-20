---
source_sha: ea21ab98df90390ac692a9f672d95bb7f91e4108969863bd4a2b00e1c3aa6e85
translated: machine
---

# Sisäänrakennettujen tyyppien vaativuus

Pythonin sisäänrakennetuilla tyypeillä on hyvin määritellyt vaativuusominaisuudet operaatioilleen. Tässä osiossa käydään läpi yleisimmin käytetyt tyypit yksityiskohtaisesti.

## Yleiskatsaus

| Tyyppi | Käyttötarkoitus | Haku (keskim.) | Lisäys (keskim.) | Poisto (keskim.) |
|------|----------|-----------|-----------|-----------|
| `list` | Järjestetyt jonot | O(1) | O(n) | O(n) |
| `tuple` | Muuttumaton jono | O(1) | - | - |
| `range` | Lukujonot | O(1) | - | - |
| `str` | Teksti | O(1) | - | - |
| `bytes` | Binääridata | O(1) | - | - |
| `dict` | Avain-arvo-kuvaus | O(1) | O(1) | O(1) |
| `set` | Uniikit alkiot | - | O(1) | O(1) |
| `frozenset` | Muuttumattomat uniikit alkiot | - | - | - |

## Yksityiskohtaiset oppaat

### Jonotyypit
- **[Lista](list.md)** - Joustavin jonotyyppi
- **[Monikko](tuple.md)** - Muuttumattomat jonot
- **[Lukualue](range.md)** - Laiskasti laskettavat lukujonot
- **[Merkkijono](str.md)** - Teksti ja merkkijonot
- **[Tavut ja tavutaulukot](bytes.md)** - Binääridata ja muuttuvat tavut

### Kuvaus- ja joukkotyypit
- **[Sanakirja](dict.md)** - Hajautukseen perustuva avain-arvo-säilö
- **[Joukko](set.md)** - Järjestämättömät uniikit alkiot
- **[Frozenset](frozenset.md)** - Muuttumattomat uniikit alkiot

## Keskeiset käsitteet

### Tasoitettu vaativuus

Joillakin operaatioilla, kuten `list.append()`, on **tasoitettu O(1)** -vaativuus. Tämä tarkoittaa:

- Useimmat append-operaatiot ovat O(1)
- Ajoittain tapahtuu koon muuttaminen, joka vaatii O(n)
- Monen operaation yli keskiarvo on O(1)

### Toteutuksen yksityiskohdat

CPython käyttää:

- **Listat**: Dynaamisia taulukoita ylivarauksella
- **Sanakirjat**: Hajautustauluja avoimella osoituksella
- **Joukot**: Hajautustauluja (samaan tapaan kuin sanakirjat)

## Versiohuomiot

Eri Python-versioissa on omat optimointinsa:

- **Python 3.7+**: Sanakirjan lisäysjärjestys taataan (kielimäärittely)
- **Python 3.9+**: Parannuksia uuteen sanakirjatoteutukseen
- **Python 3.10+**: Lisäoptimointeja yleisiin operaatioihin

Katso [Versiot](../versions/index.md) julkaisukohtaista muutoslokia varten.
