import pytest
import pandas as pd
from datetime import datetime, timedelta
from parsers import normalize_invoice_ref, clean_bank_account
from checks import run_all_checks

def test_normalize_invoice_numbers():
    """Validates that INV/001, INV-1, and INV001 normalize identically."""
    n1 = normalize_invoice_ref("INV/001")
    n2 = normalize_invoice_ref("INV-1")
    n3 = normalize_invoice_ref("INV001")
    n4 = normalize_invoice_ref("inv 001")
    n5 = normalize_invoice_ref("INV#01")
    assert n1 == "INV1"
    assert n2 == "INV1"
    assert n3 == "INV1"
    assert n4 == "INV1"
    assert n5 == "INV1"

def test_normalize_leading_zeros():
    """Validates leading zero stripping on purely numeric and prefixed references."""
    assert normalize_invoice_ref("00450") == "450"
    assert normalize_invoice_ref("00001") == "1"
    assert normalize_invoice_ref("INV00045") == "INV45"
    assert clean_bank_account("000123456789") == "123456789"

def test_exact_duplicate_invoice_detection():
    """Validates detection of exact normalized duplicate invoice under same vendor."""
    vendors = pd.DataFrame([{
        "vendor_code": "V1", "vendor_name": "Test Co", "address": "", 
        "gstin": "27AAACA1234P1Z1", "pan": "AAACA1234P", "bank_account": "123", "ifsc": "SBIN0001", "creation_date": "2024-01-01"
    }])
    invoices = pd.DataFrame([
        {"vendor_code": "V1", "invoice_reference": "INV/001", "invoice_date": "2024-10-01", "posting_date": "2024-10-02", "amount": 50000.0, "document_number": "101", "payment_status": "PAID"},
        {"vendor_code": "V1", "invoice_reference": "INV-1", "invoice_date": "2024-10-01", "posting_date": "2024-10-02", "amount": 50000.0, "document_number": "102", "payment_status": "OPEN"},
    ])
    invoices["norm_ref"] = invoices["invoice_reference"].apply(normalize_invoice_ref)
    invoices["invoice_date"] = pd.to_datetime(invoices["invoice_date"])
    invoices["posting_date"] = pd.to_datetime(invoices["posting_date"])

    res = run_all_checks(vendors, invoices)
    dups = res["duplicates"]
    assert len(dups) == 1
    assert dups.iloc[0]["duplicate_type"] == "Exact Normalized Reference"
    assert dups.iloc[0]["amount"] == 50000.0
    assert "One Paid, One Open" in dups.iloc[0]["payment_state"]

def test_date_window_same_amount_duplicate():
    """Validates same amount within date window (default 7 days) vs outside window."""
    vendors = pd.DataFrame([{
        "vendor_code": "V1", "vendor_name": "Test Co", "address": "", 
        "gstin": "27AAACA1234P1Z1", "pan": "AAACA1234P", "bank_account": "123", "ifsc": "SBIN0001", "creation_date": "2024-01-01"
    }])
    invoices = pd.DataFrame([
        {"vendor_code": "V1", "invoice_reference": "BILL-A", "invoice_date": "2024-10-01", "posting_date": "2024-10-02", "amount": 90000.0, "document_number": "201", "payment_status": "PAID"},
        {"vendor_code": "V1", "invoice_reference": "BILL-B", "invoice_date": "2024-10-05", "posting_date": "2024-10-06", "amount": 90000.0, "document_number": "202", "payment_status": "OPEN"},
        {"vendor_code": "V1", "invoice_reference": "BILL-C", "invoice_date": "2024-11-20", "posting_date": "2024-11-21", "amount": 90000.0, "document_number": "203", "payment_status": "OPEN"},
    ])
    invoices["norm_ref"] = invoices["invoice_reference"].apply(normalize_invoice_ref)
    invoices["invoice_date"] = pd.to_datetime(invoices["invoice_date"])
    invoices["posting_date"] = pd.to_datetime(invoices["posting_date"])

    res = run_all_checks(vendors, invoices, date_window_days=7)
    dups = res["duplicates"]
    # Only BILL-A and BILL-B are within 4 days (<= 7 days). BILL-C is 50 days later.
    assert len(dups) == 1
    assert "Same Amount within 4 Days" in dups.iloc[0]["duplicate_type"]

def test_shared_bank_account_detection():
    """Validates detection when multiple distinct vendor codes share the same bank account."""
    vendors = pd.DataFrame([
        {"vendor_code": "V101", "vendor_name": "Supplier One", "address": "", "gstin": "27AAACA1234P1Z1", "pan": "AAACA1234P", "bank_account": "9876543210", "ifsc": "HDFC0001", "creation_date": "2024-01-01"},
        {"vendor_code": "V102", "vendor_name": "Supplier Two", "address": "", "gstin": "27AAACA9999P1Z2", "pan": "AAACA9999P", "bank_account": "9876543210", "ifsc": "HDFC0001", "creation_date": "2024-01-01"},
    ])
    invoices = pd.DataFrame(columns=["vendor_code", "invoice_reference", "invoice_date", "posting_date", "amount", "document_number", "payment_status", "norm_ref"])

    res = run_all_checks(vendors, invoices)
    shared = res["shared_banks"]
    assert len(shared) == 1
    assert shared.iloc[0]["bank_account"] == "9876543210"
    assert shared.iloc[0]["vendor_count"] == 2

def test_invoice_ref_longer_than_16():
    """Validates flagging of invoice references exceeding SAP BKPF-XBLNR 16-char limit."""
    vendors = pd.DataFrame(columns=["vendor_code", "vendor_name", "gstin", "pan", "bank_account", "ifsc", "creation_date"])
    invoices = pd.DataFrame([
        {"vendor_code": "V1", "invoice_reference": "VALID-REF-123", "invoice_date": "2024-10-01", "posting_date": "2024-10-02", "amount": 1000.0, "document_number": "301", "payment_status": "PAID"},
        {"vendor_code": "V1", "invoice_reference": "TRUNCATED-INV-2024-00123", "invoice_date": "2024-10-01", "posting_date": "2024-10-02", "amount": 1000.0, "document_number": "302", "payment_status": "PAID"},
    ])
    invoices["norm_ref"] = invoices["invoice_reference"].apply(normalize_invoice_ref)
    invoices["invoice_date"] = pd.to_datetime(invoices["invoice_date"])

    res = run_all_checks(vendors, invoices)
    trunc = res["truncated_refs"]
    assert len(trunc) == 1
    assert trunc.iloc[0]["char_length"] == len("TRUNCATED-INV-2024-00123")