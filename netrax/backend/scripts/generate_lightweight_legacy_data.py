"""
Lightweight Legacy NetraX CSV Data Generator
Generates a small, clean legacy CSV dataset in backend/data/legacy/
"""

import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "legacy"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def write_csv(filename: str, headers: list[str], rows: list[list[str]]):
    filepath = DATA_DIR / filename
    with filepath.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print(f"  [+] Wrote {filename} ({len(rows)} rows)")

def generate():
    print("Generating lightweight legacy CSV dataset...")

    # 1. cases.csv
    write_csv("cases.csv", ["case_id", "title", "description", "status"], [
        ["CASE-1023", "Inter-State Chop Shop & Hawala Syndicate", "Targeted probe into vehicle theft ring and financial layering.", "UNDER_INVESTIGATION"]
    ])

    # 2. persons.csv
    write_csv("persons.csv", ["person_id", "name", "alias"], [
        ["PER-001", "Vikram Sharma", "Vicky Chopshop"],
        ["PER-002", "Rajesh Kumar", "Raju Mechanic"],
        ["PER-003", "Anil Mehta", "Hawala Operator"],
        ["PER-004", "Sunil Verma", "Driver"]
    ])

    # 3. vehicles.csv
    write_csv("vehicles.csv", ["vehicle_id", "model", "registration"], [
        ["VEH-001", "Hyundai Creta", "DL-01-AB-4321"],
        ["VEH-002", "Mahindra Bolero", "HR-26-DQ-8812"]
    ])

    # 4. phones.csv
    write_csv("phones.csv", ["phone_id", "phone_number", "owner_person_id"], [
        ["PHN-001", "+919876543210", "PER-001"],
        ["PHN-002", "+919812345678", "PER-002"],
        ["PHN-003", "+919899911122", "PER-003"]
    ])

    # 5. locations.csv
    write_csv("locations.csv", ["location_id", "name"], [
        ["LOC-001", "Chop Shop Garage Sector 12 Noida"],
        ["LOC-002", "Mayur Vihar Toll Plaza Delhi"]
    ])

    # 6. bank_accounts.csv
    write_csv("bank_accounts.csv", ["account_id", "masked_account", "owner_person_id"], [
        ["ACC-001", "HDFC AC# XXXX8920", "PER-001"],
        ["ACC-002", "ICICI AC# XXXX4511", "PER-003"]
    ])

    # 7. evidence.csv
    write_csv("evidence.csv", ["evidence_id", "filename", "type", "source", "content"], [
        ["EVD-001", "FIR_1023_ChopShop.txt", "FIR", "Special Cell Delhi Police", "FIR report detailing stolen Hyundai Creta DL-01-AB-4321 and suspect Vikram Sharma @ Vicky."],
        ["EVD-002", "Surveillance_Log_May2024.txt", "SURVEILLANCE", "Field Surveillance", "Surveillance observed Rajesh Kumar receiving stolen vehicles at Chop Shop Garage Sector 12 Noida."],
        ["EVD-003", "Bank_Audit_Report.txt", "FINANCIAL_RECORD", "FIU Unit", "FIU audit flagged illegal financial transfer from HDFC account XXXX8920 to Hawala Operator Anil Mehta."]
    ])

    # 8. relationships.csv
    write_csv("relationships.csv", ["relationship_id", "source_id", "target_id", "relationship_type", "evidence_id", "confidence"], [
        ["REL-001", "PER-001", "VEH-001", "OWNS", "EVD-001", "0.95"],
        ["REL-002", "PER-001", "PER-002", "WITNESSED_WITH", "EVD-002", "0.90"],
        ["REL-003", "PER-002", "LOC-001", "SEEN_AT", "EVD-002", "0.92"],
        ["REL-004", "PER-001", "ACC-001", "OWNS", "EVD-003", "0.98"],
        ["REL-005", "ACC-001", "ACC-002", "TRANSFERRED_MONEY", "EVD-003", "0.95"],
        ["REL-006", "PER-003", "ACC-002", "OWNS", "EVD-003", "0.96"]
    ])

    # 9. cdr.csv
    write_csv("cdr.csv", ["cdr_id", "caller_phone_id", "receiver_phone_id", "date", "time", "duration_seconds", "location_id"], [
        ["CDR-001", "PHN-001", "PHN-002", "2024-05-10", "14:30:00", "240", "LOC-001"],
        ["CDR-002", "PHN-001", "PHN-003", "2024-05-11", "16:15:00", "180", "LOC-002"],
        ["CDR-003", "PHN-002", "PHN-003", "2024-05-12", "18:45:00", "310", "LOC-001"]
    ])

    # 10. transactions.csv
    write_csv("transactions.csv", ["transaction_id", "from_account_id", "to_account_id", "amount", "currency", "date", "note"], [
        ["TXN-001", "ACC-001", "ACC-002", "450000", "INR", "2024-05-11", "Layering Transfer"],
        ["TXN-002", "ACC-002", "ACC-001", "120000", "INR", "2024-05-14", "Commission Return"]
    ])

    # 11. entity_resolution.csv
    write_csv("entity_resolution.csv", ["resolved_person_id", "record_a", "record_b"], [
        ["PER-001", "Vicky Sharma", "Vikram S."]
    ])

    print("\nLightweight CSV dataset generated successfully in netrax/backend/data/legacy/\n")

if __name__ == "__main__":
    generate()
