import streamlit as st
from datetime import date
import os
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

# ---------------- CONFIG ---------------- #
st.set_page_config(page_title="Shelf Life System", layout="wide")

load_dotenv()
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# ---------------- SAFE SESSION ---------------- #
if "items" not in st.session_state:
    st.session_state["items"] = []

if not isinstance(st.session_state.get("items"), list):
    st.session_state["items"] = []

# ---------------- FUNCTIONS ---------------- #
def calculate_shelf_life(mfg, exp, arrival_port):
    total_days = (exp - mfg).days
    remaining_days = (exp - arrival_port).days
    percent = (remaining_days / total_days) * 100 if total_days > 0 else 0
    return total_days, remaining_days, percent

def get_status(percent, tolerance):
    if percent <= 0:
        return "Expired"
    elif percent < tolerance:
        return "Near Expiry"
    return "OK"

# ---------------- NAV ---------------- #
st.sidebar.title("📦 Menu")
page = st.sidebar.radio("Select", ["Data Entry", "Report"])

# =====================================================
# 📥 DATA ENTRY
# =====================================================
if page == "Data Entry":

    st.title("📥 Shipment Entry")

    if st.button("🔄 Reset Session"):
        st.session_state.clear()
        st.rerun()

    # -------- HEADER -------- #
    st.header("Shipment Details")

    c1, c2 = st.columns(2)
    with c1:
        invoice = st.text_input("Invoice Number")
    with c2:
        bill_entry_number = st.text_input("Bill of Entry Number")

    c3, c4 = st.columns(2)
    with c3:
        total_lines = st.number_input("Number of Item Lines in Invoice", min_value=1)
    with c4:
        received_lines = st.number_input("Actual Number of Lines Received", min_value=0)

    c5, c6, c7 = st.columns(3)
    with c5:
        arrival_port = st.date_input("Arrival at Port")
    with c6:
        arrival_wh = st.date_input("Arrival at Warehouse")
    with c7:
        bill_entry_date = st.date_input("Bill of Entry Date")

    tolerance = st.number_input("Shelf Life Tolerance (%)", 0, 100, 60)

    verified_by = st.text_input("Expiry Verification Done By")

    st.divider()

    # -------- LINE ENTRY -------- #
    st.header("Add Line Item")

    barcode = st.text_input("Scan / Enter Barcode")
    description = st.text_input("Item Description")

    c8, c9 = st.columns(2)
    with c8:
        ordered_qty = st.number_input("Ordered Quantity", min_value=0)
    with c9:
        received_qty = st.number_input("Received Quantity", min_value=0)

    c10, c11 = st.columns(2)
    with c10:
        mfg = st.date_input("Manufacturing Date")
    with c11:
        exp = st.date_input("Expiry Date")

    if st.button("➕ Add Item"):
        if not barcode:
            st.error("Barcode required")
        elif exp <= mfg:
            st.error("Expiry must be after manufacturing")
        elif arrival_port < mfg:
            st.error("Arrival cannot be before manufacturing")
        else:
            total, remaining, percent = calculate_shelf_life(mfg, exp, arrival_port)
            status = get_status(percent, tolerance)

            st.session_state["items"].append({
                "barcode": barcode,
                "description": description,
                "ordered_qty": int(ordered_qty),
                "received_qty": int(received_qty),
                "mfg_date": str(mfg),
                "exp_date": str(exp),
                "total_days": total,
                "remaining_days": remaining,
                "shelf_life_percent": round(percent, 2),
                "status": status
            })

            st.success("Item added")

    # -------- DISPLAY -------- #
    st.subheader("Items Added")

    items = st.session_state.get("items", [])
    if not isinstance(items, list):
        items = []
        st.session_state["items"] = []

    valid_items = [i for i in items if isinstance(i, dict)]

    if valid_items:
        st.dataframe(pd.DataFrame(valid_items), use_container_width=True)
    else:
        st.info("No items added")

    # -------- SAVE -------- #
    if st.button("💾 Save Shipment"):
        if not invoice:
            st.error("Invoice required")
        elif not valid_items:
            st.error("Add at least one item")
        else:
            try:
                res = supabase.table("shipments").insert({
                    "invoice_number": invoice,
                    "bill_entry_number": bill_entry_number,
                    "arrival_port_date": str(arrival_port),
                    "arrival_warehouse_date": str(arrival_wh),
                    "bill_entry_date": str(bill_entry_date),
                    "shelf_life_tolerance": int(tolerance),
                    "total_lines": int(total_lines),
                    "received_lines": int(received_lines),
                    "verified_by": verified_by
                }).execute()

                shipment_id = res.data[0]["id"]

                for i in valid_items:
                    i["shipment_id"] = shipment_id

                supabase.table("shipment_items").insert(valid_items).execute()

                st.success("✅ Shipment saved")
                st.session_state["items"] = []

            except Exception as e:
                st.error(f"Error: {e}")

# =====================================================
# 📊 REPORT
# =====================================================
elif page == "Report":

    st.title("📊 Shelf Life Report")

    c1, c2, c3 = st.columns(3)

    with c1:
        f_invoice = st.text_input("Invoice Filter")

    with c2:
        from_date = st.date_input("From Date")

    with c3:
        to_date = st.date_input("To Date")

    if st.button("📥 Generate Report"):

        q = supabase.table("shipments").select("*")

        if f_invoice:
            q = q.eq("invoice_number", f_invoice)
        if from_date:
            q = q.gte("arrival_port_date", str(from_date))
        if to_date:
            q = q.lte("arrival_port_date", str(to_date))

        shipments = q.execute().data

        if not shipments:
            st.warning("No data found")
        else:
            ids = [s["id"] for s in shipments]

            items = supabase.table("shipment_items") \
                .select("*") \
                .in_("shipment_id", ids) \
                .execute().data

            ship_map = {s["id"]: s for s in shipments}

            rows = []
            for it in items:
                sh = ship_map[it["shipment_id"]]
                rows.append({
                    "Invoice": sh["invoice_number"],
                    "Bill Entry": sh.get("bill_entry_number"),
                    "Arrival Date": sh.get("arrival_port_date"),
                    "Barcode": it["barcode"],
                    "Description": it["description"],
                    "Shelf Life %": it["shelf_life_percent"],
                    "Status": it["status"]
                })

            df = pd.DataFrame(rows)

            # -------- KPIs -------- #
            st.subheader("Summary")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total", len(df))
            c2.metric("Expired", (df["Status"] == "Expired").sum())
            c3.metric("Near Expiry", (df["Status"] == "Near Expiry").sum())
            c4.metric("OK", (df["Status"] == "OK").sum())

            # -------- TABLE -------- #
            st.subheader("Details")
            st.dataframe(df, use_container_width=True)

            # -------- EMAIL -------- #
            st.subheader("📧 Email Draft")

            problem_df = df[df["Status"].isin(["Expired", "Near Expiry"])]

            if problem_df.empty:
                st.success("No short shelf life items")
            else:
                table_text = "\n".join(
                    [
                        f"{row['Description']} | {row['Shelf Life %']}% | {row['Status']}"
                        for _, row in problem_df.iterrows()
                    ]
                )

                verifier = shipments[0].get("verified_by", "N/A")
                invoice_text = shipments[0].get("invoice_number", "")

                email_text = f"""
Subject: Shelf Life Concern – Invoice {invoice_text}

On detailed verification of Invoice Number {invoice_text}, certain products are having short shelf life. Details are as follows:

Item Description | Shelf Life % | Status
--------------------------------------------------
{table_text}

Please do the needful.

Expiry verification done by: {verifier}
"""

                st.text_area("Email Preview", email_text, height=300)

                st.download_button(
                    "⬇️ Download Email",
                    email_text,
                    "email.txt"
                )

            # -------- DOWNLOAD -------- #
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download CSV", csv, "report.csv")
