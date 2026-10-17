---
source_sha: d68992f3f4de5abc5706af482d0525f0a95ba6718edc716dc1d6379f72e39aa0
translated: machine
---

# Merkkijono-operaatioiden vaativuus

Tyyppi `str` on muuttumaton Unicode-merkkien jono. CPython tallentaa jokaisen merkkijonon yhdellä
kiinteällä merkkikohtaisella leveydellä, 1, 2 tai 4 tavua sen leveimmän merkin mukaan, joten
indeksointi on suoraa. Koska merkkijono ei voi muuttua, täsmälleen `str`-tyyppisen merkkijonon
kopiointi palauttaa merkkijonon itsensä.

`n` on merkkijonon pituus, `m` merkkijonoargumentin (`sub`, `prefix`, `sep`, `old`) pituus, `r`
tuloksen pituus, `k` toistokerroin, `w` pyydetty leveys ja `c` `chars`-argumentin pituus. `i:j`
ovat viipaleen rajat, laskettuna sen jälkeen, kun negatiiviset arvot on normalisoitu. Kun annetaan
argumentit `start` ja `end`, `n` on haettavan alueen pituus, ja alue luetaan paikallaan eikä sitä
kopioida. Monimerkkinen argumentti, joka on tallennettu kapeampana kuin `s`, kuten ASCII-osajono
tekstissä, jossa on CJK-merkki, kopioidaan ensin `s`:n leveyteen: O(m) lisätilaa hakumetodeille
sekä metodeille `count()`, `replace()`, `split()`, `rsplit()`, `partition()` ja `rpartition()`.

## Vaativuustaulukko

### str

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `len(s)` | O(1) | O(1) | Pituus on tallennettu merkkijonoon, sitä ei lasketa |
| `s[k]` | O(1) | O(1) | Suora indeksointi; tulos on yhden merkin merkkijono |
| `s[i:j]` (viipalointi) | O(j-i) | O(j-i) | Askeleen kanssa O(r); täsmälleen `str`-tyyppisen merkkijonon `s[:]` palauttaa `s`:n itsensä |
| `s[:]`, `str(s)`, `copy.copy(s)` | O(1) | O(1) | Palauttavat `s`:n itsensä, kun se on täsmälleen `str`; aliluokan instanssi kopioidaan ajassa O(n) |
| `s + t` (yhdistäminen) | O(n+len(t)) | O(n+len(t)) | Palauttaa toisen operandin itsensä, kun toinen on tyhjä; merkkijonon rakentaminen silmukassa `+=`-operaattorilla on pahimmassa tapauksessa O(r²) |
| `s * k` (toisto) | O(nk) | O(nk) | k ≤ 0 antaa tyhjän merkkijonon; `s * 1` palauttaa `s`:n itsensä |
| `s == t` | O(n) | O(1) | O(1), kun pituudet tai merkkien leveydet eroavat tai kumpikin on sama olio |
| `s < t`, `<=`, `>`, `>=` | O(min(n, len(t))) | O(1) | Pysähtyy ensimmäiseen erisuureen merkkiin |
| `hash(s)` | O(n) ensimmäisellä kutsulla; O(1) sen jälkeen | O(1) | Tulos säilytetään merkkijonossa; erikseen rakennettu yhtäsuuri merkkijono maksaa oman ensimmäisen hajautuksensa |
| `for c in s` | O(n) | O(1) | Yksi yhden merkin merkkijono askelta kohden |
| `sub in s` (osajono) | O(n) | O(1), leventäessä O(m) | Eteenpäin suuntautuva haku, jonka pahin tapaus on lineaarinen; merkkijonoa pidempi osajono palaa heti |
| **Haku** ||||
| `find(sub, start, end)` | O(n) | O(1), leventäessä O(m) | Eteenpäin suuntautuva haku; n = haettavat merkit |
| `rfind(sub, start, end)` | pahin O(n·m) | O(1), leventäessä O(m) | Taaksepäin suuntautuva haku; tyypillisellä syötteellä O(n) |
| `index(sub, start, end)` | O(n) | O(1), leventäessä O(m) | Kuten `find()`, mutta nostaa `ValueError`-poikkeuksen, jos osajonoa ei löydy |
| `rindex(sub, start, end)` | pahin O(n·m) | O(1), leventäessä O(m) | Kuten `rfind()`, mutta nostaa `ValueError`-poikkeuksen, jos osajonoa ei löydy |
| `count(sub, start, end)` | O(n) | O(1), leventäessä O(m) | Eteenpäin suuntautuva haku |
| `startswith(prefix)` | O(m) | O(1) | Vertaa vain etuliitettä |
| `endswith(suffix)` | O(m) | O(1) | Vertaa vain jälkiliitettä |
| **Korvaus ja muunnos** ||||
| `replace(old, new)` | O(n + r) | O(r), leventäessä O(m) | Eteenpäin suuntautuva haku `old`-jonolle; palauttaa `s`:n itsensä, kun `old` ei esiinny |
| `translate(table)` | O(n + r) | O(n + r) | Kukin taulukkohaku lasketaan O(1):ksi; pidempiin merkkijonoihin muuntava kuvaus tekee r:stä suuremman kuin n |
| `str.maketrans(x, y, z)` | O(e) | O(e) | e = argumenttien merkit tai sanakirjan merkinnät; staattinen metodi |
| `expandtabs(tabsize)` | O(n + r) | O(r) | Jokainen sarkain kasvattaa tulosta enintään `tabsize` merkillä; ilman sarkaimia palauttaa `s`:n itsensä |
| `removeprefix(prefix)` | O(n) | O(n) | Kopioi loput, kun `prefix` täsmää; muuten O(m) ja palauttaa `s`:n itsensä |
| `removesuffix(suffix)` | O(n) | O(n) | Kopioi loput, kun `suffix` täsmää; muuten O(m) ja palauttaa `s`:n itsensä |
| **Pilkkominen ja yhdistäminen** ||||
| `split(sep)` | O(n) | O(n) | Eteenpäin suuntautuva haku `sep`-jonolle |
| `rsplit(sep)` | pahin O(n·m) | O(n) | Hakee taaksepäin kuten `rfind()`; O(n) ilman `sep`-argumenttia tai yhden merkin erottimella |
| `splitlines()` | O(n) | O(n) | Pilkkoo rivinvaihtojen kohdalta |
| `partition(sep)` | O(n) | O(n) | Eteenpäin suuntautuva haku ensimmäiselle `sep`-jonolle |
| `rpartition(sep)` | pahin O(n·m) | O(n) | Hakee taaksepäin kuten `rfind()` |
| `sep.join(iterable)` | O(r + p) | O(r + p) | p = palat; iteroitava, joka ei ole lista tai monikko, kerätään ensin listaksi; yksittäinen täsmälleen `str`-tyyppinen pala palautetaan itsenään |
| **Kirjainkoon muunnos** ||||
| `upper()` | O(n) | O(n) | |
| `lower()` | O(n) | O(n) | |
| `capitalize()` | O(n) | O(n) | Ensimmäinen otsikkokirjaimeksi, loput pieniksi |
| `title()` | O(n) | O(n) | Sanat otsikkokirjaimin |
| `swapcase()` | O(n) | O(n) | |
| `casefold()` | O(n) | O(n) | Kirjainkoosta riippumattomaan vertailuun |
| **Riisuminen** ||||
| `strip(chars)` | O(n + (d+1)·c) | O(n) | d = riisutut merkit, joista kukin haetaan `chars`-jonosta; palauttaa `s`:n itsensä, kun mitään ei riisuta |
| `lstrip(chars)` | O(n + (d+1)·c) | O(n) | Kuten `strip()`, vasemmalta |
| `rstrip(chars)` | O(n + (d+1)·c) | O(n) | Kuten `strip()`, oikealta |
| **Täyttö ja tasaus** ||||
| `center(width)` | O(w) | O(w) | Palauttaa `s`:n itsensä, kun w ≤ n |
| `ljust(width)` | O(w) | O(w) | Palauttaa `s`:n itsensä, kun w ≤ n |
| `rjust(width)` | O(w) | O(w) | Palauttaa `s`:n itsensä, kun w ≤ n |
| `zfill(width)` | O(w) | O(w) | Palauttaa `s`:n itsensä, kun w ≤ n |
| **Predikaatit** ||||
| `isalnum()` | O(n) | O(1) | |
| `isalpha()` | O(n) | O(1) | |
| `isascii()` | O(1) | O(1) | Lukee lipun, jonka `str` säilyttää |
| `isdecimal()` | O(n) | O(1) | |
| `isdigit()` | O(n) | O(1) | |
| `isidentifier()` | O(n) | O(1) | |
| `islower()` | O(n) | O(1) | |
| `isnumeric()` | O(n) | O(1) | |
| `isprintable()` | O(n) | O(1) | |
| `isspace()` | O(n) | O(1) | |
| `istitle()` | O(n) | O(1) | |
| `isupper()` | O(n) | O(1) | |
| **Muotoilu** ||||
| `format(*args, **kwargs)` | O(n) + kunkin kentän `format()` | O(n) + kunkin kentän `format()` | n = mallipohjan pituus; katso [format()](format.md) |
| `format_map(mapping)` | O(n) + kunkin kentän `format()` | O(n) + kunkin kentän `format()` | Kuten `format()`, mutta kuvauksella |
| `s % values` | O(n) + kukin muunnos | O(n) + kukin muunnos | `%s` kutsuu `str()`-funktiota; katso [format()](format.md) |
| **Koodaus** ||||
| `encode(encoding)` | O(n) | O(n) | Muuntaa tavuiksi; olettaa koodekin, joka tekee vakiomäärän työtä merkkiä kohden |

## Kopiointi palauttaa saman merkkijonon

Täsmälleen `str`-tyyppisen merkkijonon kopio ei voisi koskaan erota alkuperäisestä, joten `s[:]`,
`str(s)` ja `copy.copy(s)` palauttavat `s`:n itsensä ajassa O(1). Useat metodit tekevät samoin,
kun niillä ei ole mitään muutettavaa: täyttö leveyteen, joka ei ole merkkijonoa suurempi,
riisuminen, kun mikään ei täsmää, `replace()`, kun `old` ei esiinny, ja yksittäisen merkkijonon
`join()`. Aliluokan instanssi kopioidaan ajassa O(n).

```python
import copy

s = "x" * 1_000_000
assert s[:] is s  # O(1)
assert str(s) is s  # O(1)
assert copy.copy(s) is s  # O(1)

assert s.center(10) is s  # w <= n
assert s.strip() is s  # nothing to strip
assert s.replace("y", "z") is s  # "y" does not occur
assert "".join([s]) is s  # a single piece


class Text(str):
    pass


t = Text("abc")
assert str(t) is not t and type(str(t)) is str  # O(n): a subclass is copied
```

## Merkkien leveys

Jokainen merkkijono tallennetaan sillä leveydellä, jonka sen levein merkki tarvitsee: 1 tavu
merkkiä kohden U+00FF:ään asti, 2 tavua U+FFFF:ään asti ja 4 tavua sen yli. Yksikin leveä merkki
tekee koko merkkijonosta leveän, minkä vuoksi kapeampi osajono täytyy leventää ennen kuin sitä
haetaan.

```python
import sys


def bytes_per_char(ch):
    return (sys.getsizeof(ch * 2_000) - sys.getsizeof(ch * 1_000)) // 1_000


assert bytes_per_char("a") == 1
assert bytes_per_char("é") == 1
assert bytes_per_char("世") == 2
assert bytes_per_char("😀") == 4

# One CJK character makes all 1,000 ASCII characters take 2 bytes each
assert sys.getsizeof("世" + "a" * 1_000) - sys.getsizeof("世") == 2_000
```

## Merkkijonojen rakentaminen

Jokainen kahden ei-tyhjän merkkijonon `+` rakentaa uuden merkkijonon, joten `+=`-silmukka voi
kopioida kaiken siihen mennessä rakennetun joka askeleella, yhteensä O(r²) kokonaispituuden
suhteen. CPython voi joskus kasvattaa merkkijonoa paikallaan, mutta vain niin kauan kuin mikään
muu ei viittaa siihen: mikä tahansa muu viittaus osittaiseen tulokseen saa jokaisen askeleen
kopioimaan. `join()` mitoittaa tuloksen kerran ja kopioi kunkin palan kerran.

```python
pieces = [str(i) for i in range(10_000)]

joined = "".join(pieces)  # O(r + p)

built = ""
for piece in pieces:
    built += piece  # O(r²) at worst

assert built == joined
```

## Osajonon haku

Eteenpäin suuntautuvien hakujen (`in`, `find()`, `index()`, `count()` sekä haku metodeissa
`split()`, `partition()` ja `replace()`) pahin tapaus on lineaarinen. Taaksepäin suuntautuvat haut
(`rfind()`, `rindex()`, `rsplit()`, `rpartition()`) ovat tyypillisellä syötteellä O(n), mutta
pahimmassa tapauksessa O(n·m). Argumenteilla `start` ja `end` luetaan vain kyseinen alue, eikä
mitään kopioida, toisin kuin viipaloitaessa ensin.

```python
s = "a" * 1_000_000 + "b"

assert s.find("b") == 1_000_000  # O(n)
assert s.find("b", 0, 1_000) == -1  # O(1,000): only the region is read
assert "a" * 999 + "b" in s  # O(n), however long the pattern
assert s.rfind("ba") == -1  # O(n) here, O(n·m) at worst
```

## Suorituskyvyn parhaat käytännöt

✅ **Tee näin**:

- Rakenna merkkijono monesta palasta `"".join(pieces)`-kutsulla: O(r + p) kerran
- Anna `find()`- tai `count()`-metodille `start` ja `end` sen sijaan, että viipaloisit ensin:
  alue luetaan paikallaan, kun taas viipale kopioi O(j-i) merkkiä
- Suosi pitkillä hahmoilla eteenpäin suuntautuvaa hakua taaksepäin suuntautuvan sijaan: O(n)
  vastaan pahimmillaan O(n·m)

❌ **Vältä**:

- `+=`-operaattoria silmukassa monen palan yli, varsinkin kun osittaiseen merkkijonoon on toinen
  viittaus
- Pitkiä `chars`-argumentteja `strip()`-metodille: kukin riisuttu merkki haetaan `chars`-jonosta

## Liittyvät tyypit

- **[Bytes](bytes.md)** - Muuttumaton tavujono
- **[Bytearray](bytearray.md)** - Muuttuva tavujono
- **[str()](str_func.md)** - Olioiden muuntaminen merkkijonoiksi
- **[format()](format.md)** - f-merkkijonot, `str.format()` ja `%`-muotoilu
- **[Säännölliset lausekkeet (re)](../stdlib/re.md)** - Hahmontunnistus

## Lisälukemista

- [CPython Internals: str](https://zpoint.github.io/CPython-Internals/BasicObject/str/str.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Syväluotaus CPythonin merkkijonototeutukseen
