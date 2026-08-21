---
source_sha: 08a4849b104da34098abb6cc5221e9047211c8b2131acaf75182af067ffb4cce
translated: machine
---

# Sisäänrakennettujen vaativuus

Kaikki mitä Python tarjoaa ilman importtia: sisäänrakennetut tyypit, sisäänrakennetut
funktiot, vakiot ja poikkeushierarkia. Jokainen alla oleva kohta linkittää sivulle,
jolla on täydellinen erittely; tämän sivun taulukot antavat päävaativuuden, jotta
löydät etsimäsi yhdellä silmäyksellä.

## Sisäänrakennetut tyypit

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

### Luku- ja totuusarvotyypit

- **[Kokonaisluku](int.md)** - Mielivaltaisen tarkkuuden kokonaisluvut
- **[Liukuluku](float.md)** - IEEE 754 -kaksoistarkkuus
- **[Totuusarvo](bool.md)** - Kaksi singletonia, `int`-tyypin aliluokka

## Sisäänrakennetut funktiot

### Iterointi

Tämän ryhmän funktiot palauttavat iteraattorin. Sen luominen on halpaa; Huomiot-sarakkeessa
mainittu kustannus on se, minkä maksat iteraattorin läpikäynnistä.

| Funktio | Aika | Tila | Huomiot |
|----------|------|-------|-------|
| [`iter()`](iter.md) | O(1) | O(1) | Kääri iteroitavan iteraattoriksi |
| [`next()`](next.md) | O(1)* | O(1) | * kustannus riippuu taustalla olevasta iteraattorista |
| [`aiter()`](aiter.md) | O(1) | O(1) | `iter()`-funktion asynkroninen vastine |
| [`anext()`](anext.md) | O(1) | O(1) | Odottaminen maksaa sen, minkä asynkroninen generaattori maksaa |
| [`enumerate()`](enumerate.md) | O(1) | O(1) | O(n) läpikäyntiin; tuottaa `(indeksi, alkio)` -monikoita |
| [`zip()`](zip.md) | O(1) | O(1) | O(n) läpikäyntiin; pysähtyy lyhimpään iteroitavaan |
| [`map()`](map.md) | O(1) | O(1) | O(n*k) läpikäyntiin, k = funktion aika |
| [`filter()`](filter.md) | O(1) | O(1) | O(n*k) läpikäyntiin, k = predikaatin aika |
| [`reversed()`](reversed.md) | O(1) | O(1) | O(n) läpikäyntiin; vaatii `__reversed__` tai `__getitem__` |

### Koonti ja järjestäminen

| Funktio | Aika | Tila | Huomiot |
|----------|------|-------|-------|
| [`len()`](len.md) | O(1) | O(1) | Sisäänrakennetut säilöt tallettavat pituutensa |
| [`sum()`](sum.md) | O(n) | O(1) | O(n²) jos sitä käytetään väärin merkkijonojen yhdistämiseen |
| [`min()`](min.md) | O(n) | O(1) | Vertailtava jokainen alkio |
| [`max()`](max.md) | O(n) | O(1) | Vertailtava jokainen alkio |
| [`sorted()`](sorted.md) | O(n log n) | O(n) | Timsort (≤3.10), Powersort (3.11+) |
| [`all()`](all.md) | O(n) | O(1) | Katkaisee ensimmäiseen epätoteen alkioon |
| [`any()`](any.md) | O(n) | O(1) | Katkaisee ensimmäiseen toteen alkioon |

### Luvut ja lukujärjestelmät

| Funktio | Aika | Tila | Huomiot |
|----------|------|-------|-------|
| [`abs()`](abs.md) | O(1) | O(1) | O(k) omalle `__abs__()`-toteutukselle |
| [`divmod()`](divmod.md) | O(1) | O(1) | O(n²) mielivaltaisen tarkkuuden kokonaisluvuille |
| [`pow()`](pow.md) | O(log y) | O(1) | Nopea potenssiinkorotus; kolmen argumentin muoto pysyy modulaarisena |
| [`round()`](round.md) | O(1) | O(1) | Pankkiirin pyöristys tasan puolikkailla |
| [`bin()`](bin.md) | O(log n) | O(log n) | Kustannus on tulosteen pituus |
| [`hex()`](hex.md) | O(log n) | O(log n) | Kustannus on tulosteen pituus |
| [`oct()`](oct.md) | O(log n) | O(log n) | Kustannus on tulosteen pituus |

### Teksti ja merkit

| Funktio | Aika | Tila | Huomiot |
|----------|------|-------|-------|
| [`chr()`](chr.md) | O(1) | O(1) | Koodipisteestä merkiksi |
| [`ord()`](ord.md) | O(1) | O(1) | Merkistä koodipisteeksi |
| [`format()`](format.md) | O(n) | O(n) | n = tuloksen pituus |
| [`repr()`](repr.md) | O(n) | O(n) | Etenee rekursiivisesti säilöihin |
| [`ascii()`](ascii.md) | O(n) | O(n) | Kuten `repr()`, mutta suojaa ei-ASCII-merkit |
| [`hash()`](hash.md) | O(k) | O(1) | O(n) merkkijonoille, välimuistissa ensimmäisen kutsun jälkeen |

### Oliot, attribuutit ja tyypit

| Funktio | Aika | Tila | Huomiot |
|----------|------|-------|-------|
| [`type()`](type_func.md) | O(1) | O(1) | O(n) kolmen argumentin luokan luovassa muodossa |
| [`isinstance()`](isinstance.md) | O(d) | O(1) | d = MRO:n syvyys; käytännössä O(1) |
| [`issubclass()`](issubclass.md) | O(d) | O(1) | d = MRO:n syvyys; käytännössä O(1) |
| [`callable()`](callable.md) | O(1) | O(1) | Tarkistaa `__call__`-metodin |
| [`id()`](id.md) | O(1) | O(1) | `is`-operaattorin perusta |
| [`getattr()`](getattr.md) | O(d) | O(1) | Osuma ilmentymän sanakirjaan on keskimäärin O(1) |
| [`setattr()`](setattr.md) | O(1) | O(1) | Lisäys hajautustauluun |
| [`hasattr()`](hasattr.md) | O(d) | O(1) | Sama haku kuin `getattr()`, poikkeus napataan kiinni |
| [`delattr()`](delattr.md) | O(1) | O(1) | Poisto hajautustaulusta |
| [`dir()`](dir.md) | O(n log n) | O(n) | Tuloksen järjestäminen hallitsee kustannusta |
| [`vars()`](vars.md) | O(1) | O(1) | Palauttaa viitteen `__dict__`-sanakirjaan, ei kopiota |
| [`super()`](super.md) | O(d) | O(d) | Kulkee MRO:n läpi, joka on välimuistissa |
| [`property()`](property.md) | O(1) | O(1) | Kuvaajan luonti ja käyttö |
| [`classmethod()`](classmethod.md) | O(1) | O(1) | Kuvaajan luonti; haku on O(d) |
| [`staticmethod()`](staticmethod.md) | O(1) | O(1) | Kuvaajan luonti; haku on O(d) |

### Tyyppien konstruktorit

| Konstruktori | Aika | Tila | Huomiot |
|-------------|------|-------|-------|
| [`bool()`](bool_func.md) | O(1) | O(1) | Säilöt vastaavat `__len__()`-metodilla, joka on O(1) |
| [`int()`](int_func.md) | O(1) | O(1) | O(n²) hyvin pitkän lukumerkkijonon jäsennyksessä |
| [`float()`](float_func.md) | O(1) | O(1) | O(n) merkkijonosta |
| [`complex()`](complex_func.md) | O(1) | O(1) | O(n) merkkijonosta |
| [`str()`](str_func.md) | O(1) | O(1) | O(n) säilöille ja omalle `__str__()`-toteutukselle |
| [`bytes()`](bytes_func.md) | O(n) | O(n) | n = lähteen pituus |
| [`bytearray()`](bytearray_func.md) | O(n) | O(n) | n = lähteen pituus |
| [`memoryview()`](memoryview_func.md) | O(1) | O(1) | Näkymä puskuriin, ei koskaan kopio |
| [`list()`](list_func.md) | O(n) | O(n) | n = iteroitavan pituus |
| [`tuple()`](tuple_func.md) | O(n) | O(n) | O(1) kun argumentti on jo monikko |
| [`dict()`](dict_func.md) | O(n) | O(n) | O(n²) pahimmassa tapauksessa hajautustörmäyksillä |
| [`set()`](set_func.md) | O(n) | O(n) | O(n²) pahimmassa tapauksessa hajautustörmäyksillä |
| [`frozenset()`](frozenset_func.md) | O(n) | O(n) | O(1) kun argumentti on jo frozenset |
| [`slice()`](slice.md) | O(1) | O(1) | Tallettaa vain indeksit; sen soveltaminen maksaa O(k) |
| [`object()`](object_func.md) | O(1) | O(1) | Jokaisen luokan perusta |

### Koodin suoritus

| Funktio | Aika | Tila | Huomiot |
|----------|------|-------|-------|
| [`eval()`](eval.md) | O(n + m) | O(n + m) | n = lähdekoodin pituus, m = evaluoinnin kustannus |
| [`exec()`](exec.md) | O(n + m) | O(n + m) | n = lähdekoodin pituus, m = suorituksen kustannus |
| [`compile()`](compile.md) | O(n) | O(n) | Jäsennys sekä tavukoodin generointi |
| [`globals()`](globals.md) | O(1) | O(1) | Palauttaa olemassa olevan moduulin sanakirjan |
| [`locals()`](locals_func.md) | O(1) | O(1) | O(m) optimoiduissa funktioiden näkyvyysalueissa |

### Syöte, tuloste ja virheenjäljitys

| Funktio | Aika | Tila | Huomiot |
|----------|------|-------|-------|
| [`print()`](print.md) | O(n) | O(n) | n = tulosteen kokonaispituus; I/O hallitsee kustannusta |
| [`input()`](input.md) | O(k) | O(k) | k = luetun rivin pituus |
| [`open()`](open.md) | O(1)* | O(1) | * järjestelmäkutsu; luku ja kirjoitus maksavat sen minkä siirtävät |
| [`help()`](help.md) | O(n) | O(n) | n = tarkasteltavan rajapinnan koko |
| [`breakpoint()`](breakpoint.md) | O(1) | O(1) | Luovuttaa hallinnan virheenjäljittimelle |

## Vakiot

| Vakio | Aika | Tila | Huomiot |
|----------|------|-------|-------|
| [`None`](none.md) | O(1) | O(1) | Singleton; vertaa `is`-operaattorilla |
| [`True`](true.md) | O(1) | O(1) | Singleton-`bool` |
| [`False`](false.md) | O(1) | O(1) | Singleton-`bool` |
| [`NotImplemented`](notimplemented.md) | O(1) | O(1) | Operaattorit palauttavat tämän kieltäytyessään |
| [`Ellipsis`](ellipsis.md) | O(1) | O(1) | `...`-singleton |

## Poikkeukset ja tulkki

- **[Poikkeukset](exceptions.md)** - Sisäänrakennettu poikkeushierarkia sekä nosto- ja kiinniottokustannukset
- **[Tulkin tiedot](interpreter_info.md)** - `copyright`, `credits`, `license`
- **[Exit/Quit](exit_quit.md)** - `exit` ja `quit`

## Keskeiset käsitteet

### Tasoitettu vaativuus

Joillakin operaatioilla, kuten `list.append()`, on **tasoitettu O(1)** -vaativuus. Tämä tarkoittaa:

- Useimmat append-operaatiot ovat O(1)
- Ajoittain tapahtuu koon muuttaminen, joka vaatii O(n)
- Monen operaation yli keskiarvo on O(1)

### Laiska vs. ahne

Useat sisäänrakennetut funktiot palauttavat iteraattorin tuloksen sijaan. Niiden kutsuminen
on O(1) riippumatta syötteen koosta; varsinainen työ tapahtuu iteraattoria läpi käytäessä,
eikä sitä tehdä lainkaan ohitetuille alkioille. Kutsun kääriminen `list()`-funktioon tekee
siitä jälleen ahneen ja palauttaa O(n)-tilavaativuuden.

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

## Katso myös

- [Standardikirjasto](../stdlib/index.md)
- [Toteutukset](../implementations/index.md)
