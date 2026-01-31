import sqlite3
import pandas as pd
import os
import json
from datetime import datetime
import io
import shutil

class EnginexBackend:
    def __init__(self, db_path='enginex_core.db'):
        """
        Inisialisasi Backend Database.
        CATATAN UNTUK STREAMLIT CLOUD:
        Sistem file cloud seringkali 'Ephemeral' (sementara). 
        Kita akan mencoba menyimpan di root dulu, jika gagal (Read-Only),
        kita pindah ke folder sementara sistem (/tmp).
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
        # Coba koneksi ke Database
        try:
            self._connect_db(self.db_path)
        except sqlite3.OperationalError:
            # Jika gagal (biasanya karena permission), pindah ke /tmp
            print("⚠️ Read-Only Filesystem terdeteksi. Beralih ke /tmp/...")
            temp_path = os.path.join('/tmp', os.path.basename(db_path))
            self._connect_db(temp_path)
            self.db_path = temp_path

        self.init_db()

    def _connect_db(self, path):
        """Helper internal untuk koneksi database"""
        # Pastikan folder tujuan ada (jika pakai folder)
        folder = os.path.dirname(path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
            
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.cursor = self.conn.cursor()

    def init_db(self):
        """Membuat tabel jika belum ada"""
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS riwayat_konsultasi (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tanggal TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    project_name TEXT,
                    gem_name TEXT,
                    role TEXT,
                    content TEXT
                )
            ''')
            self.conn.commit()
        except Exception as e:
            print(f"❌ Error Init DB: {e}")

    # ==========================================
    # FITUR CHAT (CRUD)
    # ==========================================
    
    def simpan_chat(self, project, gem, role, text):
        """Menyimpan pesan baru ke database"""
        try:
            # Timestamp manual agar konsisten
            waktu_sekarang = datetime.now()
            
            self.cursor.execute(
                "INSERT INTO riwayat_konsultasi (tanggal, project_name, gem_name, role, content) VALUES (?, ?, ?, ?, ?)", 
                (waktu_sekarang, project, gem, role, text)
            )
            self.conn.commit()
        except Exception as e: 
            print(f"❌ Error Simpan Chat: {e}")

    def get_chat_history(self, project, gem):
        """Mengambil riwayat chat berdasarkan Proyek & Ahli"""
        try:
            query = "SELECT role, content FROM riwayat_konsultasi WHERE project_name = ? AND gem_name = ? ORDER BY id ASC"
            # Menggunakan pandas untuk safety & kemudahan
            df = pd.read_sql(query, self.conn, params=(project, gem))
            
            # Konversi ke format list of dicts yang diminta Streamlit
            return df.to_dict(orient='records')
        except Exception as e:
            print(f"⚠️ Gagal load history: {e}")
            return []

    def clear_chat(self, project, gem):
        """Menghapus chat spesifik (Reset)"""
        try:
            self.cursor.execute("DELETE FROM riwayat_konsultasi WHERE project_name = ? AND gem_name = ?", (project, gem))
            self.conn.commit()
        except Exception as e:
            print(f"❌ Error Clear Chat: {e}")

    def daftar_proyek(self):
        """List semua nama proyek unik"""
        try:
            df = pd.read_sql("SELECT DISTINCT project_name FROM riwayat_konsultasi", self.conn)
            if not df.empty:
                return df['project_name'].tolist()
            return []
        except: 
            return []

    # ==========================================
    # FITUR MANAJEMEN DATA (BACKUP & RESTORE)
    # ==========================================

    def export_data(self):
        """Export semua data ke format JSON String"""
        try:
            df = pd.read_sql("SELECT * FROM riwayat_konsultasi", self.conn)
            # Konversi datetime ke string agar valid JSON
            if 'tanggal' in df.columns:
                df['tanggal'] = df['tanggal'].astype(str)
                
            return df.to_json(orient='records', date_format='iso')
        except Exception as e: 
            return json.dumps({"error": str(e)})

    def import_data(self, json_file):
        """Restore data dari file JSON yang diupload user"""
        try:
            # 1. Baca File JSON
            data = json.load(json_file)
            
            # 2. Validasi Data Kosong
            if not data:
                return False, "⚠️ File JSON kosong atau format salah."

            # 3. Hapus Database Lama (Clean Slate) - Opsional, bisa diubah jadi append
            self.cursor.execute("DELETE FROM riwayat_konsultasi")
            
            # 4. Proses DataFrame
            df = pd.DataFrame(data)
            
            # Buang kolom ID lama agar Auto-Increment baru bekerja
            if 'id' in df.columns:
                df = df.drop(columns=['id'])
            
            # PENTING: Fix Format Tanggal
            # SQLite butuh format standard, kita pastikan kolom tanggal dikenali
            if 'tanggal' in df.columns:
                df['tanggal'] = pd.to_datetime(df['tanggal'], errors='coerce')
            
            # 5. Masukkan ke SQL
            df.to_sql('riwayat_konsultasi', self.conn, if_exists='append', index=False)
            
            self.conn.commit()
            return True, f"✅ Sukses Restore! {len(df)} pesan dikembalikan."
            
        except Exception as e:
            # Rollback jika gagal di tengah jalan
            self.conn.rollback()
            return False, f"❌ Gagal Restore: {str(e)}"

    def close(self):
        """Tutup koneksi database"""
        if self.conn:
            self.conn.close()
