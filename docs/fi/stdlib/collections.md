---
source_sha: f5c4b3c5bd9a612e361874983042cd25d27aa989a7e7b47532e46516d57e6430
translated: machine
---

# collections-moduulin vaativuus

`collections`-moduuli tarjoaa säiliötyyppejä, jotka erikoistavat tyyppejä `dict`, `list`, `str` ja
`tuple`. Viidellä niistä on oma sivunsa, joihin linkitetään alla, ja `collections.abc`-moduulin
abstrakteilla kantaluokilla on omansa. Tämän sivun loppuosa kattaa `ChainMap`-tyypin, joka hakee
kuvausten listasta järjestyksessä yhdistämättä niitä, sekä tyypit `UserDict`, `UserList` ja
`UserString`, jotka pitävät tavallista `dict`-, `list`- tai `str`-oliota `data`-attribuutissa ja
välittävät jokaisen operaation sille.

## deque

Katso [deque](deque.md): operaatiot, vaativuus ja esimerkit.

## defaultdict

Katso [defaultdict](defaultdict.md): operaatiot, vaativuus ja esimerkit.

## Counter

Katso [Counter](counter.md): operaatiot, vaativuus ja esimerkit.

## namedtuple

Katso [namedtuple](namedtuple.md): operaatiot, vaativuus ja esimerkit.

## OrderedDict

Katso [OrderedDict](ordereddict.md): operaatiot, vaativuus ja esimerkit.

## collections.abc

Katso [collections.abc](collections.abc.md): abstraktit kantaluokat ja niiden mixin-metodien hinta.
Kaikki, mitä `ChainMap` ja kääreet eivät määrittele itse, tulee näistä mixineistä, ja mixin on
kirjoitettu kääreen omien `__getitem__`-, `__iter__`- ja `__setitem__`-metodien varaan, joten
aliluokka, joka ylikirjoittaa jonkin niistä, maksaa siitä mixinin jokaisella askeleella.

## Kokomuuttujat

`ChainMap`-tyypille `n` on kuvausten määrä, `i` ensimmäisen avaimen sisältävän kuvauksen sijainti
(`n` hudille), `N` kaikkien kuvausten alkioiden kokonaismäärä ja `m` alkioiden määrä
`maps[0]`-kuvauksessa. Kääreille `n` on `len(wrapper)`, ja `d` on niiden paikkojen määrä, jotka
aiemmat poistot jättivät sanakirjan tauluun. Kaikkialla `k` on toisen operandin koko tai annettujen
alkioiden määrä. Avainten hajautus ja vertailu ovat O(1), `ChainMap`-rivit olettavat kuvausten
olevan sanakirjoja, ja `data`-oliolle välitetty operaatio maksaa sen, mitä
[dict](../builtins/dict.md)-, [list](../builtins/list.md)- tai [str](../builtins/str.md)-sivu sanoo.

## Vaativuusviite

### ChainMap

| Operaatio | Aika | Tila | Huomautukset |
|-----------|------|-------|-------|
| `collections.ChainMap(*maps)` | O(n) | O(n) | Pitää kuvaukset listassa; mitään ei kopioida eikä yhdistetä, joten minkä tahansa kuvauksen myöhempi muutos näkyy läpi |
| `ChainMap.maps` | O(1) | O(1) | Lista itse; järjestä uudelleen tai laajenna sitä muuttaaksesi hakujärjestystä |
| `cm[key]` | O(i) | O(1) | Kokeilee kuvauksia järjestyksessä, kunnes jollakin on avain; huti kokeilee kaikki n ja nostaa `KeyError`-poikkeuksen |
| `key in cm` | O(i) | O(1) | Sama haku |
| `cm.get(key, default=None)` | O(i) | O(1) | Hakee osuman sattuessa kaksi kertaa: kerran `in`-tarkistukseen, kerran arvoon |
| `cm[key] = value`, `del cm[key]`, `cm.pop(key)`, `cm.popitem()` | O(1) | O(1) | Vain `maps[0]`; myöhemmässä kuvauksessa olevan avaimen poisto nostaa `KeyError`-poikkeuksen |
| `cm.update(other)`, `cm \|= other` | O(k) | O(k) | Kuvaukseen `maps[0]` |
| `cm.setdefault(key, default=None)` | O(i) | O(1) | Palauttaa mistä tahansa kuvauksesta löytyneen arvon; vain huti kirjoittaa, ja se kirjoittaa kuvaukseen `maps[0]` |
| `cm.clear()` | O(m) | O(1) | Tyhjentää `maps[0]`-kuvauksen eikä mitään muuta |
| `bool(cm)` | O(n) | O(1) | Pysähtyy ensimmäiseen epätyhjään kuvaukseen; tyhjien kuvausten ketju tarkistaa jokaisen |
| `len(cm)` | O(n + N) | O(n + N) | Rakentaa joukon kaikista avaimista laskeakseen erilliset ja käy jokaisen kuvauksen läpi, tyhjänkin |
| `cm.keys()`, `cm.items()`, `cm.values()` | O(1) | O(1) | Näkymiä ketjuun; hinta maksetaan, kun niitä iteroidaan |
| `cm`- tai `cm.keys()`-iterointi | O(n + N) | O(N) | Rakentaa sanakirjan kaikista avaimista ennen ensimmäisen tuottamista: viimeisen kuvauksen avaimet, sitten kunkin aiemman kuvauksen uudet avaimet |
| `cm.items()`- tai `cm.values()`-iterointi, `dict(cm)` | O(n + N·n) | O(N) | Avainkierros ja sitten `cm[key]` jokaiselle avaimelle, mikä hakee ketjusta uudelleen |
| `cm == other` | O(n + N·n + k) | O(N + k) | Litistää molemmat puolet sanakirjoiksi ja vertaa niitä |
| `cm.new_child(m=None, **kwargs)` | O(n + k) | O(n + k) | Uusi `ChainMap`, joka jakaa kaikki olemassa olevat kuvaukset ja jossa `m` on edessä; avainsana-argumentit kirjoitetaan `m`-kuvaukseen, kun molemmat annetaan, ja muuten uuteen sanakirjaan |
| `ChainMap.parents` | O(n) | O(n) | Uusi `ChainMap` kuvauksista `maps[1:]`; kuvaukset jaetaan, listaa ei |
| `cm.copy()` | O(m + n) | O(m + n) | Kopioi `maps[0]`-kuvauksen ja jakaa loput |
| `ChainMap.fromkeys(iterable, value=None)` | O(k) | O(k) | Yksi sanakirja yhden kuvauksen ketjussa |
| `cm \| other` | O(m + n + k) | O(m + n + k) | `copy()` ja sitten `other` kopion ensimmäiseen kuvaukseen |
| `other \| cm` | O(n + N + k) | O(N + k) | Yhden kuvauksen `ChainMap`, jossa jokainen alkio on litistetty: kerrokset ovat poissa |

### UserDict

| Operaatio | Aika | Tila | Huomautukset |
|-----------|------|-------|-------|
| `collections.UserDict(dict=None, /, **kwargs)` | O(k) | O(k) | Täyttää `data`-sanakirjan `update()`-kutsulla, yksi `__setitem__`-kutsu per alkio |
| `UserDict.data` | O(1) | O(1) | Tavallinen sanakirja; käytä sitä suoraan ohittaaksesi kääreen ja sen mixinit |
| `ud[key]`, `ud[key] = value`, `del ud[key]`, `key in ud`, `len(ud)` | O(1) | O(1) | Välitetään; `ud[key]` tarkistaa ensin jäsenyyden, jotta aliluokan `__missing__` voi ajautua |
| `ud.get(key, default=None)` | O(1) | O(1) | Python 3.12+: ei kutsu `__missing__`-metodia; ennen 3.12:ta kutsui |
| `ud.keys()`, `ud.items()`, `ud.values()` | O(1) | O(1) | Näkymiä, jotka pitävät viittauksen kääreeseen |
| `ud`- tai `ud.keys()`-iterointi | O(n) | O(1) | Sanakirjan oma iterointi |
| `ud.items()`- tai `ud.values()`-iterointi | O(n) | O(1) | Yksi `ud[key]` per avain |
| `ud.update(other)` | O(k) | O(1) | Yksi `__setitem__`-kutsu per alkio |
| `ud \|= other` | O(k) | O(1) | Yksi `dict.update` `data`-sanakirjalle |
| `ud \| other` | O(n + k) | O(n + k) | Yhdistää kaksi sanakirjaa ja rakentaa sitten tuloksesta uuden kääreen, joten jokainen alkio kulkee `__setitem__`-metodin läpi uudelleen |
| `ud.copy()` | O(n) | O(n) | Tavallinen `UserDict` kopioi `data`-sanakirjan; aliluokka kopioidaan pinnallisesti ja täytetään sitten uudelleen `update()`-kutsulla |
| `UserDict.fromkeys(iterable, value=None)` | O(k) | O(k) | Yksi `__setitem__`-kutsu per avain |
| `ud.pop(key)`, `ud.setdefault(key, default=None)` | O(1) | O(1) | `ud[key]` ja sitten `del ud[key]` tai `ud[key] = default` |
| `ud.popitem()` | O(d) | O(1) | Poistaa iterointijärjestyksen ensimmäisen avaimen; d on sitä ennen poistettujen alkioiden määrä, jotka uuden iteraattorin on ohitettava |
| `ud.clear()` | O(n·(n + d)) | O(1) | `popitem()` tyhjäksi asti, ja jokainen kutsu ohittaa kaikki aiempien tyhjentämät paikat; `ud.data.clear()` on O(n) |
| `ud == other` | O(n + k) | O(n + k) | Litistää molemmat puolet sanakirjoiksi ja vertaa niitä, vaikka `other` olisi jo sanakirja |

### UserList

| Operaatio | Aika | Tila | Huomautukset |
|-----------|------|-------|-------|
| `collections.UserList(initlist=None)` | O(k) | O(k) | Kopioi listan tai toisen `UserList`-olion; mikä tahansa muu iteroitava kulutetaan uuteen listaan |
| `UserList.data` | O(1) | O(1) | Tavallinen lista |
| `ul[i]`, `ul[i] = value`, `len(ul)` | O(1) | O(1) | Välitetään |
| `ul[i:j]` | O(j - i) | O(j - i) | Palauttaa `type(ul)`-olion, joka rakennetaan sen `__init__`-metodilla; samoin `copy()`, `+` ja `*` |
| `ul.append(x)` | O(1) tasoitettu | O(1) | Välitetään |
| `ul.insert(i, x)`, `del ul[i]`, `ul.pop(i=-1)`, `ul.remove(x)` | O(n) | O(1) | Alkiot kohdan `i` jälkeen siirtyvät, joten `pop()` lopusta on O(1) |
| `ul.extend(other)`, `ul += other` | O(k) | O(k) | `+=` kopioi muun kuin listan iteroitavan listaksi ennen laajentamista |
| `ul + other`, `ul * k` | O(n + k), O(n·k) | O(n + k), O(n·k) | Uusi `type(ul)`-olio; `other` voi olla lista, `UserList` tai mikä tahansa iteroitava |
| `ul *= k` | O(n·k) | O(n·k) | Paikallaan |
| `x in ul`, `ul.count(x)`, `ul.index(x)`, `ul.reverse()` | O(n) | O(1) | Välitetään |
| `ul.sort(*, key=None, reverse=False)` | O(n log n) | O(n) | `list.sort` `data`-listalle |
| `ul.clear()`, `ul.copy()` | O(n) | O(1), O(n) | `copy()` on `type(ul)(ul)` |
| `ul`- tai `reversed(ul)`-iterointi | O(n) | O(1) | `Sequence`-mixinit: yksi `ul[i]`-kutsu per alkio, ja `iter()` päättyy `ul[n]`-kutsun `IndexError`-poikkeukseen |
| `ul == other`, `ul < other` | O(min(n, k)) | O(1) | Vertaa `data`-listaa toiseen listaan tai toisen `UserList`-olion `data`-listaan |

### UserString

| Operaatio | Aika | Tila | Huomautukset |
|-----------|------|-------|-------|
| `collections.UserString(seq)` | O(1) | O(1) | `str` pidetään sellaisenaan, ei kopioida; kaikki muu kulkee ensin `str()`-kutsun läpi sen muunnoksen hinnalla |
| `UserString.data` | O(1) | O(1) | Tavallinen merkkijono |
| `us[i]`, `us[i:j]` | O(1), O(j - i) | O(1), O(j - i) | Uusi `type(us)`-olio merkin tai viipaleen ympärillä, ei koskaan `str` |
| `us`-iterointi | O(n) | O(1) | `Sequence`-mixin: yksi `us[i]` per merkki, joten jokainen merkki saapuu uutena kääreenä |
| `len(us)`, `str(us)` | O(1) | O(1) | `str(us)` on `data` itse |
| `hash(us)` | O(n) | O(1) | `data`-merkkijonon hajautusarvo |
| `sub in us`, `us.count(sub)`, `us.find(sub)`, `us.rfind(sub)`, `us.index(sub)`, `us.rindex(sub)`, `us.startswith(prefix)`, `us.endswith(suffix)` | O(n + k) keskim. | O(1) | `str`-haun keskimääräinen tapaus; tavalliset `int`- tai `bool`-tulokset |
| `us.capitalize()`, `us.casefold()`, `us.center(width)`, `us.expandtabs()`, `us.ljust(width)`, `us.lower()`, `us.lstrip()`, `us.removeprefix(prefix)`, `us.removesuffix(suffix)`, `us.replace(old, new)`, `us.rjust(width)`, `us.rstrip()`, `us.strip()`, `us.swapcase()`, `us.title()`, `us.translate(table)`, `us.upper()`, `us.zfill(width)` | O(n + tuloste) | O(n + tuloste) | Uusi `str` käärittynä `type(us)`-olioon, tulosteen pituinen: n kirjainkoko- ja strip-metodeille, `width` täyttömetodeille ja se, mitä korvaus tai taulu tuottaa |
| `us.split()`, `us.rsplit()`, `us.splitlines()`, `us.partition(sep)`, `us.rpartition(sep)` | O(n) | O(n) | Tavallinen `list` tai `tuple` `str`-olioita: kääretyyppi putoaa pois |
| `us.join(iterable)` | O(k + tuloste) | O(k + tuloste) | Tavallinen `str`; k = yhdistettävät merkkijonot, jotka kootaan ensin listaan, ellei syöte ole jo sekvenssi |
| `us.encode()` | O(n) | O(n) | Tavallinen `bytes` |
| `us.format(*args, **kwargs)`, `us.format_map(mapping)` | O(n + tuloste) | O(n + tuloste) | Tavallinen `str`; koko mallipohja käydään läpi |
| `us.isalnum()`, `us.isalpha()`, `us.isdecimal()`, `us.isdigit()`, `us.isidentifier()`, `us.islower()`, `us.isnumeric()`, `us.isprintable()`, `us.isspace()`, `us.istitle()`, `us.isupper()` | O(n) | O(1) | Pysähtyvät ensimmäiseen merkkiin, joka ratkaisee vastauksen |
| `us.isascii()` | O(1) | O(1) | Lukee lipun, jota `str` pitää yllä |
| `us + other`, `other + us` | O(n + k) | O(n + k) | Uusi kääre; muu kuin `str`-operandi kulkee `str()`-kutsun läpi |
| `us * k`, `us % args` | O(n·k), O(n + tuloste) | O(n·k), O(n + tuloste) | Uusi kääre |
| `us == other`, `us < other` | O(min(n, k)) | O(1) | Vertaa `data`-merkkijonoa; `other` voi olla `str` tai `UserString` |
| `UserString.maketrans(x, y=None, z=None)` | O(k) | O(k) | `str.maketrans` itse |
| `int(us)` | O(n²) | O(n) | `int()` `data`-merkkijonolle, joten [int](../builtins/int.md)-sivun desimaalinumeroiden raja pätee |
| `float(us)`, `complex(us)` | O(n) | O(n) | `data`-merkkijonon muunnokset |

## Kerrostaminen ChainMap-tyypillä

### Haut kulkevat ketjun läpi

`ChainMap` pitää viittauksia, ei kopioita. Jokainen luku kokeilee kuvauksia järjestyksessä ja
pysähtyy ensimmäiseen osumaan, joten viimeisessä kuvauksessa oleva avain maksaa n hakua ja huti
maksaa aina saman. Kirjoitukset menevät yksin `maps[0]`-kuvaukseen, mikä tekee ketjusta hyödyllisen
näkyvyysalueille: lapsialue peittää vanhempansa koskematta niihin.

```python
from collections import ChainMap

defaults = {"timeout": 30, "retries": 3}
user = {"timeout": 60}
config = ChainMap(user, defaults)  # O(n) - two references, nothing copied

assert config["timeout"] == 60  # O(i) - found in the first map
assert config["retries"] == 3  # O(i) - found in the second
assert config.get("colour", "none") == "none"  # O(n) - a miss checks every map

config["retries"] = 5  # O(1) - into maps[0]
assert user == {"timeout": 60, "retries": 5}
assert defaults["retries"] == 3  # the parent is untouched

del config["timeout"]  # O(1) - maps[0] has it
try:
    del config["timeout"]  # now only defaults has it
except KeyError as error:
    assert "first mapping" in str(error)
else:
    raise AssertionError("a key in a later map was deleted")

# Scopes: new_child() puts a fresh map in front, parents drops the front one
scope = config.new_child()  # O(n) - shares every map
scope["timeout"] = 1
assert scope["timeout"] == 1 and config["timeout"] == 30
assert scope.parents.maps == config.maps  # O(n) - a new list over the same maps
```

### Laskeminen ja iterointi maksavat jokaisen avaimen

`len()`-kutsulle ei ole oikotietä: ketju rakentaa joukon kaikista avaimista selvittääkseen, kuinka
moni on erillinen, ja iterointi rakentaa sanakirjan kaikista avaimista ennen ensimmäisen tuottamista.
Molemmat käyvät läpi jokaisen kuvauksen ja jokaisen alkion, O(n + N), rakenteella, joka ei muuten pidä
mitään, joten suurten kuvausten ketjua ei pitäisi mitata eikä iteroida silmukassa. Iterointijärjestys on viimeisen kuvauksen avaimet
ja sitten kunkin aiemman kuvauksen avaimet, joita ei ole vielä nähty.

```python
from collections import ChainMap

first = {"a": 1, "b": 2}
second = {"c": 3, "a": 0}
chain = ChainMap(first, second)

assert len(chain) == 3  # O(n + N) - a set of every key, counted once each
assert list(chain) == ["c", "a", "b"]  # O(n + N) - built before the first key is yielded
assert dict(chain) == {"a": 1, "b": 2, "c": 3}  # O(n + N·n) - each key searched again

# Flattening through | keeps the values the chain would return, but not the layers
flat = {"z": 26} | chain  # O(n + N + k)
assert flat.maps == [{"z": 26, "c": 3, "a": 1, "b": 2}]
```

## Käärintä UserDict-, UserList- ja UserString-tyypeillä

### Koukut ajetaan kerran per alkio

Kääreet ovat olemassa periytettäviksi. Ylikirjoitettu `UserDict.__setitem__` näkee rakentamisen,
`update()`-, `fromkeys()`- ja `|`-operaatiot, jotka kaikki kulkevat sen läpi alkio kerrallaan,
toisin kuin `dict`-tyyppiä periytettäessä; `|=` ja `data`-oliolle välitetyt metodit ohittavat sen.
Ylikirjoitettu `__getitem__` `UserList`- tai `UserString`-oliossa näkee iteroinnin jokaisen
askeleen, sillä iterointi kulkee indeksi kerrallaan sen läpi eikä alla olevan olion iteraattorin kautta.

```python
from collections import UserDict, UserList

class Recording(UserDict):
    def __init__(self, *args, **kwargs):
        self.writes = 0
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        self.writes += 1
        super().__setitem__(key, value)

recorded = Recording({"a": 1, "b": 2, "c": 3})  # O(k) - one __setitem__ per item
assert recorded.writes == 3

recorded.update(d=4)  # O(k) - the mixin loop, one __setitem__ per item
assert recorded.writes == 4

merged = recorded | {"e": 5}  # O(n + k) - the merged dict is fed back through __setitem__
assert merged.writes == 5
assert recorded.writes == 4

class Indexed(UserList):
    reads = 0

    def __getitem__(self, index):
        Indexed.reads += 1
        return super().__getitem__(index)

items = Indexed([10, 20, 30])
assert list(items) == [10, 20, 30]  # O(n) - n + 1 __getitem__ calls, the last raising IndexError
assert Indexed.reads == 4
```

### UserDict-olion tyhjentäminen

`UserDict` ei määrittele metodeja `clear()`, `popitem()` eikä `pop()`; se perii ne
`MutableMapping`-luokalta. Sen `popitem()` ottaa ensimmäisen avaimen, jonka uusi iteraattori tuottaa,
ja sanakirjan iteraattorin on ohitettava jokainen paikka, jonka aiemmat poistot tyhjensivät, joten
`popitem()` maksaa O(d) ja koko sanakirjan tyhjentäminen `clear()`-kutsulla maksaa O(n·(n + d)).
Tyhjennä `data`-sanakirja suoraan.

```python
from collections import UserDict

wrapped = UserDict({"a": 1, "b": 2, "c": 3})

assert wrapped.popitem() == ("a", 1)  # O(d) - the first key still present
assert wrapped.popitem() == ("b", 2)

wrapped.data.clear()  # O(n) - the dict's own clear
assert len(wrapped) == 0

wrapped.update(zip("xyz", range(3)))
wrapped.clear()  # O(n·(n + d)) - popitem() until empty
assert len(wrapped) == 0
```

### Kääreet palaavat kääreinä

Tekstiä muuntavat `UserString`-metodit, kuten `upper()` ja `strip()`, palauttavat uuden
`type(us)`-olion, samoin indeksointi ja iterointi, joten silmukka `UserString`-olion yli varaa yhden
kääreen per merkki. Tekstisäiliöitä palauttavat metodit, kuten `split()` ja `partition()`, palauttavat
tavallisia `str`-olioita tavallisessa `list`- tai `tuple`-säiliössä, ja `join()`, `format()` ja
`format_map()` palauttavat tavallisen `str`-olion.
`UserList`-olion viipalointi ja aritmetiikka palauttavat niin ikään `type(ul)`-olion, joka rakennetaan
`__init__`-metodilla, joten aliluokan konstruktori, jolla on ylimääräisiä pakollisia argumentteja,
rikkoo viipaloinnin.

```python
from collections import UserString

source = "abc"
text = UserString(source)  # O(1) - the str is held, not copied
assert text.data is source

assert type(text.upper()) is UserString  # O(n) - a new str, wrapped
assert type(text[0]) is UserString  # O(1) - even one character is wrapped
assert all(type(char) is UserString for char in text)  # O(n) - one wrapper per character

assert type(text.split()) is list and type(text.split()[0]) is str  # O(n) - plain str inside
assert type(text.join(["x", "y"])) is str  # O(output) - plain str
assert type(text.encode()) is bytes
assert text.count("b") == 1 and text.find("z") == -1  # O(n + k) - plain int results
```

## Yleisiä malleja

### Asetukset ylikirjoituksilla

```python
from collections import ChainMap

defaults = {"host": "localhost", "port": 8000, "debug": False}
environment = {"port": 8080}
command_line = {"debug": True}

settings = ChainMap(command_line, environment, defaults)  # O(n) - three references

assert settings["port"] == 8080  # O(i) - the environment wins over the default
assert settings["debug"] is True  # O(i) - the command line wins over everything
assert settings["host"] == "localhost"  # O(n) - found in the last map

# Read the resolved settings once, then work from the dict
resolved = dict(settings)  # O(n + N·n) - once, not on every read
assert resolved == {"host": "localhost", "port": 8080, "debug": True}
```

## Suorituskyvyn parhaat käytännöt

✅ **Tee näin**:

- Pidä `ChainMap` lyhyenä: jokainen huti, `get()` oletusarvolla ja viimeisessä kuvauksessa olevan avaimen luku maksaa yhden haun per kuvaus
- Litistä `dict(chain)`-kutsulla kerran, kun ketjua luetaan silmukassa, jotta kuvauskohtainen haku tapahtuu kerran per avain eikä kerran per luku
- Tyhjennä `UserDict` `data.clear()`-kutsulla; peritty `clear()` on neliöllinen alkioiden ja niitä ennen poistettujen paikkojen määrässä
- Käytä `ud.data`-, `ul.data`- tai `us.data`-attribuuttia, kun kuuma silmukka ei tarvitse aliluokan koukkuja

❌ **Vältä**:

- `len()`-kutsua tai iterointia `ChainMap`-olion yli silmukassa - jokainen kutsu rakentaa uudelleen joukon tai sanakirjan kaikista avaimista
- `UserDict`-olion vertaamista `==`-operaattorilla kuumalla polulla: mixin litistää molemmat puolet uusiksi sanakirjoiksi joka kerta
- `UserString`-olion iterointia merkki kerrallaan; jokainen merkki on uusi kääreolio
- `UserList`-aliluokkaa, jonka `__init__` tarvitsee ylimääräisiä argumentteja: viipalointi, `copy()`, `+` ja `*` rakentavat kaikki sen kautta

## Versiohuomautukset

- **Python 3.12+**: `UserDict.get()` palauttaa oletusarvon puuttuvalle avaimelle kutsumatta `__missing__`-metodia; ennen 3.12:ta peritty `Mapping.get()` kulki `__getitem__`-metodin läpi ja kutsui sitä
- **Kaikki Python 3 -versiot**: `len()` ja iterointi `ChainMap`-olion yli maksavat jokaisen alkion jokaisessa kuvauksessa; ketjusta ei välimuistiteta mitään

## Liittyvät moduulit

- **[dict](../builtins/dict.md)** - mitä välitetyt `UserDict`-operaatiot maksavat
- **[list](../builtins/list.md)** - mitä välitetyt `UserList`-operaatiot maksavat
- **[str](../builtins/str.md)** - mitä välitetyt `UserString`-operaatiot maksavat
