from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.styles import (
    Alignment, Border, Font, PatternFill, Side
)
from openpyxl.utils import get_column_letter

from app.database.database import session_scope
from app.database.models import (
    Campaign, Customer, Installment, Order, Payment
)
from sqlalchemy import select
from sqlalchemy.orm import joinedload


# ---------------------------------------------------------------------------
# Stilovi
# ---------------------------------------------------------------------------

def _thin_border() -> Border:
    thin = Side(style="thin")
    return Border(left=thin, right=thin, top=thin, bottom=thin)

def _header_fill() -> PatternFill:
    return PatternFill("solid", fgColor="1F3864")   # tamno plava kao original

def _subheader_fill() -> PatternFill:
    return PatternFill("solid", fgColor="BDD7EE")   # svjetlo plava

def _ukupno_fill() -> PatternFill:
    return PatternFill("solid", fgColor="D9E1F2")   # još svjetlija

def _bold(size: int = 10, white: bool = False) -> Font:
    return Font(bold=True, size=size, color="FFFFFF" if white else "000000",
                name="Calibri")

def _normal(size: int = 9) -> Font:
    return Font(size=size, name="Calibri")

def _center() -> Alignment:
    return Alignment(horizontal="center", vertical="center", wrap_text=True)

def _left() -> Alignment:
    return Alignment(horizontal="left", vertical="center", wrap_text=True)


# ---------------------------------------------------------------------------
# Dohvat podataka
# ---------------------------------------------------------------------------

def _get_report_data(campaign_id: int) -> dict:
    """
    Dohvata sve narudžbe kampanje sa ratama i uplatama.
    Vraća strukturirani dict spreman za pisanje u Excel.
    """
    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        if not campaign:
            raise ValueError(f"Kampanja ID={campaign_id} ne postoji.")

        stmt = (
            select(Order)
            .where(Order.campaign_id == campaign_id)
            .options(
                joinedload(Order.customer),
                joinedload(Order.installments).joinedload(Installment.payments),
            )
            .order_by(Order.id.asc())
        )
        orders = list(session.execute(stmt).scalars().unique())

        rows = []
        for idx, order in enumerate(orders, start=1):
            installments = sorted(
                order.installments, key=lambda i: i.installment_number
            )
            inst_data = []
            total_paid = Decimal("0.00")

            for inst in installments:
                paid = sum(
                    (p.amount for p in inst.payments), Decimal("0.00")
                )
                total_paid += paid
                inst_data.append({
                    "number":   inst.installment_number,
                    "due_date": inst.due_date,
                    "amount":   inst.amount,
                    "paid":     paid,
                })

            total_amount = order.total_price_snapshot
            remaining = total_amount - total_paid

            rows.append({
                "rbr":          idx,
                "order_id":     order.id,
                "customer":     order.customer.full_name if order.customer else "?",
                "product":      order.product_name_snapshot,
                "product_code": order.product_code_snapshot or "",
                "total_amount": total_amount,
                "inst_count":   order.installments_count,
                "installments": inst_data,
                "total_paid":   total_paid,
                "remaining":    remaining if remaining > 0 else Decimal("0.00"),
            })

        # Broj kolona za rate = max broj rata u kampanju
        max_inst = max((len(r["installments"]) for r in rows), default=1)

        return {
            "campaign_name": campaign.name,
            "start_date":    campaign.start_date,
            "end_date":      campaign.end_date,
            "rows":          rows,
            "max_inst":      max_inst,
        }


# ---------------------------------------------------------------------------
# Generisanje Excel fajla
# ---------------------------------------------------------------------------

def generate_naplata_excel(
    campaign_id: int,
    output_path: Path,
    agent_code: str = "",
    agent_name: str = "KRUNIĆ STOJANOVIĆ SANJA",
) -> Path:
    """
    Generira Excel izvještaj naplate u formatu "EVIDENCIJA O UPLATAMA RATA".

    Args:
        campaign_id:  ID kampanje iz baze
        output_path:  Putanja gdje se sprema .xlsx fajl
        agent_code:   Saradnički broj (npr. "4-1-11-2-1-3")
        agent_name:   Ime saradnika

    Returns:
        Path do kreiranog fajla
    """
    data = _get_report_data(campaign_id)
    rows = data["rows"]
    max_inst = data["max_inst"]
    campaign_name = data["campaign_name"]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Evidencija naplate"

    # Kolone: B=rbr, C=br_ugovora, D=kupac, E=proizvod, F=vrijednost,
    #         G=br_rata, H..H+max_inst-1=rate, zatim Ukupno, Preostalo
    # Koristimo 1-based indekse za openpyxl

    COL_RBR       = 2   # B
    COL_UGOVOR    = 3   # C
    COL_KUPAC     = 4   # D
    COL_PROIZVOD  = 5   # E
    COL_VRIJED    = 6   # F
    COL_BR_RATA   = 7   # G
    COL_INST_1    = 8   # H — prva rata
    COL_UKUPNO    = COL_INST_1 + max_inst      # iza svih rata
    COL_PREOSTALO = COL_UKUPNO + 1
    LAST_COL      = COL_PREOSTALO

    # Širine kolona
    ws.column_dimensions["A"].width = 2
    ws.column_dimensions[get_column_letter(COL_RBR)].width = 5
    ws.column_dimensions[get_column_letter(COL_UGOVOR)].width = 12
    ws.column_dimensions[get_column_letter(COL_KUPAC)].width = 22
    ws.column_dimensions[get_column_letter(COL_PROIZVOD)].width = 24
    ws.column_dimensions[get_column_letter(COL_VRIJED)].width = 10
    ws.column_dimensions[get_column_letter(COL_BR_RATA)].width = 6
    for i in range(max_inst):
        ws.column_dimensions[get_column_letter(COL_INST_1 + i)].width = 9
    ws.column_dimensions[get_column_letter(COL_UKUPNO)].width = 10
    ws.column_dimensions[get_column_letter(COL_PREOSTALO)].width = 10

    # ---- Red 1: prazan ----
    current_row = 1

    # ---- Red 2: Naslov kompanije ----
    current_row = 2
    ws.row_dimensions[current_row].height = 18
    cell = ws.cell(row=current_row, column=COL_RBR,
                   value='EVIDENCIJA O UPLATAMA RATA ZA „MORE FOR LESS" d.o.o. '
                         'Istočno Sarajevo, Bosna i Hercegovina')
    cell.font = _bold(11, white=False)
    cell.alignment = _left()
    ws.merge_cells(
        start_row=current_row, start_column=COL_RBR,
        end_row=current_row, end_column=LAST_COL
    )

    # ---- Red 3: Info o saradniku i kampanji ----
    current_row = 3
    ws.row_dimensions[current_row].height = 15

    ws.cell(row=current_row, column=COL_RBR, value="Saradnik:").font = _bold()
    ws.cell(row=current_row, column=COL_UGOVOR, value=agent_code).font = _normal()
    ws.cell(row=current_row, column=COL_KUPAC, value=agent_name).font = _bold()
    ws.cell(row=current_row, column=COL_VRIJED, value="Kampanja:").font = _bold()
    ws.cell(row=current_row, column=COL_BR_RATA, value=campaign_name).font = _normal()

    # ---- Red 4: Zaglavlje kolona — nazivi ----
    current_row = 4
    ws.row_dimensions[current_row].height = 28

    headers_row1 = {
        COL_RBR:      "R.\nbr.",
        COL_UGOVOR:   "Br. ugovora\ni datum",
        COL_KUPAC:    "Prezime i\nime",
        COL_PROIZVOD: "Šifra\nproizvoda",
        COL_VRIJED:   "Vrijed.\n(KM)",
        COL_BR_RATA:  "Br.\nrata",
    }
    # Nazivi rata: I, II, III...
    roman = ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"]
    for i in range(max_inst):
        headers_row1[COL_INST_1 + i] = roman[i] if i < len(roman) else str(i+1)
    headers_row1[COL_UKUPNO]    = "Ukupno\n(KM)"
    headers_row1[COL_PREOSTALO] = "Preostalo\n(KM)"

    for col, val in headers_row1.items():
        c = ws.cell(row=current_row, column=col, value=val)
        c.font = _bold(9, white=True)
        c.fill = _header_fill()
        c.alignment = _center()
        c.border = _thin_border()

    # ---- Red 5: Datumi dospijeća rata ----
    current_row = 5
    ws.row_dimensions[current_row].height = 18

    # Prazne ćelije za fiksne kolone
    for col in [COL_RBR, COL_UGOVOR, COL_KUPAC, COL_PROIZVOD,
                COL_VRIJED, COL_BR_RATA, COL_UKUPNO, COL_PREOSTALO]:
        c = ws.cell(row=current_row, column=col, value="")
        c.fill = _subheader_fill()
        c.border = _thin_border()

    # Datumi: uzmemo iz prvog reda koji ima dovoljno rata
    inst_dates: list[Optional[date]] = [None] * max_inst
    for row_data in rows:
        for inst in row_data["installments"]:
            idx = inst["number"] - 1
            if idx < max_inst and inst_dates[idx] is None:
                inst_dates[idx] = inst["due_date"]

    for i, due in enumerate(inst_dates):
        label = due.strftime("%-d.%b.").lower() if due else ""
        c = ws.cell(row=current_row, column=COL_INST_1 + i, value=label)
        c.font = _bold(8, white=False)
        c.fill = _subheader_fill()
        c.alignment = _center()
        c.border = _thin_border()

    # ---- Redovi podataka ----
    for row_data in rows:
        current_row += 1
        ws.row_dimensions[current_row].height = 15

        def _fmt(val: Decimal) -> str:
            return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        ws.cell(row=current_row, column=COL_RBR,
                value=row_data["rbr"]).alignment = _center()
        ws.cell(row=current_row, column=COL_UGOVOR,
                value=str(row_data["order_id"])).alignment = _center()
        ws.cell(row=current_row, column=COL_KUPAC,
                value=row_data["customer"]).alignment = _left()
        ws.cell(row=current_row, column=COL_PROIZVOD,
                value=row_data["product"]).alignment = _left()
        ws.cell(row=current_row, column=COL_VRIJED,
                value=_fmt(row_data["total_amount"])).alignment = Alignment(
                    horizontal="right", vertical="center")
        ws.cell(row=current_row, column=COL_BR_RATA,
                value=row_data["inst_count"]).alignment = _center()

        # Rate
        for inst in row_data["installments"]:
            col = COL_INST_1 + inst["number"] - 1
            if col > COL_UKUPNO - 1:
                continue
            paid = inst["paid"]
            if paid > 0:
                c = ws.cell(row=current_row, column=col, value=_fmt(paid))
                c.alignment = Alignment(horizontal="right", vertical="center")
                c.font = Font(size=9, color="0070C0", bold=True, name="Calibri")

        # Ukupno i preostalo
        ws.cell(row=current_row, column=COL_UKUPNO,
                value=_fmt(row_data["total_paid"])).alignment = Alignment(
                    horizontal="right", vertical="center")
        ws.cell(row=current_row, column=COL_PREOSTALO,
                value=_fmt(row_data["remaining"])).alignment = Alignment(
                    horizontal="right", vertical="center")

        # Border na svim ćelijama reda
        for col in range(COL_RBR, LAST_COL + 1):
            cell = ws.cell(row=current_row, column=col)
            cell.border = _thin_border()
            if not cell.font or cell.font.size is None:
                cell.font = _normal()

        # Alternativne boje redova
        if row_data["rbr"] % 2 == 0:
            light_fill = PatternFill("solid", fgColor="F2F2F2")
            for col in range(COL_RBR, LAST_COL + 1):
                existing = ws.cell(row=current_row, column=col).fill
                if not existing or existing.fgColor.rgb in ("00000000", "FFFFFFFF"):
                    ws.cell(row=current_row, column=col).fill = light_fill

    # ---- UKUPNO red ----
    current_row += 1
    ws.row_dimensions[current_row].height = 16

    ukupno_cells = [COL_RBR, COL_UGOVOR, COL_KUPAC, COL_PROIZVOD,
                    COL_VRIJED, COL_BR_RATA]

    ws.cell(row=current_row, column=COL_RBR, value="UKUPNO")
    ws.merge_cells(
        start_row=current_row, start_column=COL_RBR,
        end_row=current_row, end_column=COL_BR_RATA
    )
    ws.cell(row=current_row, column=COL_RBR).font = _bold(10)
    ws.cell(row=current_row, column=COL_RBR).alignment = _center()

    # Suma po kolonama rata
    for i in range(max_inst):
        col = COL_INST_1 + i
        col_total = sum(
            (r["installments"][i]["paid"]
             if i < len(r["installments"]) else Decimal("0"))
            for r in rows
        )
        if col_total > 0:
            c = ws.cell(row=current_row, column=col,
                        value=_fmt(col_total))
            c.font = _bold(9)
            c.alignment = Alignment(horizontal="right", vertical="center")

    # Ukupno naplaćeno
    grand_paid = sum(r["total_paid"] for r in rows)
    grand_remaining = sum(r["remaining"] for r in rows)
    ws.cell(row=current_row, column=COL_UKUPNO,
            value=_fmt(grand_paid)).font = _bold(9)
    ws.cell(row=current_row, column=COL_PREOSTALO,
            value=_fmt(grand_remaining)).font = _bold(9)

    # Stil UKUPNO reda
    for col in range(COL_RBR, LAST_COL + 1):
        ws.cell(row=current_row, column=col).fill = _ukupno_fill()
        ws.cell(row=current_row, column=col).border = _thin_border()
        ws.cell(row=current_row, column=col).alignment = Alignment(
            horizontal="right", vertical="center"
        )

    # ---- Freeze panes — zaglavlje ostaje vidljivo pri scrollu ----
    ws.freeze_panes = f"{get_column_letter(COL_KUPAC)}6"

    # ---- Orijentacija za print ----
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_title_rows = "4:5"   # zaglavlje se ponavlja na svakoj str.

    wb.save(output_path)
    return output_path
