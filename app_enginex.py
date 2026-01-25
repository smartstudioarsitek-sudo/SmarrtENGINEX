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

# --- 1. SETUP API KEY (DENGAN PEMBERSIH & INPUT MANUAL) ---
with st.sidebar:
    st.title("🏗️ ENGINEX")
    
    # Prioritaskan Input Manual agar Kakak bisa ganti key kapan saja
    api_key_input = st.text_input("🔑 API Key Baru (Wajib Diisi):", type="password")
    
    if api_key_input:
        raw_key = api_key_input
        st.caption("ℹ️ Memakai Key Manual")
    else:
        # Cadangan ambil dari secrets kalau input kosong
        raw_key = st.secrets.get("GOOGLE_API_KEY")
        
    if not raw_key:
        st.warning("⚠️ Masukkan API Key dulu.")
        st.stop()

    # BERSIHKAN KEY (Hapus spasi/enter tersembunyi)
    clean_api_key = raw_key.strip()

# KONFIGURASI JALUR REST (Supaya tidak timeout/illegal metadata)
try:
    genai.configure(api_key=clean_api_key, transport="rest")
except Exception as e:
    st.error(f"Gagal Konfigurasi: {e}")

# --- 2. MODEL SELECTION (HARDCODED - JANGAN AUTO DETECT LAGI) ---
# Kita paksa pakai 1.5 Flash (Kuota 1500/hari)
# Jangan biarkan AI memilih 2.5 Flash (Kuota cuma 20/hari)
TARGET_MODEL = "gemini-1.5-flash"

# --- 3. DEFINISI OTAK GEMS (FULL TEAM SESUAI GAMBAR) ---
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
    # Tampilkan Model yang Dipaksa
    st.caption(f"Status: ✅ Terhubung\nModel: `{TARGET_MODEL}` (Kuota Besar)") 
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
                # PAKSA PAKE 1.5 FLASH
                model = genai.GenerativeModel(TARGET_MODEL)
                
                full_prompt = f"PERAN: {gems_persona[selected_gem]}\nUSER: {prompt}"
                
                chat_history_formatted = [{"role": "user" if h['role']=="user" else "model", "parts": [h['content']]} for h in history]
                
                chat = model.start_chat(history=chat_history_formatted)
                response = chat.send_message(full_prompt)
                
                st.markdown(response.text)
                db.simpan_chat(nama_proyek, selected_gem, "assistant", response.text)
                
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg:
                    # Kalau masih limit juga, berarti API Key-nya beneran habis total
                    st.error("⚠️ Kuota API Key Habis Total. Mohon input API KEY BARU lagi di Sidebar.")
                elif "404" in err_msg:
                    # Fallback kalau 1.5 Flash lagi down, pakai Pro
                    try:
                        fallback_model = genai.GenerativeModel("gemini-pro")
                        chat = fallback_model.start_chat(history=chat_history_formatted)
                        response = chat.send_message(full_prompt)
                        st.markdown(response.text)
                        db.simpan_chat(nama_proyek, selected_gem, "assistant", response.text)
                    except:
                        st.error("❌ Semua model sibuk. Coba lagi nanti.")
                else:
                    st.error(f"Error: {e}")
