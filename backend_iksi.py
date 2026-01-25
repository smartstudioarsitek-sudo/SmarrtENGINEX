import sqlite3
import pandas as pd
import os
import json
import math
from datetime import datetime

class IrigasiBackend:
    def __init__(self, db_path='database/enginex_enterprise.db'):
        # Memastikan folder database tersedia
        self.db_folder = os.path.dirname(db_path)
        if self.db_folder and not os.path.exists(self.db_folder):
            try:
                os.makedirs(self.db_folder)
            except OSError: pass

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.init_db()

    def init_db(self):
        """
        Inisialisasi Seluruh Tabel Database untuk Menampung Data ENGINEX:
        1. Master Aset (Data Fisik)
        2. Inspeksi (Data Kondisi)
        3. Data Penunjang (Tanam/P3A)
        4. Riwayat Konsultasi AI (Untuk 17+ Gems Project Manager & Tim Ahli)
        """
        
        # 1. TABEL MASTER ASET (Data Statis)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS master_aset (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kode_aset TEXT UNIQUE, 
                nama_aset TEXT,
                jenis_aset TEXT,
                satuan TEXT,
                tahun_bangun INTEGER,
                tahun_rehab_terakhir INTEGER,
                dimensi_teknis TEXT, 
                luas_layanan_desain REAL, 
                nilai_aset_baru REAL DEFAULT 0,
                file_kmz TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 2. TABEL INSPEKSI (Data Dinamis/Kondisi)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS inspeksi_aset (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aset_id INTEGER,
                tanggal_inspeksi DATE,
                nama_surveyor TEXT,
                kondisi_sipil REAL, 
                kondisi_me REAL,
                nilai_fungsi_sipil REAL, 
                nilai_fungsi_me REAL,
                luas_terdampak_aktual REAL,
                rekomendasi_penanganan TEXT,
                estimasi_biaya REAL,
                foto_bukti TEXT,
                FOREIGN KEY(aset_id) REFERENCES master_aset(id)
            )
        ''')

        # 3. TABEL PENUNJANG (Non-Fisik)
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_tanam (id INTEGER PRIMARY KEY, musim TEXT, luas_rencana REAL, luas_realisasi REAL, debit_andalan REAL, kebutuhan_air REAL, faktor_k REAL, prod_padi REAL, prod_palawija REAL)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_p3a (id INTEGER PRIMARY KEY, nama_p3a TEXT, desa TEXT, status TEXT, keaktifan TEXT, anggota INTEGER)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_sdm_sarana (id INTEGER PRIMARY KEY, jenis TEXT, nama TEXT, kondisi TEXT, ket TEXT)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_dokumentasi (id INTEGER PRIMARY KEY, jenis_dokumen TEXT, ada INTEGER)')
        
        # 4. TABEL RIWAYAT KONSULTASI AI (Fitur Super-Team)
        # Menyimpan chat Project Manager & Gems lain agar history tidak hilang
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS riwayat_konsultasi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tanggal TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                gem_name TEXT, 
                role TEXT, -- 'user' atau 'assistant'
                content TEXT
            )
        ''')

        # Migrasi Otomatis (Anti-Error jika kolom kurang)
        try: self.cursor.execute("ALTER TABLE master_aset ADD COLUMN nilai_aset_baru REAL DEFAULT 0")
        except: pass
        self.conn.commit()

    # --- A. FITUR BACKUP & RESTORE JSON (PENTING) ---
    def export_ke_json(self):
        data = {}
        try:
            for table in ['master_aset', 'inspeksi_aset', 'data_tanam', 'data_p3a', 'data_sdm_sarana', 'data_dokumentasi', 'riwayat_konsultasi']:
                try:
                    data[table] = pd.read_sql(f"SELECT * FROM {table}", self.conn).to_dict(orient='records')
                except: data[table] = [] 
            return json.dumps(data, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def import_dari_json(self, json_file):
        try:
            data = json.load(json_file)
            self.hapus_semua_data() # Reset bersih sebelum restore
            for table, rows in data.items():
                if rows:
                    pd.DataFrame(rows).to_sql(table, self.conn, if_exists='append', index=False)
            self.conn.commit()
            return "✅ Restore Berhasil! Semua data kembali."
        except Exception as e:
            return f"❌ Gagal Restore: {e}"

    # --- B. CRUD MASTER ASET ---
    def tambah_master_aset(self, nama, jenis, satuan, thn_bangun, thn_rehab, luas, nab, detail, kmz=None):
        try:
            kode = f"{str(jenis)[:3].upper()}-{int(datetime.now().timestamp())}"
            kmz_name = kmz.name if kmz else "-"
            try:
                detail_json = json.dumps(json.loads(detail)) if isinstance(detail, str) and detail.startswith('{') else json.dumps({"desc": detail})
            except:
                detail_json = "{}"

            self.cursor.execute('''INSERT INTO master_aset 
                (kode_aset, nama_aset, jenis_aset, satuan, tahun_bangun, tahun_rehab_terakhir, luas_layanan_desain, nilai_aset_baru, dimensi_teknis, file_kmz)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                (kode, nama, jenis, satuan, thn_bangun, thn_rehab, luas, nab, detail_json, kmz_name))
            self.conn.commit()
            return "✅ Aset Tersimpan!"
        except Exception as e: return f"❌ Gagal Simpan: {e}"

    def get_master_aset(self):
        return pd.read_sql("SELECT * FROM master_aset", self.conn)

# --- LANJUT KE BAGIAN 2 ---
# --- C. CRUD INSPEKSI (BLANGKO 02-O) ---
    def tambah_inspeksi(self, aset_id, surveyor, ks, kme, fs, fme, luas_impact, rek, biaya):
        try:
            tgl = datetime.now().strftime("%Y-%m-%d")
            self.cursor.execute('''INSERT INTO inspeksi_aset
                (aset_id, tanggal_inspeksi, nama_surveyor, kondisi_sipil, kondisi_me, nilai_fungsi_sipil, nilai_fungsi_me, luas_terdampak_aktual, rekomendasi_penanganan, estimasi_biaya)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (aset_id, tgl, surveyor, ks, kme, fs, fme, luas_impact, rek, biaya))
            self.conn.commit()
            return "✅ Laporan Inspeksi Disimpan!"
        except Exception as e: return f"❌ Gagal Simpan Inspeksi: {e}"

    # --- D. CORE ENGINE: HITUNG IKSI (ALGORITMA PERMEN PUPR) ---
    def hitung_skor_iksi_audit(self):
        """
        Menghitung Skor Kinerja Sistem Irigasi (IKSI) secara Real-time.
        Komponen: Fisik (45%), Produktivitas (15%), Sarana (10%), Org (15%), Dok (5%), P3A (10%).
        """
        
        # 1. KOMPONEN PRASARANA FISIK (Bobot 45%)
        # Logika: Weighted Average berdasarkan Luas Layanan & Hierarchy of Impact
        query_fisik = '''
            SELECT m.id, m.nama_aset, m.jenis_aset, m.luas_layanan_desain,
                   i.kondisi_sipil, i.kondisi_me, i.tanggal_inspeksi
            FROM master_aset m
            JOIN inspeksi_aset i ON m.id = i.aset_id
            ORDER BY i.tanggal_inspeksi DESC
        '''
        df_fisik = pd.read_sql(query_fisik, self.conn)
        skor_fisik_final = 0
        
        if not df_fisik.empty:
            # Ambil hanya inspeksi terbaru per aset
            df_fisik = df_fisik.drop_duplicates(subset=['id'])
            
            # Sub-Routine: Tentukan Bobot Jenis Aset
            def get_bobot_jenis(jenis):
                j = str(jenis).lower()
                if 'bendung' in j or 'pompa' in j or 'utama' in j: return 1.5 # Sangat Vital
                if 'primer' in j or 'induk' in j: return 1.2 # Vital
                return 1.0 # Sekunder/Tersier
            
            df_fisik['bobot_jenis'] = df_fisik['jenis_aset'].apply(get_bobot_jenis)
            
            # Hitung Nilai Kondisi Rata-rata (Sipil + ME) / 2
            df_fisik['nilai_kondisi_aset'] = (df_fisik['kondisi_sipil'] + df_fisik['kondisi_me']) / 2
            
            # Rumus Rata-rata Tertimbang
            pembilang = (df_fisik['nilai_kondisi_aset'] * df_fisik['luas_layanan_desain'] * df_fisik['bobot_jenis']).sum()
            penyebut = (df_fisik['luas_layanan_desain'] * df_fisik['bobot_jenis']).sum()
            
            if penyebut > 0:
                skor_fisik_final = pembilang / penyebut
            else:
                skor_fisik_final = df_fisik['nilai_kondisi_aset'].mean()

        # 2. PRODUKTIVITAS TANAM (Bobot 15%)
        df_tanam = pd.read_sql("SELECT * FROM data_tanam", self.conn)
        skor_tanam = 0
        if not df_tanam.empty:
            def hitung_mt(row):
                # Faktor K (Ketersediaan Air)
                fk = row['faktor_k']
                nk = 100 if fk >= 1 else (80 if fk >= 0.7 else 60)
                # Rasio Luas Tanam
                ratio = row['luas_realisasi'] / row['luas_rencana'] if row['luas_rencana'] > 0 else 0
                nl = 100 if ratio >= 0.9 else 80
                return (nk * 0.6) + (nl * 0.4) 
            skor_tanam = df_tanam.apply(hitung_mt, axis=1).mean()

        # 3. SARANA PENUNJANG (Bobot 10%)
        df_sarana = pd.read_sql("SELECT * FROM data_sdm_sarana WHERE jenis NOT LIKE '%Personil%'", self.conn)
        skor_sarana = 0
        if not df_sarana.empty:
            mapping = {'Baik': 100, 'Sedang': 80, 'Rusak Ringan': 60, 'Rusak Berat': 40}
            vals = df_sarana['kondisi'].map(mapping).fillna(60)
            skor_sarana = vals.mean()

        # 4. ORGANISASI PERSONALIA (Bobot 15%)
        df_sdm = pd.read_sql("SELECT * FROM data_sdm_sarana WHERE jenis LIKE '%Personil%' OR jenis LIKE '%Juru%'", self.conn)
        skor_sdm = 0
        if not df_sdm.empty:
            # Jika data personil ada, diasumsikan terisi (Simple Logic)
            skor_sdm = 100 

        # 5. DOKUMENTASI (Bobot 5%)
        df_dok = pd.read_sql("SELECT * FROM data_dokumentasi", self.conn)
        skor_dok = 0
        if not df_dok.empty:
            skor_dok = (df_dok['ada'].sum() / len(df_dok)) * 100

        # 6. P3A (Bobot 10%)
        df_p3a = pd.read_sql("SELECT * FROM data_p3a", self.conn)
        skor_p3a = 0
        if not df_p3a.empty:
            def nilai_p3a(val):
                v = str(val).lower()
                if 'aktif' in v and 'tidak' not in v: return 100
                if 'sedang' in v: return 75
                return 50
            skor_p3a = df_p3a['keaktifan'].apply(nilai_p3a).mean()

        # REKAPITULASI TOTAL
        total_iksi = (skor_fisik_final * 0.45) + \
                     (skor_tanam * 0.15) + \
                     (skor_sarana * 0.10) + \
                     (skor_sdm * 0.15) + \
                     (skor_dok * 0.05) + \
                     (skor_p3a * 0.10)

        return {
            "Total IKSI": round(total_iksi, 2),
            "Rincian": {
                "Prasarana Fisik (45%)": round(skor_fisik_final, 2),
                "Produktivitas Tanam (15%)": round(skor_tanam, 2),
                "Sarana Penunjang (10%)": round(skor_sarana, 2),
                "Organisasi Personalia (15%)": round(skor_sdm, 2),
                "Dokumentasi (5%)": round(skor_dok, 2),
                "P3A (10%)": round(skor_p3a, 2)
            }
        }

    # --- E. PRIORITAS PENANGANAN (MATRIKS RISIKO) ---
    def get_prioritas_matematis(self):
        query = '''
            SELECT m.nama_aset, m.jenis_aset, i.kondisi_sipil, i.kondisi_me, 
                   i.nilai_fungsi_sipil, i.nilai_fungsi_me, i.luas_terdampak_aktual, i.estimasi_biaya
            FROM master_aset m
            JOIN inspeksi_aset i ON m.id = i.aset_id
            ORDER BY i.tanggal_inspeksi DESC
        '''
        try:
            df = pd.read_sql(query, self.conn)
            df = df.drop_duplicates(subset=['nama_aset'])
            if df.empty: return df

            def hitung_skor(row):
                # Logika: (Kerusakan + Kegagalan Fungsi) * Dampak Luas Logaritmik
                K = min(row['kondisi_sipil'], row['kondisi_me']) 
                F = min(row['nilai_fungsi_sipil'], row['nilai_fungsi_me'])
                A = row['luas_terdampak_aktual']
                
                # Bobot Kerusakan vs Fungsi
                Nilai_Resiko = ((100 - K) * 0.4) + ((100 - F) * 0.6)
                # Faktor Dampak (Log base 10 agar area luas tidak mendominasi berlebihan)
                Faktor_Dampak = math.log10(A + 1) if A > 0 else 0.1
                
                return Nilai_Resiko * Faktor_Dampak

            df['Skor_Prioritas'] = df.apply(hitung_skor, axis=1)
            
            def label_prioritas(skor):
                if skor > 150: return "1. DARURAT 🔴"
                if skor > 80: return "2. MENDESAK 🟠"
                if skor > 40: return "3. PERLU PERHATIAN 🟡"
                return "4. RUTIN 🟢"
                
            df['Kelas_Prioritas'] = df['Skor_Prioritas'].apply(label_prioritas)
            return df.sort_values(by='Skor_Prioritas', ascending=False)
        except: return pd.DataFrame()

    # --- F. FITUR SUPER-TEAM AI (HISTORY CHAT) ---
    def simpan_chat_ai(self, gem_name, role, content):
        """Menyimpan percakapan dengan Gems agar tidak hilang saat refresh"""
        try:
            self.cursor.execute("INSERT INTO riwayat_konsultasi (gem_name, role, content) VALUES (?, ?, ?)", 
                               (gem_name, role, content))
            self.conn.commit()
        except Exception as e: print(f"Error saving chat: {e}")

    def get_chat_history(self, gem_name):
        """Mengambil 50 chat terakhir untuk konteks AI"""
        try:
            return pd.read_sql(f"SELECT role, content FROM riwayat_konsultasi WHERE gem_name = '{gem_name}' ORDER BY id ASC LIMIT 50", self.conn).to_dict(orient='records')
        except: return []
        
    def hapus_chat_history(self, gem_name):
        self.cursor.execute("DELETE FROM riwayat_konsultasi WHERE gem_name = ?", (gem_name,))
        self.conn.commit()

    # --- G. UTILS & DATA PENUNJANG ---
    def hapus_semua_data(self):
        # Hati-hati! Ini menghapus seluruh database proyek.
        for t in ['master_aset','inspeksi_aset','data_tanam','data_p3a','data_sdm_sarana','data_dokumentasi', 'riwayat_konsultasi']:
            try:
                self.cursor.execute(f"DELETE FROM {t}")
                self.cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{t}'")
            except: pass
        self.conn.commit()
        return "✅ Database Bersih"
        
    def get_table_data(self, t): return pd.read_sql(f"SELECT * FROM {t}", self.conn)
    
    def tambah_data_tanam_lengkap(self, m, lr, lrl, qa, qb, pd, pl):
        fk = qa/qb if qb>0 else 0
        self.cursor.execute("INSERT INTO data_tanam VALUES (NULL,?,?,?,?,?,?,?,?)", (m,lr,lrl,qa,qb,round(fk,2),pd,pl)); self.conn.commit(); return "✅ Data Tanam Tersimpan"
        
    def tambah_data_p3a(self, nm, ds, st, akt, ang): 
        self.cursor.execute("INSERT INTO data_p3a VALUES (NULL,?,?,?,?,?)", (nm,ds,st,akt,ang)); self.conn.commit(); return "✅ Data P3A Tersimpan"
        
    def update_dokumentasi(self, d):
        self.cursor.execute("DELETE FROM data_dokumentasi"); 
        [self.cursor.execute("INSERT INTO data_dokumentasi VALUES (?,?)", (k,1 if v else 0)) for k,v in d.items()]
        self.conn.commit(); return "✅ Status Dokumen Terupdate"

