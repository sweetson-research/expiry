import streamlit as st
from datetime import date
import os
from supabase import create_client
from dotenv import load_dotenv
import pandas as pd

# ---------------- CONFIG ---------------- #
st.set_page_config(page_title="Shelf Life Tracker", layout="wide")
st.title("📦 Shipment Shelf-Life Tracker")

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- HELPERS ---------------- #
def calculate_shelf_life(mfg, exp):
    total_days = (exp - mfg).days
    remaining_days = (exp - date.today()).days
    return total_days, remaining_days

def get_status(remaining, total, tolerance):
    if total <= 0:
        return "Invalid"
    percent = (remaining / total) * 100
    if remaining <= 0:
        return "Expired"
    elif percent < tolerance:
        return "Near Expiry"
    return "OK"

# ---------------- SESSION STATE ---------------- #
if "items" not in st.session_state:
    st.session_state.items = []

# ---------------- HEADER ---------------- #
st.header("Shipment Details")

col1, col2, col3 = st.columns(3)

with col1:
    invoice = st.text_input("Invoice Number")

with col2:
    total_lines = st.number_input("Invoice Line Count", min_value=1, step=1)

with col3:
    received_lines = st.number_input("Received Line Count", min_value=0, step=1)

col4, col5, col6 = st.columns(3)

with col4:
    arrival_port = st.date_input("Arrival at Port")

with col5:
    arrival_wh = st.date_input("Arrival at Warehouse")

with col6:
    bill_entry = st.date_input("Bill of Entry Date")

tolerance = st.slider("Shelf Life Tolerance (%)", 0, 100, 20)

st.divider()

# ---------------- LINE ENTRY ---------------- #
st.header("Add Line Item")

col7, col8 = st.columns(2)

with col7:
    barcode = st.text_input("Scan / Enter Barcode")

with col8:
    description = st.text_input("Item Description")

col9, col10 = st.columns(2)

with col9:
    ordered_qty = st.number_input("Ordered Qty", min_value=0)

with col10:
    received_qty = st.number_input("Received Qty", min_value=0)

col11, col12 = st.columns(2)

with col11:
    mfg = st.date_input("Manufacturing Date")

with col12:
    exp = st.date_input("Expiry Date")

# ---------------- ADD ITEM ---------------- #
if st.button("➕ Add Item"):
    if exp <= mfg:
        st.error("Expiry date must be after manufacturing date")
    else:
        total, remaining = calculate_shelf_life(mfg, exp)
        status = get_status(remaining, total, tolerance)

        st.session_state.items.append({
            "barcode": barcode,
            "description": description,
            "ordered_qty": ordered_qty,
            "received_qty": received_qty,
            "mfg_date": str(mfg),
            "exp_date": str(exp),
            "total_days": total,
            "remaining_days": remaining,
            "status": status
        })
        st.success("Item added")

# ---------------- DISPLAY ITEMS ---------------- #
st.subheader("Items Added")

if st.session_state.items:
    df = pd.DataFrame(st.session_state.items)
    st.dataframe(df, use_container_width=True)
else:
    st.info("No items added yet")

# ---------------- SAVE ---------------- #
st.divider()

if st.button("💾 Save Shipment"):
    if not invoice:
        st.error("Invoice number required")
    elif not st.session_state.items:
        st.error("Add at least one item")
    else:
        try:
            # Insert shipment header
            res = supabase.table("shipments").insert({
                "invoice_number": invoice,
                "arrival_port_date": str(arrival_port),
                "arrival_warehouse_date": str(arrival_wh),
                "bill_entry_date": str(bill_entry),
                "shelf_life_tolerance": tolerance,
                "total_lines": total_lines,
                "received_lines": received_lines
            }).execute()

            shipment_id = res.data[0]["id"]

            # Insert items
            for item in st.session_state.items:
                item["shipment_id"] = shipment_id
                supabase.table("shipment_items").insert(item).execute()

            st.success("✅ Shipment saved successfully")

            # Reset
            st.session_state.items = []

        except Exception as e:
            st.error(f"Error: {e}")