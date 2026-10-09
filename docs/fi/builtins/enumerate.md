---
source_sha: b889a562e9f00aad128b2d24a4fa016dfcc7707bf8eb8dc89a3f513d6c9e708f
translated: machine
---

# enumerate()-funktion vaativuus

Funktio `enumerate(iterable, start=0)` palauttaa iteraattorin, joka tuottaa `(index, item)`
-monikoita. Se on laiska: sen luominen kutsuu `iter(iterable)` eikä kuluta yhtään alkiota, ja
jokainen askel ottaa yhden alkion tuosta iteraattorista ja liittää siihen laskurin arvon.

`n` on enumerate-oliosta otettujen alkioiden määrä. Kunkin alkion hakeminen taustalla olevasta
iteraattorista hinnoitellaan O(1):ksi, kuten listoille, monikoille, merkkijonoille ja
range-olioille; iteraattori, joka tekee enemmän työtä alkiota kohden, lisää sen kustannuksen
jokaiseen askeleeseen. Jokainen indeksi hinnoitellaan O(1):ksi, mikä pätee, kun `start` mahtuu
konesanaan.

## Vaativuusviite

### enumerate

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `enumerate(iterable, start=0)` | O(1) | O(1) | Kutsuu `iter(iterable)` kerran eikä ota alkioita; iteroitumaton olio nostaa `TypeError`-poikkeuksen tässä |
| `next()` enumerate-oliolle | O(1) | O(1) | Ottaa yhden alkion taustalla olevasta iteraattorista |
| enumerate-olion iterointi | O(n) | O(1) | Monikot tuotetaan yksi kerrallaan, niitä ei kerätä talteen |
| `list(enumerate(iterable))` | O(n) | O(n) | Säilyttää kaikki n monikkoa |
| `enumerate[T]` | O(1) | O(1) | Geneerinen alias tyyppivihjeitä varten |

## Peruskäyttö

### Yksinkertainen numerointi

```python
items = ['a', 'b', 'c']

pairs = []
for index, item in enumerate(items):      # O(n)
    pairs.append((index, item))
assert pairs == [(0, 'a'), (1, 'b'), (2, 'c')]

assert list(enumerate(items)) == [(0, 'a'), (1, 'b'), (2, 'c')]   # O(n) time and space
```

### Oma aloitusindeksi

`start` asettaa ensimmäisen indeksin. Sen on oltava int tai olio, jolla on `__index__`.

```python
items = ['a', 'b', 'c']

assert list(enumerate(items, start=1)) == [(1, 'a'), (2, 'b'), (3, 'c')]
assert list(enumerate(items, 10)) == [(10, 'a'), (11, 'b'), (12, 'c')]
assert list(enumerate(items, -1)) == [(-1, 'a'), (0, 'b'), (1, 'c')]

try:
    enumerate(items, start=1.5)
except TypeError as exc:
    assert "cannot be interpreted as an integer" in str(exc)
else:
    raise AssertionError("a float start did not raise")
```

## Laiska, kertakäyttöinen iterointi

enumerate-olion luominen ei ota alkioita, ja aikaisin pysähtyvä silmukka maksaa vain
ottamistaan alkioista. Olio on iteraattori oman iteraattorinsa yli, joten sen voi kuluttaa vain
kerran.

```python
taken = []

def numbers():
    for value in range(10**9):
        taken.append(value)
        yield value

pairs = enumerate(numbers())      # O(1) - nothing is taken yet
assert taken == []

for index, value in pairs:        # O(k) for k items taken
    if index == 3:
        break
assert taken == [0, 1, 2, 3]

assert next(pairs) == (4, 4)      # O(1) - resumes where the loop stopped
```

```python
pairs = enumerate(['a', 'b'])
assert list(pairs) == [(0, 'a'), (1, 'b')]
assert list(pairs) == []          # already exhausted

try:
    len(enumerate(['a', 'b']))
except TypeError as exc:
    assert "has no len()" in str(exc)
else:
    raise AssertionError("len() did not raise")

try:
    enumerate(['a', 'b'])[0]
except TypeError as exc:
    assert "not subscriptable" in str(exc)
else:
    raise AssertionError("indexing did not raise")
```

Parien kääntämiseksi tai indeksoimiseksi rakenna ensin lista, mikä vie O(n) aikaa ja tilaa:

```python
pairs = list(enumerate(['a', 'b', 'c']))      # O(n)
assert pairs[::-1] == [(2, 'c'), (1, 'b'), (0, 'a')]
assert pairs[1] == (1, 'b')
```

## enumerate() vs range(len(...))

`for i in range(len(seq))` yhdessä `seq[i]`:n kanssa vaatii sekvenssin, joka tukee `len()`-kutsua
ja indeksointia, ja jokainen `seq[i]` lisää sekvenssin indeksoinnin kustannuksen. Listalla se on
O(1), joten molemmat silmukat ovat O(n). `deque`-oliossa indeksointi kaukana päistä on O(n),
mikä tekee silmukasta O(n²), kun taas `enumerate()` käy dequen läpi kerran. `enumerate()` toimii
myös generaattoreilla, tiedostoilla ja muilla iteroituvilla olioilla, joita ei voi indeksoida.

```python
from collections import deque

d = deque(range(1000))

by_index = [(i, d[i]) for i in range(len(d))]    # O(n²) - each d[i] walks the deque
by_enumerate = list(enumerate(d))               # O(n)
assert by_index == by_enumerate

lines = iter(['first', 'second'])
assert list(enumerate(lines, start=1)) == [(1, 'first'), (2, 'second')]
```

## Yleisiä malleja

### Jokaisen sijainnin löytäminen

Yksi läpikäynti `enumerate()`-funktiolla löytää jokaisen osuman ajassa O(n). `list.index()`
palauttaa vain ensimmäisen osuman ja nostaa `ValueError`-poikkeuksen, jos osumaa ei ole.

```python
items = ['apple', 'banana', 'cherry', 'banana']

positions = [i for i, item in enumerate(items) if item == 'banana']   # O(n)
assert positions == [1, 3]

assert items.index('banana') == 1     # O(n) - first match only

try:
    items.index('date')
except ValueError:
    pass
else:
    raise AssertionError("index() found a missing item")
```

### Yhdistäminen zip()-funktioon

```python
names = ['Alice', 'Bob', 'Charlie']
ages = [30, 25, 35]

rows = [f"{i}: {name} is {age}" for i, (name, age) in enumerate(zip(names, ages))]   # O(n)
assert rows == ["0: Alice is 30", "1: Bob is 25", "2: Charlie is 35"]
```

### Hakutaulun rakentaminen

```python
items = ['apple', 'banana', 'cherry']

by_number = dict(enumerate(items, start=1))               # O(n)
assert by_number == {1: 'apple', 2: 'banana', 3: 'cherry'}

position = {item: i for i, item in enumerate(items)}      # O(n) once, then O(1) lookups
assert position['cherry'] == 2
```

## Erikoistapaukset

```python
assert list(enumerate([])) == []
assert list(enumerate('ab')) == [(0, 'a'), (1, 'b')]
assert list(enumerate({'x': 1, 'y': 2})) == [(0, 'x'), (1, 'y')]   # dict keys

try:
    enumerate(42)
except TypeError as exc:      # raised when the object is built, not when it is iterated
    assert "not iterable" in str(exc)
else:
    raise AssertionError("enumerate(42) did not raise")
```

## Suorituskyvyn parhaat käytännöt

✅ **Tee näin**:

- Käytä `enumerate()`-funktiota, kun tarvitset sekä indeksin että alkion - yksi O(n) läpikäynti mistä tahansa iteroituvasta
- Pysähdy aikaisin `break`-lauseella - maksat vain ottamistasi alkioista
- Rakenna `{item: index}`-sanakirja kerran, kun haet erillisten, hajautuskelpoisten alkioiden sijainteja toistuvasti

❌ **Vältä**:

- `range(len(seq))` ja `seq[i]` `deque`-oliolla tai muulla sekvenssillä, jonka indeksointi on kallista - O(n²)
- `list(enumerate(...))`, kun yksi silmukka parien yli riittää - O(n) tilaa turhaan
- Jo loppuun kulutetun enumerate-olion iterointia uudelleen - toinen läpikäynti on tyhjä

## Liittyvät funktiot

- **[zip()](zip.md)** - Yhdistää useita iteroituvia
- **[range()](range.md)** - Tuottaa lukujonoja
- **[iter()](iter.md)** - Luo iteraattoreita
- **[next()](next.md)** - Hakee iteraattorin seuraavan alkion

## Versiohuomautukset

- **Kaikki Python 3 -versiot**: `enumerate()` on laiska ja kertakäyttöinen, ja sen rajat ovat samat kaikissa tuetuissa versioissa
