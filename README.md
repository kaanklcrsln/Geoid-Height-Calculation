# Geoider

3. derece polinom yüzeyi ile geoid ondülasyonu (N) kestirimi ve arazi üzerinde iki nokta arası yükseklik farkı hesabı.

## Arayüz

<!-- Ekran görüntüsünü docs/screenshot.png olarak ekleyin -->
<img width="1473" height="982" alt="arayüz" src="https://github.com/user-attachments/assets/6faaee97-de4b-4886-8452-dddc5ba141af" />


## Kurulum

```bash
pip install numpy pandas matplotlib scipy
```

## Kullanım

```bash
python geoider.py                      # arayüz
python Geoid-Height-Calculation.py     # sadece hesap, sonucu terminale yazar
```

Arayüzde haritaya **sol tık** ile konum alınır, yükseklik girilip *Ekle* denir; **sağ tık** ile nokta seçilir. İki nokta seçtikten sonra *Fark Hesapla* şunları verir:

```
Yatay mesafe       :     8949.808 m
Elipsoidal fark dh :     -298.128 m
Egim               :       -3.331 %
N(A) =   34.896 m     H(A) =   1188.586 m
N(B) =   34.717 m     H(B) =    890.637 m
Ortometrik fark dH :     -297.948 m
```

## Yöntem

Bilinen noktalarda `N = h - H` alınır ve koordinatlar km'ye normalize edilerek 3. derece polinom yüzeyi en küçük karelerle uydurulur:

```
N = a₀ + a₁u + a₂v + a₃u² + a₄uv + a₅v² + a₆u³ + a₇u²v + a₈uv² + a₉v³
```

Yeni bir noktada `H = h - N` bulunur. Örnek veriyle model karesel ortalama hatası **m₀ = 0.0191 m**.

## Dosyalar

| Dosya | İçerik |
|---|---|
| `geoider.py` | Tkinter arayüzü |
| `Geoid-Height-Calculation.py` | Model uydurma ve kestirim |
| `known_stations.csv` | Bilinen noktalar (`x,y,h,H`) |
| `new_stations.csv` | Kestirilecek noktalar (`x,y,h`) |

CSV yüklerken `x,y,h` sütunları zorunlu, `ad` opsiyonel. `H` sütunu yoksa geoid modeli kurulamaz, yalnızca elipsoidal fark gösterilir. Yüzey çizimi için en az 4 nokta gerekir.
