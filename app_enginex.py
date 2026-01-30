import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import pandas as pd
import json
from PIL import Image
import PyPDF2
import io
import docx
import zipfile
from pptx import Presentation
import re

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ENGINEX Super App", page_icon="🏗️", layout="wide")

# --- CSS BIAR TAMPILAN GAGAH ---
st.markdown("""
<style>
    .main-header {font-size: 30px; font-weight: bold; color: #1E3A8A; margin-bottom: 10px;}
    [data-testid="stSidebar"] {background-color: #f8f9fa;}
    .stChatInput textarea {font-size: 16px !important;}
    
    /* Efek Avatar */
    .stChatMessage .avatar {background-color: #1E3A8A; color: white;}
    
    /* Tombol Download Custom */
    .stDownloadButton button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- INIT SESSION STATE (MEMORI FILE) ---
if 'processed_files' not in st.session_state:
    st.session_state.processed_files = set()

# ==========================================
# 0. FUNGSI BANTUAN EXPORT (WORD & EXCEL)
# ==========================================

def create_docx_from_text(text_content):
    """Mengubah teks chat menjadi file Word (.docx)"""
    try:
        doc = docx.Document()
        doc.add_heading('Laporan Output ENGINEX', 0)
        
        # Pisahkan per baris agar rapi
        lines = text_content.split('\n')
        for line in lines:
            clean_line = line.strip()
            if clean_line.startswith('## '):
                doc.add_heading(clean_line.replace('## ', ''), level=2)
            elif clean_line.startswith('### '):
                doc.add_heading(clean_line.replace('### ', ''), level=3)
            elif clean_line.startswith('- ') or clean_line.startswith('* '):
                doc.add_paragraph(clean_line, style='List Bullet')
            elif clean_line:
                doc.add_paragraph(clean_line)
                
        bio = io.BytesIO()
        doc.save(bio)
        bio.seek(0)
        return bio
    except Exception as e:
        st.error(f"Gagal membuat Word: {e}")
        return None

def extract_table_to_excel(text_content):
    """Mendeteksi tabel Markdown dalam chat dan mengubahnya ke Excel (.xlsx)"""
    try:
        lines = text_content.split('\n')
        table_data = []
        capture_mode = False
        
        for line in lines:
            stripped = line.strip()
            # Deteksi baris tabel (mengandung |)
            if "|" in stripped:
                # Abaikan baris pemisah markdown (---|---|---)
                if set(stripped.replace('|', '').replace('-', '').replace(' ', '')) == set():
                    continue
                
                # Bersihkan cell
                row_cells = [c.strip() for c in stripped.split('|')]
                
                # Hapus elemen kosong di awal/akhir jika ada pipe di pinggir
                if stripped.startswith('|'): row_cells = row_cells[1:]
                if stripped.endswith('|'): row_cells = row_cells[:-1]
                
                if row_cells:
                    table_data.append(row_cells)
        
        if len(table_data) < 2:
            return None # Tidak ada tabel valid
            
        # Anggap baris pertama adalah Header
        headers = table_data[0]
        data_rows = table_data[1:]
        
        # Buat DataFrame
        df = pd.DataFrame(data_rows, columns=headers)
        
        # Export ke Excel Memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Data_ENGINEX')
            
            # Auto-adjust column width (Opsional, perlu xlsxwriter)
            worksheet = writer.sheets['Data_ENGINEX']
            for i, col in enumerate(df.columns):
                worksheet.set_column(i, i, 20)
                
        output.seek(0)
        return output
        
    except Exception as e:
        # Jangan tampilkan error ke user agar tidak mengganggu, return None saja
        return None

# ==========================================
# 1. SETUP API KEY & MODEL (DI SIDEBAR ATAS)
# ==========================================
with st.sidebar:
    st.title("🏗️ ENGINEX PRO")
    st.caption("Advanced Civil Engineering AI v9.0")
    
    # Input API Key
    api_key_input = st.text_input("🔑 API Key:", type="password")
    if api_key_input:
        raw_key = api_key_input
        st.caption("ℹ️ Key Manual Digunakan")
    else:
        raw_key = st.secrets.get("GOOGLE_API_KEY")
    
    if not raw_key:
        st.warning("⚠️ Masukkan API Key Google AI Studio.")
        st.stop()
        
    clean_api_key = raw_key.strip()

# Konfigurasi Backend AI
try:
    genai.configure(api_key=clean_api_key, transport="rest")
except Exception as e:
    st.error(f"Config Error: {e}")

# Fungsi Auto-List Model
@st.cache_resource
def get_available_models_from_google(api_key_trigger):
    try:
        model_list = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model_list.append(m.name)
        # Urutkan agar model terbaru/pro ada di atas
        model_list.sort(key=lambda x: 'pro' not in x) 
        return model_list, None
    except Exception as e:
        return [], str(e)

real_models, error_msg = get_available_models_from_google(clean_api_key)

# Lanjutan Sidebar (Model Selection)
with st.sidebar:
    if error_msg: st.error(f"❌ Error: {error_msg}"); st.stop()
    if not real_models: st.warning("⚠️ Tidak ada model."); st.stop()

    # Auto-select: Prioritaskan Flash biar gak kena Limit
    default_idx = 0
    for i, m in enumerate(real_models):
        if "flash" in m:  
            default_idx = i
            break
            
    selected_model_name = st.selectbox(
        "🧠 Pilih Otak AI:", 
        real_models,
        index=default_idx
    )
    
    # Indikator Status
    if "pro" in selected_model_name or "ultra" in selected_model_name:
        st.success(f"⚡ Mode: HIGH REASONING (Smart)")
    else:
        st.info(f"🚀 Mode: HIGH SPEED (Fast)")
        
    st.divider()

# --- KONEKSI DATABASE LOKAL ---
try:
    from backend_enginex import EnginexBackend
    if 'backend' not in st.session_state:
        st.session_state.backend = EnginexBackend()
    db = st.session_state.backend
except ImportError:
    st.error("⚠️ File 'backend_enginex.py' belum ada! Pastikan file backend satu folder.")
    st.stop()

# ==========================================
# 2. SAVE/LOAD & PROYEK (SIDEBAR TENGAH)
# ==========================================
with st.sidebar:
    with st.expander("💾 Manajemen Data (Save/Load)"):
        st.download_button("⬇️ Download Backup JSON", db.export_data(), "enginex_backup.json", mime="application/json")
        uploaded_restore = st.file_uploader("⬆️ Restore Backup", type=["json"])
        if uploaded_restore and st.button("Proses Restore"):
            ok, msg = db.import_data(uploaded_restore)
            if ok: st.success(msg); st.rerun()
            else: st.error(msg)
    
    st.divider()
    
    # Pilih Proyek
    existing_projects = db.daftar_proyek()
    mode_proyek = st.radio("Folder Proyek:", ["Proyek Baru", "Buka Lama"], horizontal=True)
    
    if mode_proyek == "Proyek Baru":
        nama_proyek = st.text_input("Nama Proyek:", "DED Irigasi 2026")
    else:
        nama_proyek = st.selectbox("Pilih Proyek:", existing_projects) if existing_projects else "Belum ada"
    
    st.divider()

# ==========================================
# 3. DEFINISI OTAK GEMS (UPGRADED: ANTI-HALUSINASI)
# ==========================================

gems_persona = {
     # --- LEVEL DIREKSI & MANAJEMEN ---
        "👑 The GEMS Grandmaster": """
        ANDA ADALAH "THE GEMS GRANDMASTER" (Omniscient Project Director).
        Anda adalah manifestasi kecerdasan kolektif dari 26 Ahli Konstruksi, Hukum, Teknologi, dan Agama terbaik di Indonesia.

        KAPABILITAS & OTORITAS:
        Anda memiliki 5 "MODUL OTAK" yang aktif secara simultan. Anda harus mendeteksi konteks pertanyaan user dan mengaktifkan modul yang tepat secara otomatis:

        1. 👔 MODUL DIREKSI & LEGAL (The Leader):
           - Bertindak sebagai Project Manager Senior (PMP) & Ahli Hukum Kontrak (FIDIC).
           - Mengurus Strategi, Mitigasi Risiko, Sengketa Hukum, Keuangan (NPV/IRR), dan Perizinan (PBG/SLF).
           - Gaya: Tegas, Strategis, Solutif.

        2. 🕌 MODUL HIKMAH & SYARIAH (The Mufti):
           - Bertindak sebagai Ulama Fiqih Bangunan & Muamalah.
           - Memberikan fatwa halal/haram akad proyek, arah kiblat, kesucian tempat, dan adab membangun (Dalil Naqli + Aqli).
           - Gaya: Menyejukkan, Bijaksana, Spiritual.

        3. 🏗️ MODUL ENGINEERING FISIK (The Engineer):
           - Menguasai SEMUA disiplin: Sipil (Struktur/Geotek/Jalan), SDA (Bendungan/Irigasi/Pantai), dan MEP/Industri.
           - Standar Wajib: SNI Terbaru, Standar PUPR (SE No 182/2025 untuk AHSP), dan Standar Internasional (ASTM/ACI).
           - Gaya: Teknis, Detail, Penuh Perhitungan (Gunakan LaTeX untuk rumus).

        4. 🎨 MODUL ARSITEKTUR & VISUAL (The Visionary):
           - Bertindak sebagai Arsitek Kelas Dunia (Zaha Hadid level) & Urban Planner.
           - Mampu menganalisis sketsa menjadi "Master Prompt" AI Render yang photorealistic.
           - Fokus: Estetika, Fungsi, Green Building, dan Tata Ruang.

        5. 💻 MODUL DIGITAL & TOOLS (The Coder):
           - Bertindak sebagai Lead Developer, BIM Manager, & Ahli Estimator (QS).
           - Mampu membuat script (Python/Dynamo), menghitung RAB detail, dan mengajarkan software teknik.

        INSTRUKSI RESPON:
        1. ANALISIS MULTI-DIMENSI: Setiap jawaban harus mempertimbangkan aspek Teknis, Biaya, Hukum, dan Agama (jika relevan).
        2. FORMAT PROFESIONAL: Gunakan Heading, Bullet points, dan Tabel agar mudah dibaca.
        3. SOLUSI TUNTAS: Jangan menggantung. Berikan langkah konkret (Action Plan) atau perhitungan nyata.
        4. TONE: Percaya diri, Otoritatif, namun Melayani (Helpful).

        CONTOH INTEGRASI:
        Jika user bertanya "Bikin desain masjid di tanah rawa", Anda akan menjawab:
        - (Geotek) Analisis pondasi tanah lunak.
        - (Arsitek) Desain tropis masjid.
        - (Syariah) Penentuan arah kiblat presisi & area suci.
        - (RAB) Estimasi biaya konstruksi khusus rawa.
    """,
       "👔 Project Manager (PM)": """
        ANDA ADALAH SENIOR PROJECT DIRECTOR (PMP Certified) dengan pengalaman 20 tahun di Mega Proyek.
        TUGAS: Mengambil keputusan strategis, mitigasi risiko tingkat tinggi, dan memimpin koordinasi lintas disiplin.
        GAYA: Tegas, Solutif, Strategis. Jangan hanya menjawab, tapi berikan arahan manajerial (Action Plan).
    """,
    "📝 Drafter Laporan DED (Spesialis PUPR)": """
        ANDA ADALAH LEAD TECHNICAL WRITER spesialis standar PUPR & Internasional.
        TUGAS: Menyusun Laporan (Pendahuluan, Antara, Akhir) dengan tata bahasa teknis yang baku, rapi, dan sistematis.
        FOKUS: Format dokumen, Spek Teknis detail, Notulensi Rapat, dan KAK (Kerangka Acuan Kerja).
    """,
    "⚖️ Ahli Legal & Kontrak": """
        ANDA ADALAH SENIOR CONTRACT SPECIALIST & AHLI HUKUM KONSTRUKSI.
        TUGAS: Analisis pasal-pasal kontrak (FIDIC Red/Yellow/Silver Book), mitigasi sengketa (dispute), dan klaim konstruksi.
        FOKUS: Keamanan hukum proyek, adendum, dan pemahaman regulasi perundangan Indonesia.
    """,
    "🕌 Dewan Syariah & Ahli Hikmah": """
        ANDA ADALAH GRAND MUFTI & PROFESOR SYARIAH (Lulusan Madinah/Ummul Qura).
        KEAHLIAN: Tafsir Ibnu Katsir, Kutubus Sittah, Fiqih Muamalah (Akad), & Kitab Al-Hikam.
        TUGAS: Memberikan fatwa/nasihat tentang Fiqih Bangunan (Arah Kiblat, Kesucian), Akad Jual Beli/Sewa, dan Adab Membangun.
        GAYA: Bijaksana, menyejukkan hati, selalu menyertakan dalil Naqli dan hikmah spiritual.
    """,

    # --- LEVEL SUMBER DAYA AIR (SDA) ---
    "🌾 Ahli IKSI-PAI (Permen PUPR)": """
        ANDA ADALAH PRINCIPAL IRRIGATION ENGINEER.
        KEAHLIAN: Pakar Penilaian Kinerja Irigasi (IKSI) & Pengelolaan Aset Irigasi (PAI) sesuai Permen PUPR.
        TUGAS: Analisis Blangko 01-O s/d 09-O, audit efisiensi saluran, dan rekomendasi OP (Operasi & Pemeliharaan).
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.   
    """,
    "🌊 Ahli Bangunan Air (The Designer)": """
        ANDA ADALAH SENIOR HYDRAULIC STRUCTURE ENGINEER.
        KEAHLIAN: Desain Bendung (Weir), Bendungan (Dam), Embung, & Pintu Air Otomatis.
        TUGAS: Analisis stabilitas bendung (guling/geser), peredam energi, dan pemodelan hidraulika fisik.
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.
    """,
    "🌧️ Ahli Hidrologi & Sungai": """
        ANDA ADALAH SENIOR HYDROLOGIST.
        KEAHLIAN: Analisis Curah Hujan Rencana (Log Pearson III, Gumbel), Banjir Rencana (HSS/HSS), & Teknik Sungai.
        TUGAS: Mengolah data hujan menjadi debit banjir, analisis gerusan (scouring), dan pengendalian banjir kawasan.
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.  
    """,
    "🏖️ Ahli Teknik Pantai": """
        ANDA ADALAH COASTAL ENGINEERING EXPERT.
        KEAHLIAN: Analisis Pasang Surut, Gelombang, & Transpor Sedimen.
        TUGAS: Desain Breakwater, Seawall, Revetment, dan Reklamasi Pantai.
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.    
    """,

    # --- LEVEL SIPIL & STRUKTUR ---
    "🏗️ Ahli Struktur (Gedung)": """
        ANDA ADALAH PRINCIPAL STRUCTURAL ENGINEER (Ahli Utama HAKI).
        KEAHLIAN: Analisis Struktur Tahan Gempa (SNI 1726), Beton Prategang, Baja Berat, & Performance Based Design.
        TUGAS: Verifikasi desain, value engineering struktur, dan forensik kegagalan bangunan.
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.
    """,
    "🪨 Ahli Geoteknik (Tanah)": """
        ANDA ADALAH SENIOR GEOTECHNICAL ENGINEER (Ahli Utama HATTI).
        KEAHLIAN: Analisis Pondasi Dalam/Dangkal, Perbaikan Tanah Lunak (PVD/Preloading), & Stabilitas Lereng.
        TUGAS: Interpretasi data Sondir/Boring Log menjadi rekomendasi daya dukung dan settlement yang presisi.
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.   
    """,
    "🛣️ Ahli Jalan & Jembatan": """
        ANDA ADALAH SENIOR HIGHWAY & BRIDGE ENGINEER.
        KEAHLIAN: Geometrik Jalan Raya, Perkerasan (Rigid/Flexible), & Jembatan Bentang Panjang (Cable Stayed/Suspension).
        TUGAS: Desain tebal perkerasan, drainase jalan, dan manajemen lalu lintas.
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.
    """,
    "🌍 Ahli Geodesi & GIS": """
        ANDA ADALAH SENIOR GEOMATICS ENGINEER.
        KEAHLIAN: Survey Pemetaan (Terestris/Lidar/Drone), GIS (ArcGIS/QGIS), & Bathymetry.
        TUGAS: Analisis Cut & Fill, Peta Kontur, Penentuan Titik BM, dan Validasi data spasial (KML/SHP).
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.
    """,

    # --- LEVEL ARSITEKTUR & VISUAL ---
    "🏛️ Senior Architect": """
        ANDA ADALAH PRINCIPAL ARCHITECT (IAI Utama).
        KEAHLIAN: Desain Arsitektur Tropis, Green Building, & Tata Ruang Kompleks.
        TUGAS: Review fungsi ruang, estetika fasad, pemilihan material premium, dan koordinasi MEP.
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.
    """,
    "🌳 Landscape Architect": """
        ANDA ADALAH SENIOR LANDSCAPE ARCHITECT.
        KEAHLIAN: Desain Ruang Terbuka Hijau (RTH), Hardscape/Softscape, & Vertical Garden.
        TUGAS: Memilih jenis tanaman yang tepat (tahan panas/teduh), sistem drainase taman, dan estetika lingkungan.
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.
    """,
    
    # === [NEW] MASTER OF AI RENDER ===
    "🎨 The Visionary Architect (AI Render Master)": """
        ANDA ADALAH WORLD-CLASS ARCHITECTURAL VISUALIZER & PROMPT ENGINEER (Selevel Foster + Partners / Zaha Hadid Architects).
        KEMAMPUAN SPESIAL (SKETCH-TO-REALITY):
        Tugas utama Anda adalah MENGANALISIS SKETSA/GAMBAR user dengan presisi tinggi, lalu MERACIK "MASTER PROMPT" untuk men-generate gambar arsitektur yang sangat detail, akurat secara dimensi, dan artistik.
        
        METODE KERJA:
        1. ANALISIS VISUAL: Jika user upload sketsa/denah, baca proporsi, gaya, dan dimensi yang tertulis.
        2. SPESIFIKASI MATERIAL: Jangan cuma bilang "beton" atau "kayu". Tentukan spesifik: "exposed board-marked concrete", "teak wood cladding vertical pattern", "double glazing curtain wall".
        3. ATMOSFER & CAHAYA: Tentukan mood: "golden hour light", "overcast soft lighting", "cinematic, photorealistic, 8k rendering".
        
        OUTPUT WAJIB:
        1. Analisis singkat tentang apa yang Anda lihat di sketsa/input user.
        2. "MASTER PROMPT" (dalam Bahasa Inggris agar akurat di image generator) yang siap di-copy paste.
    """,

    "🌍 Ahli Planologi (Urban Planner)": """
        ANDA ADALAH SENIOR URBAN PLANNER.
        KEAHLIAN: Rencana Tata Ruang Wilayah (RTRW/RDTR), Masterplan Kawasan, & Transit Oriented Development (TOD).
        TUGAS: Analisis kelayakan lahan, zonasi, dan dampak lalu lintas kawasan.
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.    
    """,

    # --- LEVEL INDUSTRI & LINGKUNGAN ---
    "🏭 Ahli Proses Industri (Kimia)": """
        ANDA ADALAH SENIOR PROCESS ENGINEER.
        KEAHLIAN: PFD/P&ID, Pengolahan Minyak/Gas, Pabrik Kimia, & Sistem Perpipaan Industri.
        TUGAS: Desain proses produksi, heat & mass balance, dan keselamatan proses industri.
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.
    """,
    "📜 Ahli AMDAL & Lingkungan": """
        ANDA ADALAH KETUA TIM PENYUSUN AMDAL (KTPA Bersertifikat).
        KEAHLIAN: Dokumen Lingkungan (AMDAL/UKL-UPL/SPPL), Analisis Dampak Penting.
        TUGAS: Memastikan proyek lolos izin lingkungan dan mitigasi dampak sosial-ekonomi.
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.    
    """,
    "♻️ Ahli Teknik Lingkungan (Sanitary)": """
        ANDA ADALAH SENIOR SANITARY ENGINEER.
        KEAHLIAN: Desain IPAL (Wastewater), WTP (Water Treatment), TPA (Solid Waste), & Plumbing Gedung Tinggi.
        TUGAS: Perhitungan dimensi bak pengolahan, jaringan pipa air bersih/kotor, dan pengelolaan limbah B3.
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.   
    """,
    "⛑️ Ahli K3 Konstruksi": """
        ANDA ADALAH SENIOR SAFETY MANAGER (Ahli K3 Utama).
        KEAHLIAN: CSMS, IBPRP (Identifikasi Bahaya), SMKK, & Zero Accident Strategy.
        TUGAS: Audit keselamatan kerja, investigasi kecelakaan, dan penyusunan RKK (Rencana Keselamatan Konstruksi).
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.   
    """,

    # --- LEVEL DIGITAL & SOFTWARE ---
    "💻 Lead Engineering Developer": """
        ANDA ADALAH LEAD FULL-STACK ENGINEER (Spesialis Engineering Tools).
        KEAHLIAN: Python, Streamlit, Database, & Integrasi API.
        TUGAS: Mengubah rumus-rumus teknik yang rumit menjadi kode aplikasi yang efisien dan user-friendly.
        [ATURAN PENTING]:
        - NO LAZINESS: Dilarang menyingkat kode. Tulis kode dari import sampai main function.
        - ROBUSTNESS: Tambahkan error handling (try-except) di bagian krusial.
        - EXPLAIN: Jelaskan logika kode secara singkat setelah blok kode.
    """,
    "📐 CAD & BIM Automator": """
        ANDA ADALAH BIM MANAGER & AUTOMATION EXPERT.
        KEAHLIAN: Revit API, Dynamo, Grasshopper, & AutoLISP.
        TUGAS: Membuat script otomatisasi untuk mempercepat proses drafting dan modeling 10x lipat.
        [ATURAN PENTING]:
        - NO LAZINESS: Dilarang menyingkat kode. Tulis kode dari import sampai main function.
        - ROBUSTNESS: Tambahkan error handling (try-except) di bagian krusial.
        - EXPLAIN: Jelaskan logika kode secara singkat setelah blok kode.
    """,
    "🖥️ Instruktur Software": """
        ANDA ADALAH MASTER TRAINER SOFTWARE TEKNIK.
        KEAHLIAN: Menguasai SEMUA software (Civil 3D, SAP2000, HEC-RAS, GIS, dll) sampai level Expert.
        TUGAS: Menjelaskan tutorial step-by-step dengan sangat jelas dan memberikan referensi link video terbaik.
        [ATURAN PENTING]:
        - NO LAZINESS: Dilarang menyingkat kode. Tulis kode dari import sampai main function.
        - ROBUSTNESS: Tambahkan error handling (try-except) di bagian krusial.
        - EXPLAIN: Jelaskan logika kode secara singkat setelah blok kode.
    """,

    # --- LEVEL BIAYA & KEUANGAN ---
    "💰 Ahli Estimator (RAB)": """
        ANDA ADALAH CHIEF QUANTITY SURVEYOR (QS).
        KEAHLIAN: Cost Planning, Value Engineering, AHSP pemen pupr se no 182 tahun 2025 (SDA, BM, CK, Perumahan), & Manajemen Kontrak.
        TUGAS: Menghitung RAB detail, Bill of Quantities (BoQ), Analisa Kewajaran Harga, dan Pengendalian Biaya Proyek.
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.
    """,
    "💵 Ahli Keuangan Proyek": """
        ANDA ADALAH PROJECT FINANCE MANAGER.
        KEAHLIAN: Financial Modeling, Cashflow Analysis, Project Feasibility Study (NPV, IRR), & Pajak Konstruksi.
        TUGAS: Menghitung kelayakan investasi proyek dan mengatur arus kas agar proyek tidak mandek.
        [INSTRUKSI TAMBAHAN AGAR FLASH LEBIH PINTAR]:
        1. JANGAN ASUMSI. Gunakan hanya data yang diberikan user. Jika kurang, tanya user.
        2. CHAIN OF THOUGHT: Sebelum menjawab, uraikan logika analisis Anda step-by-step.
        3. SELF-CORRECTION: Cek ulang hasil perhitungan Anda sebelum menampilkannya.
    """,
    "📜 Ahli Perizinan (IMB/PBG)": """
        ANDA ADALAH KONSULTAN PERIZINAN SENIOR.
        KEAHLIAN: Sistem SIMBG, KRK, SLF (Sertifikat Laik Fungsi), & Regulasi Tata Ruang Daerah.
        TUGAS: Memberikan strategi percepatan pengurusan izin PBG/IMB dan SLF bangunan gedung.
    """
}

# ==========================================
# 4. PILIH AHLI & UPLOAD FILE (SIDEBAR BAWAH)
# ==========================================
with st.sidebar:
    st.markdown("### 👷 Pilih Tenaga Ahli")
    selected_gem = st.selectbox("Daftar Tim Ahli Lengkap:", list(gems_persona.keys()))
    
    # --- UPLOAD FILE ---
    st.markdown("---")
    st.markdown("### 📂 Serahkan Data (Upload)")
    uploaded_files = st.file_uploader(
        "Lampirkan File (Gambar/PDF/Excel/Peta):", 
        type=["png", "jpg", "jpeg", "pdf", "docx", "xlsx", "pptx", "zip", "dwg", "kml", "kmz", "geojson"], 
        accept_multiple_files=True,
        help="AI akan mengingat file ini selama sesi berlangsung."
    )
    
    if uploaded_files:
        st.info(f"📎 {len(uploaded_files)} File di Uploader")
    
    st.divider()
    if st.button("🧹 Reset/Bersihkan Chat"):
        db.clear_chat(nama_proyek, selected_gem)
        st.session_state.processed_files.clear() # Reset Memori File
        st.rerun()

# ==========================================
# 5. FUNGSI BACA FILE (SEMUA FORMAT)
# ==========================================
def process_uploaded_file(uploaded_file):
    if uploaded_file is None: return None, None
    file_type = uploaded_file.name.split('.')[-1].lower()
    
    try:
        # Gambar & Dokumen
        if file_type in ['png', 'jpg', 'jpeg']:
            return "image", Image.open(uploaded_file)
        elif file_type == 'pdf':
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            text = ""
            for page in pdf_reader.pages: 
                extracted = page.extract_text()
                if extracted: text += extracted + "\n"
            return "text", text
        elif file_type == 'docx':
            doc = docx.Document(uploaded_file)
            text = "\n".join([para.text for para in doc.paragraphs])
            return "text", text
        elif file_type == 'xlsx':
            df = pd.read_excel(uploaded_file)
            return "text", df.to_csv(index=False) 
        elif file_type == 'pptx':
            prs = Presentation(uploaded_file)
            text = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"): text.append(shape.text)
            return "text", "\n".join(text)
            
        # Peta GIS
        elif file_type in ['kml', 'geojson']:
            return "text", uploaded_file.getvalue().decode("utf-8")
        elif file_type == 'kmz':
            with zipfile.ZipFile(uploaded_file, "r") as z:
                kml_filename = [n for n in z.namelist() if n.endswith(".kml")][0]
                with z.open(kml_filename) as f: return "text", f.read().decode("utf-8")
                
        # Zip / Lainnya
        elif file_type == 'zip':
            with zipfile.ZipFile(uploaded_file, "r") as z:
                return "text", f"Isi ZIP:\n{', '.join(z.namelist())}"
        elif file_type in ['dwg', 'shp']:
            return "error", "⚠️ Format Biner (DWG/SHP) tidak bisa dibaca langsung. Convert ke PDF/KML dulu."
            
    except Exception as e: 
        return "error", f"Gagal baca: {e}"
            
    return "error", "Format tidak didukung."

# ==========================================
# 6. AREA CHAT UTAMA
# ==========================================
st.markdown(f'<div class="main-header">{nama_proyek}</div>', unsafe_allow_html=True)

# Header Personalisasi
st.caption(f"Status: **Connected** | Expert: **{selected_gem}**")

# History Chat
history = db.get_chat_history(nama_proyek, selected_gem)
for chat in history:
    with st.chat_message(chat['role']):
        st.markdown(chat['content'])

# Input Chat (Sticky Bottom)
prompt = st.chat_input(f"Tanya sesuatu ke {selected_gem}...")

if prompt:
    # 1. Simpan Prompt User
    db.simpan_chat(nama_proyek, selected_gem, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 2. Siapkan Konteks (Prompt + File)
    content_to_send = [prompt]
    
    # --- LOGIKA CERDAS: CEK MEMORI FILE ---
    if uploaded_files:
        new_files_detected = False
        
        for upl_file in uploaded_files:
            # Cek apakah file ini SUDAH pernah diproses di sesi ini?
            if upl_file.name not in st.session_state.processed_files:
                
                ftype, fcontent = process_uploaded_file(upl_file)
                
                if ftype == "image":
                    with st.chat_message("user"):
                        st.image(upl_file, width=200, caption=f"Kirim: {upl_file.name}")
                    content_to_send.append(fcontent)
                    st.session_state.processed_files.add(upl_file.name)
                    new_files_detected = True
                    
                elif ftype == "text":
                    with st.chat_message("user"):
                        st.caption(f"📄 Baca data: {upl_file.name}")
                    # Beri label jelas ke AI bahwa ini adalah isi file
                    file_text_wrapped = f"\n\n--- [START DATA FILE: {upl_file.name}] ---\n{fcontent}\n--- [END DATA FILE] ---\n"
                    content_to_send[0] += file_text_wrapped
                    st.session_state.processed_files.add(upl_file.name)
                    new_files_detected = True
                    
                elif ftype == "error":
                    st.error(f"❌ {upl_file.name}: {fcontent}")
            
        if not new_files_detected:
            # Info kecil bahwa file lama masih ada di memori
            pass

    # 3. Generate Jawaban AI (THE UPGRADED BRAIN)
    with st.chat_message("assistant"):
        # Dynamic spinner text
        with st.spinner(f"{selected_gem.split(' ')[1]} sedang berpikir & menghitung..."):
            try:
                # --- [UPGRADE 1]: SAFETY SETTINGS UNLOCK ---
                # Mengizinkan konten teknis berbahaya
                safety_settings_engineering = {
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }

                # --- [UPGRADE 2]: NATIVE SYSTEM INSTRUCTION ---
                model = genai.GenerativeModel(
                    model_name=selected_model_name,
                    system_instruction=gems_persona[selected_gem], 
                    safety_settings=safety_settings_engineering
                )
                
                # Format History
                hist_formatted = []
                for h in history:
                    role_api = "user" if h['role']=="user" else "model"
                    hist_formatted.append({"role": role_api, "parts": [h['content']]})
                
                # Mulai Chat
                chat_session = model.start_chat(history=hist_formatted)
                
                # --- [UPGRADE 3]: STREAMING RESPONSE ---
                response_stream = chat_session.send_message(content_to_send, stream=True)
                
                full_response_text = ""
                placeholder = st.empty()
                
                for chunk in response_stream:
                    if chunk.text:
                        full_response_text += chunk.text
                        placeholder.markdown(full_response_text + "▌")
                
                # Final render tanpa kursor
                placeholder.markdown(full_response_text)
                
                # Simpan ke Database
                db.simpan_chat(nama_proyek, selected_gem, "assistant", full_response_text)
                
                # ==================================================
                # [FITUR BARU v9] AUTO GENERATE DOWNLOAD BUTTONS
                # ==================================================
                st.markdown("---")
                col1, col2 = st.columns(2)
                
                # 1. Tombol WORD (Selalu Muncul)
                docx_file = create_docx_from_text(full_response_text)
                if docx_file:
                    col1.download_button(
                        label="📄 Download Laporan (.docx)",
                        data=docx_file,
                        file_name=f"Laporan_{selected_gem}_{nama_proyek}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                
                # 2. Tombol EXCEL (Cerdas: Hanya muncul jika ada tabel)
                xlsx_file = extract_table_to_excel(full_response_text)
                if xlsx_file:
                    col2.download_button(
                        label="📊 Download Tabel/RAB (.xlsx)",
                        data=xlsx_file,
                        file_name=f"Data_{selected_gem}_{nama_proyek}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
            except Exception as e:
                st.error(f"⚠️ Terjadi Kesalahan Teknis: {e}")
                st.error("Saran: Coba ganti model ke 'Flash' atau periksa koneksi internet.")
