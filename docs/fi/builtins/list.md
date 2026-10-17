---
source_sha: e5d540424cf900e9f6a380860ebd4036e31f6ee63640234552e2d102a7e0b262
translated: machine
---

# Listaoperaatioiden vaativuus

Tyyppi `list` on muuttuva, järjestetty jono. CPython toteuttaa sen dynaamisena viittausten
taulukkona: se säilyttää viittauksen jokaiseen alkioon ja ylivaraa tilaa, jotta loppuun
kasvattaminen vaatii harvoin kokomuutosta.

`n` on listan pituus, `k` on numeerisen argumentin arvo (indeksi tai toistokerroin), `i:j` ovat
viipaleen rajat ja `len(t)` on toisen operandin pituus. Askeleellinen viipale, jonka askel on `s`,
valitsee `m` alkiota, ja sen `i` on pienin sen valitsema indeksi. Indeksit lasketaan sen jälkeen,
kun negatiiviset arvot on normalisoitu. Kahden alkion vertailu ja `key`-funktion kutsu lasketaan
O(1):ksi; operandin, joka ei jo ole lista tai monikko, iterointi lisää oman kustannuksensa.
"Tasoitettu" tarkoittaa, että yksittäinen kutsu voi toisinaan maksaa O(n)-kokomuutoksen, joka
jakautuu sitä edeltäneille kutsuille.

## Vaativuustaulukko

### list

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `len(l)` | O(1) | O(1) | Pituus on tallennettu listaan, sitä ei lasketa |
| `l[k]` | O(1) | O(1) | Suora indeksointi |
| `l[k] = x` | O(1) | O(1) | Korvaa yhden paikan |
| `del l[k]` | O(n-k) | O(1) | Siirtää k:n jälkeisiä alkioita yhden paikan vasemmalle |
| `l.append(x)` | O(1) tasoitettu | O(1) tasoitettu | |
| `l.insert(0, x)` | O(n) | O(1) tasoitettu | Jokainen alkio siirtyy yhden paikan oikealle |
| `l.insert(k, x)` | O(n-k) tasoitettu | O(1) tasoitettu | Siirtää alkioita indeksistä k alkaen yhden paikan oikealle |
| `l.remove(x)` | O(n) | O(1) | Hakee alusta ja siirtää sitten osuman jälkeiset alkiot |
| `l.pop()` | O(1) tasoitettu | O(1) | Poistaa viimeisen alkion; mitään ei siirretä |
| `l.pop(0)` | O(n) | O(1) | Jokainen jäljelle jäävä alkio siirtyy yhden paikan vasemmalle |
| `l.pop(k)` | O(n-k) tasoitettu | O(1) | Siirtää k:n jälkeisiä alkioita yhden paikan vasemmalle |
| `l.clear()` | O(n) | O(1) | Vapauttaa jokaisen alkion |
| `l.index(x)` | O(n) | O(1) | Lineaarinen haku; `l.index(x, i, j)` hakee vain viipaleesta `l[i:j]`, O(j-i) |
| `l.count(x)` | O(n) | O(1) | Lineaarinen läpikäynti |
| `l.sort(key=None, reverse=False)` | O(n log n) | O(n) | Järjestetty tai käänteisesti järjestetty syöte vaatii vain O(n) vertailua; `key` kutsutaan kerran alkiota kohden |
| `l.reverse()` | O(n) | O(1) | Paikallaan |
| `l.copy()` | O(n) | O(n) | Pinnallinen kopio |
| `l.extend(t)` | O(len(t)) tasoitettu | O(len(t)) | Lisäksi t:n iteroinnin kustannus |
| `l += t` | O(len(t)) tasoitettu | O(len(t)) | Sama kuin `l.extend(t)`; lista pysyy samana oliona |
| `l[i:j]` (viipalointi) | O(j-i) | O(j-i) | Askeleen kanssa O(m) |
| `l[i:j] = t` | O(j-i), jos len(t) == j-i, muuten O(n-i+len(t)) tasoitettu | O(j-i+len(t)) | Yhtä pitkät korvataan paikallaan; muuten kaikki j:n jälkeen siirtyy |
| `l[i:j:s] = t` (s ≠ 1) | O(m) | O(m) | t:ssä on oltava täsmälleen m alkiota, joten mitään ei siirretä |
| `del l[i:j]` | O(n-i) | O(j-i) | Kaikki j:n jälkeen siirtyy vasemmalle |
| `del l[i:j:s]` | O(n-i) | O(m) | Kaikki i:n jälkeen tiivistyy |
| `l1 + l2` (yhdistäminen) | O(len(l1)+len(l2)) | O(len(l1)+len(l2)) | Uusi lista |
| `l * k` (toisto) | O(nk) | O(nk) | Uusi lista, jossa n·k viittausta; k ≤ 0 antaa tyhjän listan |
| `l *= k` | O(nk) | O(nk) | Paikallaan; k ≤ 0 tyhjentää listan ajassa O(n) |
| `l1 == l2` | O(n) | O(1) | O(1), kun pituudet eroavat; muuten pysähtyy ensimmäiseen erisuureen pariin |
| `l1 < l2`, `<=`, `>`, `>=` | O(min(len(l1), len(l2))) | O(1) | Pysähtyy ensimmäiseen erisuureen pariin |
| `for x in l` (iterointi) | O(n) | O(1) | O(1) askelta kohden |
| `reversed(l)` | O(1) | O(1) | Laiska iteraattori; sen läpikäynti on O(n) |
| `x in l` (jäsenyys) | O(n) | O(1) | Lineaarinen haku |
| `min(l)`, `max(l)` | O(n) | O(1) | n-1 vertailua |

## Kasvattaminen lopusta

`append()` on tasoitetusti O(1), koska kokomuutos varaa tilaa myöhemmille lisäyksille, joten
useimmat lisäykset kirjoittavat tilaan, joka listalla jo on.

```python
import sys

lst = []
resizes = 0
size = sys.getsizeof(lst)
for i in range(10_000):
    lst.append(i)  # O(1) amortized
    if sys.getsizeof(lst) != size:
        resizes += 1
        size = sys.getsizeof(lst)

assert len(lst) == 10_000
assert resizes < 100
```

## Työskentely alussa

Lisääminen tai poistaminen indeksissä 0 siirtää jokaista muuta alkiota, joten jokainen kutsu on
O(n) ja niiden silmukka O(n²). `collections.deque` lisää ja poistaa molemmista päistä ajassa O(1).

```python
from collections import deque

lst = list(range(10_000))
lst.insert(0, -1)  # O(n): every element moves one slot right
assert lst[0] == -1 and len(lst) == 10_001
assert lst.pop(0) == -1  # O(n): every element moves back

queue = deque(range(10_000))
queue.appendleft(-1)  # O(1)
assert queue.popleft() == -1  # O(1)
```

## Viipaleeseen sijoittaminen

Viipaleen korvaaminen yhtä monella alkiolla kirjoittaa sen paikallaan. Mikä tahansa muu pituus
avaa tai sulkee aukon, joten kaikki viipaleen jälkeen siirtyy. Askeleellinen viipale (askel muu
kuin 1) hyväksyy vain täsmälleen niin monta alkiota kuin se valitsee.

```python
lst = list(range(10))
lst[2:5] = ["a", "b", "c"]  # O(j-i): same length, overwritten in place
assert lst == [0, 1, "a", "b", "c", 5, 6, 7, 8, 9]

lst[2:5] = ["x"]  # O(n-i+len(t)): the tail moves left to close the gap
assert lst == [0, 1, "x", 5, 6, 7, 8, 9]

lst[::2] = "ABCD"  # O(m)
assert lst == ["A", 1, "B", 5, "C", 7, "D", 9]

try:
    lst[::2] = "AB"
except ValueError as exc:
    assert "sequence of size 2 to extended slice of size 4" in str(exc)
else:
    raise AssertionError("expected ValueError")
```

## Listan rakentaminen

`l + t` rakentaa uuden listan, joten `l = l + t` silmukassa kopioi kaiken siihen asti rakennetun
joka kierroksella. `l += t` ja `extend()` lisäävät olemassa olevaan listaan ajassa O(len(t))
tasoitettu.

```python
parts = [[i] for i in range(1_000)]

slow = []
for part in parts:
    slow = slow + part  # O(len(slow)): copies the list each time

fast = []
for part in parts:
    fast += part  # O(len(part)) amortized

assert slow == fast == list(range(1_000))
```

## Lajittelu

`sort()` on vakaa ja mukautuva: valmiiksi järjestetty tai käänteisesti järjestetty syöte vaatii
vain O(n) vertailua. `key`-funktiota kutsutaan kerran alkiota kohden, ei kerran vertailua kohden.

```python
calls = 0


def key(word):
    global calls
    calls += 1
    return word.lower()


words = ["pear", "Apple", "fig", "banana"]
words.sort(key=key)  # O(n log n)
assert words == ["Apple", "banana", "fig", "pear"]
assert calls == len(words)
```

## Suorituskyvyn parhaat käytännöt

✅ **Tee näin**:

- Lisää loppuun `append()`- tai `extend()`-metodilla: tasoitetusti O(1) alkiota kohden
- Rakenna lista käänteisessä järjestyksessä lisäämällä loppuun ja kutsu sitten `reverse()` kerran:
  yhteensä O(n)
- Korvaa jakso sijoituksella `l[i:j] = t`, jossa `len(t) == j - i`: mikään sen jälkeen ei siirry
- Anna `sort()`-metodille `key=` mieluummin kuin `functools.cmp_to_key()`-vertailu: avainta
  kutsutaan n kertaa, vertailufunktiota kerran vertailua kohden

❌ **Vältä**:

- `insert(0, x)` tai `pop(0)` silmukassa: kumpikin O(n) - käytä `collections.deque`
- `l = l + [x]` silmukassa: jokainen kierros kopioi listan, yhteensä O(n²)
- `x in l` toisen silmukan sisällä: O(n) testiä kohden - rakenna [joukko](set.md) kerran, jolloin
  haut ovat keskimäärin O(1)

## Liittyvät tyypit

- **[Deque](../stdlib/collections.md#deque)** - O(1) lisäys ja poisto molemmista päistä
- **[Array](../stdlib/array.md)** - Muistitehokkaampi suurille lukulistoille
- **[Monikko](tuple.md)** - Muuttumaton vaihtoehto
- **[list()](list_func.md)** - Listan rakentaminen iteroitavasta

## Lisälukemista

- [CPython Internals: list](https://zpoint.github.io/CPython-Internals/BasicObject/list/list.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Syväluotaus CPythonin listatoteutukseen
