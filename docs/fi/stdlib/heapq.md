---
source_sha: bc027a0b06cdd8740a2521704ec5280e0839aa5d5e037704f37c0fb6913b975e
translated: machine
---

# heapq-moduulin vaativuus

Moduuli `heapq` pitää binäärikekoa tavallisen `list`-olion sisällä: kekotyyppiä ei ole, vain
funktioita, jotka siirtelevät alkioita omistamassasi listassa niin, että `heap[0]` on aina
pienin. Jokainen operaatio tehdään paikallaan, ja vain `nlargest`, `nsmallest` ja `merge`
pitävät mitään omanaan.

`n` on keon alkiot, `m` on syötteenä annetuista iteroitavista otetut alkiot, `k` on alkiot,
joita `nlargest` tai `nsmallest` pyydetään palauttamaan, ja `r` on `merge`-funktiolle annetut
iteroitavat. Jokainen raja laskee alkioiden välisiä vertailuja ja käsittelee yhtä vertailua ja
yhtä `key`-funktion kutsua O(1)-operaationa.

## Vaativuustaulukko

### Minimikeon funktiot

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|------|---------|
| `heapq.heapify(x)` | O(n) | O(1) | Paikallaan |
| `heapq.heappush(heap, item)` | O(log n) tasoitettu | O(1) tasoitettu | Lista kasvaa samoin kuin `append`-kutsussa |
| `heapq.heappop(heap)` | O(log n) tasoitettu | O(1) | Lista kutistuu samoin kuin `pop`-kutsussa; tyhjälle keolle nostaa `IndexError`-poikkeuksen |
| `heapq.heappushpop(heap, item)` | O(log n) | O(1) | O(1), kekoon koskematta, kun keko on tyhjä tai `item` ei ole suurempi kuin `heap[0]` |
| `heapq.heapreplace(heap, item)` | O(log n) | O(1) | Poistaa ennen lisäämistä, joten se voi palauttaa alkion, joka on suurempi kuin `item`; tyhjälle keolle nostaa `IndexError`-poikkeuksen |
| `heap[0]`:n lukeminen | O(1) | O(1) | Pienin alkio poistamatta sitä |

### Maksimikeon funktiot

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|------|---------|
| `heapq.heapify_max(x)` | O(n) | O(1) | Python 3.14+; `heap[0]` on sen jälkeen suurin alkio |
| `heapq.heappush_max(heap, item)` | O(log n) tasoitettu | O(1) tasoitettu | Python 3.14+ |
| `heapq.heappop_max(heap)` | O(log n) tasoitettu | O(1) | Python 3.14+; tyhjälle keolle nostaa `IndexError`-poikkeuksen |
| `heapq.heappushpop_max(heap, item)` | O(log n) | O(1) | Python 3.14+; O(1), kekoon koskematta, kun keko on tyhjä tai `item` ei ole pienempi kuin `heap[0]` |
| `heapq.heapreplace_max(heap, item)` | O(log n) | O(1) | Python 3.14+; tyhjälle keolle nostaa `IndexError`-poikkeuksen |

### Valinta ja yhdistäminen

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|------|---------|
| `heapq.nlargest(k, iterable, key=None)` | O(m log k) | O(k) | Yksi vertailu alkiolle, joka ei pääse tulokseen, joten satunnainen syöte pienellä k:lla maksaa lähes O(m); nouseva syöte päästää jokaisen alkion sisään. k = 1 on yksi `max()`-läpikäynti, O(m). `key` kutsutaan kerran alkiota kohden |
| `heapq.nsmallest(k, iterable, key=None)` | O(m log k) | O(k) | Peilikuva: laskeva syöte on pahin tapaus, ja k = 1 on yksi `min()`-läpikäynti |
| `heapq.merge(*iterables, key=None, reverse=False)` | O(r + m log r) | O(r) | Laiska: pitää yhden alkion syötettä kohden. Jokaisen syötteen on oltava valmiiksi järjestetty tulosteen suuntaan; tätä ei tarkisteta. `key` kutsutaan enintään kerran alkiota kohden |

## Keon rakenne

Keko on lista, jossa indeksin `i` alkio ei ole suurempi kuin kumpikaan indekseissä `2*i + 1` ja
`2*i + 2` olevista. `heapify` saa aikaan vain tämän, ajassa O(n): lista ei ole järjestetty, ja
vain `heap[0]`:n tiedetään olevan pienin.

```python
import heapq

data = [5, 3, 7, 1, 9, 4]
heapq.heapify(data)  # O(n), in place

assert data[0] == 1          # O(1) - the root is the smallest
assert data != sorted(data)  # a heap, not a sorted list
for parent in range(len(data)):
    for child in (2 * parent + 1, 2 * parent + 2):
        if child < len(data):
            assert data[parent] <= data[child]
```

## Lisääminen ja poistaminen

Lisäys tai poisto kulkee yhden polun juuren ja lehden välillä, joten se maksaa keon korkeuden,
O(log n). Koko keon tyhjentäminen on siksi O(n log n).

```python
import heapq

heap = []
for priority in [5, 1, 4, 2, 3]:
    heapq.heappush(heap, priority)  # O(log n) amortized

assert heap[0] == 1  # O(1) peek
drained = [heapq.heappop(heap) for _ in range(len(heap))]  # O(n log n) in total
assert drained == [1, 2, 3, 4, 5]

try:
    heapq.heappop(heap)
except IndexError as error:
    assert 'index out of range' in str(error)
else:
    raise AssertionError('popped from an empty heap')
```

### Tasapelit ja vertailukelvottomat hyötykuormat

Monikot vertaillaan kenttä kerrallaan, joten kaksi alkiota, joilla on sama prioriteetti,
siirtyvät vertailemaan seuraavaa kenttää. Laita siihen yksilöllinen laskuri, niin hyötykuormaa ei
koskaan vertailla: samat prioriteetit tulevat silloin ulos lisäysjärjestyksessä, eikä
hyötykuormalta, joka ei tue `<`-vertailua, koskaan pyydetä sitä.

```python
import heapq
import itertools

class Job:
    def __init__(self, name):
        self.name = name

heap = []
try:
    heapq.heappush(heap, (1, Job('a')))
    heapq.heappush(heap, (1, Job('b')))  # equal priority reaches Job < Job
except TypeError as error:
    assert "'<' not supported" in str(error)
else:
    raise AssertionError('two Jobs were compared')

counter = itertools.count()
heap = []
for name in ['a', 'b', 'c']:
    heapq.heappush(heap, (1, next(counter), Job(name)))  # O(log n)

assert [heapq.heappop(heap)[2].name for _ in range(3)] == ['a', 'b', 'c']
```

## Yhdistetty lisäys ja poisto

`heappushpop` ja `heapreplace` tekevät lisäyksen ja poiston yhdellä kutsulla, joka jättää keon
koon ennalleen. Ne eroavat järjestyksessä: `heappushpop` lisää ensin, joten alkio, joka ei ole
juurta suurempi, palaa suoraan takaisin yhden vertailun jälkeen; `heapreplace` poistaa ensin,
joten se palauttaa aina vanhan juuren, silloinkin kun se on uutta alkiota suurempi.

```python
import heapq

heap = [2, 4, 6]
heapq.heapify(heap)

assert heapq.heappushpop(heap, 1) == 1  # O(1) here - 1 never enters the heap
assert heap == [2, 4, 6]

assert heapq.heapreplace(heap, 1) == 2  # O(log n) - pops 2, then pushes 1
assert sorted(heap) == [1, 4, 6]

assert heapq.heappushpop([], 7) == 7  # an empty heap returns the item
```

## k suurimman valitseminen

Kun k on suurempi kuin 1, `nlargest` pitää keossa k parasta tähän mennessä nähtyä alkiota ja
vertaa jokaista uutta alkiota niistä heikoimpaan. Alkio, joka ei pääse joukkoon, maksaa tuon
yhden vertailun, joten satunnaisella syötteellä ja pienellä k:lla kekoon kosketaan harvoin;
joukkoon pääsevä alkio maksaa O(log k). Valmiiksi nousevassa järjestyksessä oleva syöte on
`nlargest`-funktion pahin tapaus, koska jokainen alkio voittaa kaikki aiemmat, ja laskeva syöte
on `nsmallest`-funktion pahin tapaus. Kummassakin tapauksessa kyse on yhdestä läpikäynnistä,
joka pitää k alkiota, kun taas `sorted()` pitää kaikki m alkiota.

```python
import heapq

scores = [31, 7, 88, 54, 12, 99, 63, 5]

assert heapq.nlargest(3, scores) == [99, 88, 63]  # O(m log k), O(k) memory
assert heapq.nsmallest(2, scores) == [5, 7]       # O(m log k)
assert heapq.nlargest(3, scores) == sorted(scores, reverse=True)[:3]  # same answer, O(m log m)

# key is called once per item, and the items themselves are returned
words = ['pear', 'fig', 'banana', 'kiwi']
assert heapq.nlargest(2, words, key=len) == ['banana', 'pear']

# The input can be any iterable, consumed in one pass
assert heapq.nsmallest(2, (x * x for x in range(-3, 4))) == [0, 1]
```

## Järjestettyjen syötteiden yhdistäminen

`merge` on generaattori. Ensimmäinen `next()` ottaa yhden alkion jokaisesta syötteestä ja tekee
niistä keon, O(r); sen jälkeen jokainen tuotettu alkio maksaa enintään yhden O(log r) -seulonnan,
jolla saman syötteen seuraava alkio tuodaan mukaan. Yhtä alkiota syötettä kohden pidemmälle ei
lueta etukäteen, joten se voi yhdistää muistiin mahtumattomia syötteitä, mutta se luottaa
saamaansa järjestykseen: järjestämätön syöte tuottaa järjestämättömän tulosteen ilman virhettä.

```python
import heapq

merged = heapq.merge([1, 4, 7], [2, 5, 8], [3, 6, 9])  # O(1) - nothing is read yet
assert next(merged) == 1                               # O(r) - one item from each input
assert list(merged) == [2, 3, 4, 5, 6, 7, 8, 9]        # O(log r) per item

# key and reverse: each input must already be sorted that way
by_length = heapq.merge(['fig', 'pear'], ['kiwi', 'banana'], key=len)
assert list(by_length) == ['fig', 'pear', 'kiwi', 'banana']
descending = heapq.merge([9, 5, 1], [8, 2], reverse=True)
assert list(descending) == [9, 8, 5, 2, 1]

# Unsorted input is not detected
assert list(heapq.merge([3, 1], [2])) == [2, 3, 1]
```

## Maksimikeot

### Maksimikeon funktiot

Python 3.14 lisää `_max`-parin kullekin viidestä kekofunktiosta. Niillä on samat kustannukset
kuin minimikeon funktioilla, mutta `heap[0]` on suurin alkio pienimmän sijaan.

```python
import heapq

data = [3, 1, 4, 1, 5, 9, 2, 6]
heapq.heapify_max(data)  # O(n)
assert data[0] == 9      # O(1) - the root is the largest

heapq.heappush_max(data, 10)          # O(log n) amortized
assert heapq.heappop_max(data) == 10  # O(log n) amortized

assert heapq.heapreplace_max(data, 7) == 9   # O(log n) - pops 9, then pushes 7
assert heapq.heappushpop_max(data, 8) == 8   # O(1) here - 8 is not smaller than the root
assert data[0] == 7
```

### Ennen Python 3.14:ää

Numeeristen prioriteettien vastaluvuiksi muuttaminen tekee minimikeon funktioista maksimikeon
samalla kustannuksella.

```python
import heapq

data = [3, 1, 4, 1, 5]
max_heap = [-x for x in data]  # O(n)
heapq.heapify(max_heap)        # O(n)

assert -max_heap[0] == 5               # O(1) peek
assert -heapq.heappop(max_heap) == 5   # O(log n)
heapq.heappush(max_heap, -9)           # O(log n)
assert -max_heap[0] == 9
```

## Yleisiä ratkaisumalleja

### Rajattu k suurimman joukko virrasta

Kun alkioita saapuu yksi kerrallaan ja vain k suurinta merkitsee, k alkion minimikeko pitää ne:
juuri on heikoin jäljellä oleva, ja `heappushpop` korvaa sen vain, kun uusi alkio voittaa sen.

```python
import heapq

k = 3
best = []
for reading in [12, 40, 7, 33, 51, 8, 29, 60]:
    if len(best) < k:
        heapq.heappush(best, reading)      # O(log k)
    else:
        heapq.heappushpop(best, reading)   # O(log k), O(1) if it cannot get in

assert sorted(best, reverse=True) == [60, 51, 40]  # O(k) memory throughout
```

### Tehtävien prioriteettijono

```python
import heapq
import itertools

counter = itertools.count()
queue = []

def submit(priority, task):
    heapq.heappush(queue, (priority, next(counter), task))  # O(log n)

def take():
    priority, _, task = heapq.heappop(queue)  # O(log n)
    return task

submit(2, 'write report')
submit(1, 'fix outage')
submit(2, 'answer email')

assert [take() for _ in range(3)] == ['fix outage', 'write report', 'answer email']
```

## Parhaat käytännöt

✅ **Tee näin**:

- Lue `heap[0]` kurkistaaksesi; se on O(1) eikä vaadi poistoa ja lisäystä
- Käytä `heappushpop`- tai `heapreplace`-funktiota, kun lisäät ja poistat yhdessä: yksi kutsu,
  ei koon muuttamista, ja `heappushpop` palauttaa alkion, joka ei pääse sisään, yhden vertailun
  jälkeen
- Käytä `nlargest`- tai `nsmallest`-funktiota muutaman alkion poimimiseen suuresta tai
  virtaavasta syötteestä; muistinkäyttö seuraa k:ta
- Laita laskuri prioriteetin ja hyötykuorman väliin, jotta tasapelit eivät koskaan vertaile
  hyötykuormia
- Käytä `merge`-funktiota valmiiksi järjestettyihin syötteisiin: se on laiska ja pitää yhden
  alkion syötettä kohden

❌ **Vältä**:

- Koko listan järjestämistä vain muutaman alkion ottamiseksi - O(m log m) aikaa ja O(m) muistia
- Keon tyhjentämistä yhden alkion löytämiseksi; keko järjestää vain juuren
- `heapify`-kutsua jokaisen lisäyksen jälkeen - joka kerta O(n), kun lisäys olisi O(log n)
- Järjestämättömien syötteiden antamista `merge`-funktiolle; tuloste ei ole järjestetty, eikä
  mikään kerro siitä

## Versiohuomiot

- **Python 3.14+**: Lisätty `heapify_max`, `heappush_max`, `heappop_max`, `heappushpop_max` ja
  `heapreplace_max`

## Liittyvät moduulit

- **[queue](queue.md)** - `PriorityQueue` on lukittu `heapq`-keko tuottaja- ja kuluttajasäikeille
- **[sched](sched.md)** - tapahtuma-ajastin, joka on rakennettu ajastettujen tapahtumien keon päälle
- **[bisect](bisect.md)** - pitää listan sen sijaan täysin järjestettynä, O(n)-lisäyksin
- **[sorted()](../builtins/sorted.md)** - O(m log m), kun tarvitaan jokainen alkio eikä vain k suurinta
