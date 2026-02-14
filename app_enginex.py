import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from PIL import Image
import PyPDF2
import io
import docx
import zipfile
from pptx import Presentation
import re
import time

# --- IMPORT MODUL INTERNAL (Pastikan file ini ada di satu folder) ---
try:
    from backend_enginex import EnginexBackend
    from persona import gems_persona, get_persona_list, get_system_instruction
    from export_enginex import EnginexExporter
    from streamlit_folium import st_folium
except ImportError as e:
    st.error(f"❌ CRITICAL ERROR: File modul pendukung tidak ditemukan! \nDetail: {e}")
    st.stop()

# ==========================================
# 1. KONFIGURASI HALAMAN & CSS
# ==========================================
st.set_page_config(
    page_title="ENGINEX Ultimate: AI Consultant",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Custom untuk Tampilan Profesional "Gagah"
st.markdown("""
<style>
    /* Main Header */
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        color: #0F172A; /* Slate 900 */
        margin-bottom: 0.5rem;
        border-bottom: 4px solid #3B82F6; /* Blue 500 */
        padding-bottom: 10px;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #F8FAFC;
        border-right: 1px solid #E2E8F0;
    }
    
    /* Chat Message Bubbles */
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
    
    /* Tombol Download Custom */
    div.stDownloadButton > button {
        width: 100%;
        background-color: #EFF6FF;
        color: #1D4ED8;
        border: 1px solid #BFDBFE;
        font-weight: 600;
        border-radius: 8px;
    }
    div.stDownloadButton > button:hover {
        background-color: #DBEAFE;
        border-color: #3B82F6;
    }
    
    /* Auto Pilot Banner */
    .auto-pilot-box {
        background-color: #ECFDF5;
        border-left: 5px solid #10B981;
        padding: 15px;
        border-radius: 5px;
        color: #064E3B;
        font-weight: bold;
        margin-bottom: 15px;
    }

    /* Plot Container */
    .plot-container {
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 10px;
        background: white;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. INISIALISASI SESSION STATE
# ==========================================
if 'processed_files' not in st.session_state:
    st.session_state.processed_files = set()

if 'current_expert_active' not in st.session_state:
    st.session_state.current_expert_active = "👑 The GEMS Grandmaster"

if 'backend' not in st.session_state:
    st.session_state.backend = EnginexBackend()  # Inisialisasi Database

db = st.session_state.backend  # Shortcut variable

# ==========================================
# 3. FUNGSI UTILITAS & VISUALISASI
# ==========================================

def execute_generated_code(code_str):
    """
    [SAFE SANDBOX] Mengeksekusi kode Python untuk plotting grafik.
    Menggunakan exec() dengan batasan variabel lokal.
    """
    try:
        # Siapkan environment variabel
        local_vars = {
            "pd": pd,
            "np": np,
            "plt": plt,
            "st": st
        }
        
        # Bersihkan plot sebelumnya
        plt.clf()
        
        # Eksekusi kode
        exec(code_str, {}, local_vars)
        return True
    except Exception as e:
        st.error(f"⚠️ Gagal Render Grafik: {str(e)}")
        return False

def extract_dataframe_from_markdown(text):
    """
    Mencoba mengekstrak tabel markdown menjadi Pandas DataFrame
    untuk keperluan ekspor Excel.
    """
    try:
        lines = text.split('\n')
        data = []
        headers = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('|') and line.endswith('|'):
                # Cek apakah ini baris pemisah (---|---|---)
                if '---' in line:
                    continue
                
                # Bersihkan cell
                cells = [c.strip() for c in line.split('|')[1:-1]]
                
                if not headers:
                    headers = cells
                else:
                    data.append(cells)
                    
        if headers and data:
            return pd.DataFrame(data, columns=headers)
        return None
    except:
        return None

def process_uploaded_file(uploaded_file):
    """
    Membaca berbagai jenis file yang diupload user.
    Mendukung: Dokumen Office, Gambar, PDF, dan Geospasial.
    """
    if uploaded_file is None: return None, None
    
    file_type = uploaded_file.name.split('.')[-1].lower()
    
    try:
        # --- IMAGE ---
        if file_type in ['png', 'jpg', 'jpeg']:
            return "image", Image.open(uploaded_file)
            
        # --- PDF ---
        elif file_type == 'pdf':
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            text = ""
            for page in pdf_reader.pages:
                extracted = page.extract_text()
                if extracted: text += extracted + "\n"
            return "text", text
            
        # --- WORD (.DOCX) ---
        elif file_type == 'docx':
            doc = docx.Document(uploaded_file)
            text = "\n".join([para.text for para in doc.paragraphs])
            return "text", text
            
        # --- EXCEL (.XLSX) ---
        elif file_type in ['xlsx', 'xls']:
            df = pd.read_excel(uploaded_file)
            # Batasi preview agar token tidak meledak
            return "text", f"[PREVIEW DATA EXCEL - 50 Baris Pertama]\n{df.head(50).to_string()}"
            
        # --- POWERPOINT (.PPTX) ---
        elif file_type == 'pptx':
            prs = Presentation(uploaded_file)
            text = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text.append(shape.text)
            return "text", "\n".join(text)
            
        # --- PYTHON CODE (.PY) ---
        elif file_type == 'py':
            return "text", uploaded_file.getvalue().decode("utf-8")
            
        # --- GEOSPATIAL (GEOJSON/KML/KMZ) ---
        elif file_type in ['geojson', 'kml', 'gpx']:
            return "geo", uploaded_file.getvalue().decode("utf-8")
            
        elif file_type == 'kmz':
            with zipfile.ZipFile(uploaded_file, "r") as z:
                kml_filename = [n for n in z.namelist() if n.endswith(".kml")][0]
                with z.open(kml_filename) as f:
                    return "geo", f.read().decode("utf-8")
                    
        else:
            return "error", "Format file tidak didukung."
            
    except Exception as e:
        return "error", f"Gagal membaca file: {str(e)}"

# ==========================================
# 4. SIDEBAR CONTROLS
# ==========================================
with st.sidebar:
    st.title("🏗️ ENGINEX ULTIMATE")
    st.caption("v11.0 | Integrated Engineering AI")
    st.markdown("---")
    
    # --- API KEY ---
    api_key_input = st.text_input("🔑 Google API Key:", type="password", help="Wajib diisi untuk akses AI")
    
    # Prioritas: Input Manual > Secrets
    if api_key_input:
        clean_api_key = api_key_input.strip()
    else:
        clean_api_key = st.secrets.get("GOOGLE_API_KEY", "")
        
    if not clean_api_key:
        st.warning("⚠️ Masukkan API Key untuk memulai.")
        st.stop()
        
    # Konfigurasi Gemini
    try:
        genai.configure(api_key=clean_api_key)
    except Exception as e:
        st.error(f"API Error: {e}")
        st.stop()

    # --- MODEL SELECTION ---
    # Mendapatkan list model yang tersedia
    try:
        model_list = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model_list.append(m.name)
        # Urutkan agar versi 'Pro' atau terbaru di atas
        model_list.sort(key=lambda x: 'gemini-1.5' in x, reverse=True)
    except:
        model_list = ["models/gemini-1.5-flash", "models/gemini-pro"]

    selected_model_name = st.selectbox("🧠 Model Otak:", model_list, index=0)
    
    use_auto_pilot = st.checkbox("🤖 Mode Auto-Pilot", value=True, help="AI otomatis memilih ahli yang tepat sesuai pertanyaan.")
    
    st.markdown("---")

    # --- PROJECT MANAGEMENT ---
    with st.expander("📁 Manajemen Proyek", expanded=True):
        existing_projects = db.daftar_proyek()
        mode_proyek = st.radio("Mode:", ["Buka Proyek Lama", "Buat Proyek Baru"])
        
        if mode_proyek == "Buat Proyek Baru":
            nama_proyek = st.text_input("Nama Proyek:", "DED Bendungan 2026")
        else:
            if existing_projects:
                nama_proyek = st.selectbox("Pilih Proyek:", existing_projects)
            else:
                st.warning("Belum ada proyek tersimpan.")
                nama_proyek = "Proyek Tanpa Nama"
                
    # --- EXPERT SELECTION ---
    st.markdown("### 👷 Tenaga Ahli")
    manual_expert = st.selectbox(
        "Pilih Manual:", 
        get_persona_list(), 
        disabled=use_auto_pilot,
        index=0
    )
    
    # --- FILE UPLOAD ---
    st.markdown("### 📎 Lampiran Data")
    uploaded_files = st.file_uploader(
        "Upload File (PDF, Excel, Docx, GeoJSON, DWG):", 
        accept_multiple_files=True
    )
    
    # --- RESET BUTTON ---
    st.markdown("---")
    col_res1, col_res2 = st.columns(2)
    with col_res1:
        if st.button("🧹 Hapus Chat"):
            db.clear_chat(nama_proyek, st.session_state.current_expert_active)
            st.rerun()
    with col_res2:
        if st.button("🔄 Refresh"):
            st.rerun()

# ==========================================
# 5. AUTO-ROUTER FUNCTION (AI LOGIC)
# ==========================================
def get_auto_pilot_decision(query):
    """
    Menggunakan model cepat (Flash) untuk menentukan siapa ahli yang cocok
    menjawab pertanyaan user.
    """
    try:
        # Gunakan model ringan untuk routing agar cepat
        router = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = f"""
        Tugas: Pilih SATU nama ahli dari daftar di bawah yang paling relevan untuk menjawab: "{query}"
        
        Daftar Ahli:
        {list(gems_persona.keys())}
        
        Output: HANYA tulis nama ahlinya saja persis. Jika pertanyaan umum/tidak jelas, pilih '👑 The GEMS Grandmaster'.
        """
        
        resp = router.generate_content(prompt)
        decision = resp.text.strip()
        
        # Validasi apakah output ada di daftar persona
        if decision in gems_persona:
            return decision
        return "👑 The GEMS Grandmaster"
    except:
        # Fallback jika error
        return "👑 The GEMS Grandmaster"

# ==========================================
# 6. HALAMAN UTAMA (MAIN INTERFACE)
# ==========================================

# Judul Proyek
st.markdown(f'<div class="main-header">{nama_proyek}</div>', unsafe_allow_html=True)

# Tentukan Expert Aktif
if use_auto_pilot:
    active_expert = st.session_state.current_expert_active
else:
    active_expert = manual_expert
    st.session_state.current_expert_active = manual_expert

st.caption(f"🟢 Status: Online | Ahli Aktif: **{active_expert}**")

# --- RENDER CHAT HISTORY ---
history_data = db.get_chat_history(nama_proyek, active_expert)

for chat in history_data:
    with st.chat_message(chat['role']):
        # Render Text
        st.markdown(chat['content'])
        
        # Cek apakah ada kode plot di history assistant
        if chat['role'] == 'assistant' and "```python" in chat['content']:
            code_match = re.search(r"```python(.*?)```", chat['content'], re.DOTALL)
            if code_match and ("plt." in code_match.group(1) or "matplotlib" in code_match.group(1)):
                with st.expander("📊 Lihat Grafik Tersimpan"):
                    execute_generated_code(code_match.group(1))
                    st.pyplot(plt.gcf())

# --- INPUT USER ---
user_input = st.chat_input(f"Konsultasi dengan {active_expert}...")

if user_input:
    # 1. Tentukan Siapa yang Menjawab (Routing)
    target_expert = active_expert
    
    if use_auto_pilot:
        with st.status("🔄 Menganalisis konteks pertanyaan...", expanded=True) as status:
            target_expert = get_auto_pilot_decision(user_input)
            st.session_state.current_expert_active = target_expert
            status.update(label=f"✅ Dialihkan ke: {target_expert}", state="complete", expanded=False)
            
        # Tampilkan notifikasi peralihan jika berubah
        if target_expert != active_expert:
            st.markdown(f'<div class="auto-pilot-box">🤖 Auto-Pilot mengaktifkan modul: {target_expert}</div>', unsafe_allow_html=True)
            active_expert = target_expert # Update variabel lokal

    # 2. Simpan & Tampilkan Pesan User
    db.simpan_chat(nama_proyek, active_expert, "user", user_input)
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # 3. Proses Lampiran (Files)
    content_payload = [user_input] # List konten untuk dikirim ke Gemini
    
    # Cek file upload baru
    geo_content_detected = None
    geo_type_detected = None
    
    if uploaded_files:
        for f in uploaded_files:
            # Hindari memproses file yang sama berulang kali dalam satu sesi (hemat token)
            if f.name not in st.session_state.processed_files:
                ftype, fcontent = process_uploaded_file(f)
                
                if ftype == "image":
                    with st.chat_message("user"):
                        st.image(f, width=300, caption=f.name)
                    content_payload.append(fcontent) # Image object
                    
                elif ftype == "text":
                    with st.chat_message("user"):
                        st.caption(f"📄 Membaca dokumen: {f.name}")
                    content_payload.append(f"\n\n--- KONTEKS TAMBAHAN DARI FILE {f.name} ---\n{fcontent}\n--- END FILE ---\n")
                
                elif ftype == "geo":
                    with st.chat_message("user"):
                        st.caption(f"🌍 Memuat data spasial: {f.name}")
                        # Render Peta Langsung
                        m = EnginexExporter.render_geospatial_map(fcontent, f.name.split('.')[-1])
                        if m:
                            st_folium(m, width=700, height=400, key=f"map_{f.name}")
                    
                    # Simpan konten geo untuk dikirim ke AI sebagai teks referensi
                    content_payload.append(f"\n\n--- DATA GEOSPASIAL ({f.name}) ---\n{fcontent[:5000]}... (Data dipotong)\n")
                    
                elif ftype == "error":
                    st.error(f"Error pada file {f.name}: {fcontent}")
                
                # Tandai file sudah diproses
                st.session_state.processed_files.add(f.name)

    # 4. Generate AI Response
    with st.chat_message("assistant"):
        with st.spinner(f"{active_expert.split(' ')[-1]} sedang menyusun analisis..."):
            try:
                # Ambil System Instruction sesuai Persona
                base_instruction = get_system_instruction(active_expert)
                
                # Tambahkan Instruksi Plotting Khusus untuk Level 3 Agent
                # Cek apakah agent ini tipe 'Engineer' atau 'Drafter'
                is_text_only = any(x in active_expert for x in ["Legal", "Syariah", "Admin", "Perizinan"])
                
                final_instruction = base_instruction
                if not is_text_only:
                    # Inject aturan plotting jika dia engineer
                    final_instruction += """
                    \n[PERINTAH TAMBAHAN - VISUALISASI]:
                    Jika user meminta grafik/kurva, WAJIB generate kode Python (matplotlib).
                    Selalu akhiri kode dengan 'st.pyplot(plt.gcf())'.
                    Gunakan style 'ggplot'.
                    """

                # Init Model
                model = genai.GenerativeModel(
                    model_name=selected_model_name,
                    system_instruction=final_instruction,
                    safety_settings={
                        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    }
                )

                # Build History untuk Konteks Percakapan
                chat_history_objs = []
                previous_chats = db.get_chat_history(nama_proyek, active_expert)
                
                # Ambil 10 percakapan terakhir saja agar token tidak penuh
                for h in previous_chats[-10:]:
                    if h['content'] != user_input: # Hindari duplikasi prompt terakhir
                        role_str = "user" if h['role'] == "user" else "model"
                        chat_history_objs.append({"role": role_str, "parts": [h['content']]})

                # Kirim ke AI
                chat_session = model.start_chat(history=chat_history_objs)
                response_stream = chat_session.send_message(content_payload, stream=True)
                
                # Stream Output
                full_response = ""
                response_placeholder = st.empty()
                
                for chunk in response_stream:
                    if chunk.text:
                        full_response += chunk.text
                        response_placeholder.markdown(full_response + "▌")
                
                response_placeholder.markdown(full_response)
                
                # Simpan ke DB
                db.simpan_chat(nama_proyek, active_expert, "assistant", full_response)
                
                # 5. POST-PROCESSING (Code Execution & Plotting)
                # Cari blok kode python
                code_blocks = re.findall(r"```python(.*?)```", full_response, re.DOTALL)
                
                for code in code_blocks:
                    if "plt." in code or "matplotlib" in code:
                        st.markdown("### 📉 Analisis Grafis Engineering")
                        with st.container(): # Container khusus plot
                            success = execute_generated_code(code)
                            if success:
                                st.pyplot(plt.gcf())
                                plt.clf() # Bersihkan memori plot
                            else:
                                st.warning("Gagal merender grafik.")

                # 6. EXPORT CENTER (Tombol Download)
                st.markdown("---")
                st.markdown("### 📥 Download Laporan Kerja")
                
                # Siapkan kolom tombol
                col1, col2, col3, col4 = st.columns(4)
                
                # A. Export Word
                docx_file = EnginexExporter.create_pupr_word(full_response, nama_proyek)
                col1.download_button(
                    label="📄 Laporan Word",
                    data=docx_file,
                    file_name=f"{nama_proyek}_{active_expert[:10]}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
                
                # B. Export Excel (Jika ada tabel)
                df_table = extract_dataframe_from_markdown(full_response)
                if df_table is not None:
                    xlsx_file = EnginexExporter.create_pupr_excel(df_table)
                    col2.download_button(
                        label="📊 Data Excel",
                        data=xlsx_file,
                        file_name=f"Data_{active_expert[:5]}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    col2.button("📊 Data Excel", disabled=True, help="Tidak ada tabel terdeteksi di output.")

                # C. Export PPT
                ppt_file = EnginexExporter.create_pupr_pptx(full_response, nama_proyek)
                col3.download_button(
                    label="📢 Slide Presentasi",
                    data=ppt_file,
                    file_name=f"Presentasi_{nama_proyek}.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                )
                
                # D. Export Civil 3D CSV (Jika ada data koordinat)
                # Cek sederhana apakah ada data koordinat (P, N, E, Z) di dataframe
                if df_table is not None and 'x' in df_table.columns.str.lower():
                    csv_data = EnginexExporter.export_to_civil3d_csv(df_table)
                    col4.download_button(
                        label="🏗️ Civil 3D Points",
                        data=csv_data,
                        file_name="Survey_Points.csv",
                        mime="text/csv"
                    )
                else:
                    col4.button("🏗️ Civil 3D CSV", disabled=True, help="Tidak ada data koordinat (X, Y, Z).")
                    
            except Exception as e:
                st.error(f"❌ Terjadi Kesalahan Sistem: {str(e)}")
                st.info("Tips: Coba refresh halaman atau kurangi jumlah file yang diupload.")

# Footer
st.markdown("---")
st.caption("© 2026 ENGINEX Ultimate System | Powered by Gemini 1.5 Pro & Flash")
