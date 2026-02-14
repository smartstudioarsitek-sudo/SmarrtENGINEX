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
import xlsxwriter
import re
import time

# ==========================================
# 0. CEK MODUL PENDUKUNG
# ==========================================
try:
    from backend_enginex import EnginexBackend
    from persona import gems_persona, get_persona_list, get_system_instruction
    from streamlit_folium import st_folium
except ImportError as e:
    st.error(f"❌ CRITICAL ERROR: Modul tidak ditemukan! \nDetail: {e}")
    st.stop()

# ==========================================
# 1. UNIVERSAL REPORT GENERATOR (THE ENGINE)
# ==========================================
class UniversalReportGenerator:
    """
    Mesin pembuat laporan 'All-in-One'.
    Menangani Word (Teks+Gambar), Excel, PPT, CSV, dan Zip.
    """
    
    @staticmethod
    def create_word_report(project_name, expert_name, text_content, visual_assets):
        """Membuat Word Laporan Lengkap (Teks + Grafik Terlampir)"""
        doc = docx.Document()
        
        # --- SETUP HALAMAN A4 ---
        section = doc.sections[0]
        section.page_height = Cm(29.7)
        section.page_width = Cm(21.0)
        section.left_margin = Cm(2.54)
        section.right_margin = Cm(2.54)
        
        # --- HEADER ---
        header = section.header
        htable = header.add_table(1, 2, width=Inches(6))
        htable.autofit = False
        htable.columns[0].width = Inches(2)
        htable.columns[1].width = Inches(4)
        
        cell_logo = htable.cell(0, 0)
        cell_logo.text = "ENGINEX CONSULTANT"
        
        cell_info = htable.cell(0, 1)
        p = cell_info.paragraphs[0]
        p.text = f"PROYEK: {project_name}\nAHLI: {expert_name}"
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        
        # --- TITLE ---
        doc.add_heading(f"LAPORAN ANALISIS TEKNIS", 0).alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph(f"Tanggal Generate: {time.strftime('%d-%m-%Y')}")
        doc.add_paragraph("-" * 70)

        # --- CONTENT PARSING ---
        lines = text_content.split('\n')
        for line in lines:
            line = line.strip()
            if not line: continue
            
            if line.startswith('### '): doc.add_heading(line.replace('### ', ''), level=3)
            elif line.startswith('## '): doc.add_heading(line.replace('## ', ''), level=2)
            elif line.startswith('# '): doc.add_heading(line.replace('# ', ''), level=1)
            elif line.startswith('- ') or line.startswith('* '): doc.add_paragraph(line[2:], style='List Bullet')
            elif line.startswith('1. '): doc.add_paragraph(line, style='List Number')
            else: doc.add_paragraph(line).alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

        # --- VISUAL ASSETS (GRAFIK/GAMBAR) ---
        if visual_assets:
            doc.add_page_break()
            doc.add_heading("LAMPIRAN: DOKUMENTASI VISUAL & GRAFIK", level=1)
            
            for i, asset in enumerate(visual_assets):
                try:
                    doc.add_heading(f"Gambar {i+1}: {asset.get('caption', 'Grafik Analisis')}", level=3)
                    
                    img_stream = asset['data']
                    
                    # Jika tipe 'plot' (BytesIO), perlu seek(0). Jika 'image' (PIL), perlu save ke BytesIO
                    final_stream = io.BytesIO()
                    if asset['type'] == 'image':
                        asset['data'].save(final_stream, format='PNG')
                    else:
                        img_stream.seek(0)
                        final_stream.write(img_stream.read())
                    
                    final_stream.seek(0)
                    doc.add_picture(final_stream, width=Inches(6))
                    doc.add_paragraph("") # Spacer
                except Exception as e:
                    doc.add_paragraph(f"[Gagal render gambar: {str(e)}]")

        # --- SAVE ---
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer

    @staticmethod
    def create_excel_table(text_content):
        """Ekstrak tabel markdown ke Excel"""
        try:
            lines = text_content.split('\n')
            data, headers = [], []
            for line in lines:
                if "|" in line and "---" not in line:
                    row = [c.strip() for c in line.split('|')[1:-1]]
                    if not headers: headers = row
                    else: 
                        if len(row) == len(headers): data.append(row)
            
            if not headers: return None
            
            df = pd.DataFrame(data, columns=headers)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Data Analisis')
            output.seek(0)
            return output
        except: return None

    @staticmethod
    def create_civil3d_csv(text_content):
        """Ekstrak koordinat ke format Civil 3D (P,N,E,Z,D)"""
        try:
            # Cari tabel dulu
            excel_io = UniversalReportGenerator.create_excel_table(text_content)
            if not excel_io: return None
            
            df = pd.read_excel(excel_io)
            cols = [c.lower() for c in df.columns]
            
            # Cek kolom minimal (X, Y atau N, E)
            if any('x' in c for c in cols) and any('y' in c for c in cols):
                # Mapping sederhana
                out_df = pd.DataFrame()
                out_df['P'] = range(1, len(df)+1)
                
                # Cari kolom Y (Northing) dan X (Easting)
                y_col = next((c for c in df.columns if 'y' in c.lower() or 'north' in c.lower()), None)
                x_col = next((c for c in df.columns if 'x' in c.lower() or 'east' in c.lower()), None)
                z_col = next((c for c in df.columns if 'z' in c.lower() or 'elev' in c.lower()), None)
                d_col = next((c for c in df.columns if 'ket' in c.lower() or 'desc' in c.lower()), None)
                
                if x_col and y_col:
                    out_df['N'] = df[y_col]
                    out_df['E'] = df[x_col]
                    out_df['Z'] = df[z_col] if z_col else 0
                    out_df['D'] = df[d_col] if d_col else "Point"
                    return out_df.to_csv(index=False, header=False).encode('utf-8')
            return None
        except: return None

    @staticmethod
    def create_ppt_presentation(text_content, project_name):
        """Buat PPT sederhana dari poin-poin"""
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        slide.shapes.title.text = project_name
        slide.placeholders[1].text = "Laporan Analisis ENGINEX"
        
        lines = text_content.split('\n')
        curr_slide = None
        for line in lines:
            line = line.strip()
            if line.startswith('## '):
                curr_slide = prs.slides.add_slide(prs.slide_layouts[1])
                curr_slide.shapes.title.text = line.replace('## ', '')
            elif line.startswith('- ') and curr_slide:
                p = curr_slide.shapes.placeholders[1].text_frame.add_paragraph()
                p.text = line.replace('- ', '')
        
        out = io.BytesIO()
        prs.save(out)
        out.seek(0)
        return out

    @staticmethod
    def create_zip_images(visual_assets):
        """Bundle semua grafik/gambar jadi satu ZIP"""
        if not visual_assets: return None
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for i, asset in enumerate(visual_assets):
                ext = "png"
                img_stream = io.BytesIO()
                
                if asset['type'] == 'image':
                    asset['data'].save(img_stream, format='PNG')
                else: # plot (BytesIO)
                    asset['data'].seek(0)
                    img_stream.write(asset['data'].read())
                
                img_stream.seek(0)
                zf.writestr(f"Gambar_{i+1}_{asset.get('caption','plot')}.png", img_stream.read())
        
        zip_buffer.seek(0)
        return zip_buffer

# ==========================================
# 2. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(
    page_title="ENGINEX Ultimate: All-in-One",
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
    /* Tombol Download Sidebar yang Rapi */
    .stDownloadButton button {
        width: 100%;
        background-color: #F8FAFC;
        color: #334155;
        border: 1px solid #CBD5E1;
        font-weight: 600;
        text-align: left;
        padding: 8px 15px;
        margin-bottom: 5px;
        border-radius: 6px;
        transition: all 0.2s;
    }
    .stDownloadButton button:hover {
        background-color: #EFF6FF;
        border-color: #2563EB;
        color: #1D4ED8;
        transform: translateX(3px);
    }
    .download-header {
        font-weight: bold;
        color: #0F172A;
        margin-top: 15px;
        margin-bottom: 5px;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. SESSION STATE & DATABASE
# ==========================================
if 'processed_files' not in st.session_state: st.session_state.processed_files = set()
if 'current_expert_active' not in st.session_state: st.session_state.current_expert_active = "👑 The GEMS Grandmaster"
if 'backend' not in st.session_state: st.session_state.backend = EnginexBackend()

# State Khusus untuk Menyimpan Hasil agar Tombol Download Awet
if 'generated_visuals' not in st.session_state: st.session_state.generated_visuals = [] 
if 'last_analysis_text' not in st.session_state: st.session_state.last_analysis_text = ""

db = st.session_state.backend

# ==========================================
# 4. FUNGSI UTILITAS
# ==========================================
def execute_generated_code(code_str):
    """Jalankan kode plot & simpan ke state visuals"""
    try:
        local_vars = {"pd": pd, "np": np, "plt": plt, "st": st}
        plt.clf()
        exec(code_str, {}, local_vars)
        
        # Simpan grafik ke memory
        fig = plt.gcf()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        
        st.session_state.generated_visuals.append({
            'type': 'plot',
            'data': buf,
            'caption': "Grafik Engineering"
        })
        return True
    except Exception as e:
        st.error(f"⚠️ Error Plot: {e}")
        return False

def process_uploaded_file(uploaded_file):
    if uploaded_file is None: return None, None
    file_type = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_type in ['png', 'jpg', 'jpeg']:
            return "image", Image.open(uploaded_file)
        elif file_type == 'pdf':
            pdf = PyPDF2.PdfReader(uploaded_file)
            return "text", "\n".join([p.extract_text() for p in pdf.pages])
        elif file_type == 'docx':
            doc = docx.Document(uploaded_file)
            return "text", "\n".join([p.text for p in doc.paragraphs])
        elif file_type in ['xlsx', 'xls']:
            df = pd.read_excel(uploaded_file)
            return "text", f"[EXCEL PREVIEW]\n{df.head(50).to_string()}"
        elif file_type in ['geojson', 'kml']:
            return "geo", uploaded_file.getvalue().decode("utf-8")
        else: return "text", uploaded_file.getvalue().decode("utf-8")
    except Exception as e: return "error", str(e)

# ==========================================
# 5. SIDEBAR LENGKAP (ALL MENUS)
# ==========================================
with st.sidebar:
    st.title("🏗️ ENGINEX V14")
    st.caption("Ultimate Integrated System")
    st.markdown("---")
    
    # API KEY
    key_in = st.text_input("🔑 API Key:", type="password")
    api_key = key_in.strip() if key_in else st.secrets.get("GOOGLE_API_KEY", "")
    if not api_key: st.warning("Butuh API Key"); st.stop()
    try: genai.configure(api_key=api_key)
    except: st.error("Key Error"); st.stop()
    
    # PROJECT
    with st.expander("📁 Proyek", expanded=False):
        projs = db.daftar_proyek()
        mode = st.radio("Mode:", ["Lama", "Baru"])
        nama_proyek = st.text_input("Nama:", "Proyek 2026") if mode=="Baru" else st.selectbox("Pilih:", projs if projs else ["Baru"])
        auto_pilot = st.checkbox("🤖 Auto-Pilot", True)
        manual_expert = st.selectbox("Ahli:", get_persona_list(), disabled=auto_pilot)
        
    # UPLOAD
    st.markdown("### 📎 Upload Data")
    uploaded_files = st.file_uploader("", accept_multiple_files=True)
    
    if st.button("🧹 Reset"):
        db.clear_chat(nama_proyek, st.session_state.current_expert_active)
        st.session_state.generated_visuals = []
        st.session_state.last_analysis_text = ""
        st.rerun()
        
    st.markdown("---")
    
    # ==========================================
    # 📥 DOWNLOAD CENTER (KEMBALI LENGKAP)
    # ==========================================
    st.header("📥 Download Center")
    
    # Cek apakah ada data analisis terakhir
    if st.session_state.last_analysis_text:
        txt = st.session_state.last_analysis_text
        vis = st.session_state.generated_visuals
        
        # 1. LAPORAN UTAMA (WORD)
        st.markdown('<div class="download-header">📄 Laporan Resmi</div>', unsafe_allow_html=True)
        word_data = UniversalReportGenerator.create_word_report(nama_proyek, st.session_state.current_expert_active, txt, vis)
        st.download_button("Download Word (.docx)", word_data, f"{nama_proyek}_Laporan.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        
        # 2. DATA TABEL (EXCEL)
        st.markdown('<div class="download-header">📊 Data Perhitungan</div>', unsafe_allow_html=True)
        excel_data = UniversalReportGenerator.create_excel_table(txt)
        if excel_data:
            st.download_button("Download Excel (.xlsx)", excel_data, f"{nama_proyek}_Tabel.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.button("Excel (Tidak ada tabel)", disabled=True)
            
        # 3. PRESENTASI (PPT)
        st.markdown('<div class="download-header">📢 Bahan Presentasi</div>', unsafe_allow_html=True)
        ppt_data = UniversalReportGenerator.create_ppt_presentation(txt, nama_proyek)
        st.download_button("Download Slide (.pptx)", ppt_data, f"{nama_proyek}_Slide.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation")
        
        # 4. GAMBAR & GRAFIK (ZIP)
        if vis:
            st.markdown('<div class="download-header">🖼️ Album Gambar</div>', unsafe_allow_html=True)
            zip_data = UniversalReportGenerator.create_zip_images(vis)
            st.download_button("Download Album (.zip)", zip_data, f"{nama_proyek}_Images.zip", "application/zip")
            
        # 5. CIVIL 3D (CSV)
        csv_data = UniversalReportGenerator.create_civil3d_csv(txt)
        if csv_data:
            st.markdown('<div class="download-header">🏗️ Civil 3D Points</div>', unsafe_allow_html=True)
            st.download_button("Download Points (.csv)", csv_data, f"{nama_proyek}_Points.csv", "text/csv")

    else:
        st.info("Silakan mulai konsultasi untuk mengaktifkan menu download.")

# ==========================================
# 6. LOGIKA CHAT
# ==========================================
st.markdown(f'<div class="main-header">{nama_proyek}</div>', unsafe_allow_html=True)

if auto_pilot: active_expert = st.session_state.current_expert_active
else: active_expert = manual_expert; st.session_state.current_expert_active = manual_expert

st.caption(f"Status: **Online** | Ahli: **{active_expert}**")

# Load History
for chat in db.get_chat_history(nama_proyek, active_expert):
    with st.chat_message(chat['role']):
        st.markdown(chat['content'])
        # Re-render visual only (archives)
        if chat['role'] == 'assistant' and "plt." in chat['content']:
             with st.expander("Lihat Grafik Arsip"):
                 match = re.search(r"```python(.*?)```", chat['content'], re.DOTALL)
                 if match: 
                     try: exec(match.group(1), {"pd":pd,"np":np,"plt":plt,"st":st}); st.pyplot(plt.gcf()); plt.clf()
                     except: pass

# User Input
user_input = st.chat_input(f"Tanya {active_expert}...")

if user_input:
    # Routing
    target = active_expert
    if auto_pilot:
        try: 
            r = genai.GenerativeModel("models/gemini-1.5-flash")
            res = r.generate_content(f"Pilih SATU ahli dr {list(gems_persona.keys())} utk: '{user_input}'. Output Nama Saja.")
            if res.text.strip() in gems_persona: target = res.text.strip(); st.session_state.current_expert_active = target
        except: pass
    
    if target != active_expert: st.info(f"🤖 Mengalihkan ke {target}"); active_expert = target
    
    # Save & Show User
    db.simpan_chat(nama_proyek, active_expert, "user", user_input)
    with st.chat_message("user"): st.markdown(user_input)
    
    # Prep Content
    payload = [user_input]
    # PENTING: Reset visual session untuk chat baru ini (opsional, agar gambar lama tidak ikut terus)
    # st.session_state.generated_visuals = [] # Uncomment jika ingin reset tiap chat
    
    if uploaded_files:
        for f in uploaded_files:
            if f.name not in st.session_state.processed_files:
                typ, cont = process_uploaded_file(f)
                if typ == "image":
                    with st.chat_message("user"): st.image(f, width=200)
                    # Add to visual assets for report
                    buf = io.BytesIO(); cont.save(buf, format='PNG')
                    st.session_state.generated_visuals.append({'type':'image', 'data':cont, 'caption':f"Upload: {f.name}"})
                    payload.append(cont)
                elif typ == "text": payload.append(f"\nFILE {f.name}:\n{cont}")
                st.session_state.processed_files.add(f.name)
    
    # AI Response
    with st.chat_message("assistant"):
        with st.spinner("Menganalisis..."):
            try:
                # Instruksi
                instr = get_system_instruction(active_expert)
                if "Code" not in active_expert: instr += "\n[VISUAL]: Buat grafik Python (matplotlib) jika perlu. Akhiri st.pyplot(plt.gcf())."
                
                # Model
                try: model = genai.GenerativeModel("models/gemini-1.5-pro", system_instruction=instr)
                except: model = genai.GenerativeModel("models/gemini-1.5-flash", system_instruction=instr)
                
                # History
                hist = [{"role": ("user" if h['role']=="user" else "model"), "parts": [h['content']]} 
                        for h in db.get_chat_history(nama_proyek, active_expert)[-5:] if h['content'] != user_input]
                
                # Generate
                chat = model.start_chat(history=hist)
                full_resp = ""
                box = st.empty()
                stream = chat.send_message(payload, stream=True)
                for chunk in stream:
                    if chunk.text: full_resp += chunk.text; box.markdown(full_resp + "▌")
                
                box.markdown(full_resp)
                db.simpan_chat(nama_proyek, active_expert, "assistant", full_resp)
                
                # Exec Plots
                codes = re.findall(r"```python(.*?)```", full_resp, re.DOTALL)
                for c in codes:
                    if "plt." in c:
                        st.markdown("### 📉 Grafik")
                        with st.container():
                            if execute_generated_code(c): st.pyplot(plt.gcf()); plt.clf()
                
                # Trigger Sidebar Update
                st.session_state.last_analysis_text = full_resp
                st.rerun()
                
            except Exception as e: st.error(f"Error: {e}")
