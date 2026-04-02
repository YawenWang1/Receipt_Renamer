# Receipt_Renamer

**AI-powered receipt scanner and smart file renamer**

A clean, private tool that extracts key information from receipts and invoices, then intelligently renames the files for easy organization.

### Features
- Extracts: Date, Vendor, Amount, Category, Currency, Receipt Number
- Automatically renames files in a clean format (`YYYY_MM_DD_Vendor_Amount.jpg`)
- Supports multi-page PDFs and images (JPG, PNG)
- Clean review & edit interface
- Exports a ZIP with renamed files + summary CSV (ready for Excel)
- Light / Dark theme
- Runs 100% locally (no data leaves your computer)

### Live Demo
[Try the Demo Version](https://receiptrenamer-demo.streamlit.app/)  
*(Runs in mock mode — no Ollama required)*

### Screenshots
[Review Local Version](Screenshots/Full_local_Receipt_Renamer_Streamlit.pdf)  
[Preview_Demo](Screenshots/Receipt_Renamer_Demo_Streamlit.pdf)

### Quick Local Setup (Full AI Version)

1. Install Ollama from [ollama.com](https://ollama.com)
2. Run in terminal:
   ```bash
   ollama serve                               # Keep this terminal open
   ollama pull qwen2.5:7b-instruct-q4_K_M     # Download model (only once)
