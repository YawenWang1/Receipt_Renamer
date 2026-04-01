import streamlit as st
import pandas as pd
import cv2
import zipfile
import io
import os
import concurrent.futures
import time
import warnings
import subprocess
import sys

from utils import load_file_as_images, perform_ocr, extract_document_data_llm


warnings.filterwarnings("ignore", message="missing ScriptRunContext")
warnings.filterwarnings("ignore", category=UserWarning, module="paddle")
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"


st.set_page_config(page_title="Receipt Renamer", layout="wide")

# ====================== THEME MANAGEMENT ======================
if 'theme' not in st.session_state:
    st.session_state.theme = "dark"

def toggle_theme():
    st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"

if st.session_state.theme == "dark":
    st.markdown("""
        <style>
        .stApp { background-color: #0e1117; color: #fafafa; }
        .css-1d391kg { background-color: #1f2937; border-radius: 12px; }
        </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <style>
        .stApp { background-color: #f8f9fa; color: #1f2937; }
        .css-1d391kg { background-color: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-radius: 12px; }
        </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="Receipt Renamer", page_icon="🧾", layout="wide")

# ====================== HEADER ======================
col1, col2 = st.columns([6, 1])
with col1:
    st.title("🧾 Receipt Renamer")
with col2:
    if st.button("☀️" if st.session_state.theme == "dark" else "🌙", help="Toggle theme"):
        toggle_theme()
        st.rerun()

st.markdown("**Simple • Private • Local** — AI-powered receipt scanner and renamer")
st.divider()


# ====================== OLLAMA CHECK ======================
def check_ollama_running():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        return response.status_code == 200
    except:
        return False

# ====================== OLLAMA WARNING ======================
if not check_ollama_running():
    st.error("❌ **Ollama is not running**")
    st.markdown("""
    This app requires **Ollama** to be installed and running on your computer.

    **Quick Setup:**
    1. Download and install Ollama from [ollama.com](https://ollama.com)
    2. Open a terminal and run:
       ```bash
       ollama serve
       ```
    3. In another terminal, run:
       ```bash
       ollama pull qwen2.5:7b-instruct-q4_K_M
       ```
    4. Refresh this page.
    """)
    st.stop()

# ====================== OLLAMA SETTINGS ======================
def setup_ollama_environment():
    """Set optimal Ollama settings automatically"""
    os.environ.setdefault("OLLAMA_MAX_LOADED_MODELS", "1")
    os.environ.setdefault("OLLAMA_FLASH_ATTENTION", "1")
    os.environ.setdefault("OLLAMA_NUM_CTX", "8192")
    os.environ.setdefault("OLLAMA_KV_CACHE_TYPE", "q8_0")

# Call the automatic settings
setup_ollama_environment()

# ====================== USER EDITABLE PARALLEL SETTING ======================
st.sidebar.header("⚙️ Ollama Settings")

num_parallel = st.sidebar.slider(
    "OLLAMA_NUM_PARALLEL (Concurrent Calls)",
    min_value=1,
    max_value=16,
    value=int(os.environ.get("OLLAMA_NUM_PARALLEL", 8)),
    step=1,
    help="Higher values can speed up processing but may cause throttling on laptops."
)

# Apply the user-selected value
os.environ["OLLAMA_NUM_PARALLEL"] = str(num_parallel)

# Show current applied settings in sidebar
st.sidebar.info(f"""
**Current Ollama Settings:**
- NUM_PARALLEL: **{num_parallel}**
- FLASH_ATTENTION: Enabled
- NUM_CTX: 8192
- KV_CACHE_TYPE: q8_0
""")


# ====================== DEVICE SELECTION ======================
st.sidebar.header("🖥️ Hardware Settings")

device_choice = st.sidebar.radio(
    "OCR Device",
    options=["GPU (recommended if available)", "CPU (safer & more stable)"],
    index=0,  # default to GPU
    help="GPU is faster but may cause crashes on some systems. CPU is slower but more reliable."
)

# Store choice
st.session_state.ocr_device = "gpu" if "GPU" in device_choice else "cpu"

# --- RESET LOGIC ---
def reset_state():
    st.session_state.data_processed = False
    st.session_state.df_results = pd.DataFrame()
    st.session_state.images_cache = {}
    for key in ["total_time", "ocr_time", "llm_time"]:
        if key in st.session_state:
            del st.session_state[key]

# ====================== UPLOADER ======================
uploaded_files = st.file_uploader("Upload Receipts (JPG, PNG, PDF)",
                                  type=['jpg', 'jpeg', 'png', 'pdf'],
                                  accept_multiple_files=True,
                                  on_change=reset_state)

# Initialize Session State
if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False
if 'df_results' not in st.session_state:
    st.session_state.df_results = pd.DataFrame()
if 'images_cache' not in st.session_state:
    st.session_state.images_cache = {}

if uploaded_files:

    max_workers = st.slider("Max concurrent AI calls", 1, 12, 8, 1)

    if st.button(f"Process {len(uploaded_files)} Files"):
        st.session_state.images_cache = {}
        ocr_results_per_file = {}

        progress_bar = st.progress(0)
        status_text = st.empty()

        processing_start = time.time()

        # # STAGE 1: OCR (Sequential)
        ocr_start = time.time()
        for idx, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"👁️ Vision OCR: Reading {idx + 1}/{len(uploaded_files)}: {uploaded_file.name}")
            uploaded_file.seek(0)
            images = load_file_as_images(uploaded_file)

            if not images:
                st.error(f"Could not load {uploaded_file.name}")
                continue

            st.session_state.images_cache[uploaded_file.name] = images[0]
            text_lines = [line for page_img in images for line in perform_ocr(page_img)]
            ocr_results_per_file[uploaded_file.name] = text_lines

            progress_bar.progress((idx + 1) / len(uploaded_files))

        # =====================================================================
        # STAGE 1: PARALLEL OCR (NEW — this will save ~15-20 minutes)
        # =====================================================================
        # ocr_start = time.time()
        # status_text.text("👁️ Parallel OCR in progress...")
        #
        # def process_file(uploaded_file):
        #     uploaded_file.seek(0)
        #     images = load_file_as_images(uploaded_file)
        #     if not images:
        #         return uploaded_file.name, None, []
        #     first_page = images[0]
        #     # OCR all pages
        #     text_lines = [line for page_img in images for line in perform_ocr(page_img)]
        #     return uploaded_file.name, first_page, text_lines
        #
        #
        # with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:  # 8 is safe & fast
        #     future_to_file = {executor.submit(process_file, f): f for f in uploaded_files}
        #
        #     completed = 0
        #     for future in concurrent.futures.as_completed(future_to_file):
        #         completed += 1
        #         filename, first_page, text_lines = future.result()
        #         if first_page is not None:
        #             st.session_state.images_cache[filename] = first_page
        #             ocr_results_per_file[filename] = text_lines
        #         status_text.text(f"👁️ OCR: {completed}/{len(uploaded_files)} files done")
        #         progress_bar.progress(completed / len(uploaded_files))
        #         time.sleep(0.2)

        ocr_time = time.time() - ocr_start

        # STAGE 2: LLM (Concurrent)
        status_text.text("🧠 AI structuring data (parallel)...")
        progress_bar.empty()

        results = []
        llm_start = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_filename = {
                executor.submit(extract_document_data_llm, text_lines): filename
                for filename, text_lines in ocr_results_per_file.items()
            }

            completed = 0
            for future in concurrent.futures.as_completed(future_to_filename):
                filename = future_to_filename[future]
                completed += 1
                status_text.text(f"🧠 LLM: {completed}/{len(uploaded_files)} completed")
                try:
                    data = future.result()
                    results.append({
                        "Original File": filename,
                        "Date": data.date,
                        "Vendor": data.vendor_name.capitalize(),
                        "Category": data.category,
                        "Currency": getattr(data, 'currency', None),
                        "Amount": data.total_amount,
                        "Order Number": data.receipt_number,
                        "Raw Text": " | ".join(ocr_results_per_file[filename])
                    })
                except Exception as exc:
                    st.error(f"Failed {filename}: {exc}")
                time.sleep(0.05)

        llm_time = time.time() - llm_start
        total_time = time.time() - processing_start

        st.session_state.df_results = pd.DataFrame(results)
        st.session_state.data_processed = True
        st.session_state.ocr_time = round(ocr_time, 2)
        st.session_state.llm_time = round(llm_time, 2)
        st.session_state.total_time = round(total_time, 2)

        st.rerun()

# =====================================================================
# REVIEW UI (unchanged — timers, preview, summary, ZIP all still here)
# =====================================================================
if st.session_state.data_processed and not st.session_state.df_results.empty:
    st.divider()

    with st.expander("🕵️ Debug: View Raw OCR Output"):
        st.dataframe(st.session_state.df_results[["Original File", "Raw Text"]])


    def format_filename(row):
        try:
            d_part = row['Date'][2:].replace('-', '_')
            v_part = str(row['Vendor']).replace(' ', '_')
            a_part = f"{float(row['Amount']):.2f}"
            return f"{d_part}_{v_part}_{a_part}.jpg"
        except:
            return "error.jpg"


    display_df = st.session_state.df_results.drop(columns=["Raw Text"]).copy()
    display_df["New Filename"] = display_df.apply(format_filename, axis=1)

    st.subheader("Review & Edit")

    # Make Original File column clickable
    edited_df = st.data_editor(
        display_df,
        column_config={
            "Original File": st.column_config.TextColumn(
                "Original File",
                help="Click to preview the full receipt",
                disabled=True
            ),
            "Amount": st.column_config.NumberColumn(format="%.2f"),
            "New Filename": st.column_config.TextColumn(disabled=False),
            "Order Number": st.column_config.TextColumn(disabled=False),
            "Currency": st.column_config.TextColumn(disabled=False),
        },
        column_order=["Original File", "Date", "Vendor", "Category", "Currency", "Amount", "Order Number", "New Filename"],
        use_container_width=True,
        hide_index=True
    )
    # Clickable Preview Logic
    st.subheader("Receipt Preview")
    selected_file = st.selectbox(
        "Select a receipt to view full image",
        options=edited_df["Original File"].tolist(),
        key="preview_selector"
    )

    if selected_file and selected_file in st.session_state.get('images_cache', {}):
        img = st.session_state.images_cache[selected_file]
        try:
            if img.ndim == 3 and img.shape[2] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        except:
            pass
        st.image(img, caption=f"Full view: {selected_file}", width='stretch')

    if 'total_time' in st.session_state:
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("⏱️ Total Processing Time", f"{st.session_state.total_time} seconds")
        c2.metric("👁️ OCR Time", f"{st.session_state.ocr_time} seconds")
        c3.metric("🧠 LLM Time", f"{st.session_state.llm_time} seconds")

    st.subheader("📊 Quick Summary")
    total_receipts = len(edited_df)
    total_amount = edited_df["Amount"].sum()
    currencies = edited_df["Currency"].dropna().unique()
    currency_str = ", ".join(currencies) if len(currencies) > 0 else "Unknown"

    colA, colB = st.columns(2)
    colA.metric("Total Receipts", total_receipts)
    colB.metric("Grand Total", f"{currency_str} {total_amount:.2f}")

    if st.button("📦 Generate ZIP", type="primary"):
        final_df = edited_df.copy()
        final_df["New Filename"] = final_df["New Filename"].apply(
            lambda x: f"{os.path.splitext(str(x))[0]}.jpg"
        )

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for _, row in final_df.iterrows():
                orig = row['Original File']
                new_n = row['New Filename']
                if orig in st.session_state.get('images_cache', {}):
                    success, buf = cv2.imencode(".jpg", st.session_state.images_cache[orig])
                    if success:
                        zf.writestr(new_n, buf.tobytes())
            zf.writestr("summary.csv", final_df.to_csv(sep=";", decimal=",", index=False).encode('utf-8'))

        st.download_button(
            label="⬇️ Download ZIP",
            data=zip_buffer.getvalue(),
            file_name="renamed_receipts.zip",
            mime="application/zip"
        )