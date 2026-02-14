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
from docx.shared import Inches, Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
import zipfile
from pptx import Presentation
import re
import time

# ==========================================
# 0. MODUL PENDUKUNG & BACKEND
# ==========================================
# Pastikan file backend_enginex.py dan persona.py ada di folder yang sama
try:
    from backend_enginex import EnginexBackend
    from persona import gems_persona, get_persona_list, get_system_instruction
    from streamlit_folium import st_folium
    import folium
except ImportError as e:
    st.error(f"❌ CRITICAL ERROR: File modul pendukung tidak ditemukan! \nDetail: {e}")
    st.warning("Pastikan file: 'backend_enginex.py' dan 'persona.py' sudah diupload.")
    st.stop()

# ==========================================
# 1. ADVANCED REPORT GENERATOR (PU-PR STANDARD)
# ==========================================
class ProReportGenerator:
    """
    Kelas khusus untuk menghasilkan laporan Word Standar PU-PR
    yang menggabungkan Teks, Tabel, dan Grafik secara rapi.
    """
    @staticmethod
    def create_full_report(project_name, expert_name, text_content, visual_assets):
        """
        visual_assets: list of dict {'type': 'plot'/'image', 'data': BytesIO/ImageObject, 'caption': str}
        """
        doc = docx.Document()
        
        # --- 1. SETUP HALAMAN (A4, Margin Standar Dinas) ---
        section = doc.sections[0]
        section.page_height = Cm(29.7)
        section.page_width = Cm(21.0)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)

        # --- 2. STYLE FONT (Arial/Times New Roman 11pt) ---
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Arial'
        font.size = Pt(11)

        # --- 3. HEADER KOP SURAT (SIMULASI) ---
        header = section.header
        htable = header.add_table(1, 2, width=Inches(6))
        htable.autofit = False
        htable.columns[0].width = Inches(1.5)
        htable.columns[1].width = Inches(4.5)
        
        # Logo/Nama Perusahaan
        cell_logo = htable.cell(0, 0)
        cell_logo.text = "ENGINEX\nCONSULTANT"
        
        # Info Proyek
        cell_info = htable.cell(0, 1)
        p_head = cell_info.paragraphs[0]
        p_head.text = f"PROYEK: {project_name}\nDOKUMEN: LAPORAN ANALISIS TEKNIS"
        p_head.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        # --- 4. JUDUL LAPORAN ---
        doc.add_paragraph("\n")
        title = doc.add_heading(f"LAPORAN ANALISIS: {project_name.upper()}", 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        sub = doc.add_paragraph(f"Disusun Oleh Ahli: {expert_name}")
        sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sub.runs[0].italic = True
        doc.add_paragraph("\n")

        # --- 5. PARSING KONTEN TEKS ---
        # Membersihkan markdown sederhana menjadi format Word
        lines = text_content.split('\n')
        for line in lines:
            line = line.strip()
            if not line: continue
            
            if line.startswith('### '):
                doc.add_heading(line.replace('### ', ''), level=3)
            elif line.startswith('## '):
                doc.add_heading(line.replace('## ', ''), level=2)
            elif line.startswith('# '):
                doc.add_heading(line.replace('# ', ''), level=1)
            elif line.startswith('- ') or line.startswith('* '):
                p = doc.add_paragraph(line[2:], style='List Bullet')
            elif line.startswith('1. '):
                p = doc.add_paragraph(line, style='List Number')
            else:
                # Cek jika ini tabel markdown
                if "|" in line and "---" not in line:
                    # (Fitur tabel sederhana bisa ditambahkan jika perlu, 
                    # tapi untuk stabilitas kita taruh sebagai teks monospace dulu atau skip)
                    p = doc.add_paragraph(line)
                elif "---" in line:
                    continue
                else:
                    p = doc.add_paragraph(line)
                    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

        # --- 6. MENYISIPKAN LAMPIRAN VISUAL (GRAFIK & GAMBAR) ---
        if visual_assets:
            doc.add_page_break()
            doc.add_heading("LAMPIRAN A: DATA VISUAL & GRAFIK", level=1)
            doc.add_paragraph("Berikut adalah hasil analisis grafis dan visualisasi pendukung:")
            
            for i, asset in enumerate(visual_assets):
                try:
                    # Judul Gambar
                    doc.add_heading(f"Gambar A.{i+1}: {asset['caption']}", level=3)
                    
                    # Proses Gambar
                    img_data = asset['data']
                    
                    if asset['type'] == 'plot':
                        # Plot sudah dalam BytesIO
                        img_data.seek(0)
                        doc.add_picture(img_data, width=Inches(6))
                        
                    elif asset['type'] == 'image':
                        # Konversi PIL Image ke BytesIO
                        img_byte_arr = io.BytesIO()
                        img_data.save(img_byte_arr, format='PNG')
                        img_byte_arr.seek(0)
                        doc.add_picture(img_byte_arr, width=Inches(6))
                    
                    last_p = doc.paragraphs[-1] 
                    last_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    doc.add_paragraph("\n") # Spasi antar gambar
                    
                except Exception as e:
                    doc.add_paragraph(f"[Gagal memuat gambar: {str(e)}]")

        # --- 7. FOOTER ---
        section = doc.sections[0]
        footer = section.footer
        p_foot = footer.paragraphs[0]
        p_foot.text = "Dokumen ini digenerate otomatis oleh Sistem Cerdas ENGINEX Ultimate."
        p_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Save to buffer
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer

# ==========================================
# 2. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(
    page_title="ENGINEX Ultimate: Pro Consultant",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1E293B;
        border-bottom: 4px solid #2563EB;
        padding-bottom: 10px;
        margin-bottom: 20px;
    }
    .stDownloadButton button {
        width: 100%;
        background-color: #F1F5F9;
        color: #0F172A;
        border: 1px solid #CBD5E1;
        font-weight: 600;
        text-align: left;
        padding-left: 15px;
    }
    .stDownloadButton button:hover {
        background-color: #DBEAFE;
        border-color: #2563EB;
        color: #1D4ED8;
    }
    .plot-box {
        border: 1px solid #E2E8F0;
        padding: 15px;
        border-radius: 8px;
        background: white;
        margin-top: 10px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. SESSION STATE & DATABASE
# ==========================================
if 'processed_files' not in st.session_state:
    st.session_state.processed_files = set()
if 'current_expert_active' not in st.session_state:
    st.session_state.current_expert_active = "👑 The GEMS Grandmaster"
if 'backend' not in st.session_state:
    st.session_state.backend = EnginexBackend()

# --- STATE KHUSUS VISUALISASI ---
# Ini untuk menyimpan grafik/gambar agar bisa didownload di sidebar
if 'generated_visuals' not in st.session_state:
    st.session_state.generated_visuals = [] # List of {'type':, 'data':, 'caption':}
if 'last_analysis_text' not in st.session_state:
    st.session_state.last_analysis_text = ""

db = st.session_state.backend

# ==========================================
# 4. FUNGSI UTILITAS (HELPER)
# ==========================================
def execute_generated_code(code_str):
    """
    Eksekusi kode Python (Matplotlib) dan SIMPAN hasilnya ke memory
    agar bisa dimasukkan ke laporan Word.
    """
    try:
        local_vars = {"pd": pd, "np": np, "plt": plt, "st": st}
        plt.clf() # Bersihkan plot lama
        
        # Eksekusi
        exec(code_str, {}, local_vars)
        
        # Tangkap Figur
        fig = plt.gcf()
        
        # Simpan ke Buffer untuk Report
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        
        # Simpan ke Session State Visuals
        st.session_state.generated_visuals.append({
            'type': 'plot',
            'data': buf,
            'caption': "Grafik Analisis Teknis"
        })
        
        return True
    except Exception as e:
        st.error(f"⚠️ Gagal Render Grafik: {str(e)}")
        return False

def process_uploaded_file(uploaded_file):
    """Membaca berbagai format file."""
    if uploaded_file is None: return None, None
    file_type = uploaded_file.name.split('.')[-1].lower()
    
    try:
        if file_type in ['png', 'jpg', 'jpeg']:
            img = Image.open(uploaded_file)
            return "image", img
        elif file_type == 'pdf':
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            text = ""
            for page in pdf_reader.pages: text += page.extract_text() + "\n"
            return "text", text
        elif file_type == 'docx':
            doc = docx.Document(uploaded_file)
            text = "\n".join([para.text for para in doc.paragraphs])
            return "text", text
        elif file_type in ['xlsx', 'xls']:
            df = pd.read_excel(uploaded_file)
            return "text", f"[PREVIEW EXCEL]\n{df.head(50).to_string()}"
        elif file_type == 'py':
            return "text", uploaded_file.getvalue().decode("utf-8")
        elif file_type in ['geojson', 'kml', 'gpx']:
            return "geo", uploaded_file.getvalue().decode("utf-8")
        else:
            return "error", "Format tidak didukung."
    except Exception as e:
        return "error", str(e)

# ==========================================
# 5. SIDEBAR SETTINGS & DOWNLOAD CENTER
# ==========================================
with st.sidebar:
    st.title("🏗️ ENGINEX ULTIMATE")
    st.caption("v13.0 | Integrated Visual Report")
    st.markdown("---")
    
    # --- API KEY ---
    api_key_input = st.text_input("🔑 Google API Key:", type="password")
    clean_key = api_key_input.strip() if api_key_input else st.secrets.get("GOOGLE_API_KEY", "")
    if not clean_key: st.warning("Masukkan API Key."); st.stop()
    try: genai.configure(api_key=clean_key)
    except: st.error("API Key Invalid."); st.stop()

    # --- MODEL SELECTOR ---
    future_models = [
        "models/gemini-2.5-flash-lite", "models/gemini-2.5-flash-image",
        "models/gemini-1.5-pro", "models/gemini-1.5-flash"
    ]
    selected_model = st.selectbox("🧠 Model AI:", future_models, index=2)
    
    # --- PROJECT MANAGER ---
    with st.expander("📁 Proyek & Ahli", expanded=False):
        projects = db.daftar_proyek()
        mode = st.radio("Mode:", ["Buka Lama", "Buat Baru"])
        nama_proyek = st.text_input("Nama Proyek:", "DED Bendungan 2026") if mode == "Buat Baru" else st.selectbox("Pilih:", projects if projects else ["Baru"])
        
        st.markdown("---")
        auto_pilot = st.checkbox("🤖 Auto-Pilot", value=True)
        manual_expert = st.selectbox("Ahli:", get_persona_list(), disabled=auto_pilot)

    # --- UPLOAD ---
    st.markdown("### 📎 Upload Data")
    uploaded_files = st.file_uploader("", accept_multiple_files=True)
    
    if st.button("🧹 Reset Sesi"):
        db.clear_chat(nama_proyek, st.session_state.current_expert_active)
        st.session_state.generated_visuals = [] # Clear visuals
        st.session_state.last_analysis_text = ""
        st.rerun()

    st.markdown("---")
    
    # ==========================================
    # 🌟 NEW: SIDEBAR DOWNLOAD CENTER
    # ==========================================
    st.header("📥 Download Center")
    st.caption("Unduh laporan lengkap dengan grafik.")
    
    dl_container = st.container()
    
    if st.session_state.last_analysis_text:
        with dl_container:
            # 1. GENERATE WORD REPORT (TEKS + GAMBAR)
            docx_buffer = ProReportGenerator.create_full_report(
                nama_proyek, 
                st.session_state.current_expert_active, 
                st.session_state.last_analysis_text,
                st.session_state.generated_visuals
            )
            
            st.download_button(
                label="📄 Laporan Resmi (.docx)\n(Teks + Grafik Terlampir)", 
                data=docx_buffer, 
                file_name=f"{nama_proyek}_Full_Report.docx", 
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
            # 2. DOWNLOAD GRAFIK/GAMBAR SAJA (ZIP)
            if st.session_state.generated_visuals:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for i, vis in enumerate(st.session_state.generated_visuals):
                        ext = "png"
                        data = vis['data']
                        data.seek(0)
                        zf.writestr(f"Gambar_{i+1}.{ext}", data.read())
                
                zip_buffer.seek(0)
                st.download_button(
                    label="🖼️ Galeri Visual (.zip)\n(Hanya Gambar & Grafik)", 
                    data=zip_buffer, 
                    file_name=f"{nama_proyek}_Visuals.zip", 
                    mime="application/zip"
                )
            else:
                st.info("ℹ️ Belum ada grafik/gambar yang digenerate.")
    else:
        st.info("Belum ada analisis untuk didownload.")

# ==========================================
# 6. MAIN CHAT LOGIC
# ==========================================
st.markdown(f'<div class="main-header">{nama_proyek}</div>', unsafe_allow_html=True)

# Ahli Aktif
if auto_pilot:
    active_expert = st.session_state.current_expert_active
else:
    active_expert = manual_expert
    st.session_state.current_expert_active = manual_expert

st.caption(f"Status: **Online** | Ahli: **{active_expert}**")

# --- HISTORY ---
history = db.get_chat_history(nama_proyek, active_expert)
for chat in history:
    with st.chat_message(chat['role']):
        st.markdown(chat['content'])
        # Re-render plot if exists in history (Visual only, not saving to report again to avoid dupes)
        if chat['role'] == 'assistant' and "```python" in chat['content']:
            code_match = re.search(r"```python(.*?)```", chat['content'], re.DOTALL)
            if code_match and "plt." in code_match.group(1):
                with st.expander("📊 Lihat Grafik (Arsip)"):
                    try:
                        exec(code_match.group(1), {"pd":pd, "np":np, "plt":plt, "st":st})
                        st.pyplot(plt.gcf())
                        plt.clf()
                    except: pass

# --- INPUT ---
user_input = st.chat_input(f"Konsultasi dengan {active_expert}...")

if user_input:
    # 1. Routing
    target_expert = active_expert
    if auto_pilot:
        try:
            router = genai.GenerativeModel("models/gemini-1.5-flash")
            resp = router.generate_content(f"Pilih SATU ahli dari {list(gems_persona.keys())} untuk: '{user_input}'. Output Nama Saja.")
            if resp.text.strip() in gems_persona:
                target_expert = resp.text.strip()
                st.session_state.current_expert_active = target_expert
        except: pass
    
    if target_expert != active_expert:
        st.info(f"🤖 Auto-Pilot: Mengalihkan ke {target_expert}")
        active_expert = target_expert

    # 2. User Chat
    db.simpan_chat(nama_proyek, active_expert, "user", user_input)
    with st.chat_message("user"): st.markdown(user_input)

    # 3. Content Prep
    payload = [user_input]
    # Reset visuals for NEW chat only (optional strategy, here we keep appending or clear on demand)
    # st.session_state.generated_visuals = [] # Uncomment jika ingin reset gambar tiap chat baru
    
    if uploaded_files:
        for f in uploaded_files:
            if f.name not in st.session_state.processed_files:
                ftype, fcontent = process_uploaded_file(f)
                if ftype == "image":
                    with st.chat_message("user"): st.image(f, width=250)
                    # Simpan gambar upload user ke report juga
                    img_byte_arr = io.BytesIO()
                    fcontent.save(img_byte_arr, format='PNG')
                    st.session_state.generated_visuals.append({'type':'image', 'data':fcontent, 'caption':f"Upload User: {f.name}"})
                    payload.append(fcontent)
                elif ftype == "text":
                    payload.append(f"\n[DOKUMEN {f.name}]: {fcontent}")
                st.session_state.processed_files.add(f.name)

    # 4. Generate AI
    with st.chat_message("assistant"):
        with st.spinner("Sedang menganalisis & merancang..."):
            try:
                # Instruksi Plotting Wajib
                sys_instr = get_system_instruction(active_expert)
                if "Code" not in active_expert and "Visionary" not in active_expert:
                    sys_instr += "\n[VISUALISASI]: Jika butuh grafik, buat kode Python (matplotlib). Akhiri dgn 'st.pyplot(plt.gcf())'."

                # Fallback Model Logic
                try: model = genai.GenerativeModel(selected_model, system_instruction=sys_instr)
                except: model = genai.GenerativeModel("models/gemini-1.5-pro", system_instruction=sys_instr)

                # History
                hist_objs = []
                for h in db.get_chat_history(nama_proyek, active_expert)[-5:]:
                    if h['content'] != user_input:
                        hist_objs.append({"role": "user" if h['role']=="user" else "model", "parts": [h['content']]})
                
                chat = model.start_chat(history=hist_objs)
                
                # Handling Stream & Fallback
                full_resp = ""
                box = st.empty()
                try:
                    stream = chat.send_message(payload, stream=True)
                    for chunk in stream:
                        if chunk.text:
                            full_resp += chunk.text
                            box.markdown(full_resp + "▌")
                except:
                    # Retry non-stream if flash model fails
                    fallback = genai.GenerativeModel("models/gemini-1.5-pro", system_instruction=sys_instr)
                    full_resp = fallback.start_chat(history=hist_objs).send_message(payload).text
                
                box.markdown(full_resp)
                db.simpan_chat(nama_proyek, active_expert, "assistant", full_resp)
                
                # 5. EXECUTE PLOTS & SAVE TO VISUALS
                codes = re.findall(r"```python(.*?)```", full_resp, re.DOTALL)
                for c in codes:
                    if "plt." in c:
                        st.markdown("### 📉 Grafik Engineering")
                        with st.container():
                            # Fungsi ini sudah otomatis menyimpan ke st.session_state.generated_visuals
                            success = execute_generated_code(c)
                            if success:
                                st.pyplot(plt.gcf())
                                # Jangan lupa clf agar tidak tumpang tindih
                                plt.clf() 

                # 6. UPDATE REPORT STATE
                st.session_state.last_analysis_text = full_resp
                st.rerun() # Refresh agar tombol download di sidebar muncul/update

            except Exception as e:
                st.error(f"Error Sistem: {e}")
