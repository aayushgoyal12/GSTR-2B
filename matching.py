import difflib
import pandas as pd
from typing import Dict, Tuple
from parsers import normalize_invoice_number, is_valid_gstin

def run_reconciliation(
    sap_df: pd.DataFrame, 
    gstr2b_df: pd.DataFrame, 
    amt_tolerance: float = 1.0, 
    fuzzy_cutoff: float = 0.80
) -> Dict[str, pd.DataFrame]:
    """
    Executes exhaustive reconciliation between SAP Books and GSTR-2B.
    Produces zero auto-approvals; every item is assigned a Review Status.
    """
    # Defensive copies with original indexes preserved
    books = sap_df.copy().reset_index(drop=True)
    g2b = gstr2b_df.copy().reset_index(drop=True)

    books["norm_inv"] = books["invoice_number"].apply(normalize_invoice_number)
    g2b["norm_inv"] = g2b["invoice_number"].apply(normalize_invoice_number)

    # 1. Validation rule: Check Invalid GSTINs in SAP Books
    invalid_gstin_mask = ~books["vendor_gstin"].apply(is_valid_gstin)
    invalid_gstin_df = books[invalid_gstin_mask].copy()
    invalid_gstin_df["issue_reason"] = "Invalid GSTIN format (does not match 15-digit PAN-based GST structure)"
    invalid_gstin_df["review_status"] = "Pending"

    # 2. Validation rule: Invoice Number > 16 Characters
    # (Section 31 of CGST Act / GST Rules specify invoice numbers cannot exceed 16 characters)
    inv_len_mask = books["invoice_number"].astype(str).str.len() > 16
    inv_too_long_df = books[inv_len_mask].copy()
    inv_too_long_df["issue_reason"] = "Invoice number length exceeds statutory 16-character limit"
    inv_too_long_df["review_status"] = "Pending"

    # 3. Duplicate checks in Books (Same GSTIN + same normalized invoice number booked > 1 time)
    books_clean_validation = books[~invalid_gstin_mask & ~inv_len_mask].copy()
    dup_mask = books_clean_validation.duplicated(subset=["vendor_gstin", "norm_inv"], keep=False)
    duplicate_books_df = books_clean_validation[dup_mask].copy()
    duplicate_books_df["issue_reason"] = "Duplicate booking in SAP books (same GSTIN & Invoice No entered multiple times)"
    duplicate_books_df["review_status"] = "Pending"

    # Eligible books records for reconciliation matching
    eligible_books = books_clean_validation[~dup_mask].copy()
    eligible_g2b = g2b.copy()

    # Tracking sets for matched row indices
    matched_books_idx = set()
    matched_g2b_idx = set()

    exact_matches = []
    amount_mismatches = []
    probable_matches = []

    # Map GSTR-2B by key: (vendor_gstin, norm_inv) -> list of row indices
    g2b_key_map = {}
    for idx, row in eligible_g2b.iterrows():
        key = (row["vendor_gstin"], row["norm_inv"])
        g2b_key_map.setdefault(key, []).append(idx)

    # STEP A: Exact Key Match [(GSTIN, Normalized Invoice)]
    for b_idx, b_row in eligible_books.iterrows():
        key = (b_row["vendor_gstin"], b_row["norm_inv"])
        if key in g2b_key_map:
            # Pick first unmatched GSTR-2B item under this key
            candidate_indices = [i for i in g2b_key_map[key] if i not in matched_g2b_idx]
            if candidate_indices:
                g_idx = candidate_indices[0]
                g_row = eligible_g2b.loc[g_idx]

                tax_diff = round(b_row["total_tax"] - g_row["total_tax"], 2)
                txval_diff = round(b_row["taxable_value"] - g_row["taxable_value"], 2)

                record = {
                    "vendor_gstin": b_row["vendor_gstin"],
                    "vendor_name": b_row["vendor_name"] or g_row["vendor_name"],
                    "sap_invoice_number": b_row["invoice_number"],
                    "g2b_invoice_number": g_row["invoice_number"],
                    "sap_date": b_row["invoice_date"],
                    "g2b_date": g_row["invoice_date"],
                    "sap_taxable": b_row["taxable_value"],
                    "g2b_taxable": g_row["taxable_value"],
                    "diff_taxable": txval_diff,
                    "sap_tax": b_row["total_tax"],
                    "g2b_tax": g_row["total_tax"],
                    "diff_tax": tax_diff,
                    "sap_igst": b_row["igst"],
                    "g2b_igst": g_row["igst"],
                    "sap_cgst": b_row["cgst"],
                    "g2b_cgst": g_row["cgst"],
                    "sap_sgst": b_row["sgst"],
                    "g2b_sgst": g_row["sgst"],
                    "review_status": "Pending"
                }

                if abs(tax_diff) <= amt_tolerance and abs(txval_diff) <= amt_tolerance:
                    exact_matches.append(record)
                else:
                    record["issue_reason"] = f"Tax diff: ₹{tax_diff:,.2f}, Taxable diff: ₹{txval_diff:,.2f}"
                    amount_mismatches.append(record)

                matched_books_idx.add(b_idx)
                matched_g2b_idx.add(g_idx)

    # STEP B: Probable Match (Same GSTIN, Fuzzy Invoice Number or Exact Amount)
    remaining_books_idx = [i for i in eligible_books.index if i not in matched_books_idx]
    remaining_g2b_idx = [i for i in eligible_g2b.index if i not in matched_g2b_idx]

    for b_idx in remaining_books_idx:
        b_row = eligible_books.loc[b_idx]
        b_gstin = b_row["vendor_gstin"]
        b_norm = b_row["norm_inv"]

        best_g_idx = None
        best_similarity = 0.0

        for g_idx in remaining_g2b_idx:
            if g_idx in matched_g2b_idx:
                continue
            g_row = eligible_g2b.loc[g_idx]

            if g_row["vendor_gstin"] == b_gstin:
                # String similarity ratio
                sim = difflib.SequenceMatcher(None, b_norm, g_row["norm_inv"]).ratio()
                if sim >= fuzzy_cutoff and sim > best_similarity:
                    best_similarity = sim
                    best_g_idx = g_idx

        if best_g_idx is not None:
            g_row = eligible_g2b.loc[best_g_idx]
            tax_diff = round(b_row["total_tax"] - g_row["total_tax"], 2)
            txval_diff = round(b_row["taxable_value"] - g_row["taxable_value"], 2)

            probable_matches.append({
                "vendor_gstin": b_row["vendor_gstin"],
                "vendor_name": b_row["vendor_name"] or g_row["vendor_name"],
                "sap_invoice_number": b_row["invoice_number"],
                "g2b_invoice_number": g_row["invoice_number"],
                "similarity_pct": f"{round(best_similarity * 100, 1)}%",
                "sap_date": b_row["invoice_date"],
                "g2b_date": g_row["invoice_date"],
                "sap_taxable": b_row["taxable_value"],
                "g2b_taxable": g_row["taxable_value"],
                "diff_taxable": txval_diff,
                "sap_tax": b_row["total_tax"],
                "g2b_tax": g_row["total_tax"],
                "diff_tax": tax_diff,
                "issue_reason": f"Likely typo in invoice number ({best_similarity*100:.0f}% match)",
                "review_status": "Pending"
            })
            matched_books_idx.add(b_idx)
            matched_g2b_idx.add(best_g_idx)

    # STEP C: In Books but Not in GSTR-2B (ITC At Risk - Supplier not filed)
    unmatched_books_idx = [i for i in eligible_books.index if i not in matched_books_idx]
    in_books_not_2b_df = eligible_books.loc[unmatched_books_idx].copy()
    in_books_not_2b_df["issue_reason"] = "Supplier omitted invoice in GSTR-1 / GSTR-2B; ITC at statutory risk (Rule 36(4))"
    in_books_not_2b_df["review_status"] = "Pending"

    # STEP D: In GSTR-2B but Not in Books (Unclaimed ITC / Omitted from SAP)
    unmatched_g2b_idx = [i for i in eligible_g2b.index if i not in matched_g2b_idx]
    in_2b_not_books_df = eligible_g2b.loc[unmatched_g2b_idx].copy()
    in_2b_not_books_df["issue_reason"] = "Appears in GSTR-2B but not booked in SAP purchase register; potential unavailed ITC"
    in_2b_not_books_df["review_status"] = "Pending"

    return {
        "exact_matches": pd.DataFrame(exact_matches),
        "amount_mismatches": pd.DataFrame(amount_mismatches),
        "probable_matches": pd.DataFrame(probable_matches),
        "books_only": in_books_not_2b_df,
        "g2b_only": in_2b_not_books_df,
        "duplicate_in_books": duplicate_books_df,
        "invalid_gstin": invalid_gstin_df,
        "inv_no_too_long": inv_too_long_df
    }

def generate_vendor_summary(results: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Consolidates mismatch exposure and status per vendor."""
    vendor_records = {}

    def get_entry(gstin, name=""):
        if gstin not in vendor_records:
            vendor_records[gstin] = {
                "vendor_gstin": gstin,
                "vendor_name": name,
                "total_invoices": 0,
                "exact_matched": 0,
                "amount_mismatched": 0,
                "probable_matched": 0,
                "itc_at_risk_count": 0,
                "itc_at_risk_amount": 0.0,
                "g2b_unclaimed_count": 0,
                "g2b_unclaimed_amount": 0.0,
                "compliance_issues": 0
            }
        if name and not vendor_records[gstin]["vendor_name"]:
            vendor_records[gstin]["vendor_name"] = name
        return vendor_records[gstin]

    # Exact
    if not results["exact_matches"].empty:
        for _, r in results["exact_matches"].iterrows():
            e = get_entry(r["vendor_gstin"], r.get("vendor_name", ""))
            e["total_invoices"] += 1
            e["exact_matched"] += 1

    # Amount mismatch
    if not results["amount_mismatches"].empty:
        for _, r in results["amount_mismatches"].iterrows():
            e = get_entry(r["vendor_gstin"], r.get("vendor_name", ""))
            e["total_invoices"] += 1
            e["amount_mismatched"] += 1
            e["itc_at_risk_amount"] += max(0.0, r.get("diff_tax", 0.0))

    # Probable match
    if not results["probable_matches"].empty:
        for _, r in results["probable_matches"].iterrows():
            e = get_entry(r["vendor_gstin"], r.get("vendor_name", ""))
            e["total_invoices"] += 1
            e["probable_matched"] += 1

    # Books only (ITC at risk)
    if not results["books_only"].empty:
        for _, r in results["books_only"].iterrows():
            e = get_entry(r["vendor_gstin"], r.get("vendor_name", ""))
            e["total_invoices"] += 1
            e["itc_at_risk_count"] += 1
            e["itc_at_risk_amount"] += float(r.get("total_tax", 0.0))

    # 2B only
    if not results["g2b_only"].empty:
        for _, r in results["g2b_only"].iterrows():
            e = get_entry(r["vendor_gstin"], r.get("vendor_name", ""))
            e["g2b_unclaimed_count"] += 1
            e["g2b_unclaimed_amount"] += float(r.get("total_tax", 0.0))

    # Invalid / duplicates / too long
    for cat in ["invalid_gstin", "inv_no_too_long", "duplicate_in_books"]:
        df = results[cat]
        if not df.empty:
            for _, r in df.iterrows():
                e = get_entry(r["vendor_gstin"], r.get("vendor_name", ""))
                e["compliance_issues"] += 1
                e["itc_at_risk_amount"] += float(r.get("total_tax", 0.0))

    df_summary = pd.DataFrame(list(vendor_records.values()))
    if not df_summary.empty:
        df_summary["itc_at_risk_amount"] = df_summary["itc_at_risk_amount"].round(2)
        df_summary["g2b_unclaimed_amount"] = df_summary["g2b_unclaimed_amount"].round(2)
        df_summary = df_summary.sort_values(by="itc_at_risk_amount", ascending=False)
    return df_summary