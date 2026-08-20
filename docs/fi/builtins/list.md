---
source_sha: 2c9b1483aa05e2e0dbb6693a2258ac1a811fbbbb06b82e37147b372fe2ca1fc9
translated: machine
---

# Listaoperaatioiden vaativuus

Tyyppi `list` on muuttuva, järjestetty jono. CPythonissa se on toteutettu dynaamisena taulukkona.

## Vaativuustaulukko

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | Suora haku |
| `access[i]` | O(1) | O(1) | Suora indeksointi |
| `append(x)` | O(1) tasoitettu | O(1) tasoitettu | Voi muuttaa kokoa; pahimmillaan O(n), kun uudelleenvaraus tarvitaan |
| `insert(0, x)` | O(n) | O(1) | Kaikkia alkioita on siirrettävä |
| `insert(i, x)` | O(n-i) | O(1) | Siirtää alkiot indeksistä i alkaen |
| `remove(x)` | O(n) | O(1) | Vaatii haun ja siirron |
| `pop()` | O(1) | O(1) | Poistaa viimeisen alkion |
| `pop(0)` | O(n) | O(1) | Siirtää jäljelle jäävät alkiot |
| `pop(i)` | O(n-i) | O(1) | Siirtää indeksin i jälkeiset alkiot |
| `clear()` | O(n) | O(1) | Vapauttaa muistin |
| `index(x)` | O(n) | O(1) | Lineaarinen haku |
| `count(x)` | O(n) | O(1) | Lineaarinen läpikäynti |
| `sort()` | O(n log n) keskim./pahin, O(n) paras | O(n) | Timsort/Powersort; mukautuu osittain järjestettyyn dataan |
| `reverse()` | O(n) | O(1) | Käännös paikallaan |
| `copy()` | O(n) | O(n) | Pinnallinen kopio |
| `extend(iterable)` | O(k) | O(k) | k = iteroituvan pituus; voi laukaista O(n)-kokomuutoksen |
| `in` (jäsenyys) | O(n) | O(1) | Lineaarinen haku |
| `x + y` (yhdistäminen) | O(m+n) | O(m+n) | m ja n ovat pituuksia |
| `[::2]` (viipalointi) | O(k) | O(k) | k = viipaleen pituus |

## Toteutuksen yksityiskohdat

### Dynaamisen taulukon koon muuttaminen

CPythonin lista käyttää kasvukerroinstrategiaa:

```
If size >= capacity:
    new_capacity = (newsize + newsize // 8 + 6) & ~3  # Aligned to multiple of 4
```

Tämä tarkoittaa:

- Append on tasoitetusti O(1)
- Kokoa ei muuteta jokaisella append-kutsulla
- Ylivaraus vähentää kokomuutosten tiheyttä

### Appendin suorituskyky

```python
# O(1) amortized
lst = []
for i in range(1000000):
    lst.append(i)  # Resizes ~log(n) times
```

### Insertin suorituskyky

```python
# O(n) - must shift all elements after insertion point
lst = [0] * 1000000
lst.insert(0, -1)  # Shifts 1,000,000 elements!
```

## Versiohuomiot

- **Python 3.8+**: Nykyinen käyttäytyminen vakiintunut
- **Python 3.11+**: `append()` noin 15 % nopeampi, listakoosteet 20-30 % nopeampia
- **Python 3.12+**: Koosteet sisällytetään suoraan koodiin (jopa 2x nopeampia)
- **Kaikki versiot**: Perusvaativuudet ovat pysyneet ennallaan Python 3.x:n alkuajoista

## Toteutusten vertailu

### CPython
Standardi viitetoteutus, joka käyttää dynaamista taulukkoa.

### PyPy
Samat vaativuusominaisuudet JIT-optimoinnin ansiosta.

### Jython
Samankaltainen, mutta kokomuutoskertoimet voivat poiketa Javan taulukoiden vuoksi.

## Parhaat käytännöt

✅ **Tee näin**:

- Käytä `append()`-metodia alkioiden lisäämiseen
- Käytä `extend()`-metodia useille alkioille
- Lisää loppuun ja käännä lopuksi, jos tarvitset lisäystä alkuun

❌ **Vältä**:

- `insert(0, x)` toistuvissa operaatioissa - käytä sen sijaan `collections.deque`
- Toistuvaa `pop(0)`-kutsua - käytä `deque.popleft()`
- Suurten listojen rakentamista yhdistämällä (`+`) `append()`- tai `extend()`-metodien sijaan

## Liittyvät tyypit

- **[Deque](../stdlib/collections.md#deque)** - O(1) lisäys sekä alkuun että loppuun
- **[Array](../stdlib/array.md)** - Muistitehokkaampi suurille lukulistoille
- **[Monikko](tuple.md)** - Muuttumaton vaihtoehto

## Lisälukemista

- [CPython Internals: list](https://zpoint.github.io/CPython-Internals/BasicObject/list/list.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Syväluotaus CPythonin listatoteutukseen
