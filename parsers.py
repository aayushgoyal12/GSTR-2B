import re
import pandas as pd
from typing import Any, Dict

# Statutory Format Patterns (India)
GSTIN_REGEX = re.compile(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}[Z]{1}[0-9A-Z]{1}$')
PAN_REGEX = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$')

def normalize_invoice_ref(ref: Any) -> str:
    """
    Normalizes SAP invoice reference numbers (XBLNR):
    1. Converts to uppercase string.
    2. Strips spaces, slashes, dashes, periods, underscores, and special characters.
    3. Strips leading zeros from numeric components (e.g., INV/001, INV-1, INV001 -> INV1).
    """
    if pd.isna(ref) or ref is None:
        return ""
    s = str(ref).strip().upper()
    # Strip spaces, hyphens, slashes, periods, underscores, hash
    s = re.sub(r'[\s\-_/\\.,:#]', '', s)
    # Strip leading zeros preceded by alpha prefix (e.g. INV001 -> INV1)
    s = re.sub(r'(?<=[A-Z])0+(?=\d)', '', s)
    # Strip leading zeros at start of string (e.g. 00123 -> 123)
    s = re.sub(r'^0+(?=\d)', '', s)
    return s

def clean_bank_account(acc: Any) -> str:
    """Cleans bank account numbers by stripping spaces, hyphens, and leading zeros."""
    if pd.isna(acc) or acc is None:
        return ""
    s = re.sub(r'[\s\-]', '', str(acc).strip())
    # Retain single '0' if account is '0', otherwise strip leading zeros
    s = re.sub(r'^0+(?=\d)', '', s)
    return s

def is_valid_gstin(gstin: Any) -> bool:
    """Validates 15-character Indian GSTIN format."""
    if pd.isna(gstin) or not gstin:
        return False
    return bool(GSTIN_REGEX.match(str(gstin).strip().upper()))

def is_valid_pan(pan: Any) -> bool:
    """Validates 10-character Indian Income Tax PAN format."""
    if pd.isna(pan) or not pan:
        return False
    return bool(PAN_REGEX.match(str(pan).strip().upper()))

def mask_vendor_name(name: Any) -> str:
    """Masks vendor name for confidential audit reviews: Tata Consultancy -> T••• C••••••••••"""
    if pd.isna(name) or not name:
        return ""
    parts = str(name).strip().split()
    masked = []
    for p in parts:
        if len(p) <= 2:
            masked.append(p)
        else:
            masked.append(p[0] + "•" * (len(p) - 1))
    return " ".join(masked)

def mask_gstin(gstin: Any) -> str:
    """Masks GSTIN: 27AAAAA0000A1Z5 -> 27AAAA•••••1Z5"""
    if pd.isna(gstin) or not gstin:
        return ""
    g = str(gstin).strip().upper()
    if len(g) == 15:
        return f"{g[:6]}•••••{g[11:]}"
    return g[:3] + "••••"

def mask_bank_acc(acc: Any) -> str:
    """Masks bank account number: 9876543210 -> ••••••3210"""
    if pd.isna(acc) or not acc:
        return ""
    s = str(acc).strip()
    if len(s) > 4:
        return "•" * (len(s) - 4) + s[-4:]
    return "••••"

def standardize_vendor_master(df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
    """Maps and standardizes raw Vendor Master export dataframe."""
    out = pd.DataFrame()
    for std_col, raw_col in mapping.items():
        if raw_col and raw_col in df.columns:
            out[std_col] = df[raw_col]
        else:
            out[std_col] = ""

    out["vendor_code"] = out["vendor_code"].astype(str).str.strip().str.upper()
    out["vendor_name"] = out["vendor_name"].astype(str).str.strip()
    out["gstin"] = out["gstin"].astype(str).str.strip().str.upper()
    out["pan"] = out["pan"].astype(str).str.strip().str.upper()
    out["bank_account"] = out["bank_account"].apply(clean_bank_account)
    out["ifsc"] = out["ifsc"].astype(str).str.strip().str.upper()
    out["creation_date"] = pd.to_datetime(out["creation_date"], errors="coerce")
    return out

def standardize_invoice_items(df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
    """Maps and standardizes raw Invoice Line Items export dataframe."""
    out = pd.DataFrame()
    for std_col, raw_col in mapping.items():
        if raw_col and raw_col in df.columns:
            out[std_col] = df[raw_col]
        else:
            out[std_col] = "" if std_col != "amount" else 0.0

    out["vendor_code"] = out["vendor_code"].astype(str).str.strip().str.upper()
    out["invoice_reference"] = out["invoice_reference"].astype(str).str.strip()
    out["document_number"] = out["document_number"].astype(str).str.strip()
    out["invoice_date"] = pd.to_datetime(out["invoice_date"], errors="coerce")
    out["posting_date"] = pd.to_datetime(out["posting_date"], errors="coerce")
    out["amount"] = pd.to_numeric(out["amount"], errors="coerce").fillna(0.0).round(2)
    out["payment_status"] = out["payment_status"].astype(str).str.strip()
    out["norm_ref"] = out["invoice_reference"].apply(normalize_invoice_ref)
    return out