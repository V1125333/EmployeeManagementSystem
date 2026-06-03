# ReKnew Certificate Generator 🎓

A professional, production-ready certificate generation tool for ReKnew AI programmes.  
Generates branded PDF certificates that faithfully match the official ReKnew template — suitable for LinkedIn upload and sharing.

---

## 📐 Technical Approach

**Stack: Python + Streamlit + ReportLab**

| Choice | Reason |
|--------|--------|
| **Streamlit** | Form-based UI, zero frontend code, perfect for non-technical users |
| **ReportLab** | Industry-standard PDF generation in Python, fine-grained layout control |
| **Pandas** | Robust CSV/Excel parsing with easy column normalisation |
| No external API | Fully offline — no internet needed after install |

## 🎨 Design Reproduction

The certificate visually reproduces the template from the screenshot:
- **Light grey background (#F0F0F0)** with white inner panel card
- **re·knew wordmark** with coral accent on the middle dot
- **CERTIFICATE OF COMPLETION** heading with letter-spacing
- **Recipient name** in large serif (Lora / DejaVu Serif Bold) — auto-shrinks for long names
- **Horizontal rule** separating name from programme details
- **Bottom row**: medal icon | date of issue | CEO signature block
- **Certificate ID** centred at the very bottom
- **ReKnew chevron logo icon** (coral/orange triangle) top-right

Fonts used in the PDF:
- Poppins (headings, labels, UI text)
- Lora Variable / DejaVu Serif (recipient name, programme name — elegant serif)

> **Note:** Bricolage Grotesque and Raleway (original fonts) can be substituted  
> by dropping `.ttf` files into the `fonts/` folder and updating `certificate_generator.py`.

---

## 📁 Project Structure

```
reknew_cert_generator/
├── app.py                      # Streamlit UI
├── certificate_generator.py    # Core PDF generation engine
├── requirements.txt
├── sample_batch.csv            # Example CSV for bulk upload
├── README.md
├── fonts/                      # Bundled TTF font files
│   ├── Poppins-Regular.ttf
│   ├── Poppins-Bold.ttf
│   ├── Poppins-Medium.ttf
│   ├── Poppins-Light.ttf
│   ├── Lora-Variable.ttf
│   ├── DejaVuSerif.ttf
│   └── DejaVuSerif-Bold.ttf
├── assets/                     # (optional) logo images etc.
└── output/                     # Generated PDFs written here (auto-created)
```

---

## ⚡ Setup & Run

### 1. Clone / unzip the project

```bash
unzip reknew_cert_generator.zip
cd reknew_cert_generator
```

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
streamlit run app.py
```

The app opens at **http://localhost:8501** in your browser.

---

## 📄 Usage

### Single Certificate (Tab 1)
1. Fill in First Name, Surname, Certificate Type, Duration, Serial Number
2. Set Cohort Code and Year in the sidebar
3. Click **Generate Certificate**
4. Click **Download PDF**

### Bulk Manual Entry (Tab 2)
1. Click **➕ Add Row** for each recipient
2. Fill in all fields
3. Review the preview table
4. Click **Generate All Certificates** → **Download ZIP**

### CSV / Excel Upload (Tab 3)
1. Download the **Sample CSV** as a template
2. Fill in your recipients
3. Upload the file
4. Fix any validation warnings
5. Click **Generate All Certificates** → **Download ZIP**

---

## 📋 CSV Format

```csv
FirstName,Surname,CertificateType,Duration,SerialNumber,CohortCode,Year
Venu,Madhav,ReKnew Context Engineer,4 Weeks,1,C1,2026
Priya,Sharma,ReKnew AI Cloud Practitioner,6 Weeks,2,C1,2026
```

- **CohortCode** and **Year** columns are optional — they fall back to sidebar values.
- Blank rows are silently skipped.
- Column names are case-insensitive and space/underscore-tolerant.

---

## 🗂️ Certificate ID Format

```
RK-{CohortCode}-{Year}-{SerialNumber}

Examples:
  RK-C1-2026-001
  RK-C2-2026-014
  RK-C3-2025-101
```

---

## 🖨️ PDF Output Notes

- Output format: **landscape A4** (297 × 210 mm)
- Suitable for **LinkedIn Licences & Certifications** upload
- Named as: `RK_Certificate_FirstName_Surname_CertType.pdf`
- High resolution, vector text — crisp at any zoom level

---

## 🗺️ Supported Certificate Types

```
ReKnew AI Cloud Practitioner
ReKnew AI Cloud Architect
ReKnew AI Foundational Engineer
ReKnew Context Engineer
ReKnew Context Architect
ReKnew Snowflake AI Practitioner
ReKnew DataBricks AI Practitioner
```

To add more, edit the `CERT_TYPES` list in `certificate_generator.py`.

---

## 🔮 Future Improvements

| Feature | Complexity |
|---------|-----------|
| Swap in Bricolage Grotesque + Raleway fonts | Low — drop TTFs in fonts/ |
| Add actual re·knew logo PNG/SVG image | Low — embed via ReportLab ImageReader |
| PPTX output alongside PDF | Medium — use python-pptx |
| Email delivery of certificates | Medium — add SMTP config |
| Custom CEO name / signature image | Low — add to sidebar settings |
| Certificate verification URL / QR code | Medium — encode cert ID in QR |
| Dark/light theme toggle | Low — CSS variable swap |
| Streamlit Cloud / Docker deployment | Low — add Dockerfile |

---

## 🐛 Troubleshooting

| Issue | Fix |
|-------|-----|
| Font rendering looks wrong | Ensure `fonts/` directory has all TTF files |
| `streamlit: command not found` | Run `pip install streamlit` |
| Excel file not reading | Run `pip install openpyxl` |
| Date format error on Windows | Change `%-d` to `%d` in `certificate_generator.py` line with `strftime` |

---

*Built for ReKnew AI · 2026*
