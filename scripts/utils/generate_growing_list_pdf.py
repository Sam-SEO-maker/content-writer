"""
Génère un rapport PDF de l'impact des refreshs sur la New Growing List (SP Ressources).
Source : _local/growing_list_impact_30d.json

Usage :
    python scripts/utils/generate_growing_list_pdf.py
"""

import json
from pathlib import Path
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "_local" / "growing_list_impact_30d.json"
OUTPUT_PATH = ROOT / "_local" / "growing_list_impact_30d.pdf"

# Palette Superprof
SP_RED = colors.HexColor("#FE5C5D")
SP_DARK = colors.HexColor("#1A1A2E")
SP_GREY = colors.HexColor("#6B7280")
SP_LIGHT = colors.HexColor("#F9FAFB")
SP_GREEN = colors.HexColor("#10B981")
SP_ORANGE = colors.HexColor("#F59E0B")
SP_BLUE = colors.HexColor("#3B82F6")
WHITE = colors.white


def load_data():
    with open(DATA_PATH) as f:
        return json.load(f)


def delta_str(v, suffix=""):
    sign = "+" if v >= 0 else ""
    return f"{sign}{v}{suffix}"


def pct_str(cur, prev):
    if prev == 0:
        return "+100%" if cur > 0 else "0%"
    p = round((cur - prev) / prev * 100, 1)
    sign = "+" if p >= 0 else ""
    return f"{sign}{p}%"


def build_pdf():
    data = load_data()
    published = data["published"]
    pret = data["pret_pour_relecture"]
    all_articles = published + pret

    period_cur = data["periods"]["current"]
    period_prev = data["periods"]["prev"]

    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    # Styles personnalisés
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Normal"],
        fontSize=22,
        textColor=WHITE,
        fontName="Helvetica-Bold",
        leading=28,
        alignment=TA_LEFT,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#FFD6D6"),
        fontName="Helvetica",
        leading=16,
        alignment=TA_LEFT,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Normal"],
        fontSize=13,
        textColor=SP_DARK,
        fontName="Helvetica-Bold",
        leading=18,
        spaceBefore=14,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        textColor=SP_DARK,
        fontName="Helvetica",
        leading=14,
    )
    small_style = ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontSize=8,
        textColor=SP_GREY,
        fontName="Helvetica",
        leading=11,
    )
    kpi_label_style = ParagraphStyle(
        "KPILabel",
        parent=styles["Normal"],
        fontSize=8,
        textColor=SP_GREY,
        fontName="Helvetica",
        alignment=TA_CENTER,
    )
    kpi_value_style = ParagraphStyle(
        "KPIValue",
        parent=styles["Normal"],
        fontSize=20,
        textColor=SP_DARK,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        leading=24,
    )
    kpi_delta_style = ParagraphStyle(
        "KPIDelta",
        parent=styles["Normal"],
        fontSize=11,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        leading=14,
    )
    note_style = ParagraphStyle(
        "Note",
        parent=styles["Normal"],
        fontSize=8,
        textColor=SP_GREY,
        fontName="Helvetica-Oblique",
        leading=12,
        leftIndent=8,
    )

    story = []

    # ------------------------------------------------------------------ HEADER
    date_style = ParagraphStyle(
        "DateRight",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#FFD6D6"),
        fontName="Helvetica",
        leading=13,
        alignment=TA_RIGHT,
    )
    header_data = [[
        [
            Paragraph("Rapport d'impact — Refreshs SP Ressources", title_style),
            Spacer(1, 4),
            Paragraph(f"New Growing List · {date.today().strftime('%d/%m/%Y')}", subtitle_style),
        ],
        [
            Paragraph(f"Periode actuelle<br/>{period_cur}", date_style),
            Spacer(1, 6),
            Paragraph(f"Periode precedente<br/>{period_prev}", date_style),
        ],
    ]]
    header_table = Table(header_data, colWidths=[11 * cm, 6 * cm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SP_RED),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.5 * cm))

    # --------------------------------------------------------------- KPI TOTAL
    story.append(Paragraph("Vue consolidee — 89 articles refreshes", section_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E5E7EB"), spaceAfter=8))

    tot_clk_prev = sum(r["prev"]["clicks"] for r in all_articles)
    tot_clk_cur = sum(r["current"]["clicks"] for r in all_articles)
    tot_impr_prev = sum(r["prev"]["impressions"] for r in all_articles)
    tot_impr_cur = sum(r["current"]["impressions"] for r in all_articles)
    gainers = len([r for r in all_articles if r["delta_clicks"] > 0])
    losers = len([r for r in all_articles if r["delta_clicks"] < 0])
    stable = len([r for r in all_articles if r["delta_clicks"] == 0])

    def kpi_cell(label, value, delta, delta_color=SP_GREEN):
        return [
            Paragraph(label, kpi_label_style),
            Paragraph(value, kpi_value_style),
            Paragraph(delta, ParagraphStyle("kd", parent=kpi_delta_style, textColor=delta_color)),
        ]

    kpi_data = [[
        kpi_cell("CLICKS", str(tot_clk_cur), pct_str(tot_clk_cur, tot_clk_prev), SP_GREEN),
        kpi_cell("IMPRESSIONS", f"{tot_impr_cur:,}".replace(",", " "), pct_str(tot_impr_cur, tot_impr_prev), SP_GREEN),
        kpi_cell("EN HAUSSE", str(gainers), f"{gainers}/{len(all_articles)} articles", SP_BLUE),
        kpi_cell("EN BAISSE", str(losers), f"{losers}/{len(all_articles)} articles", SP_ORANGE),
    ]]
    # Transposer pour avoir 4 colonnes
    kpi_rows = list(zip(*[kpi_cell(
        *args
    ) for args in [
        ("CLICKS", str(tot_clk_cur), pct_str(tot_clk_cur, tot_clk_prev)),
        ("IMPRESSIONS", f"{tot_impr_cur:,}".replace(",", " "), pct_str(tot_impr_cur, tot_impr_prev)),
        ("EN HAUSSE", str(gainers), f"{gainers}/{len(all_articles)}"),
        ("EN BAISSE", str(losers), f"{losers}/{len(all_articles)}"),
    ]]))

    def make_kpi_table(items):
        """items = [(label, value, delta, delta_color), ...]"""
        col_w = 17 * cm / len(items)
        rows = [
            [Paragraph(it[0], kpi_label_style) for it in items],
            [Paragraph(it[1], kpi_value_style) for it in items],
            [Paragraph(it[2], ParagraphStyle("kd2", parent=kpi_delta_style, textColor=it[3])) for it in items],
        ]
        t = Table(rows, colWidths=[col_w] * len(items))
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SP_LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        return t

    story.append(make_kpi_table([
        ("CLICKS (total)", str(tot_clk_cur), pct_str(tot_clk_cur, tot_clk_prev), SP_GREEN),
        ("IMPRESSIONS", f"{tot_impr_cur:,}".replace(",", " "), pct_str(tot_impr_cur, tot_impr_prev), SP_GREEN),
        ("EN HAUSSE", str(gainers), f"{gainers}/{len(all_articles)} articles", SP_GREEN),
        ("STABLES", str(stable), f"{stable}/{len(all_articles)} articles", SP_GREY),
        ("EN BAISSE", str(losers), f"{losers}/{len(all_articles)} articles", SP_ORANGE),
    ]))
    story.append(Spacer(1, 0.4 * cm))

    # --------------------------------------------------------- PUBLISHED BLOCK
    def section_block(group, label, badge_color):
        items = []
        n = len(group)
        clk_prev = sum(r["prev"]["clicks"] for r in group)
        clk_cur = sum(r["current"]["clicks"] for r in group)
        impr_prev = sum(r["prev"]["impressions"] for r in group)
        impr_cur = sum(r["current"]["impressions"] for r in group)
        g = len([r for r in group if r["delta_clicks"] > 0])
        s = len([r for r in group if r["delta_clicks"] == 0])
        l = len([r for r in group if r["delta_clicks"] < 0])
        pos_impr = len([r for r in group if r.get("delta_pos") is not None and r["delta_pos"] < -0.5])

        items.append(Paragraph(f"{label}  ({n} articles)", section_style))
        items.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E5E7EB"), spaceAfter=6))

        items.append(make_kpi_table([
            ("CLICKS", str(clk_cur), pct_str(clk_cur, clk_prev), SP_GREEN if clk_cur >= clk_prev else SP_ORANGE),
            ("IMPRESSIONS", f"{impr_cur:,}".replace(",", " "), pct_str(impr_cur, impr_prev), SP_GREEN if impr_cur >= impr_prev else SP_ORANGE),
            ("EN HAUSSE", str(g), f"{g}/{n}", SP_GREEN),
            ("POSITION AMÉL.", str(pos_impr), f"{pos_impr}/{n} articles", SP_BLUE),
        ]))
        items.append(Spacer(1, 0.3 * cm))

        # Top 5 gagnants
        top5 = sorted(group, key=lambda x: x["delta_clicks"], reverse=True)[:5]
        headers = ["Article", "Clk avant", "Clk après", "Delta", "Impr avant", "Impr après", "Pos avant", "Pos après"]
        col_ws = [5.8 * cm, 1.4 * cm, 1.4 * cm, 1.2 * cm, 1.6 * cm, 1.6 * cm, 1.5 * cm, 1.5 * cm]

        def tbl_para(txt, bold=False, align=TA_LEFT, color=SP_DARK):
            st = ParagraphStyle("tc", parent=styles["Normal"], fontSize=7.5,
                                fontName="Helvetica-Bold" if bold else "Helvetica",
                                textColor=color, alignment=align, leading=10)
            return Paragraph(str(txt), st)

        header_row = [tbl_para(h, bold=True, align=TA_CENTER) for h in headers]
        rows = [header_row]
        for r in top5:
            slug = r["url"].split("/")[-1].replace(".html", "")[:42]
            d = r["delta_clicks"]
            d_color = SP_GREEN if d > 0 else (SP_ORANGE if d < 0 else SP_GREY)
            pos_b = r["prev"]["position"] if r["prev"]["position"] > 0 else "-"
            pos_a = r["current"]["position"] if r["current"]["position"] > 0 else "-"
            rows.append([
                tbl_para(slug),
                tbl_para(r["prev"]["clicks"], align=TA_CENTER),
                tbl_para(r["current"]["clicks"], align=TA_CENTER),
                tbl_para(delta_str(d), bold=True, align=TA_CENTER, color=d_color),
                tbl_para(r["prev"]["impressions"], align=TA_CENTER),
                tbl_para(r["current"]["impressions"], align=TA_CENTER),
                tbl_para(pos_b, align=TA_CENTER),
                tbl_para(pos_a, align=TA_CENTER),
            ])

        t = Table(rows, colWidths=col_ws)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), badge_color),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SP_LIGHT]),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        items.append(Paragraph("Top 5 gagnants (clicks)", ParagraphStyle("sh", parent=styles["Normal"],
            fontSize=9, fontName="Helvetica-Bold", textColor=SP_GREY, spaceAfter=4)))
        items.append(t)
        items.append(Spacer(1, 0.25 * cm))

        # Top progressions position
        pos_top = sorted(
            [r for r in group if r.get("delta_pos") is not None and r["delta_pos"] < -0.5],
            key=lambda x: x["delta_pos"]
        )[:5]
        if pos_top:
            items.append(Paragraph("Meilleures progressions de position", ParagraphStyle("sh2", parent=styles["Normal"],
                fontSize=9, fontName="Helvetica-Bold", textColor=SP_GREY, spaceAfter=4)))
            pos_rows = [[tbl_para(h, bold=True, align=TA_CENTER) for h in ["Article", "Delta pos", "Pos avant", "Pos après", "Clk avant", "Clk après"]]]
            pos_col_ws = [6.5 * cm, 2 * cm, 2 * cm, 2 * cm, 2 * cm, 2.5 * cm]
            for r in pos_top:
                slug = r["url"].split("/")[-1].replace(".html", "")[:46]
                dp = r["delta_pos"]
                pos_rows.append([
                    tbl_para(slug),
                    tbl_para(f"{dp:+.1f}", bold=True, align=TA_CENTER, color=SP_GREEN),
                    tbl_para(r["prev"]["position"], align=TA_CENTER),
                    tbl_para(r["current"]["position"], align=TA_CENTER),
                    tbl_para(r["prev"]["clicks"], align=TA_CENTER),
                    tbl_para(r["current"]["clicks"], align=TA_CENTER),
                ])
            tp = Table(pos_rows, colWidths=pos_col_ws)
            tp.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), badge_color),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SP_LIGHT]),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            items.append(tp)
        items.append(Spacer(1, 0.3 * cm))

        return items

    story.extend(section_block(published, "Articles Publies", SP_RED))
    story.extend(section_block(pret, "Pret pour relecture", SP_BLUE))

    # --------------------------------------------------------------- OPPORTUNITES
    story.append(Paragraph("Opportunites — A publier en priorite", section_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E5E7EB"), spaceAfter=8))

    # URLs prêt avec meilleure progression de position
    opps = sorted(
        [r for r in pret if r.get("delta_pos") is not None and r["delta_pos"] < -3],
        key=lambda x: x["delta_pos"]
    )[:8]

    if opps:
        opp_rows = [[Paragraph(h, ParagraphStyle("oh", parent=styles["Normal"], fontSize=8,
                    fontName="Helvetica-Bold", textColor=WHITE, alignment=TA_CENTER))
                    for h in ["Article", "Mot-cle principal", "Pos avant", "Pos apres", "Delta", "Impressions"]]]
        opp_col_ws = [5.5 * cm, 4 * cm, 1.7 * cm, 1.7 * cm, 1.5 * cm, 2.6 * cm]
        for r in opps:
            slug = r["url"].split("/")[-1].replace(".html", "")
            dp = r["delta_pos"]
            opp_rows.append([
                Paragraph(slug, ParagraphStyle("oc", parent=styles["Normal"], fontSize=7.5, fontName="Helvetica", leading=10)),
                Paragraph(r.get("main_kw", ""), ParagraphStyle("oc2", parent=styles["Normal"], fontSize=7.5, fontName="Helvetica-Oblique", textColor=SP_GREY, leading=10)),
                Paragraph(str(r["prev"]["position"]), ParagraphStyle("oc3", parent=styles["Normal"], fontSize=7.5, alignment=TA_CENTER)),
                Paragraph(str(r["current"]["position"]), ParagraphStyle("oc4", parent=styles["Normal"], fontSize=7.5, alignment=TA_CENTER)),
                Paragraph(f"{dp:+.1f}", ParagraphStyle("oc5", parent=styles["Normal"], fontSize=7.5, fontName="Helvetica-Bold", textColor=SP_GREEN, alignment=TA_CENTER)),
                Paragraph(str(r["current"]["impressions"]), ParagraphStyle("oc6", parent=styles["Normal"], fontSize=7.5, alignment=TA_CENTER)),
            ])
        opp_t = Table(opp_rows, colWidths=opp_col_ws)
        opp_t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SP_DARK),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SP_LIGHT]),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(Paragraph(
            "Ces articles sont encore en attente de publication mais progressent deja en position — "
            "les publier accelererait la conversion impressions → clicks.",
            note_style
        ))
        story.append(Spacer(1, 0.2 * cm))
        story.append(opp_t)

    # ------------------------------------------------------------------ FOOTER
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB")))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        f"Rapport genere le {date.today().strftime('%d/%m/%Y')} · "
        f"Source : Google Search Console · Propriete : superprof.fr/ressources/",
        ParagraphStyle("footer", parent=styles["Normal"], fontSize=7, textColor=SP_GREY,
                       fontName="Helvetica", alignment=TA_CENTER)
    ))

    doc.build(story)
    print(f"[OK] PDF genere : {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
