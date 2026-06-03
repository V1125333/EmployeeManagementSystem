"""
ReKnew Certificate Generator — Streamlit App  (v1.3)
=====================================================
Fix: st.rerun() was being called right after st.download_button(),
     wiping the button before the user could click it.
     Now uses session_state to persist generated files across reruns.

Run with:
    streamlit run app.py
"""

import io
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from certificate_generator import (
    CERT_TYPES,
    generate_certificate_pdf,
    build_filename,
)
from serial_registry import (
    peek_next,
    consume_next,
    consume_batch,
    get_all_counters,
    set_counter_to,
)

# ─────────────────────────────────────────────────────────────
#  Page config
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ReKnew Certificate Generator",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Poppins', sans-serif; }

  .rk-hero {
      background: linear-gradient(135deg, #1A1F2E 0%, #2C3557 100%);
      border-radius: 12px; padding: 28px 36px; margin-bottom: 28px;
      display: flex; align-items: center; justify-content: space-between;
  }
  .rk-hero h1 { color: white; font-size: 2rem; font-weight: 700; margin: 0; }
  .rk-hero span.accent { color: #E8472A; }
  .rk-hero p  { color: #AAB0C4; margin: 6px 0 0 0; font-size: 0.95rem; }
  .rk-badge   { background:#E8472A; color:white; padding:6px 16px;
                border-radius:20px; font-size:0.78rem; font-weight:600; letter-spacing:0.05em; }

  .rk-section-title {
      font-size:0.8rem; font-weight:600; letter-spacing:0.1em;
      text-transform:uppercase; color:#7A7A7A;
      margin-bottom:14px; border-bottom:2px solid #F0F0F0; padding-bottom:8px;
  }
  .sn-chip {
      display:inline-block; background:#E8F5E9; color:#2E7D32;
      border:1px solid #A5D6A7; border-radius:20px;
      padding:3px 12px; font-size:0.82rem; font-weight:600;
  }
  .counter-row { display:flex; align-items:center; gap:10px;
                 padding:6px 0; border-bottom:1px solid #F5F5F5; }
  .counter-label { flex:1; font-size:0.82rem; color:#333; }
  .counter-val   { font-weight:700; font-size:0.95rem; color:#1A1F2E;
                   min-width:38px; text-align:right; }
  div.stButton > button[kind="primary"] {
      background:#E8472A; border:none; border-radius:8px;
      font-weight:600; font-size:1rem; padding:12px 32px; width:100%;
  }
  div.stButton > button[kind="primary"]:hover { background:#C73820; }
  .stTabs [aria-selected="true"] {
      color:#E8472A !important; border-bottom-color:#E8472A !important;
  }
  /* Download button styling */
  div.stDownloadButton > button {
      background: #1A1F2E; color: white; border: none;
      border-radius: 8px; font-weight: 600; width: 100%;
  }
  div.stDownloadButton > button:hover { background: #2C3557; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  Hero
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="rk-hero">
  <div>
    <h1>re<span class="accent">·</span>knew &nbsp;🎓&nbsp; Certificate Generator</h1>
    <p>Generate professional, LinkedIn-ready certificates. Serial numbers assigned automatically per programme.</p>
  </div>
  <span class="rk-badge">v1.3</span>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  Session state init — stores generated files so rerun doesn't wipe them
# ─────────────────────────────────────────────────────────────
for key in ["single_pdf", "single_fname", "single_cert_id",
            "bulk_zip", "bulk_zip_name",
            "csv_zip",  "csv_zip_name"]:
    if key not in st.session_state:
        st.session_state[key] = None

if "bulk_rows" not in st.session_state:
    st.session_state.bulk_rows = [
        {"first_name": "", "surname": "", "cert_type": CERT_TYPES[0], "duration": "4 Weeks"}
    ]

# ─────────────────────────────────────────────────────────────
#  Sidebar
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️  Global Settings")
    st.markdown("---")

    cohort_code = st.text_input(
        "Cohort Code", value="C1",
        help="e.g. C1, C2, C3 — used in Certificate IDs.",
    ).strip().upper()

    year = st.number_input(
        "Year", min_value=2020, max_value=2099,
        value=date.today().year, step=1,
    )

    issued_date_input = st.date_input(
        "Date of Issue", value=date.today(),
        help="Defaults to today. Override if back-dating.",
    )

    st.markdown("---")

    st.markdown("---")
    st.markdown("### 🔢  Serial Counters")
    st.caption(f"Last issued for {cohort_code} / {year}")

    counters = get_all_counters()
    prefix   = f"|{cohort_code}|{year}"
    relevant = {k: v for k, v in counters.items() if k.endswith(prefix)}

    if relevant:
        for k, last in sorted(relevant.items()):
            short = k.split("|")[0].replace("ReKnew ", "")
            st.markdown(
                f'<div class="counter-row">'
                f'<span class="counter-label">{short}</span>'
                f'<span class="counter-val">#{last:03d}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("No certificates issued yet.")

    with st.expander("🔧 Admin: Adjust a Counter"):
        admin_ct  = st.selectbox("Certificate Type", CERT_TYPES, key="admin_ct")
        admin_val = st.number_input(
            "Set last-issued serial to", min_value=0, value=0, step=1,
            help="Next issued will be this value + 1.",
        )
        if st.button("Apply", key="admin_apply"):
            set_counter_to(admin_ct, cohort_code, year, int(admin_val))
            st.success(f"Done. Next serial → {int(admin_val)+1:03d}")

    st.markdown("---")
    st.caption("ReKnew Certificate Generator · v1.3")


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────

def validate_row(row):
    for f in ["first_name", "surname", "cert_type", "duration"]:
        if not str(row.get(f, "")).strip():
            return f"Missing: '{f}'"
    if row["cert_type"] not in CERT_TYPES:
        return f"Unknown cert type: '{row['cert_type']}'"
    return None


def simulate_serials(records):
    """Preview serial numbers without writing to the registry."""
    temp = {}
    out  = []
    for rec in records:
        if rec.get("_manual_sn"):
            out.append((int(rec["_manual_sn"]), "📄 file"))
        else:
            k = f"{rec['cert_type']}|{rec.get('cohort_code', cohort_code)}|{rec.get('year', year)}"
            if k not in temp:
                temp[k] = peek_next(rec["cert_type"],
                                    rec.get("cohort_code", cohort_code),
                                    int(rec.get("year", year)))
            else:
                temp[k] += 1
            out.append((temp[k], "🤖 auto"))
    return out


def make_zip(records, issued_date, tmpl="light"):
    """Build and return ZIP bytes, consuming serial numbers atomically."""
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rec in records:
            if rec.get("_manual_sn"):
                sn = int(rec["_manual_sn"])
            else:
                sn = consume_next(
                    rec["cert_type"],
                    rec.get("cohort_code", cohort_code),
                    int(rec.get("year", year)),
                )
            pdf = generate_certificate_pdf(
                first_name    = rec["first_name"],
                surname       = rec["surname"],
                cert_type     = rec["cert_type"],
                duration      = rec["duration"],
                cohort_code   = rec.get("cohort_code", cohort_code),
                year          = int(rec.get("year", year)),
                serial_number = sn,
                issued_date   = issued_date,
                template      = tmpl,
            )
            zf.writestr(
                build_filename(rec["first_name"], rec["surname"], rec["cert_type"], tmpl),
                pdf,
            )
    return zip_buf.getvalue()


# ─────────────────────────────────────────────────────────────
#  Tabs
# ─────────────────────────────────────────────────────────────
tab_single, tab_bulk, tab_csv = st.tabs([
    "✏️  Single Certificate",
    "📋  Bulk Entry (manual)",
    "📂  CSV / Excel Upload",
])


# ══════════════════════════════════════════════════════════════
#  TAB 1 — Single Certificate
# ══════════════════════════════════════════════════════════════
with tab_single:
    st.markdown('<div class="rk-section-title">Recipient Details</div>',
                unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        first_name = st.text_input("First Name *", placeholder="e.g. Venu",
                                   key="s_first")
        cert_type  = st.selectbox("Certificate Type *", CERT_TYPES, key="s_ct")
    with c2:
        surname  = st.text_input("Surname *", placeholder="e.g. Madhav",
                                  key="s_surname")
        duration = st.text_input("Duration *", placeholder="e.g. 4 Weeks",
                                  key="s_duration")

    # Live serial preview (peek only — doesn't consume)
    next_sn = peek_next(cert_type, cohort_code, year)
    cert_id = f"RK-{cohort_code}-{year}-{next_sn:03d}"
    st.markdown(
        f'Serial will be auto-assigned: <span class="sn-chip">#{next_sn:03d}</span>'
        f'&nbsp;&nbsp;→&nbsp;&nbsp;<code style="font-size:0.9rem">{cert_id}</code>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Live preview card
    if first_name or surname:
        with st.expander("📄 Certificate Preview", expanded=True):
            pa, pb = st.columns(2)
            with pa:
                st.write(f"**Full Name:** {first_name.strip()} {surname.strip()}")
                st.write(f"**Certificate Type:** {cert_type}")
                st.write(f"**Duration:** {duration or '—'}")
            with pb:
                st.write(f"**Certificate ID:** {cert_id}")
                st.write(f"**Date of Issue:** {issued_date_input.strftime('%B %-d, %Y')}")
                st.write(f"**Cohort:** {cohort_code}  |  **Year:** {year}")

    st.markdown("")

    # ── Generate button ──────────────────────────────────
    if st.button("🎓 Generate Certificate", type="primary", key="gen_single"):
        errs = []
        if not first_name.strip(): errs.append("First Name is required.")
        if not surname.strip():    errs.append("Surname is required.")
        if not duration.strip():   errs.append("Duration is required.")

        if errs:
            for e in errs:
                st.error(e)
            # Clear any stale result
            st.session_state.single_pdf = None
        else:
            with st.spinner("Generating certificate..."):
                try:
                    sn  = consume_next(cert_type, cohort_code, year)
                    pdf = generate_certificate_pdf(
                        first_name    = first_name,
                        surname       = surname,
                        cert_type     = cert_type,
                        duration      = duration,
                        cohort_code   = cohort_code,
                        year          = year,
                        serial_number = sn,
                        issued_date   = issued_date_input,
                        template      = "dark",
                    )
                    st.session_state.single_pdf      = pdf
                    st.session_state.single_fname    = build_filename(first_name, surname, cert_type, "dark")
                    st.session_state.single_cert_id  = f"RK-{cohort_code}-{year}-{sn:03d}"
                except Exception as e:
                    st.error(f"Generation failed: {e}")
                    st.session_state.single_pdf = None

    # ── Download button — always shown if a PDF is ready ──
    # Kept OUTSIDE the generate button block so it persists across reruns
    if st.session_state.single_pdf is not None:
        st.success(f"✅ Certificate ready!  **ID: {st.session_state.single_cert_id}**")
        st.download_button(
            label     = "⬇️ Download PDF",
            data      = st.session_state.single_pdf,
            file_name = st.session_state.single_fname,
            mime      = "application/pdf",
            key       = "dl_single",
        )
        if st.button("🔄 Generate Another", key="reset_single"):
            st.session_state.single_pdf     = None
            st.session_state.single_fname   = None
            st.session_state.single_cert_id = None
            st.rerun()


# ══════════════════════════════════════════════════════════════
#  TAB 2 — Bulk Manual Entry
# ══════════════════════════════════════════════════════════════
with tab_bulk:
    st.markdown('<div class="rk-section-title">Bulk Entry — one row per recipient</div>',
                unsafe_allow_html=True)
    st.caption("Serial numbers are auto-assigned per certificate type when you generate.")

    # Column headers
    h0, h1, h2, h3, _ = st.columns([2, 2, 3, 2, 0.5])
    for col, lbl in zip([h0, h1, h2, h3],
                        ["First Name", "Surname", "Certificate Type", "Duration"]):
        col.markdown(
            f"<span style='font-size:0.75rem;font-weight:600;color:#888;"
            f"text-transform:uppercase'>{lbl}</span>",
            unsafe_allow_html=True,
        )

    updated = []
    for i, row in enumerate(st.session_state.bulk_rows):
        c0, c1, c2, c3, c4 = st.columns([2, 2, 3, 2, 0.5])
        fn  = c0.text_input("fn",  value=row["first_name"], key=f"bfn_{i}",
                             label_visibility="collapsed", placeholder="First Name")
        sn  = c1.text_input("sn",  value=row["surname"],    key=f"bsn_{i}",
                             label_visibility="collapsed", placeholder="Surname")
        ct  = c2.selectbox("ct",  CERT_TYPES,
                            index=CERT_TYPES.index(row["cert_type"]),
                            key=f"bct_{i}", label_visibility="collapsed")
        dur = c3.text_input("dur", value=row["duration"],   key=f"bdur_{i}",
                             label_visibility="collapsed", placeholder="e.g. 4 Weeks")
        c4.markdown(
            f"<div style='padding-top:8px;color:#BBB;font-size:0.78rem'>#{i+1}</div>",
            unsafe_allow_html=True,
        )
        updated.append({"first_name": fn, "surname": sn,
                         "cert_type": ct, "duration": dur})
    st.session_state.bulk_rows = updated

    ca, cb, _ = st.columns([1, 1, 5])
    if ca.button("➕ Add Row", key="add_row"):
        st.session_state.bulk_rows.append(
            {"first_name": "", "surname": "", "cert_type": CERT_TYPES[0], "duration": "4 Weeks"}
        )
        st.session_state.bulk_zip = None   # clear stale result
        st.rerun()
    if cb.button("🗑️ Clear All", key="clear_rows"):
        st.session_state.bulk_rows = [
            {"first_name": "", "surname": "", "cert_type": CERT_TYPES[0], "duration": "4 Weeks"}
        ]
        st.session_state.bulk_zip = None
        st.rerun()

    st.markdown("---")

    # Validate
    valid_rows = []
    for row in st.session_state.bulk_rows:
        if not row["first_name"].strip() and not row["surname"].strip():
            continue
        err = validate_row(row)
        if err:
            st.warning(f"{row['first_name']} {row['surname']}: {err}")
        else:
            valid_rows.append({**row, "cohort_code": cohort_code,
                                "year": year, "_manual_sn": ""})

    # Preview table with simulated serials
    if valid_rows:
        simulated = simulate_serials(valid_rows)
        preview   = []
        for rec, (sn_p, _) in zip(valid_rows, simulated):
            preview.append({
                "Full Name":        f"{rec['first_name']} {rec['surname']}",
                "Certificate Type": rec["cert_type"],
                "Duration":         rec["duration"],
                "Auto Serial #":    f"{sn_p:03d}",
                "Certificate ID":   f"RK-{cohort_code}-{year}-{sn_p:03d}",
            })
        st.markdown(f"**{len(valid_rows)} recipient(s) ready — preview serial numbers below:**")
        st.dataframe(pd.DataFrame(preview), use_container_width=True, hide_index=True)

    # Generate button
    if st.button("🎓 Generate All Certificates", type="primary", key="gen_bulk"):
        if not valid_rows:
            st.error("No valid rows to generate.")
        else:
            with st.spinner(f"Generating {len(valid_rows)} certificate(s)..."):
                try:
                    zip_bytes = make_zip(valid_rows, issued_date_input, "dark")
                    st.session_state.bulk_zip      = zip_bytes
                    st.session_state.bulk_zip_name = f"ReKnew_Certs_{cohort_code}_{year}.zip"
                except Exception as e:
                    st.error(f"Generation failed: {e}")
                    st.session_state.bulk_zip = None

    # Download — persists across reruns
    if st.session_state.bulk_zip is not None:
        st.success(f"✅ {len(valid_rows or [])} certificate(s) generated!")
        st.download_button(
            label     = "⬇️ Download ZIP",
            data      = st.session_state.bulk_zip,
            file_name = st.session_state.bulk_zip_name,
            mime      = "application/zip",
            key       = "dl_bulk",
        )
        if st.button("🔄 Clear & Start New Batch", key="reset_bulk"):
            st.session_state.bulk_zip  = None
            st.session_state.bulk_rows = [
                {"first_name": "", "surname": "",
                 "cert_type": CERT_TYPES[0], "duration": "4 Weeks"}
            ]
            st.rerun()


# ══════════════════════════════════════════════════════════════
#  TAB 3 — CSV / Excel Upload
# ══════════════════════════════════════════════════════════════
with tab_csv:
    st.markdown('<div class="rk-section-title">Upload CSV or Excel file</div>',
                unsafe_allow_html=True)
    st.markdown("""
    | Column | Required | Notes |
    |--------|----------|-------|
    | `FirstName` | ✅ | |
    | `Surname` | ✅ | |
    | `CertificateType` | ✅ | Must match a supported programme name |
    | `Duration` | ✅ | e.g. `4 Weeks` |
    | `SerialNumber` | ☑️ optional | Leave blank → auto-assigned |
    | `CohortCode` | ☑️ optional | Falls back to sidebar |
    | `Year` | ☑️ optional | Falls back to sidebar |
    """)

    sample = (
        "FirstName,Surname,CertificateType,Duration,CohortCode,Year\n"
        "Venu,Madhav,ReKnew Context Engineer,4 Weeks,C1,2026\n"
        "Priya,Sharma,ReKnew AI Cloud Practitioner,6 Weeks,C1,2026\n"
        "James,O'Brien,ReKnew DataBricks AI Practitioner,8 Weeks,C1,2026\n"
    )
    st.download_button("⬇️ Download Sample CSV", data=sample,
                       file_name="ReKnew_Sample.csv", mime="text/csv",
                       key="dl_sample")

    uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx", "xls"])

    if uploaded:
        try:
            df = (pd.read_csv(uploaded) if uploaded.name.endswith(".csv")
                  else pd.read_excel(uploaded))

            # Normalise column names
            df.columns = [c.strip() for c in df.columns]
            col_map = {
                "firstname":       "FirstName",
                "surname":         "Surname",
                "certificatetype": "CertificateType",
                "duration":        "Duration",
                "serialnumber":    "SerialNumber",
                "cohortcode":      "CohortCode",
                "year":            "Year",
            }
            df.rename(
                columns={c: col_map.get(c.lower().replace(" ", "").replace("_", ""), c)
                         for c in df.columns},
                inplace=True,
            )
            df.dropna(how="all", inplace=True)
            df.fillna("", inplace=True)

            st.success(f"📄 Loaded **{len(df)} rows** from `{uploaded.name}`")
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Build records
            records, errors = [], []
            for idx, row in df.iterrows():
                rec = {
                    "first_name":  str(row.get("FirstName", "")).strip(),
                    "surname":     str(row.get("Surname", "")).strip(),
                    "cert_type":   str(row.get("CertificateType", "")).strip(),
                    "duration":    str(row.get("Duration", "")).strip(),
                    "cohort_code": str(row.get("CohortCode", cohort_code)).strip() or cohort_code,
                    "year":        str(row.get("Year", year)).strip() or str(year),
                    "_manual_sn":  str(row.get("SerialNumber", "")).strip(),
                }
                if not rec["first_name"] and not rec["surname"]:
                    continue
                err = validate_row(rec)
                if err:
                    errors.append(f"Row {idx + 2}: {err}")
                else:
                    records.append(rec)

            for e in errors:
                st.warning(e)

            if records:
                # Preview
                simulated = simulate_serials(records)
                preview   = []
                for rec, (sn_p, src) in zip(records, simulated):
                    cid = f"RK-{rec['cohort_code']}-{rec['year']}-{sn_p:03d}"
                    preview.append({
                        "Full Name":        f"{rec['first_name']} {rec['surname']}",
                        "Certificate Type": rec["cert_type"],
                        "Duration":         rec["duration"],
                        "Serial #":         f"{sn_p:03d}",
                        "Source":           src,
                        "Certificate ID":   cid,
                    })
                st.markdown(f"**✅ {len(records)} valid record(s) ready.**")
                st.dataframe(pd.DataFrame(preview), use_container_width=True, hide_index=True)

                # Generate button
                if st.button("🎓 Generate All Certificates", type="primary", key="gen_csv"):
                    with st.spinner(f"Generating {len(records)} certificate(s)..."):
                        try:
                            zip_bytes = make_zip(records, issued_date_input, "dark")
                            st.session_state.csv_zip      = zip_bytes
                            st.session_state.csv_zip_name = (
                                f"ReKnew_Certs_{cohort_code}_{year}.zip"
                            )
                        except Exception as e:
                            st.error(f"Generation failed: {e}")
                            st.session_state.csv_zip = None

                # Download — persists across reruns
                if st.session_state.csv_zip is not None:
                    st.success(f"✅ {len(records)} certificate(s) generated!")
                    st.download_button(
                        label     = "⬇️ Download ZIP",
                        data      = st.session_state.csv_zip,
                        file_name = st.session_state.csv_zip_name,
                        mime      = "application/zip",
                        key       = "dl_csv",
                    )

            else:
                st.error("No valid records found in the file.")

        except Exception as e:
            st.error(f"Error reading file: {e}")
            st.exception(e)

    st.markdown("---")
    st.caption("💡 Tip: Leave SerialNumber blank in your CSV to auto-assign.")
