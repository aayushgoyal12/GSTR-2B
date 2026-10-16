import pandas as pd
from datetime import datetime, timedelta

def generate_fictional_datasets():
    """
    Generates 25 fictional Indian vendors and ~60 fictional SAP invoices
    specifically calibrated to test and illustrate all 5 audit checks.
    """
    vendors_data = [
        # Normal Compliant Vendors
        {"vendor_code": "V1001", "vendor_name": "Apex Industrial Supplies Ltd", "address": "MIDC Turbhe, Navi Mumbai", "gstin": "27AAACA1234P1Z1", "pan": "AAACA1234P", "bank_account": "009123456789", "ifsc": "HDFC0000123", "creation_date": "2022-01-15"},
        {"vendor_code": "V1002", "vendor_name": "Zenith Tech Logistics LLP", "address": "Whitefield, Bengaluru", "gstin": "29AABCZ9876Q1Z2", "pan": "AABCZ9876Q", "bank_account": "501004561234", "ifsc": "SBIN0004567", "creation_date": "2022-03-20"},
        {"vendor_code": "V1003", "vendor_name": "BlueStar Facilities Pvt Ltd", "address": "Andheri East, Mumbai", "gstin": "27AABCB5544R1Z3", "pan": "AABCB5544R", "bank_account": "100200300400", "ifsc": "ICIC0000999", "creation_date": "2021-06-10"},
        {"vendor_code": "V1004", "vendor_name": "Kalyani Precision Tools", "address": "Bhosari, Pune", "gstin": "27AAAFK8019D1ZA", "pan": "AAAFK8019D", "bank_account": "918020304050", "ifsc": "KKBK0001234", "creation_date": "2023-02-01"},
        {"vendor_code": "V1005", "vendor_name": "Shree Ram Packaging Solutions", "address": "Naraina Indl Area, New Delhi", "gstin": "07AABCS9912H1ZQ", "pan": "AABCS9912H", "bank_account": "440011223344", "ifsc": "PUNB0123400", "creation_date": "2022-08-14"},
        {"vendor_code": "V1006", "vendor_name": "Dynamic Cloud Consultancy", "address": "Cyber City, Gurugram", "gstin": "06AAACD4411E1ZW", "pan": "AAACD4411E", "bank_account": "332211009988", "ifsc": "UTIB0000456", "creation_date": "2023-01-10"},

        # Check B: Duplicate Vendor Master (Same GSTIN/PAN under different vendor codes)
        {"vendor_code": "V1007", "vendor_name": "Apex Industrial Supplies (Plant 2)", "address": "Bhiwandi, Maharashtra", "gstin": "27AAACA1234P1Z1", "pan": "AAACA1234P", "bank_account": "009123456789", "ifsc": "HDFC0000123", "creation_date": "2023-04-05"},
        {"vendor_code": "V1008", "vendor_name": "Zenith Tech Logistics", "address": "Peenya, Bengaluru", "gstin": "29AABCZ9876Q1Z2", "pan": "AABCZ9876Q", "bank_account": "501004561234", "ifsc": "SBIN0004567", "creation_date": "2023-09-12"},

        # Check B: Fuzzy Name Match under separate codes
        {"vendor_code": "V1009", "vendor_name": "Blue Star Facilities Private Limited", "address": "Powai, Mumbai", "gstin": "27AABCB9988K1Z5", "pan": "AABCB9988K", "bank_account": "778899001122", "ifsc": "BARB0POWAIX", "creation_date": "2023-11-20"},

        # Check C: Shared Bank Account (Collusion / Ghost Vendor Risk)
        {"vendor_code": "V1010", "vendor_name": "Eagle Security & Guarding", "address": "Saket, New Delhi", "gstin": "07AAACE6655L1Z8", "pan": "AAACE6655L", "bank_account": "100200300400", "ifsc": "ICIC0000999", "creation_date": "2023-05-18"},
        {"vendor_code": "V1011", "vendor_name": "Metro Housekeeping Services", "address": "Laxmi Nagar, Delhi", "gstin": "07AABCM2211N1Z0", "pan": "AABCM2211N", "bank_account": "100200300400", "ifsc": "ICIC0000999", "creation_date": "2023-07-22"},

        # Check D: Master Data Quality Flaws (Invalid/Missing GSTIN, PAN, Bank)
        {"vendor_code": "V1012", "vendor_name": "Faulty GSTIN Vendor A", "address": "Surat, Gujarat", "gstin": "24ABCDE1234F1", "pan": "ABCDE1234F", "bank_account": "665544332211", "ifsc": "SBIN0001111", "creation_date": "2023-08-01"},
        {"vendor_code": "V1013", "vendor_name": "Missing GSTIN Contractor", "address": "Thane, Maharashtra", "gstin": "", "pan": "AABCT5566M", "bank_account": "887766554433", "ifsc": "ICIC0001212", "creation_date": "2023-09-01"},
        {"vendor_code": "V1014", "vendor_name": "Invalid PAN Supplier B", "address": "Jaipur, Rajasthan", "gstin": "08AAACJ7788R1Z4", "pan": "INVALIDPAN", "bank_account": "112233445566", "ifsc": "HDFC0004321", "creation_date": "2023-06-15"},
        {"vendor_code": "V1015", "vendor_name": "Missing Bank Details Supplier", "address": "Kanpur, UP", "gstin": "09AAACK1122P1Z7", "pan": "AAACK1122P", "bank_account": "", "ifsc": "", "creation_date": "2023-10-01"},

        # Check D: Dormant Vendors
        {"vendor_code": "V1016", "vendor_name": "Historic Inactive Vendor 1", "address": "Nagpur, MH", "gstin": "27AAACH0001D1Z1", "pan": "AAACH0001D", "bank_account": "998877665501", "ifsc": "SBIN0009901", "creation_date": "2021-01-01"},
        {"vendor_code": "V1017", "vendor_name": "Historic Inactive Vendor 2", "address": "Kolkata, WB", "gstin": "19AAACW0002E1Z2", "pan": "AAACW0002E", "bank_account": "998877665502", "ifsc": "SBIN0009902", "creation_date": "2021-02-01"},
        {"vendor_code": "V1018", "vendor_name": "Zero Transaction Vendor", "address": "Patna, Bihar", "gstin": "10AAACZ0003F1Z3", "pan": "AAACZ0003F", "bank_account": "998877665503", "ifsc": "SBIN0009903", "creation_date": "2022-01-01"},

        # Additional Standard Vendors to complete cohort
        {"vendor_code": "V1019", "vendor_name": "Om Logistics Fleet", "address": "Sector 18, Gurugram", "gstin": "06AAACF1234D1Z9", "pan": "AAACF1234D", "bank_account": "556677889901", "ifsc": "HDFC0001122", "creation_date": "2022-11-10"},
        {"vendor_code": "V1020", "vendor_name": "Global Audit Solutions", "address": "Nariman Point, Mumbai", "gstin": "27AAACG5555L1Z0", "pan": "AAACG5555L", "bank_account": "556677889902", "ifsc": "ICIC0003344", "creation_date": "2022-12-05"},
        {"vendor_code": "V1021", "vendor_name": "Trident Engineering Work", "address": "Ludhiana, Punjab", "gstin": "03AAACT9999M1Z8", "pan": "AAACT9999M", "bank_account": "556677889903", "ifsc": "PUNB0005566", "creation_date": "2023-03-14"},
        {"vendor_code": "V1022", "vendor_name": "Sterling Hospitality Services", "address": "Goa Panaji", "gstin": "30AAACS8888P1Z5", "pan": "AAACS8888P", "bank_account": "556677889904", "ifsc": "UTIB0001299", "creation_date": "2023-04-20"},
        {"vendor_code": "V1023", "vendor_name": "Premier Office Stationery", "address": "Fort, Mumbai", "gstin": "27AAACP7777Q1Z2", "pan": "AAACP7777Q", "bank_account": "556677889905", "ifsc": "SBIN0006789", "creation_date": "2023-05-11"},
        {"vendor_code": "V1024", "vendor_name": "National Courier Services", "address": "Connaught Place, New Delhi", "gstin": "07AAACN6666R1Z1", "pan": "AAACN6666R", "bank_account": "556677889906", "ifsc": "KKBK0009876", "creation_date": "2023-06-01"},
        {"vendor_code": "V1025", "vendor_name": "Horizon Security Systems", "address": "Electronic City, Bengaluru", "gstin": "29AAACH4444T1Z3", "pan": "AAACH4444T", "bank_account": "556677889907", "ifsc": "HDFC0007788", "creation_date": "2023-07-04"}
    ]

    base_date = datetime(2024, 10, 1)
    invoices_data = []
    doc_id = 5100000000

    def add_inv(v_code, ref, days_offset, amount, status):
        nonlocal doc_id
        inv_dt = base_date + timedelta(days=days_offset)
        post_dt = inv_dt + timedelta(days=2)
        invoices_data.append({
            "vendor_code": v_code,
            "invoice_reference": ref,
            "invoice_date": inv_dt.strftime("%Y-%m-%d"),
            "posting_date": post_dt.strftime("%Y-%m-%d"),
            "amount": float(amount),
            "document_number": str(doc_id),
            "payment_status": status
        })
        doc_id += 1

    # 1. Exact Normalized Duplicate Test Cases (Check A1)
    # V1001: INV/001 vs INV-1 vs INV001
    add_inv("V1001", "INV/001", 1, 150000.0, "PAID")
    add_inv("V1001", "INV-1", 1, 150000.0, "OPEN")       # Duplicate risk: ₹150,000 (Open duplicate!)
    add_inv("V1001", "INV001", 3, 150000.0, "OPEN")      # Triplicate!

    # V1002: Leading zero normalization (00450 vs 450)
    add_inv("V1002", "00450", 4, 84000.0, "PAID")
    add_inv("V1002", "450", 4, 84000.0, "PAID")          # Both paid duplicate! Realized loss ₹84,000

    # V1003: Slashes and dashes variation
    add_inv("V1003", "BLR/24-25/99", 5, 210000.0, "PAID")
    add_inv("V1003", "BLR-24-25-99", 6, 210000.0, "OPEN")

    # 2. Date Window & Same Amount Duplicate Cases (Check A2)
    # V1004: Same vendor, same amount ₹95,000 within 3 days under different bill numbers
    add_inv("V1004", "BILL-801", 10, 95000.0, "PAID")
    add_inv("V1004", "BILL-802", 13, 95000.0, "OPEN")

    # V1005: Same vendor, same amount ₹180,000 within 5 days
    add_inv("V1005", "SRP/OCT/01", 15, 180000.0, "PAID")
    add_inv("V1005", "SRP/OCT/02", 18, 180000.0, "OPEN")

    # 3. Check E: Invoice Reference > 16 Characters (SAP XBLNR truncation risk)
    add_inv("V1006", "DCC/EXP/2024-2025/00123", 2, 320000.0, "PAID")  # 24 chars
    add_inv("V1004", "KALYANI/PROJECT/OCT/99", 7, 145000.0, "OPEN")     # 22 chars
    add_inv("V1005", "SHREE-RAM-DEL-IND-00445", 9, 78000.0, "PAID")    # 23 chars

    # 4. Invoices for Dormancy testing:
    # V1016 & V1017 last billed over 300 days ago
    old_date = datetime(2023, 11, 1)
    invoices_data.append({
        "vendor_code": "V1016",
        "invoice_reference": "OLD-2023-01",
        "invoice_date": old_date.strftime("%Y-%m-%d"),
        "posting_date": (old_date + timedelta(days=2)).strftime("%Y-%m-%d"),
        "amount": 45000.0,
        "document_number": str(doc_id),
        "payment_status": "PAID"
    })
    doc_id += 1

    # 5. Populate remaining normal operational invoices across other vendors
    for idx, v_code in enumerate(["V1001", "V1002", "V1003", "V1006", "V1007", "V1008", "V1009", "V1010", "V1011", "V1019", "V1020", "V1021", "V1022", "V1023", "V1024", "V1025"]):
        for n in range(1, 4):
            amt = round(25000.0 + (idx * 3700.0) + (n * 1250.0), 2)
            add_inv(v_code, f"REG-{v_code[-3:]}-{100 + n}", (idx * 2) + n, amt, "PAID" if n % 2 == 1 else "OPEN")

    df_vendors = pd.DataFrame(vendors_data)
    df_invoices = pd.DataFrame(invoices_data)
    return df_vendors, df_invoices