import io
import pandas as pd
from typing import Dict
from parsers import mask_vendor_name, mask_gstin, mask_bank_acc

def generate_excel_risk_report(
    check_results: Dict[str, pd.DataFrame],
    mask_confidential: bool = False
) -> bytes:
    """
    Generates an executive-ready, multi-tab audit risk report in Excel.
    Includes an Executive Summary dashboard tab and individual check sheets.
    """
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book

        # Styles
        header_fmt = workbook.add_format({
            'bold': True,
            'bg_color': '#0F172A',
            'font_color': '#FFFFFF',
            'border': 1,
            'font_name': 'Segoe UI',
            'font_size': 10,
            'valign': 'vcenter'
        })
        title_fmt = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'font_color': '#0F172A',
            'font_name': 'Segoe UI'
        })
        kpi_lbl_fmt = workbook.add_format({'bold': True, 'font_color': '#475569', 'font_size': 10})
        kpi_val_fmt = workbook.add_format({'bold': True, 'font_size': 13, 'font_color': '#0284C7'})
        kpi_risk_fmt = workbook.add_format({'bold': True, 'font_size': 13, 'font_color': '#DC2626'})
        currency_fmt = workbook.add_format({'num_format': '₹#,##0.00', 'font_name': 'Segoe UI', 'font_size': 9})
        regular_fmt = workbook.add_format({'border': 1, 'font_name': 'Segoe UI', 'font_size': 9})

        # ----------------- SHEET 1: EXECUTIVE SUMMARY -----------------
        summary_sheet = workbook.add_worksheet("Audit Summary")
        summary_sheet.write("B2", "Vendor & Payment Risk Assessment Report", title_fmt)
        summary_sheet.write("B3", "Automated Forensic Scan of SAP Master & Financial Line Items")

        dups_df = check_results.get("duplicates", pd.DataFrame())
        shared_b_df = check_results.get("shared_banks", pd.DataFrame())
        dup_v_df = check_results.get("duplicate_vendors", pd.DataFrame())
        quality_df = check_results.get("master_quality", pd.DataFrame())
        trunc_df = check_results.get("truncated_refs", pd.DataFrame())

        amt_at_risk = dups_df["amount"].sum() if not dups_df.empty else 0.0

        metrics = [
            ("Potential Duplicate Invoices Identified", len(dups_df), kpi_lbl_fmt, kpi_val_fmt),
            ("Total Payment Exposure / Amount at Risk", f"₹{amt_at_risk:,.2f}", kpi_lbl_fmt, kpi_risk_fmt),
            ("Shared Bank Account Fraud Risks", len(shared_b_df), kpi_lbl_fmt, kpi_risk_fmt),
            ("Potential Duplicate Vendor Master Profiles", len(dup_v_df), kpi_lbl_fmt, kpi_val_fmt),
            ("Master Data Quality & Dormancy Anomalies", len(quality_df), kpi_lbl_fmt, kpi_val_fmt),
            ("Invoices Exceeding SAP 16-Char Limit", len(trunc_df), kpi_lbl_fmt, kpi_val_fmt),
        ]

        row = 5
        for lbl, val, l_fmt, v_fmt in metrics:
            summary_sheet.write(row, 1, lbl, l_fmt)
            summary_sheet.write(row, 3, val, v_fmt)
            row += 2

        summary_sheet.set_column("B:B", 42)
        summary_sheet.set_column("D:D", 28)

        # ----------------- INDIVIDUAL CHECK TABS -----------------
        sheet_configs = [
            ("Duplicate Invoices", dups_df),
            ("Duplicate Vendors", dup_v_df),
            ("Shared Bank Accounts", shared_b_df),
            ("Master Data Quality", quality_df),
            ("Truncated Invoices (>16)", trunc_df)
        ]

        for title, raw_df in sheet_configs:
            safe_name = title[:31]
            if raw_df is None or raw_df.empty:
                df_to_write = pd.DataFrame({"Notice": ["No risk anomalies identified under this audit rule."]})
            else:
                df_to_write = raw_df.copy()
                if mask_confidential:
                    for col in ["vendor_name", "vendor_names"]:
                        if col in df_to_write.columns:
                            df_to_write[col] = df_to_write[col].apply(mask_vendor_name)
                    for col in ["gstin"]:
                        if col in df_to_write.columns:
                            df_to_write[col] = df_to_write[col].apply(mask_gstin)
                    for col in ["bank_account"]:
                        if col in df_to_write.columns:
                            df_to_write[col] = df_to_write[col].apply(mask_bank_acc)

            df_to_write.to_excel(writer, sheet_name=safe_name, index=False, startrow=0)
            ws = writer.sheets[safe_name]

            # Style header and columns
            for col_idx, col_name in enumerate(df_to_write.columns):
                ws.write(0, col_idx, str(col_name).replace('_', ' ').title(), header_fmt)
                max_len = max(
                    len(str(col_name)),
                    df_to_write[col_name].astype(str).map(len).max() if not df_to_write.empty else 0
                )
                col_width = min(max(max_len + 3, 12), 45)
                
                # Check for currency column
                if "amount" in col_name.lower():
                    ws.set_column(col_idx, col_idx, col_width, currency_fmt)
                else:
                    ws.set_column(col_idx, col_idx, col_width, regular_fmt)

    return output.getvalue()