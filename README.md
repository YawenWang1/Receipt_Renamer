# Receipt_Renamer
**Receipt Renamer** — A clean and private AI-powered receipt scanner.  
Automatically extracts date, vendor, amount, category, currency, and receipt number from PDFs and images using local OCR + LLM (Ollama). Intelligently renames files and exports a ready-to-use ZIP with summary CSV.

### Features
- Extracts date, vendor, amount, category, currency, and receipt number
- Automatically renames files (`YYYY_MM_DD_Vendor_Amount.jpg`)
- Supports PDFs and images
- Clean review & edit interface
- Exports ZIP with renamed files + summary CSV

### Requirements
- Python 3.10+
- [Ollama](https://ollama.com) installed and running
- NVIDIA GPU recommended (but works on CPU)

### Quick Start

1. Install Ollama from [ollama.com](https://ollama.com)
2. Run in terminal:
   ```bash
   ollama serve
   ollama pull qwen2.5:7b-instruct-q4_K_M
