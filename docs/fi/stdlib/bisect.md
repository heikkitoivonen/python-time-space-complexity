---
source_sha: a94d3e8a9450b59cb245eb0f1ed57d4adf9f9336e3b33dadbbff5a31abbd09b2
translated: machine
---

# bisect-moduulin vaativuus

Moduuli `bisect` etsii sijainteja jonosta, jonka kutsuja pitää järjestyksessä. Se ei koskaan
järjestä eikä koskaan tarkista järjestystä: jokainen haku puolittaa sille annetun välin ja lukee
yhden alkion kierrosta kohden vakiomääräisellä lisämuistilla. Lisäysfunktiot yhdistävät tämän haun
jonon omaan `insert()`-metodiin, ja listalla kustannus syntyy lisäyksestä, ei hausta.

`n` on jonon pituus. Hakujen vaativuus lasketaan koetuksina: kukin on yksi alkion luku, yksi `key`-kutsu,
kun avainfunktio on annettu, ja yksi `<`-vertailu, ja jokainen hinnoitellaan O(1):ksi. Avainfunktio
tai vertailu, joka tekee enemmän työtä, kertoo haun kustannuksellaan. Indeksointi on O(1), kuten
listalla. Kaksi alkiota ovat tässä yhtä suuret, kun kumpikaan ei ole `<` toista; kun `key` on
annettu, verrataan avaimia.

## Vaativuusviite

### Haku

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `bisect.bisect_left(a, x, lo=0, hi=len(a), *, key=None)` | O(log n) | O(1) | Sijainti ennen `x`:n kanssa yhtä suurten alkioiden jaksoa; `key` sovelletaan jokaiseen koetettuun alkioon, ei koskaan `x`:ään |
| `bisect.bisect_right(a, x, lo=0, hi=len(a), *, key=None)` | O(log n) | O(1) | Sijainti `x`:n kanssa yhtä suurten alkioiden jakson jälkeen |
| `bisect.bisect(a, x, lo=0, hi=len(a), *, key=None)` | O(log n) | O(1) | Sama funktio kuin `bisect_right` |

### Lisäys

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `bisect.insort_left(a, x, lo=0, hi=len(a), *, key=None)` | O(n) | O(1) | O(log n) haku, sitten `a.insert()`, joka listalla siirtää loppuosaa; `key` sovelletaan `x`:ään kerran |
| `bisect.insort_right(a, x, lo=0, hi=len(a), *, key=None)` | O(n) | O(1) | Lisää `x`:n kanssa yhtä suurten alkioiden jakson jälkeen |
| `bisect.insort(a, x, lo=0, hi=len(a), *, key=None)` | O(n) | O(1) | Sama funktio kuin `insort_right` |

## Haku järjestetystä listasta

### Vasen ja oikea

Haut eroavat vain siinä, mihin ne osuvat yhtä suurten alkioiden jaksossa: `bisect_left` ennen sitä,
`bisect_right` sen jälkeen. Kumpikin puolittaa silti välin, joten toistuvien arvojen jakson haku on
O(log n) kuten mikä tahansa muu haku, ja yhdessä ne rajaavat jakson, oli se kuinka pitkä tahansa.

```python
import bisect

values = [1, 3, 3, 3, 5, 7, 9]

left = bisect.bisect_left(values, 3)    # O(log n)
right = bisect.bisect_right(values, 3)  # O(log n)
assert (left, right) == (1, 4)
assert values[left:right] == [3, 3, 3]
assert right - left == 3                # occurrences counted without a scan

def contains(sorted_list, x):
    i = bisect.bisect_left(sorted_list, x)  # O(log n), against O(n) for `x in sorted_list`
    return i < len(sorted_list) and sorted_list[i] == x

assert contains(values, 5)
assert not contains(values, 4)
```

### Rajaus parametreilla lo ja hi

`lo` ja `hi` rajaavat haettavan viipaleen, ja haku maksaa O(log(hi - lo)) jonon pituudesta
riippumatta. Lisäys `insort`-funktiolla maksaa silti koko listan lisäyksen. Negatiivinen `lo`
nostaa `ValueError`-poikkeuksen.

```python
import bisect

values = list(range(0, 1_000, 2))

assert bisect.bisect_left(values, 100, lo=40, hi=60) == 50  # O(log 20)

try:
    bisect.bisect_left(values, 100, lo=-1)
except ValueError as error:
    assert 'lo must be non-negative' in str(error)
else:
    raise AssertionError('a negative lo was accepted')
```

### Haku avaimella

`key` kutsutaan kerran koetusta kohden koetetulle alkiolle, joten avaimella tehty haku tekee
O(log n) avainkutsua eikä tarvitse rinnakkaista listaa. Sitä ei kutsuta `x`:lle: haut ottavat `x`:n
valmiiksi avainarvona. `insort` on poikkeus - se lisää itse tietueen, joten se kutsuu `key(x)`
kerran löytääkseen paikan.

```python
import bisect

records = [('a', 1), ('b', 3), ('c', 5)]
by_count = lambda record: record[1]

pos = bisect.bisect_right(records, 4, key=by_count)  # O(log n) key calls; x is the key value
assert pos == 2

bisect.insort(records, ('d', 4), key=by_count)  # O(n); key(x) is called here
assert records == [('a', 1), ('b', 3), ('d', 4), ('c', 5)]
```

Rinnakkainen avainlista on vaihtoehto, kun monta hakua jakaa saman listan: sen rakentaminen maksaa
O(n), ja se on pidettävä ajan tasalla jokaisen lisäyksen yhteydessä, mutta silloin yksikään haku ei
tee avainkutsuja.

```python
import bisect

records = [('a', 1), ('b', 3), ('c', 5)]
keys = [record[1] for record in records]  # O(n) once

pos = bisect.bisect_right(keys, 4)  # O(log n), no key calls
records.insert(pos, ('d', 4))       # O(n)
keys.insert(pos, 4)                 # O(n) - keys must follow every insert
assert keys == [record[1] for record in records] == [1, 3, 4, 5]
```

### Järjestämätön syöte

Mikään ei tarkista, että viipale on järjestyksessä. Järjestämättömällä syötteellä haku palauttaa
silti sijainnin nostamatta poikkeusta, mutta mikään ei takaa sen olevan oikea: siihen lisääminen voi
jättää listan epäjärjestykseen.

```python
import bisect

unsorted = [3, 1, 4, 1, 5]

pos = bisect.bisect(unsorted, 2)  # O(log n), no error
result = unsorted[:pos] + [2] + unsorted[pos:]
assert result != sorted(result)
```

## Listan pitäminen järjestyksessä

### Yksi lisäys vai erä

Jokainen `insort` listaan on O(n), joten k lisäystä n alkion listaan maksaa O(k·(n + k)).
Kun lisäykset tulevat yhdessä eikä niiden välissä ole hakuja, niiden lisääminen loppuun ja yksi
järjestäminen maksaa sen sijaan O((n + k) log(n + k)). `insort` on oikea työkalu, kun haut ja
lisäykset vuorottelevat.

```python
import bisect

values = [1, 3, 5, 7]
bisect.insort(values, 4)  # O(n) - the tail shifts
assert values == [1, 3, 4, 5, 7]

# Many inserts at once: O(k·(n + k)) one at a time
one_at_a_time = [1, 3, 5, 7, 9]
for item in [8, 2, 6, 4]:
    bisect.insort(one_at_a_time, item)  # O(n) each

# ... or O((n + k) log(n + k)) as one sort
batch = [1, 3, 5, 7, 9]
batch.extend([8, 2, 6, 4])
batch.sort()
assert batch == one_at_a_time
```

## Yleisiä malleja

### Pistemäärän kuvaaminen arvosanaväliin

```python
import bisect

breakpoints = [60, 70, 80, 90]
grades = 'FDCBA'

def grade(score):
    return grades[bisect.bisect(breakpoints, score)]  # O(log b), b = breakpoints

assert [grade(score) for score in (33, 60, 77, 89, 90, 100)] == list('FDCBAA')
```

### Aikaikkunan tapahtumat

```python
import bisect
from datetime import datetime

events = [
    (datetime(2024, 1, 1, 10), 'event1'),
    (datetime(2024, 1, 1, 12), 'event2'),
    (datetime(2024, 1, 1, 15), 'event3'),
    (datetime(2024, 1, 1, 18), 'event4'),
]
when = lambda event: event[0]

start = bisect.bisect_left(events, datetime(2024, 1, 1, 11), key=when)  # O(log n)
end = bisect.bisect_right(events, datetime(2024, 1, 1, 15), key=when)   # O(log n)
assert [name for _, name in events[start:end]] == ['event2', 'event3']  # O(m), m = matches
```

## Suorituskyvyn parhaat käytännöt

✅ **Tee näin**:

- Käytä jäsenyyden tarkistamiseen järjestetystä listasta `bisect_left`-funktiota ja yhtä vertailua
  O(n) `in`-operaation sijaan
- Käytä erotusta `bisect_right - bisect_left` yhtä suurten alkioiden jakson pituuden laskemiseen ajassa
  O(log n)
- Anna `lo` ja `hi`, kun vastauksen tiedetään olevan listan tietyssä osassa
- Käytä `key`-parametria satunnaiseen hakuun tietueista; pidä rinnakkaista avainlistaa, kun monta
  hakua jakaa sen

❌ **Vältä**:

- Avainlistan rakentamista yhtä hakua varten - se on O(n) O(log n) -vastauksen takia
- Toistuvaa `insort`-kutsua erän lataamiseen listaan - lisää loppuun ja järjestä kerran
- Hakua listasta, jota et ole pitänyt järjestyksessä - vastaus on epäluotettava, eikä mikään nosta
  poikkeusta

## Versiohuomautukset

- **Python 3.10+**: Kaikkiin kuuteen funktioon lisättiin `key`-parametri

## Liittyvät moduulit

- **[heapq](heapq.md)** - O(log n) lisäys ja poisto, kun tarvitaan vain pienin alkio eikä
  järjestettyä listaa
- **[list](../builtins/list.md)** - `insert()` ja `sort()`, kustannukset, joihin `insort` ja
  erän järjestäminen perustuvat
