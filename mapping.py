from typing import Dict, Any, Optional, List
from ai import InvoiceData, InvoiceItem

# Arabic column headers in the exact order required (RIGHT to LEFT)
# These headers match the fields requested by the user, including VAT details
ARABIC_HEADERS = [
    "الاسم التجاري",                    # Commercial Name
    "الرقم الضريبي",                    # Tax Number
    "تسلسل مصدر الدخل",                 # Income Source Sequence
    "رقم الفاتورة الإلكترونية",        # Electronic Invoice Number
    "رقم فاتورة البائع",               # Seller Invoice Number
    "تاريخ إصدار الفاتورة",            # Invoice Issue Date
    "نوع الفاتورة",                    # Invoice Type
    "نوع العملة",                      # Currency Type
    "اسم المشتري",                     # Buyer Name
    "رقم الهاتف",                      # Phone Number
    "المدينة",                         # City
    "الوصف",                           # Description
    "الكمية",                          # Quantity
    "سعر الوحدة",                      # Unit Price
    "المبلغ",                          # Amount (before discount)
    "الخصم",                           # Discount
    "الاجمالي بعد الخصم",              # Line subtotal after discount
    "نسبة الضريبة العامة",             # VAT rate (%)
    "قيمة الضريبة العامة",             # VAT amount
    "الاجمالي بعد الضريبة",            # Line total after tax
    "إجمالي قيمة الفاتورة",            # Grand total per invoice
    "مجموع قيمة الضريبة العامة (JOD)", # Total VAT amount per invoice
]

def create_invoice_rows(invoice_data: InvoiceData) -> List[Dict[str, Any]]:
    """
    Create rows from invoice data - one row per line item.
    Each row contains all invoice header information repeated for each line item.
    Returns a list of dictionaries, each representing one row.
    """
    
    rows = []
    
    # Get invoice header information (same for all rows)
    header_data = {
        "الاسم التجاري": invoice_data.commercial_name or invoice_data.seller_name or "",
        "الرقم الضريبي": invoice_data.tax_number or "",
        "تسلسل مصدر الدخل": invoice_data.income_source_sequence or "",
        "رقم الفاتورة الإلكترونية": invoice_data.electronic_invoice_number or invoice_data.invoice_number or "",
        "رقم فاتورة البائع": invoice_data.seller_invoice_number or "",
        "تاريخ إصدار الفاتورة": invoice_data.invoice_date or "",
        "نوع الفاتورة": invoice_data.invoice_type or "",
        "نوع العملة": invoice_data.currency or "",
        "اسم المشتري": invoice_data.buyer_name or invoice_data.customer_name or "",
        "رقم الهاتف": invoice_data.phone_number or "",
        "المدينة": invoice_data.city or "",
    }
    
    # If there are line items, create one row per item
    if invoice_data.items and len(invoice_data.items) > 0:
        # Keep grand total only once per invoice (first row) to avoid confusion
        grand_total_value = invoice_data.grand_total if invoice_data.grand_total is not None else ""
        # Same for total VAT across the invoice
        total_vat_value = invoice_data.total_tax if invoice_data.total_tax is not None else ""

        for idx, item in enumerate(invoice_data.items):
            row = header_data.copy()
            
            # Add line item specific data
            row["الوصف"] = item.description or ""
            row["الكمية"] = item.quantity if item.quantity is not None else 0
            row["سعر الوحدة"] = item.unit_price if item.unit_price is not None else 0
            
            # Calculate or use amount (المبلغ)
            if item.amount is not None:
                row["المبلغ"] = item.amount
            elif item.quantity is not None and item.unit_price is not None:
                row["المبلغ"] = item.quantity * item.unit_price
            else:
                row["المبلغ"] = item.line_subtotal if item.line_subtotal is not None else 0

            # Discount (الخصم)
            row["الخصم"] = item.discount if item.discount is not None else 0

            # Line subtotal after discount (الاجمالي بعد الخصم)
            if item.line_subtotal is not None:
                row["الاجمالي بعد الخصم"] = item.line_subtotal
            else:
                # Compute as amount - discount when not explicitly provided
                row["الاجمالي بعد الخصم"] = row["المبلغ"] - row["الخصم"]

            # VAT rate and amount at line level
            row["نسبة الضريبة العامة"] = item.tax_rate if item.tax_rate is not None else 0
            row["قيمة الضريبة العامة"] = item.tax_amount if item.tax_amount is not None else 0

            # Line total after tax (الاجمالي بعد الضريبة)
            if item.line_total is not None:
                row["الاجمالي بعد الضريبة"] = item.line_total
            else:
                row["الاجمالي بعد الضريبة"] = row["الاجمالي بعد الخصم"] + row["قيمة الضريبة العامة"]

            # Grand total (إجمالي قيمة الفاتورة) - only on the first row for this invoice
            row["إجمالي قيمة الفاتورة"] = grand_total_value if idx == 0 else ""
            # Total VAT for the whole invoice - only on the first row
            row["مجموع قيمة الضريبة العامة (JOD)"] = total_vat_value if idx == 0 else ""
            
            rows.append(row)
    else:
        # If no line items, create one row with header info and empty item fields
        row = header_data.copy()
        row["الوصف"] = ""
        row["الكمية"] = 0
        row["سعر الوحدة"] = 0
        row["المبلغ"] = 0
        row["الخصم"] = 0
        row["الاجمالي بعد الخصم"] = 0
        row["نسبة الضريبة العامة"] = 0
        row["قيمة الضريبة العامة"] = 0
        row["الاجمالي بعد الضريبة"] = 0
        row["إجمالي قيمة الفاتورة"] = invoice_data.grand_total if invoice_data.grand_total is not None else 0
        row["مجموع قيمة الضريبة العامة (JOD)"] = invoice_data.total_tax if invoice_data.total_tax is not None else 0
        rows.append(row)
    
    return rows


# Legacy function for backwards compatibility - returns aggregated format
def aggregate_invoice_data(invoice_data: InvoiceData) -> Dict[str, Any]:
    """
    Legacy function - returns first row from create_invoice_rows for backwards compatibility.
    """
    rows = create_invoice_rows(invoice_data)
    if rows:
        return rows[0]
    else:
        # Return empty row with all headers
        return {header: "" if header != "الكمية" else 0 for header in ARABIC_HEADERS}


# Valid tax rates for Jordan/Iraq (kept for reference, not used in new format)
VALID_TAX_RATES = [0, 1, 2, 4, 5, 10, 16]


def create_dataframe_row(aggregated_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a single row DataFrame from aggregated data."""
    return aggregated_data
