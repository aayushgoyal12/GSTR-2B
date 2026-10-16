import re
import difflib
import pandas as pd
from typing import Dict, Any
from parsers import is_valid_gstin, is_valid_pan

def check_payment_status(status: Any) -> bool:
    """Accurately detects paid status without falsely matching 'OPEN' on 'P'."""
    if pd.isna(status) or not status:
        return False
    val = str(status).strip().upper()
    if val in {"PAID", "CLEARED", "CLR", "P", "C", "YES", "SETTLED"}:
        return True
    return bool(re.search(r'\b(PAID|CLEARED|SETTLED|POSTED)\b', val))

def run_all_checks(
    vendors: pd.DataFrame,
    invoices: pd.DataFrame,
    date_window_days: int = 7,
    dormant_days: int = 180,
    fuzzy_name_cutoff: float = 0.85
) -> Dict[str, pd.DataFrame]:
    """
    Executes forensic audit checks on SAP Vendor Master and Invoice Line Items.
    Returns categorized risk DataFrames with review status tracking.
    """
    # 1. Defensive column validation & date parsing for vendors
    vendors_work = vendors.copy()
    for col in ["vendor_code", "vendor_name", "gstin", "pan", "bank_account", "ifsc", "creation_date"]:
        if col not in vendors_work.columns:
            vendors_work[col] = ""
    vendors_work["creation_date"] = pd.to_datetime(vendors_work["creation_date"], errors="coerce")

    # 2. Defensive column validation & strict datetime conversion for invoices
    inv_work = invoices.copy().reset_index(drop=True)
    for col in ["vendor_code", "invoice_reference", "document_number", "invoice_date", "posting_date", "amount", "payment_status", "norm_ref"]:
        if col not in inv_work.columns:
            inv_work[col] = "" if col != "amount" else 0.0

    # Ensure invoice_date and posting_date are parsed as Timestamp objects
    inv_work["invoice_date"] = pd.to_datetime(inv_work["invoice_date"], errors="coerce")
    inv_work["posting_date"] = pd.to_datetime(inv_work["posting_date"], errors="coerce")
    inv_work["amount"] = pd.to_numeric(inv_work["amount"], errors="coerce").fillna(0.0).round(2)
    inv_work["is_paid"] = inv_work["payment_status"].apply(check_payment_status)

    # -------------------------------------------------------------
    # CHECK A: Duplicate Invoices
    # -------------------------------------------------------------
    duplicates_records = []
    seen_exact_pairs = set()

    # Rule A1: Same Vendor + Same Normalized Invoice Number
    exact_dups = inv_work[inv_work["norm_ref"] != ""].copy()
    if not exact_dups.empty:
        grouped_exact = exact_dups.groupby(["vendor_code", "norm_ref"])
        for (v_code, norm_ref), group in grouped_exact:
            if len(group) > 1:
                sorted_grp = group.sort_values(by="invoice_date")
                for idx in range(1, len(sorted_grp)):
                    orig_row = sorted_grp.iloc[0]
                    dup_row = sorted_grp.iloc[idx]
                    pair_key = tuple(sorted([str(orig_row["document_number"]), str(dup_row["document_number"])]))
                    seen_exact_pairs.add(pair_key)

                    paid_status = "Both Paid (Realized Loss)" if (orig_row["is_paid"] and dup_row["is_paid"]) else (
                        "One Paid, One Open (Action Required)" if (orig_row["is_paid"] or dup_row["is_paid"]) else "Both Open"
                    )

                    duplicates_records.append({
                        "vendor_code": v_code,
                        "original_doc_no": orig_row["document_number"],
                        "duplicate_doc_no": dup_row["document_number"],
                        "original_ref": orig_row["invoice_reference"],
                        "duplicate_ref": dup_row["invoice_reference"],
                        "normalized_ref": norm_ref,
                        "original_date": orig_row["invoice_date"].strftime("%Y-%m-%d") if pd.notna(orig_row["invoice_date"]) else "",
                        "duplicate_date": dup_row["invoice_date"].strftime("%Y-%m-%d") if pd.notna(dup_row["invoice_date"]) else "",
                        "amount": dup_row["amount"],
                        "duplicate_type": "Exact Normalized Reference",
                        "payment_state": paid_status,
                        "confidence": "High (100%)",
                        "risk_level": "High",
                        "risk_reason": "Identical normalized reference billed under same vendor code",
                        "review_status": "Pending",
                        "review_notes": ""
                    })

    # Rule A2: Same Vendor + Same Amount + Invoice Date within Window (Different Reference)
    if not inv_work.empty:
        grouped_vendor = inv_work.groupby("vendor_code")
        for v_code, group in grouped_vendor:
            if len(group) < 2:
                continue
            sorted_v = group.sort_values(by="invoice_date").reset_index(drop=True)
            for i in range(len(sorted_v)):
                for j in range(i + 1, len(sorted_v)):
                    row_a = sorted_v.iloc[i]
                    row_b = sorted_v.iloc[j]
                    pair_key = tuple(sorted([str(row_a["document_number"]), str(row_b["document_number"])]))

                    if pair_key in seen_exact_pairs:
                        continue

                    if row_a["amount"] == row_b["amount"] and row_a["amount"] > 0:
                        dt_a = row_a["invoice_date"]
                        dt_b = row_b["invoice_date"]

                        if pd.notna(dt_a) and pd.notna(dt_b):
                            days_diff = abs((dt_b - dt_a).days)
                            if days_diff <= date_window_days:
                                paid_status = "Both Paid (Realized Loss)" if (row_a["is_paid"] and row_b["is_paid"]) else (
                                    "One Paid, One Open (Action Required)" if (row_a["is_paid"] or row_b["is_paid"]) else "Both Open"
                                )
                                duplicates_records.append({
                                    "vendor_code": v_code,
                                    "original_doc_no": row_a["document_number"],
                                    "duplicate_doc_no": row_b["document_number"],
                                    "original_ref": row_a["invoice_reference"],
                                    "duplicate_ref": row_b["invoice_reference"],
                                    "normalized_ref": f"{row_a['norm_ref']} vs {row_b['norm_ref']}",
                                    "original_date": dt_a.strftime("%Y-%m-%d"),
                                    "duplicate_date": dt_b.strftime("%Y-%m-%d"),
                                    "amount": row_b["amount"],
                                    "duplicate_type": f"Same Amount within {days_diff} Days",
                                    "payment_state": paid_status,
                                    "confidence": "Medium (Potential duplicate under reissued bill no)",
                                    "risk_level": "Medium",
                                    "risk_reason": f"Same amount ₹{row_b['amount']:,.2f} within {days_diff} days under different ref",
                                    "review_status": "Pending",
                                    "review_notes": ""
                                })

    df_check_a = pd.DataFrame(duplicates_records)

    # -------------------------------------------------------------
    # CHECK B: Possible Duplicate Across Different Vendor Codes
    # -------------------------------------------------------------
    dup_vendors = []
    v_clean = vendors_work[vendors_work["vendor_code"].astype(str).str.strip() != ""].copy()

    # Sub-check B1: Shared GSTIN
    if not v_clean.empty and "gstin" in v_clean.columns:
        valid_gstin_vendors = v_clean[v_clean["gstin"].apply(is_valid_gstin)]
        if not valid_gstin_vendors.empty:
            for gstin_val, g_grp in valid_gstin_vendors.groupby("gstin"):
                if len(g_grp["vendor_code"].unique()) > 1:
                    dup_vendors.append({
                        "match_type": "Identical GSTIN",
                        "identifier": gstin_val,
                        "vendor_codes": ", ".join(g_grp["vendor_code"].unique()),
                        "vendor_names": ", ".join(g_grp["vendor_name"].unique()),
                        "risk_level": "High",
                        "risk_reason": "Multiple SAP vendor codes assigned to identical GSTIN entity",
                        "review_status": "Pending",
                        "review_notes": ""
                    })

    # Sub-check B2: Shared PAN
    if not v_clean.empty and "pan" in v_clean.columns:
        valid_pan_vendors = v_clean[v_clean["pan"].apply(is_valid_pan)]
        if not valid_pan_vendors.empty:
            for pan_val, p_grp in valid_pan_vendors.groupby("pan"):
                if len(p_grp["vendor_code"].unique()) > 1:
                    dup_vendors.append({
                        "match_type": "Identical PAN",
                        "identifier": pan_val,
                        "vendor_codes": ", ".join(p_grp["vendor_code"].unique()),
                        "vendor_names": ", ".join(p_grp["vendor_name"].unique()),
                        "risk_level": "High",
                        "risk_reason": "Same corporate PAN used across multiple SAP vendor master entries",
                        "review_status": "Pending",
                        "review_notes": ""
                    })

    # Sub-check B3: Fuzzy Name Matches
    if not v_clean.empty:
        vendor_list = v_clean[["vendor_code", "vendor_name"]].drop_duplicates().to_dict("records")
        for i in range(len(vendor_list)):
            for j in range(i + 1, len(vendor_list)):
                v1 = vendor_list[i]
                v2 = vendor_list[j]
                if v1["vendor_code"] != v2["vendor_code"] and v1["vendor_name"] and v2["vendor_name"]:
                    sim = difflib.SequenceMatcher(None, str(v1["vendor_name"]).lower(), str(v2["vendor_name"]).lower()).ratio()
                    if sim >= fuzzy_name_cutoff:
                        dup_vendors.append({
                            "match_type": f"Fuzzy Name Similarity ({int(sim*100)}%)",
                            "identifier": f"{v1['vendor_name']} ~ {v2['vendor_name']}",
                            "vendor_codes": f"{v1['vendor_code']}, {v2['vendor_code']}",
                            "vendor_names": f"{v1['vendor_name']} | {v2['vendor_name']}",
                            "risk_level": "Medium",
                            "risk_reason": "Slightly varied vendor spelling created under separate codes",
                            "review_status": "Pending",
                            "review_notes": ""
                        })

    df_check_b = pd.DataFrame(dup_vendors).drop_duplicates(subset=["identifier", "vendor_codes"]) if dup_vendors else pd.DataFrame(columns=[
        "match_type", "identifier", "vendor_codes", "vendor_names", "risk_level", "risk_reason", "review_status", "review_notes"
    ])

    # -------------------------------------------------------------
    # CHECK C: Shared Bank Accounts
    # -------------------------------------------------------------
    shared_bank_records = []
    if not v_clean.empty and "bank_account" in v_clean.columns:
        valid_bank_vendors = v_clean[v_clean["bank_account"].astype(str).str.strip() != ""]
        if not valid_bank_vendors.empty:
            for bank_acc, b_grp in valid_bank_vendors.groupby("bank_account"):
                unique_codes = b_grp["vendor_code"].unique()
                if len(unique_codes) > 1:
                    shared_bank_records.append({
                        "bank_account": bank_acc,
                        "ifsc": ", ".join(b_grp["ifsc"].unique()),
                        "vendor_codes": ", ".join(unique_codes),
                        "vendor_names": ", ".join(b_grp["vendor_name"].unique()),
                        "vendor_count": len(unique_codes),
                        "risk_level": "High",
                        "risk_reason": "Multiple distinct vendors routing disbursements to identical bank account (Ghost vendor / collusion risk)",
                        "review_status": "Pending",
                        "review_notes": ""
                    })
    df_check_c = pd.DataFrame(shared_bank_records) if shared_bank_records else pd.DataFrame(columns=[
        "bank_account", "ifsc", "vendor_codes", "vendor_names", "vendor_count", "risk_level", "risk_reason", "review_status", "review_notes"
    ])

    # -------------------------------------------------------------
    # CHECK D: Master Data Quality
    # -------------------------------------------------------------
    quality_issues = []
    valid_dates_series = inv_work["invoice_date"].dropna()
    max_inv_date = valid_dates_series.max() if not valid_dates_series.empty else pd.Timestamp.now()
    active_vendor_codes = set(inv_work["vendor_code"].unique())
    
    last_trx_map = {}
    if not inv_work.empty and not valid_dates_series.empty:
        last_trx_map = inv_work.dropna(subset=["invoice_date"]).groupby("vendor_code")["invoice_date"].max().to_dict()

    for _, v_row in v_clean.iterrows():
        v_code = str(v_row["vendor_code"]).strip()
        v_name = str(v_row["vendor_name"]).strip()
        gstin_val = str(v_row["gstin"]).strip()
        pan_val = str(v_row["pan"]).strip()
        bank_val = str(v_row["bank_account"]).strip()

        # Missing / Invalid GSTIN
        if not gstin_val:
            quality_issues.append({
                "vendor_code": v_code,
                "vendor_name": v_name,
                "field_flagged": "GSTIN",
                "issue_type": "Missing GSTIN",
                "risk_level": "Medium",
                "risk_reason": "Vendor master lacks statutory GSTIN; risks input tax credit denial",
                "review_status": "Pending",
                "review_notes": ""
            })
        elif not is_valid_gstin(gstin_val):
            quality_issues.append({
                "vendor_code": v_code,
                "vendor_name": v_name,
                "field_flagged": "GSTIN",
                "issue_type": "Invalid GSTIN Format",
                "risk_level": "High",
                "risk_reason": f"GSTIN '{gstin_val}' violates 15-character statutory format",
                "review_status": "Pending",
                "review_notes": ""
            })

        # Missing / Invalid PAN
        if not pan_val:
            quality_issues.append({
                "vendor_code": v_code,
                "vendor_name": v_name,
                "field_flagged": "PAN",
                "issue_type": "Missing PAN",
                "risk_level": "Medium",
                "risk_reason": "Missing PAN triggers higher TDS rate (Section 206AA)",
                "review_status": "Pending",
                "review_notes": ""
            })
        elif not is_valid_pan(pan_val):
            quality_issues.append({
                "vendor_code": v_code,
                "vendor_name": v_name,
                "field_flagged": "PAN",
                "issue_type": "Invalid PAN Format",
                "risk_level": "High",
                "risk_reason": f"PAN '{pan_val}' violates 10-character alphanumeric syntax",
                "review_status": "Pending",
                "review_notes": ""
            })

        # Missing Bank Account Details
        if not bank_val:
            quality_issues.append({
                "vendor_code": v_code,
                "vendor_name": v_name,
                "field_flagged": "Bank Account",
                "issue_type": "Missing Bank Details",
                "risk_level": "Medium",
                "risk_reason": "Bank account absent in vendor master",
                "review_status": "Pending",
                "review_notes": ""
            })

        # Dormancy Check
        if v_code not in active_vendor_codes:
            quality_issues.append({
                "vendor_code": v_code,
                "vendor_name": v_name,
                "field_flagged": "Transactions",
                "issue_type": "Dormant (Zero Transactions)",
                "risk_level": "Low",
                "risk_reason": "No invoice line items found in transactional export",
                "review_status": "Pending",
                "review_notes": ""
            })
        else:
            last_date = last_trx_map.get(v_code)
            if pd.notna(last_date) and (max_inv_date - last_date).days > dormant_days:
                quality_issues.append({
                    "vendor_code": v_code,
                    "vendor_name": v_name,
                    "field_flagged": "Transactions",
                    "issue_type": f"Dormant (>{dormant_days} Days Inactive)",
                    "risk_level": "Low",
                    "risk_reason": f"Inactive for {(max_inv_date - last_date).days} days since last transaction on {last_date.strftime('%Y-%m-%d')}",
                    "review_status": "Pending",
                    "review_notes": ""
                })

    df_check_d = pd.DataFrame(quality_issues) if quality_issues else pd.DataFrame(columns=[
        "vendor_code", "vendor_name", "field_flagged", "issue_type", "risk_level", "risk_reason", "review_status", "review_notes"
    ])

    # -------------------------------------------------------------
    # CHECK E: Invoice Reference > 16 Characters (SAP XBLNR Limit)
    # -------------------------------------------------------------
    truncated_records = []
    for _, inv_row in inv_work.iterrows():
        raw_ref = str(inv_row["invoice_reference"]).strip()
        if len(raw_ref) > 16:
            truncated_records.append({
                "vendor_code": inv_row["vendor_code"],
                "document_number": inv_row["document_number"],
                "invoice_reference": raw_ref,
                "char_length": len(raw_ref),
                "invoice_date": inv_row["invoice_date"].strftime("%Y-%m-%d") if pd.notna(inv_row["invoice_date"]) else "",
                "amount": inv_row["amount"],
                "risk_level": "High",
                "risk_reason": f"Reference length ({len(raw_ref)} chars) exceeds SAP's 16-char limit (BKPF-XBLNR). Truncation risks duplicate payments.",
                "review_status": "Pending",
                "review_notes": ""
            })
    df_check_e = pd.DataFrame(truncated_records) if truncated_records else pd.DataFrame(columns=[
        "vendor_code", "document_number", "invoice_reference", "char_length", "invoice_date", "amount", "risk_level", "risk_reason", "review_status", "review_notes"
    ])

    return {
        "duplicates": df_check_a,
        "duplicate_vendors": df_check_b,
        "shared_banks": df_check_c,
        "master_quality": df_check_d,
        "truncated_refs": df_check_e
    }