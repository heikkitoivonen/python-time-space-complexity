---
source_sha: 699f54d0f15380f0acf2cc37e53cc5f55cb222c850ade1649086deaeb841be2c
translated: machine
---

# Standardikirjaston vaativuus

Pythonin standardikirjasto tarjoaa pitkälle optimoituja tietorakenteita ja algoritmeja yleisiin tehtäviin.

## Keskeiset kokoelmat

- **[Collections](collections.md)** - `deque`, `namedtuple`, `defaultdict`, `OrderedDict`, `ChainMap`, `Counter`
- **[Itertools](itertools.md)** - Tehokkaita silmukka- ja iteraattorityökaluja
- **[Heapq](heapq.md)** - Kekojono-operaatiot
- **[Bisect](bisect.md)** - Binäärihaku ja -lisäys

## Funktionaaliset työkalut ja apuvälineet

- **[Functools](functools.md)** - Korkeamman kertaluvun funktiot ja muistiinpano
- **[JSON](json.md)** - JSON-sarjallistus ja -jäsennys

## Haku ja järjestäminen

| Moduuli | Tarkoitus | Aika |
|--------|---------|------|
| `bisect` | Binäärihaku järjestetyistä listoista | O(log n) |
| `heapq` | Keko-operaatiot | O(log n) |
| `sorted()` | Järjestää minkä tahansa iteroituvan | O(n log n) |

## Usein käytetyt

### Collections-moduuli

```python
from collections import deque, defaultdict, Counter

# deque: Fast append/prepend
d = deque([1, 2, 3])
d.appendleft(0)  # O(1)

# defaultdict: Auto-default values
d = defaultdict(list)
d[key].append(value)  # Key created if missing

# Counter: Count items
c = Counter(['a', 'a', 'b'])
c['a']  # Returns 2
```

### Heapq-moduuli

```python
import heapq

# Min heap operations
heap = [3, 1, 4, 1, 5]
heapq.heapify(heap)  # O(n)
heapq.heappop(heap)  # O(log n)
heapq.heappush(heap, 2)  # O(log n)
```

### Bisect-moduuli

```python
import bisect

# Binary search in sorted lists
arr = [1, 3, 3, 3, 5]
bisect.bisect_left(arr, 3)  # O(log n)
bisect.insort(arr, 4)  # O(n) - must shift
```

## Tietorakenteiden pikataulukko

| Tyyppi | Lisäys loppuun | Lisäys alkuun | Haku | Sisältää |
|------|--------|---------|--------|----------|
| list | O(1)* | O(n) | O(1) | O(n) |
| deque | O(1) | O(1) | O(n) | O(n) |
| heapq | O(log n) | - | O(1) pienin | O(n) |
| set | - | - | - | O(1) |
| dict | - | - | O(1) | O(1) |

## Versiokohtaiset kohokohdat

- **Python 3.7+**: `dict`-lisäysjärjestys säilyy
- **Python 3.8+**: Sijoituslausekkeet (mursuoperaattori)
- **Python 3.10+**: Hahmontunnistus dataluokkien kanssa

## Katso myös

- [Sisäänrakennetut](../builtins/index.md)
- [Toteutukset](../implementations/index.md)
