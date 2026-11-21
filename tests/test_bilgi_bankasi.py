"""Bilgi bankası bütünlük testleri (model gerektirmez).

Kontroller:
  1. meta.json ile data/politikalar/*.md birebir eşleşiyor mu?
  2. Her dokümanın başlığı ve başlık tablosu meta.json ile tutarlı mı?
  3. Madde numaraları 1'den başlayıp sıralı mı, alt maddeler (N.1, N.2 ...) sıralı mı?
  4. Dokümanlar arası ve doküman içi her "Madde N" / "Madde N.M" atfı gerçekten var olan bir maddeyi mi gösteriyor?
  5. Politikalarda kanun/yönetmelik atfı yok mu? (Karar günlüğü 2026-11-21)

Çalıştırma: .\\.venv\\Scripts\\python.exe -m unittest -v tests.test_bilgi_bankasi
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR, POLICY_DIR  # noqa: E402

ERISIM_ETIKETI = {"ic": "İç kullanım", "gizli": "**GİZLİ**"}
MADDE_BASLIK = re.compile(r"^## Madde (\d+) — .+$", re.M)
ALT_MADDE = re.compile(r"^(\d+)\.(\d+)\. ", re.M)
# "POL-ESK-007 Madde 2", "Madde 3.4", "POL-GAR-003 Madde 5.1" gibi atıflar
ATIF = re.compile(r"(?:\b((?:POL|GZL)-[A-Z]+-\d{3})\s+)?Madde (\d+)(?:\.(\d+))?")
KOD = re.compile(r"\b((?:POL|GZL)-[A-Z]+-\d{3})\b")
# Kelime sınırıyla aranır: "sayılı" kanun atfıdır, "sayılır" değildir.
MEVZUAT_IFADESI = re.compile(r"\b(Kanun\w*|Yönetmeli\w*|sayılı|Resmî Gazete|TKHK|MSY)\b")


def yukle():
    meta = json.loads((DATA_DIR / "meta.json").read_text(encoding="utf-8"))
    metinler = {p.name: p.read_text(encoding="utf-8") for p in sorted(POLICY_DIR.glob("*.md"))}
    return meta, metinler


def madde_yapisi(metin):
    """{madde_no: {alt_madde_no, ...}} döndürür."""
    yapi = {}
    bolumler = re.split(r"^## Madde (\d+) — .+$", metin, flags=re.M)
    # bolumler: [giriş, no1, gövde1, no2, gövde2, ...]
    for i in range(1, len(bolumler), 2):
        no = int(bolumler[i])
        alt = {int(m.group(2)) for m in ALT_MADDE.finditer(bolumler[i + 1]) if int(m.group(1)) == no}
        yapi[no] = alt
    return yapi


class BilgiBankasiTesti(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta, cls.metinler = yukle()
        cls.kod_dosya = {m["kod"]: ad for ad, m in cls.meta.items()}
        cls.yapilar = {ad: madde_yapisi(t) for ad, t in cls.metinler.items()}

    def test_1_meta_ve_dosyalar_eslesiyor(self):
        self.assertEqual(set(self.meta), set(self.metinler))

    def test_2_baslik_ve_tablo_meta_ile_tutarli(self):
        for ad, m in self.meta.items():
            metin = self.metinler[ad]
            with self.subTest(dokuman=ad):
                self.assertTrue(ad.startswith(m["kod"] + "_"), "dosya adı kodla başlamalı")
                self.assertEqual(metin.splitlines()[0], f"# {m['kod']} — {m['baslik']}")
                tablo_satiri = next(s for s in metin.splitlines() if s.startswith(f"| {m['kod']} |"))
                hucreler = [h.strip() for h in tablo_satiri.strip("|").split("|")]
                self.assertEqual(hucreler[1], m["surum"])
                self.assertEqual(hucreler[4], ERISIM_ETIKETI[m["erisim"]])

    def test_3_madde_numaralari_sirali(self):
        for ad, yapi in self.yapilar.items():
            with self.subTest(dokuman=ad):
                self.assertEqual(list(yapi), list(range(1, len(yapi) + 1)), "maddeler 1..n sıralı olmalı")
                for no, alt in yapi.items():
                    if alt:
                        self.assertEqual(alt, set(range(1, max(alt) + 1)), f"Madde {no} alt maddeleri eksik/atlamalı")

    def test_4_tum_atiflar_gecerli(self):
        hatalar = []
        for ad, metin in self.metinler.items():
            for satir in metin.splitlines():
                if satir.startswith("## Madde"):
                    continue
                # Satırdaki kod geçmeyen "Madde N" atıfları aynı dokümana aittir
                for m in ATIF.finditer(satir):
                    kod, no, alt = m.group(1), int(m.group(2)), m.group(3)
                    hedef = self.kod_dosya.get(kod) if kod else ad
                    if hedef is None:
                        hatalar.append(f"{ad}: bilinmeyen doküman kodu {kod}")
                        continue
                    yapi = self.yapilar[hedef]
                    if no not in yapi:
                        hatalar.append(f"{ad}: '{m.group(0)}' → {hedef} içinde Madde {no} yok")
                    elif alt and int(alt) not in yapi[no]:
                        hatalar.append(f"{ad}: '{m.group(0)}' → {hedef} içinde Madde {no}.{alt} yok")
                for kod in KOD.findall(satir):
                    if kod not in self.kod_dosya:
                        hatalar.append(f"{ad}: bilinmeyen doküman kodu {kod}")
        self.assertEqual(hatalar, [], "\n" + "\n".join(hatalar))

    def test_5_politikalarda_mevzuat_atfi_yok(self):
        for ad, m in self.meta.items():
            if m["erisim"] != "ic":
                continue
            with self.subTest(dokuman=ad):
                bulunan = MEVZUAT_IFADESI.findall(self.metinler[ad])
                self.assertEqual(bulunan, [], "politikalar sade şirket dili ile yazılmalı")


if __name__ == "__main__":
    unittest.main(verbosity=2)
