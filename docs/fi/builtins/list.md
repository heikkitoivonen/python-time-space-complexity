---
source_sha: 4be9c7effa33db1176d1ac0933f57739a43404edc602043c8eb1ae684c37985d
translated: machine
---

# Listaoperaatioiden vaativuus

Tyyppi `list` on muuttuva, järjestetty jono. CPythonissa se on toteutettu dynaamisena taulukkona.

`n` on listan pituus, `k` on indeksi tai toistokerroin, `i:j` ovat viipaleen rajat ja `len(t)` on
toisen operandin pituus. Kahden alkion vertailu lasketaan O(1):ksi.

## Vaativuustaulukko

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `len(l)` | O(1) | O(1) | Pituus on tallennettu listaan, sitä ei lasketa |
| `l[k]` | O(1) | O(1) | Suora indeksointi |
| `l[k] = x` | O(1) | O(1) | Korvaa yhden paikan |
| `del l[k]` | O(n-k) | O(1) | Siirtää k:n jälkeisiä alkioita yhden paikan vasemmalle |
| `append(x)` | O(1) tasoitettu | O(1) tasoitettu | Voi muuttaa kokoa; pahimmillaan O(n), kun uudelleenvaraus tarvitaan |
| `insert(0, x)` | O(n) | O(1) tasoitettu | Kaikkia alkioita on siirrettävä |
| `insert(k, x)` | O(n-k) tasoitettu | O(1) tasoitettu | Siirtää alkioita indeksistä k alkaen yhden paikan oikealle |
| `remove(x)` | O(n) | O(1) | Vaatii haun ja siirron |
| `pop()` | O(1) tasoitettu | O(1) | Poistaa viimeisen alkion; mitään ei siirretä |
| `pop(0)` | O(n) | O(1) | Siirtää jäljelle jäävät alkiot |
| `pop(k)` | O(n-k) tasoitettu | O(1) | Siirtää k:n jälkeisiä alkioita yhden paikan vasemmalle |
| `clear()` | O(n) | O(1) | Vapauttaa muistin |
| `index(x)` | O(n) | O(1) | Lineaarinen haku |
| `count(x)` | O(n) | O(1) | Lineaarinen läpikäynti |
| `sort()` | O(n log n) pahin, O(n) järjestetylle tai käänteisesti järjestetylle syötteelle | O(n) | Timsort/Powersort; mukautuva, joten valmiiksi järjestetyt jaksot vaativat vähemmän vertailuja |
| `reverse()` | O(n) | O(1) | Käännös paikallaan |
| `copy()` | O(n) | O(n) | Pinnallinen kopio |
| `extend(t)` | O(len(t)) tasoitettu | O(len(t)) | Lisäksi t:n iteroinnin kustannus; voi laukaista O(n)-kokomuutoksen |
| `l[i:j]` (viipalointi) | O(j-i) | O(j-i) | Askeleen kanssa O(tuloksen pituus) |
| `l[i:j] = t` | O(j-i), jos len(t) == j-i, muuten O(n-i+len(t)) tasoitettu | O(j-i+len(t)) | Yhtä pitkät korvataan paikallaan; muuten kaikki j:n jälkeen siirtyy |
| `del l[i:j]` | O(n-i) | O(j-i) | Kaikki j:n jälkeen siirtyy vasemmalle |
| `l1 + l2` (yhdistäminen) | O(len(l1)+len(l2)) | O(len(l1)+len(l2)) | Uusi lista |
| `l * k` (toisto) | O(nk) | O(nk) | Uusi lista, jossa n·k viittausta |
| `for x in l` (iterointi) | O(n) | O(1) | O(1) askelta kohden |
| `x in l` (jäsenyys) | O(n) | O(1) | Lineaarinen haku |
| `min(l)`, `max(l)` | O(n) | O(1) | n-1 vertailua |

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
assert len(lst) == 1000000
```

### Insertin suorituskyky

```python
# O(n) - must shift all elements after insertion point
lst = [0] * 1000000
lst.insert(0, -1)  # Shifts 1,000,000 elements!
assert lst[0] == -1 and len(lst) == 1000001
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
