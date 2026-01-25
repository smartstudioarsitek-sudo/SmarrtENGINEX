import sqlite3
import pandas as pd
import os
import json
from datetime import datetime
import io

class EnginexBackend:
    def __init__(self, db_path='database/enginex_core.db'):
        self.db_folder = os.path.dirname(db_path)
        if self.db_folder and not os.path.exists(self.db_folder):
            try:
                os.makedirs(self.db_folder)
            except OSError: pass

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.init_db()

    def init_db(self):
        # Tabel Chat
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

    # --- FITUR CHAT ---
    def simpan_chat(self, project, gem, role, text):
        try:
            self.cursor.execute("INSERT INTO riwayat_konsultasi (project_name, gem_name, role, content) VALUES (?, ?, ?, ?)", 
                               (project, gem, role, text))
            self.conn.commit()
        except Exception as e: print(f"Error DB: {e}")

    def get_chat_history(self, project, gem):
        try:
            query = f"SELECT role, content FROM riwayat_konsultasi WHERE project_name = ? AND gem_name = ? ORDER BY id ASC"
            return pd.read_sql(query, self.conn, params=(project, gem)).to_dict(orient='records')
        except: return []

    def clear_chat(self, project, gem):
        self.cursor.execute("DELETE FROM riwayat_konsultasi WHERE project_name = ? AND gem_name = ?", (project, gem))
        self.conn.commit()

    def daftar_proyek(self):
        try:
            df = pd.read_sql("SELECT DISTINCT project_name FROM riwayat_konsultasi", self.conn)
            return df['project_name'].tolist()
        except: return []

    # --- FITUR BACKUP (SAVE) ---
    def export_data(self):
        try:
            df = pd.read_sql("SELECT * FROM riwayat_konsultasi", self.conn)
            return df.to_json(orient='records')
        except: return "[]"

    # --- FITUR RESTORE (OPEN) - BARU! ---
    def import_data(self, json_file):
        try:
            # 1. Baca JSON yang diupload
            data = json.load(json_file)
            
            # 2. Hapus data lama biar bersih (atau bisa diatur append)
            self.cursor.execute("DELETE FROM riwayat_konsultasi")
            
            # 3. Masukkan data baru
            if data:
                df = pd.DataFrame(data)
                # Buang kolom ID lama biar tidak bentrok (biar auto-increment baru)
                if 'id' in df.columns:
                    df = df.drop(columns=['id'])
                
                df.to_sql('riwayat_konsultasi', self.conn, if_exists='append', index=False)
            
            self.conn.commit()
            return True, "✅ Data Berhasil Dikembalikan!"
        except Exception as e:
            return False, f"❌ Gagal Restore: {str(e)}"
