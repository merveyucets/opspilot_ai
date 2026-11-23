"""Faz 3 RAG birim testleri (Ollama / Chroma sorgusu gerektirmez).

Kapsam:
1. Parçalama: her madde en az bir parçada, kimlikler tekil, uzunluk sınırı, erişim etiketi meta.json ile aynı
2. İçerik özeti: metin değişince özet değişir (bayat indeks koruması)
3. Erişim filtresi: müşteri modunda gizli dışlanır, bilinmeyen mod hata verir
4. Tekilleştirme: aynı maddenin ikinci parçası elenir
5. Metrikler: payda, CAPRAZ kuralı, sızıntı, ana madde eşleşmesi, eşik analizi
"""
import json
import re
import unittest
from dataclasses import replace
from types import SimpleNamespace

from config import CHUNK_SIZE, DATA_DIR, POLICY_DIR
from app.rag.chunker import tum_dokumanlari_parcala
from app.rag.indexer import icerik_ozeti
from app.rag.search import AramaSonucu, erisim_filtresi, tekillestir
from eval.metrikler import ana_madde, esik_analizi, soruyu_degerlendir


def sonuc(kod, madde_no, benzerlik=0.5, parca="0"):
    """Test için sahte arama sonucu."""
    return AramaSonucu(id=f"{kod}_M{madde_no}_{parca}", kod=kod, madde_no=madde_no, madde_baslik="",
                       kategori="", erisim="ic", kaynak=f"{kod} Madde {madde_no}", icerik="",
                       skor=1 - benzerlik, benzerlik=benzerlik, hibrit_skor=benzerlik)


class TestParcalama(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parcalar = tum_dokumanlari_parcala()
        cls.meta = json.loads((DATA_DIR / "meta.json").read_text(encoding="utf-8"))

    def test_her_madde_en_az_bir_parcada(self):
        beklenen = set()
        for dosya, m in self.meta.items():
            metin = (POLICY_DIR / dosya).read_text(encoding="utf-8")
            beklenen |= {(m["kod"], int(n)) for n in re.findall(r"^## Madde (\d+)", metin, re.M)}
        bulunan = {(p.kod, p.madde_no) for p in self.parcalar}
        self.assertEqual(beklenen, bulunan)

    def test_kimlikler_tekil(self):
        ids = [p.id for p in self.parcalar]
        self.assertEqual(len(ids), len(set(ids)))

    def test_uzunluk_siniri(self):
        for p in self.parcalar:
            self.assertLessEqual(len(p.icerik), CHUNK_SIZE, p.id)

    def test_erisim_meta_ile_ayni(self):
        kod_erisim = {m["kod"]: m["erisim"] for m in self.meta.values()}
        for p in self.parcalar:
            self.assertEqual(p.metadata["erisim"], kod_erisim[p.kod], p.id)

    def test_ozet_metin_degisince_degisir(self):
        ilk = icerik_ozeti(self.parcalar)
        degismis = [replace(self.parcalar[0], icerik=self.parcalar[0].icerik + " ")] + self.parcalar[1:]
        self.assertEqual(ilk, icerik_ozeti(list(self.parcalar)))
        self.assertNotEqual(ilk, icerik_ozeti(degismis))


class TestArama(unittest.TestCase):
    def test_erisim_filtresi(self):
        self.assertEqual(erisim_filtresi("musteri"), {"erisim": "ic"})
        self.assertIsNone(erisim_filtresi("ic"))
        with self.assertRaises(ValueError):
            erisim_filtresi("Musteri")   # yazım hatası filtresiz aramaya düşmemeli

    def test_tekillestirme(self):
        a = [sonuc("POL-HSR-004", 2, 0.9, "p1"), sonuc("POL-HSR-004", 2, 0.8, "p2"), sonuc("POL-PARA-002", 3, 0.7)]
        t = tekillestir(a)
        self.assertEqual([x.id for x in t], ["POL-HSR-004_M2_p1", "POL-PARA-002_M3_0"])


class TestMetrikler(unittest.TestCase):
    def soru(self, tur="DOGRUDAN", dok=("POL-GAR-003",), mad=("POL-GAR-003 Madde 5.1",), yasak=()):
        return {"id": "X", "tur": tur, "erisim": "ic", "beklenen_dokumanlar": list(dok),
                "beklenen_maddeler": list(mad), "yasak_dokumanlar": list(yasak)}

    def test_ana_madde(self):
        self.assertEqual(ana_madde("POL-GAR-003 Madde 5.1"), ("POL-GAR-003", 5))
        self.assertEqual(ana_madde("GZL-TDR-010 Madde 2"), ("GZL-TDR-010", 2))

    def test_ana_madde_isabeti_ve_top1(self):
        d = soruyu_degerlendir(self.soru(), [sonuc("POL-PARA-002", 2), sonuc("POL-GAR-003", 5)])
        self.assertTrue(d["dokuman_hit"])
        self.assertTrue(d["madde_hit"])
        self.assertFalse(d["top1_madde"])

    def test_yanlis_madde_isabet_degil(self):
        d = soruyu_degerlendir(self.soru(), [sonuc("POL-GAR-003", 6)])
        self.assertTrue(d["dokuman_hit"])
        self.assertFalse(d["madde_hit"])

    def test_cevapsiz_soru_paydaya_girmez(self):
        d = soruyu_degerlendir(self.soru(tur="GIZLI", dok=(), mad=(), yasak=("GZL-TDR-010",)), [sonuc("POL-KMP-009", 3, 0.42)])
        self.assertFalse(d["cevapli"])
        self.assertIsNone(d["madde_hit"])
        self.assertFalse(d["sizinti"])
        self.assertEqual(d["top1_benzerlik"], 0.42)

    def test_sizinti_tespit(self):
        d = soruyu_degerlendir(self.soru(yasak=("GZL-TDR-010",)), [sonuc("GZL-TDR-010", 5)])
        self.assertTrue(d["sizinti"])

    def test_capraz_her_iki_dokuman_gerekli(self):
        s = self.soru(tur="CAPRAZ", dok=("POL-HSR-004", "POL-KMP-009"),
                      mad=("POL-HSR-004 Madde 4.2", "POL-KMP-009 Madde 6.3"))
        yarim = soruyu_degerlendir(s, [sonuc("POL-HSR-004", 4), sonuc("POL-IADE-001", 3)])
        self.assertFalse(yarim["dokuman_hit"])
        self.assertFalse(yarim["madde_hit"])
        tam = soruyu_degerlendir(s, [sonuc("POL-HSR-004", 4), sonuc("POL-KMP-009", 6)])
        self.assertTrue(tam["dokuman_hit"])
        self.assertTrue(tam["madde_hit"])

    def test_capraz_dokuman_var_madde_yanlis(self):
        s = self.soru(tur="CAPRAZ", dok=("POL-HSR-004", "POL-KMP-009"),
                      mad=("POL-HSR-004 Madde 4.2", "POL-KMP-009 Madde 6.3"))
        d = soruyu_degerlendir(s, [sonuc("POL-HSR-004", 4), sonuc("POL-KMP-009", 2)])
        self.assertTrue(d["dokuman_hit"])
        self.assertFalse(d["madde_hit"])

    def test_esik_tam_ayrisma(self):
        e = esik_analizi([0.8, 0.7, 0.65], [0.4, 0.5])
        self.assertTrue(e["tam_ayrisiyor"])
        self.assertEqual((e["yanlis_alarm"], e["kacan"]), (0, 0))
        self.assertTrue(0.5 < e["esik"] <= 0.65)

    def test_esik_cakisma(self):
        e = esik_analizi([0.8, 0.45], [0.5, 0.3])
        self.assertFalse(e["tam_ayrisiyor"])
        self.assertEqual(e["yanlis_alarm"] + e["kacan"], 1)
        self.assertEqual(e["yanlis_alarm"], 0)   # eşitlikte yanlış alarmı az olan seçilir


if __name__ == "__main__":
    unittest.main()


class TestCevapMetrikleri(unittest.TestCase):
    BUL = "İlgili prosedür bulunamadı, üst birime yönlendirin."
    PROV = {"K1": {"kod": "POL-GAR-003", "madde_no": 5}, "K2": {"kod": "POL-PARA-002", "madde_no": 2}}
    CEVAPLI = {"id": "X", "tur": "DOGRUDAN", "beklenen_dokumanlar": ["POL-GAR-003"], "beklenen_maddeler": ["POL-GAR-003 Madde 5.1"]}
    CEVAPSIZ = {"id": "Y", "tur": "CEVAPSIZ", "beklenen_dokumanlar": [], "beklenen_maddeler": []}

    def cd(self, soru, cevap, used, valid=True):
        from eval.metrikler import cevap_degerlendir
        return cevap_degerlendir(soru, cevap, self.PROV, {"used": used, "valid": valid}, self.BUL)

    def test_dogru_atifli_cevap(self):
        d = self.cd(self.CEVAPLI, "Değişim istenebilir [K1].", ["K1"])
        self.assertTrue(d["dogru_davranis"]); self.assertTrue(d["atif_gecerli"]); self.assertTrue(d["dogru_maddeye_atif"])

    def test_yanlis_maddeye_atif(self):
        d = self.cd(self.CEVAPLI, "14 gün [K2].", ["K2"])
        self.assertFalse(d["dogru_maddeye_atif"])

    def test_cevapsizda_bulunamadi_dogru(self):
        d = self.cd(self.CEVAPSIZ, "İlgili prosedür bulunamadı, üst birime yönlendirin", [], valid=False)
        self.assertTrue(d["bulunamadi"]); self.assertTrue(d["dogru_davranis"]); self.assertIsNone(d["atif_gecerli"])

    def test_cevaplida_bulunamadi_yanlis(self):
        d = self.cd(self.CEVAPLI, self.BUL, [], valid=False)
        self.assertFalse(d["dogru_davranis"])

    def test_yasak_kod(self):
        self.assertTrue(self.cd(self.CEVAPSIZ, "Özür olarak gizli10 kodunu kullanın [K1].", ["K1"])["yasak_kod"])
