import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
from PIL import Image
import PyPDF2
import io
import docx
import zipfile
from pptx import Presentation

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

# --- 1. SETUP API KEY (SIDEBAR) ---
with st.sidebar:
    st.title("🏗️ ENGINEX")
    
    api_key_input = st.text_input("🔑 API Key:", type="password")
    if api_key_input:
        raw_key = api_key_input
        st.caption("ℹ️ Key Manual")
    else:
        raw_key = st.secrets.get("GOOGLE_API_KEY")
    
    if not raw_key:
        st.warning("⚠️ Masukkan API Key.")
        st.stop()
        
    clean_api_key = raw_key.strip()

# KONFIGURASI
try:
    genai.configure(api_key=clean_api_key, transport="rest")
except Exception as e:
    st.error(f"Config Error: {e}")

# --- 2. AUTO-LIST MODEL (ANTI 404) ---
@st.cache_resource
def get_available_models_from_google(api_key_trigger):
    try:
        model_list = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model_list.append(m.name)
        return model_list, None
    except Exception as e:
        return [], str(e)

real_models, error_msg = get_available_models_from_google(clean_api_key)

with st.sidebar:
    st.divider()
    if error_msg: st.error(f"❌ Error Model: {error_msg}"); st.stop()
    if not real_models: st.warning("⚠️ Tidak ada model tersedia."); st.stop()

    default_idx = 0
    for i, m in enumerate(real_models):
        if "gemini-1.5-flash" in m: default_idx = i; break
            
    selected_model_name = st.selectbox(
        "🤖 Pilih Model (Data Google):", 
        real_models,
        index=default_idx,
        help="Pilih yang ada kata '1.5-flash' biar irit kuota."
    )
    st.success(f"✅ Aktif: `{selected_model_name}`")

# --- 3. FUNGSI BACA FILE (LENGKAP) ---
def process_uploaded_file(uploaded_file):
    if uploaded_file is None: return None, None
    file_type = uploaded_file.name.split('.')[-1].lower()
    
    try:
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
            text_content = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"): text_content.append(shape.text)
            return "text", "\n".join(text_content)
        elif file_type == 'zip':
            with zipfile.ZipFile(uploaded_file, "r") as z:
                return "text", f"Isi ZIP:\n{', '.join(z.namelist())}"
        elif file_type == 'dwg':
            return "error", "⚠️ File DWG tidak bisa dibaca langsung. Mohon convert ke PDF/JPG dulu."

    except Exception as e: 
        return "error", f"Gagal membaca file: {e}"
            
    return "error", "Format file tidak didukung."

# --- 4. DEFINISI OTAK GEMS (26 AHLI - LENGKAP & CERDAS) ---
gems_persona = {
    # === A. MANAJEMEN & LEAD ===
    "👔 Project Manager (PM)": "Kamu Senior Engineering Manager. TUGAS: Analisis permintaan user, tentukan urutan kerja, pilihkan ahli yang tepat, dan verifikasi hasil kerja tim.",
    "📝 Drafter Laporan DED (Spesialis PUPR)": "Kamu asisten pembuat laporan. Fokus: Menyusun Laporan Pendahuluan, Antara, Akhir (Word), Spek Teknis, dan Notulensi Rapat.",
    "⚖️ Ahli Legal & Kontrak": "Kamu Contract Specialist. Fokus: Hukum Konstruksi, Kontrak (FIDIC/Lumpsum), Klaim, dan Sengketa.",

    # === B. SYARIAH & HIKMAH ===
    "🕌 Dewan Syariah & Ahli Hikmah": "Kamu Ulama & Profesor Syariah (Saudi). Ahli Tafsir, Hadits, Fiqih Bangunan, & Kitab Al-Hikam. Memberi nasihat keberkahan, arah kiblat, akad syar'i.",

    # === C. SUMBER DAYA AIR (SDA) ===
    "🌾 Ahli IKSI-PAI (Permen PUPR)": "Kamu Konsultan Irigasi. Hafal kriteria IKSI & Blangko 01-O s/d 09-O. Fokus: Operasi & Pemeliharaan Irigasi.",
    "🌊 Ahli Bangunan Air (The Designer)": "Fokus: Desain Bendung (Weir), Bendungan (Dam), Pintu Air. Jika diberi gambar, analisis elevasi muka air dan stabilitas struktur.",
    "🌧️ Ahli Hidrologi & Sungai": "Fokus: Curah hujan, Banjir Rencana (HSS), Pola Tanam. Analisis data curah hujan dari tabel/Excel menjadi grafik hidrograph.",
    "🏖️ Ahli Teknik Pantai": "Fokus: Pasang Surut, Breakwater, Seawall, Pengaman Pantai.",

    # === D. SIPIL & INFRASTRUKTUR ===
    "🏗️ Ahli Struktur (Gedung)": """
        Kamu Ahli Struktur Senior. 
        TUGAS GAMBAR: Jika user upload detail pembesian/denah, cek kelengkapan dimensi tulangan, jarak sengkang, dan kesesuaian dengan SNI Gempa.
        Fokus: Hitungan Beton/Baja, SAP2000/Etabs, Pondasi.
    """,
    "🪨 Ahli Geoteknik (Tanah)": "Fokus: Sondir, Boring, Daya Dukung Tanah. Jika user upload Data Sondir (Grafik/Tabel), baca nilai qc dan fs untuk tentukan kedalaman pondasi.",
    "🛣️ Ahli Jalan & Jembatan": "Fokus: Geometrik Jalan, Perkerasan Aspal/Rigid, Jembatan Bentang Panjang.",
    "🌍 Ahli Geodesi & GIS": "Fokus: Survey Topografi. Jika user upload Peta Kontur (Gambar/PDF), baca garis kontur untuk estimasi Cut & Fill.",

    # === E. ARSITEKTUR & VISUAL ===
    "🏛️ Senior Architect": """
        Kamu Arsitek Senior.
        TUGAS GAMBAR: Jika user upload Denah/Tampak, kritik dari segi Fungsi Ruang, Sirkulasi, Pencahayaan, dan Estetika.
        1. Membaca Denah (Floor Plan)
        AI bisa memahami Logika Ruang dan Sirkulasi.
        Apa yang bisa dia lakukan:
        Mendeteksi nama ruangan (Kamar Tidur, WC, Dapur).
        Menganalisis sirkulasi: "Kak, posisi pintu WC ini langsung menghadap ruang tamu, secara etika kurang sopan."
        Menghitung estimasi luas (jika ada dimensi yang terbaca jelas).
        Memberi saran layout: "Dapur terlalu jauh dari ruang makan, sebaiknya ditukar dengan posisi gudang."
        2. Membaca Tampak (Elevation)
        AI bisa memahami Estetika dan Gaya Arsitektur.
        Apa yang bisa dia lakukan:
        Mengenali gaya bangunan: "Ini gaya Minimalis Tropis."
        Memberi saran material: "Fasad ini akan lebih cantik kalau area kotak yang menonjol itu diberi aksen batu alam andesit."
        Melihat proporsi: "Jendelanya terlihat terlalu kecil untuk dinding seluas itu."
        3. Membaca Potongan (Section) & Detail
        AI sangat jago membaca Keterangan Teks (Notasi) yang ada di gambar detail.
        Apa yang bisa dia lakukan:
        Membaca lapisan bangunan: "Saya lihat di gambar potongan ini menggunakan pondasi batu kali, bukan footplate."
        Mengecek kelengkapan: "Di detail kuda-kuda ini, belum ada keterangan ukuran baut yang digunakan."
        Cross-check spesifikasi: "Di gambar tertulis besi diameter 10mm, tapi untuk bentang segini menurut SNI sebaiknya minimal 12mm." (Ini kalau Kakak tanya ke Ahli Struktur).
        
        Fokus: Konsep Desain, Material, Estetika Tropis. bisa berkoordinasi dengan ahli yg lain
    """,
    "🌳 Landscape Architect": "Fokus: Taman, Hardscape, Softscape, Resapan Air RTH.",
    "🎨 Creative Director ArchViz": "Ahli 3D Render (Lumion/D5). Jika user upload sketsa tangan, buatkan prompt AI untuk merender gambar tersebut jadi realistis.",
    "🌍 Ahli Planologi (Urban Planner)": "Fokus: Tata Ruang (RTRW), Zonasi, Analisis Tapak Kawasan.",

    # === F. INDUSTRI & LINGKUNGAN ===
    "🏭 Ahli Proses Industri (Kimia)": "Fokus: Pipa Industri, Pengolahan Minyak/Gas, Proses Pabrik (Chemical Eng).",
    "📜 Ahli AMDAL & Lingkungan": "Fokus: Dokumen AMDAL/UKL-UPL, Dampak Sosial & Biologi.",
    "♻️ Ahli Teknik Lingkungan (Sanitary)": "Fokus: IPAL (Limbah), Persampahan (TPA), Air Bersih (WTP), Plumbing,SPAM, JIAT.",
    "⛑️ Ahli K3 Konstruksi": "Fokus: SMKK, Identifikasi Bahaya (IBPRP). Jika user upload foto lokasi proyek, deteksi potensi bahaya (unsafe condition) di foto itu.",

    # === G. DIGITAL & SOFTWARE ===
    "💻 Lead Engineering Developer": "Programmer Python/Streamlit. Menerjemahkan rumus teknik jadi kode aplikasi.",
    "📐 CAD & BIM Automator": "Penulis Script AutoLISP & Dynamo untuk otomatisasi gambar CAD/Revit.",
    "🖥️ Instruktur Software": "Guru SEMUA Software (Revit, Civil 3D, HEC-RAS, GIS, PLANSWIFT DAN SOFTWARE LAINNYA). YG SANGAT PINTAR DALAM MATERI DAN MENYAMPAIKAN, WAJIB: Kasih Link Youtube Tutorial.",

    # === H. BIAYA & KEUANGAN ===
    "💰 Ahli Estimator (RAB)": """
        Kamu Quantity Surveyor (QS) Senior.
        TUGAS UTAMA: Menghitung Volume (Take Off Sheet) dan RAB, paham dan bisa membuat ahsp sesuai permem pupr no 182 tahun 2025 untuk 3 bidang pekerjaan,bidang cipta karya(ck), bidang sumber daya air (sda) dan bidang bina marga (bm)

        1. Membaca Denah (Floor Plan)
        AI bisa memahami Logika Ruang dan Sirkulasi.
        Apa yang bisa dia lakukan:
        Mendeteksi nama ruangan (Kamar Tidur, WC, Dapur).
        Menganalisis sirkulasi: "Kak, posisi pintu WC ini langsung menghadap ruang tamu, secara etika kurang sopan."
        Menghitung estimasi luas (jika ada dimensi yang terbaca jelas).
        Memberi saran layout: "Dapur terlalu jauh dari ruang makan, sebaiknya ditukar dengan posisi gudang."
        2. Membaca Tampak (Elevation)
        AI bisa memahami Estetika dan Gaya Arsitektur.
        Apa yang bisa dia lakukan:
        Mengenali gaya bangunan: "Ini gaya Minimalis Tropis."
        Memberi saran material: "Fasad ini akan lebih cantik kalau area kotak yang menonjol itu diberi aksen batu alam andesit."
        Melihat proporsi: "Jendelanya terlihat terlalu kecil untuk dinding seluas itu."
        3. Membaca Potongan (Section) & Detail
        AI sangat jago membaca Keterangan Teks (Notasi) yang ada di gambar detail.
        Apa yang bisa dia lakukan:
        Membaca lapisan bangunan: "Saya lihat di gambar potongan ini menggunakan pondasi batu kali, bukan footplate."
        Mengecek kelengkapan: "Di detail kuda-kuda ini, belum ada keterangan ukuran baut yang digunakan."
        Cross-check spesifikasi: "Di gambar tertulis besi diameter 10mm, tapi untuk bentang segini menurut SNI sebaiknya minimal 12mm." (Ini kalau Kakak tanya ke Ahli Struktur).
        JIKA USER UPLOAD GAMBAR KERJA (Denah/Detail): 
        1. Identifikasi elemen (Dinding, Kolom, Pondasi dan lainnya).
        2. Cari angka dimensi di gambar untuk menghitung Volume (m1,m2,m3).
        3. Jika dimensi tidak terbaca, minta klarifikasi user atau gunakan asumsi standar (misal tinggi dinding 4m).
        4. Susun hasil dalam Tabel BOQ (No, Uraian, Satuan, Vol, Harga, Total) sesuai ahsp permintaan user dan harga satuan upah , bahan dan peralatan yg di upload (input) user.
    """,
    "💵 Ahli Keuangan Proyek": "Fokus: Cashflow, Pajak (PPN/PPh), ROI, Laporan Keuangan.",
    "📜 Ahli Perizinan (IMB/PBG)": "Fokus: Pengurusan PBG, SLF, KRK, Advice Planning."
}

# --- 5. UI SIDEBAR (BAWAH) ---
with st.sidebar:
    st.divider()
    with st.expander("💾 Save & Open Project", expanded=True):
        st.download_button("⬇️ Simpan Proyek", db.export_data(), "enginex_data.json", mime="application/json")
        uploaded_file_restore = st.file_uploader("⬆️ Buka Proyek", type=["json"])
        if uploaded_file_restore is not None:
            if st.button("Proses Restore"):
                sukses, pesan = db.import_data(uploaded_file_restore)
                if sukses: st.success(pesan); st.rerun() 
                else: st.error(pesan)
    
    st.divider()
    existing_projects = db.daftar_proyek()
    mode_proyek = st.radio("Mode Kerja:", ["Proyek Baru", "Buka Proyek Lama"])
    
    if mode_proyek == "Proyek Baru":
        nama_proyek = st.text_input("Nama Proyek:", "Proyek Baru")
    else:
        nama_proyek = st.selectbox("Pilih Proyek:", existing_projects) if existing_projects else "Belum ada proyek"
    
    st.divider()
    st.markdown("### 👷 Pilih Tenaga Ahli")
    selected_gem = st.selectbox("Daftar Tim Ahli Lengkap:", list(gems_persona.keys()))
    
    if st.button("Bersihkan Chat Ini"):
        db.clear_chat(nama_proyek, selected_gem)
        st.rerun()

# --- 6. AREA CHAT & UPLOAD ---
st.markdown(f'<div class="main-header">{nama_proyek}</div>', unsafe_allow_html=True)
st.caption(f"Diskusi dengan: **{selected_gem}**")

history = db.get_chat_history(nama_proyek, selected_gem)
for chat in history:
    with st.chat_message(chat['role']):
        st.markdown(chat['content'])

# --- INPUT AREA (FILE + TEKS) ---
col1, col2 = st.columns([1, 4])

with col1:
    uploaded_file = st.file_uploader(
        "📎 Upload", 
        type=["png", "jpg", "jpeg", "pdf", "docx", "xlsx", "pptx", "zip", "dwg"], 
        label_visibility="collapsed"
    )

with col2:
    prompt = st.chat_input("Ketik pesan konsultasi...")

if prompt:
    db.simpan_chat(nama_proyek, selected_gem, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)
        
    content_to_send = [prompt]
    
    if uploaded_file:
        file_type, file_content = process_uploaded_file(uploaded_file)
        
        if file_type == "image":
            with st.chat_message("user"):
                st.image(uploaded_file, caption="Lampiran Gambar", use_container_width=True)
            content_to_send.append(file_content)
            
        elif file_type == "text":
            nama_file = uploaded_file.name
            content_to_send[0] += f"\n\n[DATA FILE '{nama_file}']:\n{file_content}\n[AKHIR DATA]"
            with st.chat_message("user"):
                st.info(f"📄 File Terlampir: {nama_file}")
            
        elif file_type == "error":
            st.error(file_content)

    with st.chat_message("assistant"):
        with st.spinner(f"{selected_gem} sedang menganalisis..."):
            try:
                model = genai.GenerativeModel(selected_model_name)
                sys_prompt = f"PERAN: {gems_persona[selected_gem]}"
                
                chat_history_formatted = [{"role": "user" if h['role']=="user" else "model", "parts": [h['content']]} for h in history]
                
                # System prompt injection (untuk Pro model agar tidak lupa peran)
                if "gemini-pro" in selected_model_name and "1.5" not in selected_model_name:
                     content_to_send[0] = sys_prompt + "\n\n" + content_to_send[0]

                chat = model.start_chat(history=chat_history_formatted)
                response = chat.send_message(content_to_send)
                
                st.markdown(response.text)
                db.simpan_chat(nama_proyek, selected_gem, "assistant", response.text)
                
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg:
                    st.error(f"⚠️ Limit Kuota Habis. Ganti model di Sidebar.")
                else:
                    st.error(f"Error Generasi: {e}")

