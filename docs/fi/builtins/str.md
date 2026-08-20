---
source_sha: ea4f8b32c47a9951d364d070e44ddc25ab93c4bb79e0e11e0590f61fa3c0e688
translated: machine
---

# Merkkijono-operaatioiden vaativuus

Tyyppi `str` on muuttumaton Unicode-merkkien jono. Pythonin merkkijonoja on optimoitu merkittävästi, erityisesti Python 3:ssa.

## Vaativuustaulukko

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | Suora haku |
| `access[i]` | O(1) | O(1) | Suora indeksointi |
| `in` (substring) | O(n + m) avg | O(1) | Käyttää CPythonissa Two-Way-/fastsearch-algoritmia |
| `s + s` (concatenation) | O(n+m) | O(n+m) | Luo uuden merkkijonon |
| `s * n` (repetition) | O(n\*len(s)) | O(n\*len(s)) | Luo uuden merkkijonon |
| `slice [::2]` | O(k) | O(k) | k = viipaleen pituus |
| **Haku** ||||
| `find(sub)` | O(n + m) avg | O(1) | Käyttää CPythonissa Two-Way-/fastsearch-algoritmia |
| `rfind(sub)` | O(n*m) worst | O(1) | Käyttää taaksepäin toimivaa Boyer-Moore-Horspoolia |
| `index(sub)` | O(n + m) | O(1) | Kuten find(), mutta nostaa ValueErrorin jos ei löydy |
| `rindex(sub)` | O(n*m) worst | O(1) | Kuten rfind(), mutta nostaa ValueErrorin jos ei löydy |
| `count(sub)` | O(n + m) avg | O(1) | n = merkkijono, m = osajono |
| `startswith(prefix)` | O(m) | O(1) | m = etuliitteen pituus |
| `endswith(suffix)` | O(m) | O(1) | m = jälkiliitteen pituus |
| **Korvaus ja muunnos** ||||
| `replace(old, new)` | O(n) | O(n) | Yksi läpikäynti |
| `translate(table)` | O(n) | O(n) | Yksi läpikäynti taulukkohaulla |
| `maketrans()` | O(k) | O(k) | k = kuvausten määrä; staattinen metodi |
| `expandtabs(tabsize)` | O(n) | O(n) | Korvaa sarkaimet välilyönneillä |
| `removeprefix(prefix)` | O(n) | O(n) | Palauttaa viipaleen, jos etuliite täsmää |
| `removesuffix(suffix)` | O(n) | O(n) | Palauttaa viipaleen, jos jälkiliite täsmää |
| **Jako ja yhdistäminen** ||||
| `split(sep)` | O(n) | O(n) | Yksi läpikäynti |
| `rsplit(sep)` | O(n) | O(n) | Jakaa oikealta |
| `splitlines()` | O(n) | O(n) | Jakaa rivinvaihtojen kohdalta |
| `partition(sep)` | O(n) | O(n) | Jakaa 3-monikoksi ensimmäisen erottimen kohdalta |
| `rpartition(sep)` | O(n) | O(n) | Jakaa 3-monikoksi viimeisen erottimen kohdalta |
| `join(iterable)` | O(n) | O(n) | n = tulosteen merkkien kokonaismäärä |
| **Kirjainkoon muunnos** ||||
| `upper()` | O(n) | O(n) | Käsittelee jokaisen merkin |
| `lower()` | O(n) | O(n) | Käsittelee jokaisen merkin |
| `capitalize()` | O(n) | O(n) | Ensimmäinen isolla, loput pienellä |
| `title()` | O(n) | O(n) | Sanojen alkukirjaimet isolla |
| `swapcase()` | O(n) | O(n) | Vaihtaa isot ja pienet keskenään |
| `casefold()` | O(n) | O(n) | Tehostettu pienennys kirjainkoosta riippumattomaan vertailuun |
| **Karsinta** ||||
| `strip(chars)` | O(n) | O(n) | Poistaa molemmista päistä |
| `lstrip(chars)` | O(n) | O(n) | Poistaa vasemmalta |
| `rstrip(chars)` | O(n) | O(n) | Poistaa oikealta |
| **Täyttö ja tasaus** ||||
| `center(width)` | O(n) | O(n) | Täyttää molemmat puolet |
| `ljust(width)` | O(n) | O(n) | Täyttää oikean puolen |
| `rjust(width)` | O(n) | O(n) | Täyttää vasemman puolen |
| `zfill(width)` | O(n) | O(n) | Täyttää nollilla |
| **Predikaatit** ||||
| `isalnum()` | O(n) | O(1) | Tarkistaa aakkosnumeerisuuden |
| `isalpha()` | O(n) | O(1) | Tarkistaa aakkosellisuuden |
| `isascii()` | O(n) | O(1) | Tarkistaa ASCII-merkit (Python 3.7+) |
| `isdecimal()` | O(n) | O(1) | Tarkistaa desimaalimerkit |
| `isdigit()` | O(n) | O(1) | Tarkistaa numeromerkit |
| `isidentifier()` | O(n) | O(1) | Tarkistaa kelvollisen tunnisteen |
| `islower()` | O(n) | O(1) | Tarkistaa pienet kirjaimet |
| `isnumeric()` | O(n) | O(1) | Tarkistaa numeeriset merkit |
| `isprintable()` | O(n) | O(1) | Tarkistaa tulostettavuuden |
| `isspace()` | O(n) | O(1) | Tarkistaa tyhjemerkit |
| `istitle()` | O(n) | O(1) | Tarkistaa otsikkomuodon |
| `isupper()` | O(n) | O(1) | Tarkistaa isot kirjaimet |
| **Muotoilu** ||||
| `format(*args)` | O(n) | O(n) | n = mallin pituus |
| `format_map(mapping)` | O(n) | O(n) | Kuten format(), mutta kuvauksella |
| **Koodaus** ||||
| `encode(encoding)` | O(n) | O(n) | Muuntaa tavuiksi |

## Toteutuksen yksityiskohdat

### Merkkijonojen sisäistäminen

```python
# Small strings and identifiers are interned (reused)
s1 = "hello"
s2 = "hello"
print(s1 is s2)  # Likely True - same object

# Large strings are not interned
s3 = "x" * 1000
s4 = "x" * 1000
print(s3 is s4)  # False - different objects
```

### Python 3:n Unicode-optimointi

```python
# Python 3 uses adaptive string representation
# ASCII strings use less memory than full Unicode

# Compact representation for ASCII
s = "hello"  # Uses 1 byte per character

# Full Unicode representation
s = "hello 世界"  # Uses more bytes for non-ASCII
```

### Merkkijonojen yhdistämisen suorituskyky

```python
# Inefficient: O(n²) - creates new strings repeatedly
result = ""
for i in range(10000):
    result += str(i)  # Copies entire string each time

# Efficient: O(n) - single allocation
result = "".join(str(i) for i in range(10000))
```

## Edistyneet ominaisuudet

### Osajonon haku

```python
# Linear time on average for substring search
s = "a" * 1000000 + "b"
result = s.find("b")  # Usually O(n) avg, not O(n²)

# CPython uses optimized algorithms (similar to Boyer-Moore)
```

## Versiohuomiot

| Versio | Muutos |
|---------|--------|
| Python 3.0+ | Unicode oletuksena |
| Python 3.3+ | Joustava merkkijonoesitys (PEP 393) |
| Python 3.8+ | f-merkkijonojen suorituskykyparannuksia |
| Python 3.11+ | Nopeammat merkkijono-operaatiot, parempi inline-käsittely |

## Toteutusten vertailu

### CPython
Erittäin optimoitu; käyttää merkkijonojen sisäistämistä ja joustavia esitysmuotoja.

### PyPy
JIT-käännös tuo lisäoptimointia toistuviin operaatioihin.

### Jython
Perustuu Javan merkkijonoihin, samankaltaiset suorituskykyominaisuudet.

## Parhaat käytännöt

✅ **Tee näin**:

- Käytä `str.join()`-metodia useiden merkkijonojen yhdistämiseen
- Käytä f-merkkijonoja muotoiluun (Python 3.6+)
- Käytä `in`-operaattoria osajonon tarkistamiseen (keskimäärin O(n))
- Käytä `.find()`- ja `.replace()`-metodeja tehokkaaseen käsittelyyn

❌ **Vältä**:

- Merkkijonojen yhdistämistä silmukoissa `+`-operaattorilla
- Toistuvia `.replace()`-kutsuja - tee kerralla tai käytä säännöllisiä lausekkeita
- Jäsenyyden tarkistamista `in`-operaattorilla sisäkkäisissä silmukoissa ilman välimuistia
- Monien välivaiheen merkkijono-olioiden luomista

## Yleisiä ratkaisumalleja

### Tehokas merkkijonon rakentaminen

```python
# Bad: O(n²)
result = ""
for word in words:
    result += word

# Good: O(n)
result = "".join(words)

# Also good: list comprehension with join
result = "".join([w.upper() for w in words])
```

### Merkkijonojen muotoilu

```python
# Python 3.6+ f-strings (preferred)
name = "World"
message = f"Hello, {name}!"  # Efficient and readable

# Older style (still works)
message = "Hello, {}!".format(name)

# Avoid %
message = "Hello, %s!" % name
```

### Hahmontunnistus

```python
# Use str methods for simple patterns
if s.startswith("test_"):  # O(m) where m = prefix length
    pass

# Use regex for complex patterns
import re
pattern = re.compile(r"test_\d+")  # Compile once
if pattern.match(s):  # Reuse compiled pattern
    pass
```

## Liittyvät tyypit

- **[Bytes](bytes_func.md)** - Muuttumaton tavujono
- **[Bytearray](bytearray_func.md)** - Muuttuva tavujono
- **[Säännölliset lausekkeet (re)](../stdlib/re.md)** - Hahmontunnistus

## Lisälukemista

- [CPython Internals: str](https://zpoint.github.io/CPython-Internals/BasicObject/str/str.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Syväluotaus CPythonin merkkijonototeutukseen
