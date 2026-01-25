import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ENGINEX Super App", page_icon="🏗️", layout="wide")

# --- KONEKSI BACKEND ---
try:
    from backend_enginex import EnginexBackend
    if 'backend' not in st.session_state:
        st.session_state.backend = EnginexBackend()
    db = st.session_state.backend
except ImportError:
    st.error("⚠️ File 'backend_enginex.py' belum dibuat di GitHub!")
    st.stop()

# --- CSS ---
st.markdown("""
<style>
    .main-header {font-size: 30px; font-weight: bold; color: #1E3A8A; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# --- 1. SETUP API KEY (VERSI EMERGENCY INPUT) ---
# Logika: Prioritaskan Input Sidebar agar User bisa ganti key kapan saja
with st.sidebar:
    st.title("🏗️ ENGINEX")
    
    # Input Key Selalu Muncul
    api_key_input = st.text_input("🔑 Ganti API Key Baru (Jika Error):", type="password")
    
    # Cek: Pakai Input User atau Secrets?
    if api_key_input:
        api_key = api_key_input
        st.caption("ℹ️ Menggunakan Key Manual")
    else:
        api_key = st.secrets.get("GOOGLE_API_KEY")
        if api_key:
            st.caption("ℹ️ Menggunakan Key dari Secrets")

    if not api_key:
        st.warning("⚠️ Masukkan API Key dulu untuk memulai.")
        st.stop()

genai.configure(api_key=api_key)

# --- 2. AUTO-DETECT MODEL (VERSI FILTER KUOTA BESAR) ---
@st.cache_resource
def get_working_model(api_key_trigger): # Tambah trigger biar refresh kalau key ganti
    try:
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # PRIORITAS 1: Flash 1.5 (Kuota 1500/hari)
        for m in all_models:
            if "flash" in m and "1.5" in m: return m, None
            
        # PRIORITAS 2: Pro (Cadangan)
        for m in all_models:
            if "gemini-pro" in m and "vision" not in m: return m, None
                
        # DARURAT
        if all_models: return all_models[0], None
            
        return None, "Tidak ada model aktif."
    except Exception as e: return None, str(e)

# Panggil fungsi (dipicu ulang jika api_key berubah)
model_name_fix, error_msg = get_working_model(api_key)

if error_msg: 
    st.error(f"❌ Masalah API Key: {error_msg}")
    model_name_fix = "gemini-1.5-flash" # Default maksa

# --- 3. DEFINISI OTAK GEMS (FINAL: SESUAI SCREENSHOT) ---
gems_persona = {
    "👔 Project Manager (PM)": "Kamu Senior Engineering Manager. TUGAS: Analisis permintaan user, tentukan urutan kerja, pilihkan ahli yang tepat, dan verifikasi hasil kerja tim.",
    "📝 Drafter Laporan DED (Spesialis PUPR)": "Kamu asisten pembuat laporan yang pintar. Fokus: Menyusun Laporan Pendahuluan, Antara, Akhir (Word), Spek Teknis, dan Notulensi Rapat.",
    "⚖️ Ahli Legal & Kontrak": "Kamu Contract Specialist. Fokus: Hukum Konstruksi, Kontrak (FIDIC/Lumpsum), Klaim, dan Sengketa.",
    "🌾 Ahli IKSI-PAI (Permen PUPR)": "Kamu Konsultan Teknis Irigasi Senior. Hafal bobot, kriteria, dan cara menilai kondisi fisik vs fungsi (IKSI). Fokus: Blangko 01-O s/d 09-O dan PAI.",
    "🌊 Ahli Bangunan Air & Irigasi (The Designer)": "Mencakup: Desain Irigasi, Bendung (Weir), Bendungan (Dam), Hidraulika. Fokus: Desain fisik, stabilitas struktur air.",
    "🌧️ Ahli Hidrologi & Sungai (The Analyst)": "Mencakup: Hidrologi, Curah hujan, Klimatologi, Pola tanam, FJ Mock, Desain Banjir, Teknik Sungai. Fokus: Analisis data air.",
    "🏖️ Ahli Teknik Pantai (The Coastal Expert)": "Mencakup: Ahli Pantai, Pelabuhan, Pasang Surut. Fokus: Dinamika laut, Breakwater, Seawall, dan proteksi garis pantai.",
    "🏗️ Ahli Struktur (Structural Expert)": "Fokus: Kekuatan Bangunan, Standar SNI, Hitungan Beton/Baja. Gunakan untuk: Menentukan dimensi kolom/balok/plat.",
    "🪨 Ahli Geoteknik & Mekanika Tanah": "Fokus: Penyelidikan Tanah (Sondir/Boring), Daya Dukung, Stabilitas Lereng, Perbaikan Tanah.",
    "🛣️ Ahli Jalan & Jembatan": "Fokus: Geometrik Jalan, Perkerasan (Pavement), Struktur Jembatan. Basis: Standar Bina Marga (PUPR) & AASHTO.",
    "🌍 Ahli Geodesi & GIS": "Fokus: Survey Topografi, Pengukuran (Total Station/GPS), Fotogrametri (Drone), Perhitungan Galian/Timbunan (Cut & Fill).",
    "🏛️ Senior Architect & Interior": "Fokus: Bangunan, Estetika, Fungsi Ruang, Material, Utilitas Bangunan, Interior Layout.",
    "🌳 Landscape Architect (Lansekap)": "Fokus: Ruang Luar, Tanaman, Hardscape, Resapan Air. Gunakan untuk: Desain taman, area hijau.",
    "🎨 Creative Director ArchViz (3D & Animation)": "Fokus: Konsep Visual, Storytelling, Cinematography, Prompt Engineering (AI Image), dan Arahan Teknis Rendering (Lumion/Enscape/D5).",
    "🌍 Ahli Planologi (Urban Planner)": "Fokus: Makro Wilayah, Peraturan (RTRW/RDTR), Perizinan, Analisis Tapak Kawasan.",
    "🏭 Ahli Proses Industri (Chemical Engineer)": "Fokus: Pengolahan Minyak Mentah/Olie Bekas, Pipa Industri, Proses Kimia. (Ranah Teknik Kimia).",
    "📜 Ahli AMDAL & Dokumen Lingkungan": "Fokus: AMDAL, UKL-UPL. Bukan soal hitungan teknik, tapi soal Hukum Lingkungan, Dampak Sosial, dan Biologi.",
    "♻️ Ahli Teknik Lingkungan (Sanitary)": "Fokus: Ilmu IPAL (Air Limbah), IPLT (Lumpur Tinja), TPA (Sampah), dan Air Bersih (WTP).",
    "⛑️ Ahli K3 Konstruksi": "Fokus: Rencana K3 (SMKK), Identifikasi Bahaya, APD, Prosedur Kerja Aman.",
    "💻 Lead Engineering Developer": "Kamu Programmer Teknik. Tidak perlu hafal pasal, tapi jago menerjemahkan tabel penilaian menjadi Kode Python/Streamlit/Database.",
    "📐 CAD & BIM Automator": "Fokus: Penulis script AutoLISP (AutoCAD) dan Dynamo (Revit) untuk otomatisasi gambar.",
    "🖥️ Instruktur Software": "Kamu Guru Software Teknik. WAJIB: Jelaskan Step-by-step & Berikan Link Youtube Search di akhir.",
    "💰 Ahli Estimator & RAB": "Fokus: Volume Material, BOQ, Harga Satuan (AHSP), Budgeting. Gunakan untuk: Menghitung biaya proyek.",
    "💵 Ahli Keuangan Proyek": "Fokus: Cashflow, Pajak Proyek, Laporan Keuangan, ROI.",
    "📜 Ahli Perizinan (IMB/PBG)": "Fokus: Pengurusan Izin Bangunan Gedung (PBG), SLF, KRK."
}

# --- 4. UI SIDEBAR ---
with st.sidebar:
    st.caption(f"Status AI: ✅ Terhubung\nModel: `{model_name_fix}`") 
    st.divider()
    
    # === SAVE & RESTORE ===
    with st.expander("💾 Save & Open Project", expanded=True):
        st.download_button("⬇️ Simpan Proyek", db.export_data(), "enginex_data.json", mime="application/json")
        uploaded_file = st.file_uploader("⬆️ Buka Proyek", type=["json"])
        if uploaded_file is not None:
            if st.button("Proses Restore"):
                sukses, pesan = db.import_data(uploaded_file)
                if sukses: st.success(pesan); st.rerun() 
                else: st.error(pesan)
    
    st.divider()
    
    # PILIH PROYEK
    existing_projects = db.daftar_proyek()
    mode_proyek = st.radio("Mode Kerja:", ["Proyek Baru", "Buka Proyek Lama"])
    
    if mode_proyek == "Proyek Baru":
        nama_proyek = st.text_input("Nama Proyek:", "Proyek Baru")
    else:
        nama_proyek = st.selectbox("Pilih Proyek:", existing_projects) if existing_projects else "Belum ada proyek"
    
    st.divider()
    
    # PILIH AHLI
    st.markdown("### 👷 Pilih Tenaga Ahli")
    selected_gem = st.selectbox("Daftar Tim Ahli Lengkap:", list(gems_persona.keys()))
    
    if st.button("Bersihkan Chat Ini"):
        db.clear_chat(nama_proyek, selected_gem)
        st.rerun()

# --- 5. AREA CHAT ---
st.markdown(f'<div class="main-header">{nama_proyek}</div>', unsafe_allow_html=True)
st.caption(f"Diskusi dengan: **{selected_gem}**")

history = db.get_chat_history(nama_proyek, selected_gem)
for chat in history:
    with st.chat_message(chat['role']):
        st.markdown(chat['content'])

if prompt := st.chat_input("Ketik pesan..."):
    db.simpan_chat(nama_proyek, selected_gem, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner(f"{selected_gem} berpikir..."):
            try:
                # INSTANSIASI MODEL
                model = genai.GenerativeModel(model_name_fix)
                full_prompt = f"PERAN: {gems_persona[selected_gem]}\nUSER: {prompt}"
                
                chat_history_formatted = [{"role": "user" if h['role']=="user" else "model", "parts": [h['content']]} for h in history]
                
                chat = model.start_chat(history=chat_history_formatted)
                response = chat.send_message(full_prompt)
                
                st.markdown(response.text)
                db.simpan_chat(nama_proyek, selected_gem, "assistant", response.text)
                
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg:
                    st.error("⚠️ SISA KUOTA API KEY 0 RUPIAH. Mohon buat KEY BARU di aistudio.google.com dan masukkan di Sidebar kiri.")
                else:
                    st.error(f"Error Generasi: {e}")
