import streamlit as st
import pandas as pd
from typing import Dict, Any

from parsers import (
    standardize_vendor_master,
    standardize_invoice_items,
    mask_vendor_name,
    mask_gstin,
    mask_bank_acc
)
from checks import run_all_checks
from sample_data import generate_fictional_datasets
from report import generate_excel_risk_report

st.set_page_config(
    page_title="Forensic Audit Radar for SAP Exports",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------- STYLING -----------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

    .stApp {
        background-color: #080D1A;
        color: #E2E8F0;
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    .partner-banner {
        background: linear-gradient(90deg, #0F172A 0%, #1E293B 100%);
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 12px;
        padding: 22px 28px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.5);
    }
    .badge-statutory {
        background-color: #0369A1;
        color: #E0F2FE;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 20px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        display: inline-block;
        margin-bottom: 8px;
    }
    .banner-title {
        font-size: 1.7rem;
        font-weight: 800;
        color: #F8FAFC;
        letter-spacing: -0.02em;
        margin: 0;
    }
    .banner-sub {
        font-size: 0.88rem;
        color: #94A3B8;
        margin-top: 6px;
    }
    .metric-card {
        background: #0E1626;
        border: 1px solid #1E293B;
        border-radius: 10px;
        padding: 16px 20px;
        position: relative;
    }
    .metric-card.danger {
        border-left: 4px solid #EF4444;
        background: linear-gradient(180deg, #181524 0%, #0E1626 100%);
    }
    .metric-card.warning {
        border-left: 4px solid #F59E0B;
        background: linear-gradient(180deg, #1C181C 0%, #0E1626 100%);
    }
    .metric-card.success {
        border-left: 4px solid #10B981;
    }
    .kpi-tag {
        font-size: 0.72rem;
        font-weight: 700;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    .kpi-value {
        font-size: 1.7rem;
        font-weight: 800;
        color: #FFFFFF;
        font-family: 'JetBrains Mono', monospace;
        margin: 4px 0 2px 0;
    }
    .kpi-sub {
        font-size: 0.8rem;
        color: #38BDF8;
        font-weight: 500;
    }
    .ca-sidebar-card {
        background: #0F172A;
        border: 1px solid #1E293B;
        border-radius: 8px;
        padding: 14px;
        font-size: 0.82rem;
        color: #94A3B8;
        line-height: 1.45;
        margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- SESSION STATE -----------------
for key in [
    "vendor_raw", "invoice_raw", "vendors_std", "invoices_std", 
    "vendor_mapping", "invoice_mapping", "sample_loaded", "firm_name"
]:
    if key not in st.session_state:
        st.session_state[key] = "" if key == "firm_name" else None

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.markdown("### ⚖️ Practice Workstation")
    st.caption("Forensic Audit & CARO 2020 Radar")
    st.markdown("---")

    st.markdown("#### 🏢 CA Firm White-Labeling")
    firm_input = st.text_input("Your CA Practice / Firm Name", value="K. Goyal & Associates", help="Personalizes dashboard and Excel audit schedules for client presentation.")
    st.session_state["firm_name"] = firm_input

    st.markdown("---")
    st.markdown("#### 🔒 Client Isolation & Privacy")
    st.markdown("""
    <div class="ca-sidebar-card">
        <b>Strict In-Memory Analysis:</b><br>
        • Zero disk caching or server logging.<br>
        • Meets ICAI confidentiality standards.<br>
        • All records clear upon tab disconnect.
    </div>
    """, unsafe_allow_html=True)

    mask_toggle = st.toggle("Mask Client Confidential Data", value=False, help="Obfuscates names, GSTINs, and accounts for screen-sharing.")

    st.markdown("---")
    st.markdown("#### ⚙️ Parameters")
    date_window = st.number_input("Duplicate Date Window (Days)", min_value=1, max_value=60, value=7, step=1)
    dormant_period = st.number_input("Dormancy Threshold (Days)", min_value=30, max_value=730, value=180, step=30)
    fuzzy_name_sim = st.slider("Fuzzy Vendor Similarity (%)", min_value=70, max_value=98, value=85, step=1) / 100.0

# ----------------- MAIN TOP BANNER -----------------
display_firm = st.session_state["firm_name"] if st.session_state["firm_name"] else "Chartered Accountants & Internal Auditors"
st.markdown(f"""
<div class="partner-banner">
    <div class="badge-statutory">Prepared for: {display_firm} • CARO 2020 & SA 240 Compliance</div>
    <div class="banner-title">SAP Vendor & Payment Forensic Risk Radar</div>
    <div class="banner-sub">Automated screening for duplicate payments, ghost accounts, shared bank details, and statutory control breakdowns.</div>
</div>
""", unsafe_allow_html=True)

# ----------------- HERO DEMO BUTTON -----------------
demo_col1, demo_col2 = st.columns([2, 1])
with demo_col1:
    if st.button("🚀 Launch Live Audit Simulation (Instant Fictional SAP Data)", type="primary", use_container_width=True):
        v_sample, i_sample = generate_fictional_datasets()
        st.session_state["vendor_raw"] = v_sample
        st.session_state["invoice_raw"] = i_sample
        st.session_state["vendors_std"] = v_sample
        st.session_state["invoices_std"] = i_sample
        st.session_state["sample_loaded"] = True
        st.rerun()
with demo_col2:
    st.caption("👈 Click to simulate an audit with 25 vendors & 60 invoices without uploading manual files.")

st.markdown("<br>", unsafe_allow_html=True)

# ----------------- MANUAL FILE UPLOADS -----------------
c_up1, c_up2 = st.columns(2)
with c_up1:
    st.markdown("##### 1. SAP Vendor Master (LFA1 / LFBK)")
    v_file = st.file_uploader("Upload Vendor Master (XLSX / CSV)", type=["xlsx", "xls", "csv"], key="v_upload", label_visibility="collapsed")
    if v_file:
        try:
            st.session_state["vendor_raw"] = pd.read_csv(v_file) if v_file.name.endswith(".csv") else pd.read_excel(v_file)
            st.session_state["sample_loaded"] = False
            st.session_state["vendors_std"] = None
        except Exception as e:
            st.error(f"Error parsing Vendor Master: {e}")

with c_up2:
    st.markdown("##### 2. SAP Invoice Line Items (FBL1N / BSAK)")
    i_file = st.file_uploader("Upload Invoice Items (XLSX / CSV)", type=["xlsx", "xls", "csv"], key="i_upload", label_visibility="collapsed")
    if i_file:
        try:
            st.session_state["invoice_raw"] = pd.read_csv(i_file) if i_file.name.endswith(".csv") else pd.read_excel(i_file)
            st.session_state["sample_loaded"] = False
            st.session_state["invoices_std"] = None
        except Exception as e:
            st.error(f"Error parsing Invoice Items: {e}")

# Helper for column matching
def match_col(cols, target_keywords):
    for c in cols:
        for k in target_keywords:
            if k.lower() in str(c).lower():
                return c
    return "-- Select Column --"

# ----------------- COLUMN MAPPING -----------------
if st.session_state["vendor_raw"] is not None and st.session_state["vendors_std"] is None:
    st.markdown("---")
    st.markdown("#### 📐 Map SAP Vendor Master Headers")
    v_cols = ["-- Select Column --"] + list(st.session_state["vendor_raw"].columns)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        map_v_code = st.selectbox("Vendor Code (LIFNR) *", v_cols, index=v_cols.index(match_col(v_cols, ["vendor_code", "lifnr", "vendor code", "account"])))
        map_v_pan = st.selectbox("PAN (J_1IPANNO)", v_cols, index=v_cols.index(match_col(v_cols, ["pan", "j_1ipanno"])))
    with col2:
        map_v_name = st.selectbox("Vendor Name (NAME1) *", v_cols, index=v_cols.index(match_col(v_cols, ["vendor_name", "name1", "supplier"])))
        map_v_bank = st.selectbox("Bank Account (BANKN)", v_cols, index=v_cols.index(match_col(v_cols, ["bank_account", "bankn", "account no"])))
    with col3:
        map_v_addr = st.selectbox("Address (STRAS)", v_cols, index=v_cols.index(match_col(v_cols, ["address", "stras", "city"])))
        map_v_ifsc = st.selectbox("IFSC / Bank Key (BANKL)", v_cols, index=v_cols.index(match_col(v_cols, ["ifsc", "bankl", "bank key"])))
    with col4:
        map_v_gstin = st.selectbox("GSTIN (STCEG)", v_cols, index=v_cols.index(match_col(v_cols, ["gstin", "stceg", "tax number 3"])))
        map_v_date = st.selectbox("Creation Date (ERDAT)", v_cols, index=v_cols.index(match_col(v_cols, ["creation_date", "erdat", "created on"])))

    if st.button("Confirm Vendor Mapping", type="primary"):
        if map_v_code == "-- Select Column --" or map_v_name == "-- Select Column --":
            st.error("Mandatory fields: Vendor Code and Vendor Name must be selected.")
        else:
            v_map = {
                "vendor_code": map_v_code, "vendor_name": map_v_name, "address": map_v_addr,
                "gstin": map_v_gstin, "pan": map_v_pan, "bank_account": map_v_bank,
                "ifsc": map_v_ifsc, "creation_date": map_v_date
            }
            st.session_state["vendor_mapping"] = v_map
            st.session_state["vendors_std"] = standardize_vendor_master(st.session_state["vendor_raw"], v_map)
            st.rerun()

if st.session_state["invoice_raw"] is not None and st.session_state["invoices_std"] is None:
    st.markdown("---")
    st.markdown("#### 📐 Map SAP Invoice Line Items Headers")
    i_cols = ["-- Select Column --"] + list(st.session_state["invoice_raw"].columns)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        map_i_code = st.selectbox("Vendor Code (LIFNR) *", i_cols, index=i_cols.index(match_col(i_cols, ["vendor_code", "lifnr", "vendor code", "account"])))
        map_i_doc = st.selectbox("Document Number (BELNR) *", i_cols, index=i_cols.index(match_col(i_cols, ["document_number", "belnr", "doc no"])))
    with c2:
        map_i_ref = st.selectbox("Invoice Reference (XBLNR) *", i_cols, index=i_cols.index(match_col(i_cols, ["invoice_reference", "xblnr", "bill no"])))
        map_i_amt = st.selectbox("Amount (WRBTR / DMBTR) *", i_cols, index=i_cols.index(match_col(i_cols, ["amount", "wrbtr", "dmbtr", "val"])))
    with c3:
        map_i_date = st.selectbox("Invoice Date (BLDAT)", i_cols, index=i_cols.index(match_col(i_cols, ["invoice_date", "bldat"])))
        map_i_status = st.selectbox("Payment Status / Clearing Date", i_cols, index=i_cols.index(match_col(i_cols, ["payment_status", "augdt", "clearing"])))
    with c4:
        map_i_post = st.selectbox("Posting Date (BUDAT)", i_cols, index=i_cols.index(match_col(i_cols, ["posting_date", "budat"])))

    if st.button("Confirm Invoice Mapping", type="primary"):
        if map_i_code == "-- Select Column --" or map_i_ref == "-- Select Column --" or map_i_amt == "-- Select Column --" or map_i_doc == "-- Select Column --":
            st.error("Mandatory fields: Vendor Code, Document Number, Invoice Reference, and Amount must be selected.")
        else:
            i_map = {
                "vendor_code": map_i_code, "invoice_reference": map_i_ref, "invoice_date": map_i_date,
                "posting_date": map_i_post, "amount": map_i_amt, "document_number": map_i_doc,
                "payment_status": map_i_status
            }
            st.session_state["invoice_mapping"] = i_map
            st.session_state["invoices_std"] = standardize_invoice_items(st.session_state["invoice_raw"], i_map)
            st.rerun()

# ----------------- RISK WORKSTATION RESULTS -----------------
if st.session_state["vendors_std"] is not None and st.session_state["invoices_std"] is not None:
    vendors_clean = st.session_state["vendors_std"]
    invoices_clean = st.session_state["invoices_std"]

    results = run_all_checks(
        vendors_clean, 
        invoices_clean, 
        date_window_days=date_window, 
        dormant_days=dormant_period, 
        fuzzy_name_cutoff=fuzzy_name_sim
    )

    dups = results["duplicates"]
    shared_b = results["shared_banks"]
    dup_v = results["duplicate_vendors"]
    qual = results["master_quality"]
    trunc = results["truncated_refs"]

    realized_loss = dups[dups["payment_state"].str.contains("Both Paid", na=False)]["amount"].sum() if not dups.empty else 0.0
    preventable_risk = dups[~dups["payment_state"].str.contains("Both Paid", na=False)]["amount"].sum() if not dups.empty else 0.0

    st.markdown("---")

    # Executive Summary Cards
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div class="metric-card danger">
            <div class="kpi-tag">🚨 Double-Paid (Realized Loss)</div>
            <div class="kpi-value" style="color: #F87171;">₹{realized_loss:,.2f}</div>
            <div class="kpi-sub">Direct Cash Recovery Candidate</div>
        </div>
        """, unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div class="metric-card warning">
            <div class="kpi-tag">⚠️ Stop-Payment Required</div>
            <div class="kpi-value" style="color: #FBBF24;">₹{preventable_risk:,.2f}</div>
            <div class="kpi-sub">{len(dups[dups['payment_state'].str.contains('One Paid|Both Open', na=False)])} Unpaid Vouchers At Risk</div>
        </div>
        """, unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="kpi-tag">🏦 Shared Bank / Ghost Accounts</div>
            <div class="kpi-value">{len(shared_b)}</div>
            <div class="kpi-sub">CARO 2020 Clause (xi) Red Flag</div>
        </div>
        """, unsafe_allow_html=True)
    with k4:
        st.markdown(f"""
        <div class="metric-card success">
            <div class="kpi-tag">📋 Master & Reference Flaws</div>
            <div class="kpi-value">{len(qual) + len(trunc)}</div>
            <div class="kpi-sub">Sec 206AA TDS & Truncation Errors</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Action bar
    act_c1, act_c2 = st.columns([3, 1])
    with act_c1:
        st.markdown(f"**Audit Working Papers for {display_firm}** — Review exceptions below, assign audit disposition, and export certified report.")
    with act_c2:
        excel_bytes = generate_excel_risk_report(results, mask_confidential=mask_toggle)
        st.download_button(
            label="📥 Export Certified Working Paper (Excel)",
            data=excel_bytes,
            file_name=f"{display_firm.replace(' ', '_')}_SAP_Audit_Schedule.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # Tabs
    tabs = st.tabs([
        f"🚨 Duplicate Invoices ({len(dups)})",
        f"🏦 Shared Bank Accounts ({len(shared_b)})",
        f"⚠️ Duplicate Vendor Masters ({len(dup_v)})",
        f"📋 Master Data Flaws ({len(qual)})",
        f"📏 Truncated References >16 ({len(trunc)})"
    ])

    def render_ca_grid(df_raw: pd.DataFrame, key_suffix: str):
        if df_raw.empty:
            st.success("✅ Clean: Zero statutory audit anomalies identified under this check.")
            return

        df_display = df_raw.copy()
        if mask_toggle:
            for n_col in ["vendor_name", "vendor_names"]:
                if n_col in df_display.columns:
                    df_display[n_col] = df_display[n_col].apply(mask_vendor_name)
            for g_col in ["gstin"]:
                if g_col in df_display.columns:
                    df_display[g_col] = df_display[g_col].apply(mask_gstin)
            for b_col in ["bank_account"]:
                if b_col in df_display.columns:
                    df_display[b_col] = df_display[b_col].apply(mask_bank_acc)

        f1, f2 = st.columns([1, 2])
        with f1:
            risk_filter = st.multiselect(
                "Filter Risk Level",
                options=df_display["risk_level"].unique().tolist(),
                default=df_display["risk_level"].unique().tolist(),
                key=f"risk_flt_{key_suffix}"
            )
        with f2:
            status_filter = st.multiselect(
                "Audit Review Disposition",
                options=["Pending", "Genuine", "Duplicate confirmed", "Follow up"],
                default=["Pending", "Genuine", "Duplicate confirmed", "Follow up"],
                key=f"stat_flt_{key_suffix}"
            )

        filtered = df_display[
            df_display["risk_level"].isin(risk_filter) &
            df_display["review_status"].isin(status_filter)
        ]

        status_config = {
            "review_status": st.column_config.SelectboxColumn(
                "Audit Disposition",
                options=["Pending", "Genuine", "Duplicate confirmed", "Follow up"],
                required=True,
            ),
            "review_notes": st.column_config.TextColumn(
                "Working Paper Notes",
                help="Enter vouching justification or recovery reference",
                width="medium"
            ),
            "risk_level": st.column_config.TextColumn("Risk", width="small")
        }
        if "amount" in filtered.columns:
            status_config["amount"] = st.column_config.NumberColumn("Exposure (₹)", format="₹%.2f")

        st.data_editor(
            filtered,
            column_config=status_config,
            disabled=[c for c in filtered.columns if c not in ["review_status", "review_notes"]],
            use_container_width=True,
            key=f"editor_{key_suffix}"
        )

    with tabs[0]:
        st.caption("Identifies identical invoices billed twice (e.g. INV/001 vs INV-1) or re-invoiced within date window. 'Both Paid' items represent immediate recovery candidates.")
        render_ca_grid(dups, "dups")

    with tabs[1]:
        st.caption("Multiple distinct vendor codes routing disbursements to identical bank accounts. High-risk indicator of employee-vendor collusion, ghost vendors, or kickbacks.")
        render_ca_grid(shared_b, "shared_b")

    with tabs[2]:
        st.caption("Multiple SAP vendor accounts registered under identical GSTIN, PAN, or high fuzzy name similarity. Bypasses credit limits and causes reporting errors.")
        render_ca_grid(dup_v, "dup_v")

    with tabs[3]:
        st.caption("Statutory syntax validation for GSTIN & PAN (Sec 206AA Higher TDS exposure), missing bank masters, and dormant vendors inactive for 180+ days.")
        render_ca_grid(qual, "qual")

    with tabs[4]:
        st.caption("Reference numbers exceeding SAP's 16-character limit (BKPF-XBLNR). Truncated references consistently bypass SAP's native duplicate checks.")
        render_ca_grid(trunc, "trunc")