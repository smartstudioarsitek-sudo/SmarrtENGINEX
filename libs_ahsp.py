import pandas as pd

class AHSP_Engine:
    def __init__(self):
        # Database Koefisien AHSP (SNI/Permen PUPR)
        # Diperluas agar AI tidak bingung
        self.koefisien = {
            # --- BETON ---
            "beton_k175": {
                "desc": "Beton K-175 (fc 14.5 MPa)",
                "bahan": {"Semen (kg)": 326, "Pasir (m3)": 0.52, "Split (m3)": 0.76},
                "upah": {"Pekerja": 1.65, "Tukang": 0.275, "Mandor": 0.083}
            },
            "beton_k225": {
                "desc": "Beton K-225 (fc 19 MPa)",
                "bahan": {"Semen (kg)": 371, "Pasir (m3)": 0.498, "Split (m3)": 0.77},
                "upah": {"Pekerja": 1.65, "Tukang": 0.275, "Mandor": 0.083}
            },
            "beton_k250": {
                "desc": "Beton K-250 (fc 21.7 MPa)",
                "bahan": {"Semen (kg)": 384, "Pasir (m3)": 0.494, "Split (m3)": 0.77},
                "upah": {"Pekerja": 1.65, "Tukang": 0.275, "Mandor": 0.083}
            },
            "beton_k300": {
                "desc": "Beton K-300 (fc 25 MPa)",
                "bahan": {"Semen (kg)": 413, "Pasir (m3)": 0.48, "Split (m3)": 0.77},
                "upah": {"Pekerja": 1.65, "Tukang": 0.275, "Mandor": 0.083}
            },
            "beton_k350": {
                "desc": "Beton K-350 (fc 29 MPa)",
                "bahan": {"Semen (kg)": 448, "Pasir (m3)": 0.47, "Split (m3)": 0.76},
                "upah": {"Pekerja": 1.65, "Tukang": 0.275, "Mandor": 0.083}
            },

            # --- BESI ---
            "pembesian_polos": {
                "desc": "Pembesian 10 kg dengan Besi Polos/Ulir",
                "bahan": {"Besi Beton (kg)": 10.5, "Kawat Beton (kg)": 0.15},
                "upah": {"Pekerja": 0.07, "Tukang": 0.07, "Mandor": 0.004}
            },
            "bekisting_balok": {
                "desc": "Pemasangan 1 m2 Bekisting Balok (Kayu)",
                "bahan": {"Kayu Kelas III (m3)": 0.04, "Paku (kg)": 0.4, "Minyak Bekisting (L)": 0.2},
                "upah": {"Pekerja": 0.66, "Tukang": 0.33, "Mandor": 0.033}
            },
            "bekisting_kolom": {
                "desc": "Pemasangan 1 m2 Bekisting Kolom",
                "bahan": {"Kayu Kelas III (m3)": 0.04, "Paku (kg)": 0.4, "Minyak (L)": 0.2, "Plywood 9mm (lbr)": 0.35},
                "upah": {"Pekerja": 0.66, "Tukang": 0.33, "Mandor": 0.033}
            },

            # --- PONDASI ---
            "pasangan_batu_kali": {
                "desc": "Pasangan Batu Kali 1:4 (Talud)",
                "bahan": {"Batu Kali (m3)": 1.2, "Semen (kg)": 163, "Pasir (m3)": 0.52},
                "upah": {"Pekerja": 1.5, "Tukang": 0.75, "Mandor": 0.075}
            },
            "bore_pile_k300": {
                "desc": "Pengecoran Bore Pile K-300",
                "bahan": {"Beton K300 (m3)": 1.05},
                "upah": {"Pekerja": 2.0, "Tukang": 0.5, "Mandor": 0.1}
            },

            # --- ARSITEKTUR ---
            "pasangan_bata_merah": {
                "desc": "Pasangan Dinding Bata Merah 1:4",
                "bahan": {"Bata Merah (bh)": 70, "Semen (kg)": 11.5, "Pasir (m3)": 0.043},
                "upah": {"Pekerja": 0.3, "Tukang": 0.1, "Mandor": 0.015}
            },
            "plesteran": {
                "desc": "Plesteran 1:4 Tebal 15mm",
                "bahan": {"Semen (kg)": 6.24, "Pasir (m3)": 0.024},
                "upah": {"Pekerja": 0.3, "Tukang": 0.15, "Mandor": 0.015}
            },
            "acian": {
                "desc": "Acian Semen",
                "bahan": {"Semen (kg)": 3.25},
                "upah": {"Pekerja": 0.2, "Tukang": 0.1, "Mandor": 0.01}
            },
            "cat_tembok": {
                "desc": "Pengecatan Tembok (2 Lapis)",
                "bahan": {"Cat Tembok (kg)": 0.26, "Plamir (kg)": 0.1},
                "upah": {"Pekerja": 0.02, "Tukang": 0.063, "Mandor": 0.003}
            },
            "pasang_kus_pintu": {
                "desc": "Pemasangan Kusen Pintu/Jendela",
                "bahan": {"Angkur (bh)": 4},
                "upah": {"Pekerja": 0.5, "Tukang": 1.0, "Mandor": 0.05}
            },
            "pasang_pipa_pvc": {
                "desc": "Pasang Pipa PVC AW 3/4 inch",
                "bahan": {"Pipa PVC (m)": 1.2, "Perlengkapan (ls)": 0.35},
                "upah": {"Pekerja": 0.036, "Tukang": 0.06, "Mandor": 0.002}
            }
        }

    def hitung_hsp(self, kode_analisa, harga_bahan_dasar, harga_upah_dasar):
        # Fallback Logic: Jika kode tidak ada persis, coba cari yang mirip
        target_kode = kode_analisa
        if kode_analisa not in self.koefisien: 
            # Jika user minta K-275 tapi gak ada, kita kasih K-300 (safety)
            if "beton" in kode_analisa: target_kode = "beton_k300"
            elif "bata" in kode_analisa: target_kode = "pasangan_bata_merah"
            else: return 0 # Nyerah
            
        data = self.koefisien[target_kode]
        total_bahan = 0
        total_upah = 0
        
        for item, koef in data['bahan'].items():
            key_clean = item.split(" (")[0].lower()
            h_satuan = 0
            # Logic pencocokan harga
            if "semen" in key_clean: h_satuan = harga_bahan_dasar.get('semen', 0)
            elif "pasir" in key_clean: h_satuan = harga_bahan_dasar.get('pasir', 0)
            elif "split" in key_clean: h_satuan = harga_bahan_dasar.get('split', 0)
            elif "kayu" in key_clean: h_satuan = harga_bahan_dasar.get('kayu', 0)
            elif "besi" in key_clean: h_satuan = harga_bahan_dasar.get('besi', 0)
            elif "batu kali" in key_clean: h_satuan = harga_bahan_dasar.get('batu kali', 0)
            elif "beton" in key_clean: h_satuan = harga_bahan_dasar.get('beton k300', 0)
            elif "bata" in key_clean: h_satuan = harga_bahan_dasar.get('bata merah', 0)
            elif "cat" in key_clean: h_satuan = harga_bahan_dasar.get('cat tembok', 0)
            elif "pipa" in key_clean: h_satuan = harga_bahan_dasar.get('pipa pvc', 0)
            elif "plywood" in key_clean: h_satuan = harga_bahan_dasar.get('plywood', 0)
            elif "paku" in key_clean: h_satuan = harga_bahan_dasar.get('paku', 0)
            elif "minyak" in key_clean: h_satuan = harga_bahan_dasar.get('minyak', 0)
            
            total_bahan += koef * h_satuan
            
        for item, koef in data['upah'].items():
            item_lower = item.lower()
            h_upah = harga_upah_dasar.get(item_lower, 0)
            total_upah += koef * h_upah
            
        return total_bahan + total_upah
