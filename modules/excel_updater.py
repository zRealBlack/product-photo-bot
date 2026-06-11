"""
excel_updater.py
Modifies the Excel file to add pricing columns, calculated averages, and best prices.
"""

import os
import openpyxl
from openpyxl.utils import get_column_letter

def update_excel_with_prices(file_path: str, products_prices: dict, output_path: str) -> str:
    """
    Open the Excel file, add pricing columns, fill them with gathered prices,
    insert formulas for average and best price, and save to output_path.
    
    products_prices: dict mapping serial_code (str) to pricing dict:
    {
        "amazon_eg": float or None,
        "noon_eg": float or None,
        "jumia_eg": float or None,
        "brand_eg": float or None,
    }
    """
    wb = openpyxl.load_workbook(file_path)
    
    # Header keywords to identify the header row in sheets
    header_keywords = {"كود الصنف", "serial", "code", "الكود", "التصنيف", "الصنف"}
    
    new_headers = [
        "سعر أمازون مصر (ج.م)",
        "سعر نون مصر (ج.م)",
        "سعر جوميا مصر (ج.م)",
        "سعر موقع البراند (ج.م)",
        "سعر السوق العام بمصر (ج.م)",
        "مصدر سعر السوق العام",
        "متوسط السعر (ج.م)",
        "أفضل سعر (ج.م)"
    ]

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        
        # 1. Find the header row
        header_row_idx = None
        max_cols = ws.max_column
        
        # We search first 20 rows for the header
        for r_idx in range(1, min(21, ws.max_row + 1)):
            cell_val = ws.cell(row=r_idx, column=1).value
            if cell_val and str(cell_val).strip().lower() in header_keywords:
                header_row_idx = r_idx
                break
        
        # If no header row found in this sheet, check if any row has product serial patterns
        # or just skip to next sheet
        if not header_row_idx:
            continue
            
        # Determine where to add new columns (after the last active column in the header row)
        # Scan header row cells to find the last non-empty header cell
        last_header_col = 1
        for c_idx in range(1, max_cols + 2):
            val = ws.cell(row=header_row_idx, column=c_idx).value
            if val is not None and str(val).strip() != "":
                last_header_col = c_idx
                
        start_col = last_header_col + 1
        
        # Add new headers
        for offset, header_text in enumerate(new_headers):
            cell = ws.cell(row=header_row_idx, column=start_col + offset)
            cell.value = header_text
            # Copy style from the cell to the left (e.g. font, fill, border) if available
            ref_cell = ws.cell(row=header_row_idx, column=last_header_col)
            if ref_cell.has_style:
                cell.font = ref_cell.font.copy()
                cell.fill = ref_cell.fill.copy()
                cell.border = ref_cell.border.copy()
                cell.alignment = ref_cell.alignment.copy()
                
        # Get column letters for the formulas
        col_amazon = get_column_letter(start_col)
        col_noon = get_column_letter(start_col + 1)
        col_jumia = get_column_letter(start_col + 2)
        col_brand = get_column_letter(start_col + 3)
        col_general = get_column_letter(start_col + 4)
        col_source = get_column_letter(start_col + 5)
        col_avg = get_column_letter(start_col + 6)
        col_best = get_column_letter(start_col + 7)
        
        # 2. Iterate through rows below header and write prices/formulas
        for r_idx in range(header_row_idx + 1, ws.max_row + 1):
            serial_val = ws.cell(row=r_idx, column=1).value
            if serial_val is None:
                continue
            serial_str = str(serial_val).strip()
            if not serial_str:
                continue
                
            # Check if this row is a section header (case: Col A has serial but it's a label, or others are empty)
            # We match against the keys in products_prices
            if serial_str in products_prices:
                prices = products_prices[serial_str]
                
                # Write individual prices
                ws.cell(row=r_idx, column=start_col).value = prices.get("amazon_eg")
                ws.cell(row=r_idx, column=start_col + 1).value = prices.get("noon_eg")
                ws.cell(row=r_idx, column=start_col + 2).value = prices.get("jumia_eg")
                ws.cell(row=r_idx, column=start_col + 3).value = prices.get("brand_eg")
                ws.cell(row=r_idx, column=start_col + 4).value = prices.get("general_eg")
                ws.cell(row=r_idx, column=start_col + 5).value = prices.get("general_source")
                
                # Write formulas for Average and Best Price (MIN)
                # We use IF(COUNT(...) > 0, AVERAGE(...), "") to avoid #DIV/0! if no prices found
                # Note: AVERAGE and MIN automatically ignore text fields (col_source is text so G:K works or G:L works since L is source)
                # To be explicitly clear, range string is from Amazon (start_col) to General (start_col + 4)
                range_str = f"{col_amazon}{r_idx}:{col_general}{r_idx}"
                
                avg_formula = f'=IF(COUNT({range_str})>0, AVERAGE({range_str}), "")'
                best_formula = f'=IF(COUNT({range_str})>0, MIN({range_str}), "")'
                
                ws.cell(row=r_idx, column=start_col + 6).value = avg_formula
                ws.cell(row=r_idx, column=start_col + 7).value = best_formula
                
                # Copy alignment/border style from column A for neat formatting
                style_ref = ws.cell(row=r_idx, column=1)
                for offset in range(len(new_headers)):
                    c = ws.cell(row=r_idx, column=start_col + offset)
                    if style_ref.border:
                        c.border = style_ref.border.copy()
                    c.alignment = openpyxl.styles.Alignment(horizontal="center")
                    
    wb.save(output_path)
    return output_path
