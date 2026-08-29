---
source_sha: e32210f0b30cd99aa404b93423279e38f89a907a66f182d9e3df1cd3ed5357f2
translated: machine
---

# Collections-moduulin vaativuus

Moduuli `collections` tarjoaa erikoistuneita tietorakenteita, jotka on optimoitu tiettyihin käyttötarkoituksiin.

## deque

### Aikavaativuus

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `append(x)` | O(1) | O(1) | Lisää oikeaan päähän |
| `appendleft(x)` | O(1) | O(1) | Lisää vasempaan päähän |
| `pop()` | O(1) | O(1) | Poistaa oikeasta päästä |
| `popleft()` | O(1) | O(1) | Poistaa vasemmasta päästä |
| `access[i]` | O(1) ends, O(n) middle | O(1) | Päät (d[0], d[-1]) ovat O(1); keskellä olevat alkiot O(n) lohkorakenteen vuoksi |
| `extend(iterable)` | O(k) | O(k) | k = iteroituvan pituus |
| `extendleft(iterable)` | O(k) | O(k) | k = iteroituvan pituus; huom. kääntää järjestyksen |
| `rotate(n)` | O(k) | O(1) | k = min(n, len(d) - n) |
| `clear()` | O(n) | O(1) | Poistaa kaikki alkiot |
| `copy()` | O(n) | O(n) | Pinnallinen kopio |
| `count(x)` | O(n) | O(1) | Laskee x:n esiintymät |
| `index(x)` | O(n) | O(1) | Etsii x:n ensimmäisen esiintymän |
| `insert(i, x)` | O(n) | O(1) | Lisää x:n kohtaan i |
| `remove(x)` | O(n) | O(1) | Poistaa x:n ensimmäisen esiintymän |
| `reverse()` | O(n) | O(1) | Kääntää paikallaan |
| `in` (membership) | O(n) | O(1) | Lineaarinen haku |

### Attribuutit

| Attribuutti | Huomiot |
|-----------|-------|
| `maxlen` | Enimmäiskoko (None jos rajoittamaton); vain luku |

### Tilavaativuus

- Tallennus: O(n) n alkiolle
- Operaatiot: O(1) lisäys- ja poisto-operaatioille

### Käyttötapaukset

```python
from collections import deque

# Process items from both ends - very efficient
queue = deque([1, 2, 3])
queue.appendleft(0)  # O(1) - add to front
queue.pop()  # O(1) - remove from back

# Much faster than list for this pattern:
# list.insert(0, x) is O(n)
# list.pop(0) is O(n)
```

## DefaultDict

### Aikavaativuus

Sama kuin `dict`:

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `d[key]` | O(1) avg | O(1) | Palauttaa oletusarvon jos puuttuu; pahimmillaan O(n) tiivistetörmäysten vuoksi |
| `d[key] = value` | O(1) avg | O(1) | Pahimmillaan O(n) tiivistetörmäysten vuoksi |
| `del d[key]` | O(1) avg | O(1) | Pahimmillaan O(n) tiivistetörmäysten vuoksi |
| `copy()` | O(n) | O(n) | Pinnallinen kopio |
| Muut dict-operaatiot | Sama kuin dict | - | |

### Attribuutit

| Attribuutti | Huomiot |
|-----------|-------|
| `default_factory` | Kutsuttava, joka tuottaa oletusarvot; voi olla None |

### Tilavaativuus

- O(n) n avain-arvo-parille
- Oletustehdasta kutsutaan vain, kun avainta haetaan

### Käyttötapaukset

```python
from collections import defaultdict

# Avoid: manual checking
data = defaultdict(list)
data['key'].append('value')  # O(1) avg - key auto-created as empty list

# Avoid: clunky dict.get()
d = {}
d['key'] = d.get('key', 0) + 1  # O(1) avg, but a get and a set spelled out

# Better: defaultdict with int
counts = defaultdict(int)
counts['key'] += 1  # O(1) avg - still a get plus a set, but one statement
                    # and no default to pass in
```

## Counter

### Aikavaativuus

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `Counter(iterable)` | O(n) | O(k) | n = iteroituvan pituus, k = uniikkien alkioiden määrä |
| `c[item]` | O(1) avg | O(1) | Palauttaa 0 jos puuttuu; pahimmillaan O(n) tiivistetörmäysten vuoksi |
| `c.most_common(k)` | O(n log k) | O(k) | n = `len(c)` eli eri avainten määrä. `k=1` käyttää `max()`-funktiota; `k >= len(c)` palautuu `sorted()`-kutsuun; näiden välillä se on kekopohjainen, ja vakiokerroin on niin suuri, että CPython 3.11:ssä ja 3.14:ssä, kun n oli 10³–10⁶, se mitattiin 2-5 kertaa hitaammaksi kuin kaiken lajittelu |
| `c.update(iterable)` | O(n) | O(k) | n = iteroituvan pituus |
| `c.subtract(iterable)` | O(n) | O(1) | Vähentää lukumääriä; säilyttää negatiiviset arvot |
| `c.total()` | O(n) | O(1) | Kaikkien lukumäärien summa (Python 3.10+) |
| `c.elements()` | O(1) init, O(total) iter | O(1) | Iteraattori, joka toistaa kunkin alkion sen lukumäärän verran |
| `c.copy()` | O(n) | O(n) | Pinnallinen kopio |
| `c.fromkeys(iterable)` | N/A | - | Ei hyödyllinen Counterille; peritty sanakirjalta |
| `c + c2` | O(n) | O(n) | Yhdistää laskurit; säilyttää positiiviset lukumäärät |
| `c - c2` | O(n) | O(n) | Vähentää; säilyttää positiiviset lukumäärät |

### Käyttötapaukset

```python
from collections import Counter

# Count items - O(n) for n items
words = ['apple', 'banana', 'apple', 'cherry', 'apple']
c = Counter(words)
# Counter({'apple': 3, 'banana': 1, 'cherry': 1})

# Most common items - O(n log k) for k items, n = len(c). Passing k is not
# the optimisation it looks like: see the note in the table above
top_3 = c.most_common(3)  # [('apple', 3), ('banana', 1), ('cherry', 1)]

# Arithmetic - O(n) over the combined keys
c1 = Counter('aab')
c2 = Counter('abc')
c1 + c2  # Counter({'a': 3, 'b': 2, 'c': 1})
```

## NamedTuple

### Aikavaativuus

Sama kuin monikolla kaikissa operaatioissa:

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| Luonti | O(1) | O(1) | Kiinteä määrä kenttiä |
| Haku indeksillä | O(1) | O(1) | Sama kuin monikolla |
| Haku nimellä | O(1) | O(1) | Sama kuin monikolla |
| Iterointi | O(n) | O(1) | n = kenttien lukumäärä |

### Käyttötapaukset

```python
from collections import namedtuple

Point = namedtuple('Point', ['x', 'y'])
p = Point(11, y=22)

# Better than plain tuple
print(p.x)  # More readable than p[0]

# Create from dict
d = {'x': 1, 'y': 2}
p = Point(**d)

# Replace values
p2 = p._replace(x=5)
```

## OrderedDict

### Aikavaativuus

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| Sama kuin dict | O(1) | O(1) | Kaikki dict-operaatiot |
| `move_to_end(key)` | O(1) | O(1) | Siirtää avaimen loppuun |

### Huomioita

- **Python 3.6+**: Tavallinen `dict` säilyttää järjestyksen, joten `OrderedDict` on hyödyllinen lähinnä seuraaviin:

  - Yhteensopivuus vanhemman koodin kanssa
  - `move_to_end()`-metodi järjestyksen muuttamiseen
  - Aikomuksen ilmaiseminen koodissa selkeästi

```python
from collections import OrderedDict

# Useful method: move_to_end()
od = OrderedDict([('a', 1), ('b', 2), ('c', 3)])
od.move_to_end('a')  # O(1) - moves 'a' to end
```

## ChainMap

### Aikavaativuus

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `access[key]` | O(n) | O(1) | n = kuvausten lukumäärä; hakee kunnes löytyy |
| `set[key]` | O(1) avg | O(1) | Asettaa ensimmäiseen kuvaukseen; pahimmillaan O(m), missä m = ensimmäisen kuvauksen koko |
| `del[key]` | O(1) avg | O(1) | Poistaa ensimmäisestä kuvauksesta; pahimmillaan O(m), missä m = ensimmäisen kuvauksen koko |
| `len()` | O(N) | O(N) | N = avainten kokonaismäärä kaikissa kuvauksissa; muodostaa sisäisesti joukkojen yhdisteen |
| `in` | O(n) | O(1) | Tarkistaa kaikki kuvaukset |

### Käyttötapaukset

```python
from collections import ChainMap

# Layer multiple dicts
defaults = {'timeout': 30, 'retries': 3}
user_config = {'timeout': 60}

config = ChainMap(user_config, defaults)
print(config['timeout'])  # 60 (from user_config)
print(config['retries'])  # 3 (from defaults)

# View layered configuration without merging
```

## Suorituskyvyn vertailu

| Operaatio | dict | defaultdict | Counter | OrderedDict |
|-----------|------|-------------|---------|------------|
| `d[key]` | O(1) | O(1) | O(1) | O(1) |
| `d[key] = value` | O(1) | O(1) | O(1) | O(1) |
| Erikoismetodit | - | `__missing__` | `most_common()` | `move_to_end()` |
| Muisti | Perustaso | +vähän | +laskurien tallennus | +järjestyksen seuranta |

## UserDict

`UserDict` kietoo tavallisen sanakirjan luokkaan, jota käyttäjä voi mukauttaa.

### Aikavaativuus

Sama kuin `dict` useimmissa operaatioissa:

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `d[key]` | O(1) avg | O(1) | Pahimmillaan O(n) tiivistetörmäysten vuoksi |
| `d[key] = value` | O(1) avg | O(1) | Pahimmillaan O(n) |
| `del d[key]` | O(1) avg | O(1) | Pahimmillaan O(n) |
| Iterointi | O(n) | O(1) | n = alkioiden lukumäärä |

## UserList

`UserList` kietoo tavallisen listan luokkaan, jota käyttäjä voi mukauttaa.

### Aikavaativuus

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| Indeksointi | O(1) | O(1) | Haku indeksillä |
| Lisäys loppuun | O(1) tasoitettu | O(1) | Pahimmillaan O(n) koon muuttuessa |
| Lisäys/poisto | O(n) | O(1) | Siirtää alkioita |
| Iterointi | O(n) | O(1) | n = listan pituus |

## UserString

`UserString` kietoo tavallisen merkkijonon luokkaan, jota käyttäjä voi mukauttaa.

### Aikavaativuus

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| Indeksointi | O(1) | O(1) | Haku indeksillä |
| Yhdistäminen | O(n) | O(n) | n = kokonaispituus |
| Viipalointi | O(k) | O(k) | k = viipaleen pituus |
| Iterointi | O(n) | O(1) | n = pituus |

## Liittyvä dokumentaatio

- [Sisäänrakennettu dict](../builtins/dict.md)
- [Sisäänrakennettu tuple](../builtins/tuple.md)
- [Heapq-moduuli](heapq.md)
