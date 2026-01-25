import sqlite3
import pandas as pd
import os
import json
from datetime import datetime

class EnginexBackend:
    def __init__(self, db_path='database/enginex_core.db'):
        # Membuat folder database jika belum ada
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
        Database Utama ENGINEX.
        Fokus: Manajemen Proyek & History Chat dengan Tim AI.
        """
        # 1. Tabel History Chat (Untuk 17+ Gems)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS riwayat_konsultasi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tanggal TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                project_name TEXT, -- Nama Proyek (misal: Rumah Tipe 100)
                gem_name TEXT,     -- Nama Ahli (misal: Ahli Struktur)
                role TEXT,         -- 'user' atau 'assistant'
                content TEXT
            )
        ''')
        
        # 2. Tabel Log Proyek (Untuk Project Manager memantau status)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS log_proyek (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama_proyek TEXT,
                kategori TEXT, -- Gedung, Jalan, Irigasi, dll
                progress REAL,
                status TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    # --- FITUR CHAT AI ---
    def simpan_chat(self, project, gem, role, text):
        try:
            self.cursor.execute("INSERT INTO riwayat_konsultasi (project_name, gem_name, role, content) VALUES (?, ?, ?, ?)", 
                               (project, gem, role, text))
            self.conn.commit()
        except Exception as e: print(f"Error DB: {e}")

    def get_chat_history(self, project, gem):
        """Ambil percakapan berdasarkan Nama Proyek & Nama Gem"""
        try:
            query = f"SELECT role, content FROM riwayat_konsultasi WHERE project_name = ? AND gem_name = ? ORDER BY id ASC"
            return pd.read_sql(query, self.conn, params=(project, gem)).to_dict(orient='records')
        except: return []

    def clear_chat(self, project, gem):
        self.cursor.execute("DELETE FROM riwayat_konsultasi WHERE project_name = ? AND gem_name = ?", (project, gem))
        self.conn.commit()

    # --- FITUR MANAJEMEN PROYEK ---
    def daftar_proyek(self):
        try:
            df = pd.read_sql("SELECT DISTINCT project_name FROM riwayat_konsultasi", self.conn)
            return df['project_name'].tolist()
        except: return []

    # --- BACKUP DATA ---
    def export_data(self):
        try:
            df = pd.read_sql("SELECT * FROM riwayat_konsultasi", self.conn)
            return df.to_json(orient='records')
        except: return "{}"
