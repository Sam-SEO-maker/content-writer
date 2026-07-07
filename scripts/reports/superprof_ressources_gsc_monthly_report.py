#!/usr/bin/env python3
"""
Rapport mensuel GSC — superprof.fr/ressources/
Génère un PDF dans _local/ et l'ouvre automatiquement.
Conçu pour être lancé via launchd le 1er de chaque mois.
"""

import os
import sys
import subprocess
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SA_PATH      = Path("/Users/samuel/.credentials/google/google-service-account.json")
LOCAL_DIR    = PROJECT_ROOT / "_local"
LOG_DIR      = LOCAL_DIR / "logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
except ImportError as e:
    sys.exit(f"[ERREUR] Dépendance manquante : {e}\nActive le venv : source .venv/bin/activate")

SCOPES   = ["https://www.googleapis.com/auth/webmasters.readonly"]
PROPERTY = "https://www.superprof.fr/ressources/"

# ── Couleurs Superprof (palette rose corail)
DARK   = colors.HexColor("#1a1a2e")
ACCENT = colors.HexColor("#FE5C5D")   # rose corail Superprof
GREEN  = colors.HexColor("#16a34a")
RED    = colors.HexColor("#dc2626")
ORANGE = colors.HexColor("#ea580c")
YELLOW = colors.HexColor("#ca8a04")
LIGHT  = colors.HexColor("#fff5f5")   # fond rose très clair
BORDER = colors.HexColor("#fecaca")
GRAY   = colors.HexColor("#64748b")


# ══════════════════════════════════════════
# GSC
# ══════════════════════════════════════════

def build_service():
    creds = service_account.Credentials.from_service_account_file(str(SA_PATH), scopes=SCOPES)
    return build("searchconsole", "v1", credentials=creds)


def query(service, date_from, date_to, dimensions=None, limit=25, order_by=None):
    body = {"startDate": date_from, "endDate": date_to, "rowLimit": limit}
    if dimensions:
        body["dimensions"] = dimensions
    if order_by:
        body["orderBy"] = order_by
    r = service.searchanalytics().query(siteUrl=PROPERTY, body=body).execute()
    return r.get("rows", [])


def get_global(service, d_from, d_to):
    rows = query(service, d_from, d_to)
    return rows[0] if rows else {}


def get_pages(service, d_from, d_to, limit=200):
    rows = query(service, d_from, d_to, dimensions=["page"], limit=limit,
                 order_by=[{"fieldName": "clicks", "sortOrder": "DESCENDING"}])
    return {r["keys"][0]: r for r in rows}


def get_keywords(service, d_from, d_to, limit=25):
    return query(service, d_from, d_to, dimensions=["query"], limit=limit,
                 order_by=[{"fieldName": "impressions", "sortOrder": "DESCENDING"}])


def get_weekly(service, base_date):
    results = []
    for i in range(4, 0, -1):
        wk_to   = base_date - timedelta(days=(i - 1) * 7)
        wk_from = wk_to - timedelta(days=6)
        rows = query(service, wk_from.strftime("%Y-%m-%d"), wk_to.strftime("%Y-%m-%d"))
        if rows:
            results.append((wk_from, wk_to, rows[0]))
    return results


# ══════════════════════════════════════════
# PDF
# ══════════════════════════════════════════

def make_styles():
    base = getSampleStyleSheet()

    def s(name, **kw):
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    return {
        "title":    s("title",    fontSize=22, textColor=DARK,   leading=28, spaceAfter=4,  fontName="Helvetica-Bold"),
        "subtitle": s("subtitle", fontSize=11, textColor=GRAY,   leading=16, spaceAfter=20),
        "h2":       s("h2",       fontSize=13, textColor=ACCENT, leading=18, spaceBefore=18, spaceAfter=8, fontName="Helvetica-Bold"),
        "body":     s("body",     fontSize=9,  textColor=DARK,   leading=14, spaceAfter=4),
        "small":    s("small",    fontSize=8,  textColor=GRAY,   leading=12),
        "caption":  s("caption",  fontSize=8,  textColor=GRAY,   leading=11, spaceAfter=6,  alignment=TA_CENTER),
    }


def hr():
    return HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=8, spaceBefore=4)


def section(title, S):
    return [Spacer(1, 0.2 * cm), Paragraph(title, S["h2"]), hr()]


def table_base_style():
    return [
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("ALIGN",         (0, 0), (0, -1),  "LEFT"),
        ("GRID",          (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [LIGHT, colors.white]),
    ]


def header_row_style():
    return [
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
    ]


def generate_pdf(data: dict, out_path: Path, period_label: str, prev_label: str):
    W = A4[0] - 4 * cm
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2.5*cm, bottomMargin=2*cm)
    S = make_styles()
    story = []

    cur  = data["cur"]
    prev = data["prev"]

    def delta_pct(key):
        if not cur or not prev or not prev.get(key): return "N/A"
        v = cur[key] - prev[key]
        return f"{v / prev[key] * 100:+.1f}%"

    def delta_pp(key):
        if not cur or not prev: return "N/A"
        v = (cur[key] - prev[key]) * 100
        return f"{v:+.2f}pp"

    # ── Header
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Superprof Ressources", S["title"]))
    story.append(Paragraph(f"Rapport GSC mensuel — {period_label}", S["subtitle"]))
    story.append(hr())
    story.append(Spacer(1, 0.3 * cm))

    # ── KPIs
    story += section("Vue Globale", S)
    kpi_data = [
        ["Clicks", "Impressions", "CTR moyen", "Position moy."],
        [f"{cur.get('clicks', 0):,.0f}".replace(",", " "),
         f"{cur.get('impressions', 0):,.0f}".replace(",", " "),
         f"{cur.get('ctr', 0) * 100:.2f}%",
         f"{cur.get('position', 0):.1f}"],
        [delta_pct("clicks"), delta_pct("impressions"), delta_pp("ctr"), delta_pct("position")],
    ]
    kpi_ts = TableStyle(table_base_style() + [
        ("BACKGROUND",  (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND",  (0, 1), (-1, 1), LIGHT),
        ("FONTNAME",    (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 1), (-1, 1), 15),
        ("TEXTCOLOR",   (0, 1), (-1, 1), DARK),
        ("FONTSIZE",    (0, 2), (-1, 2), 7.5),
        ("TEXTCOLOR",   (0, 2), (-1, 2), GREEN),
        ("FONTNAME",    (0, 2), (-1, 2), "Helvetica-Bold"),
    ])
    t = Table(kpi_data, colWidths=[W / 4] * 4)
    t.setStyle(kpi_ts)
    story.append(t)
    story.append(Paragraph(f"Comparaison : {prev_label}", S["caption"]))

    # ── Tendance hebdo
    story += section("Tendance Hebdomadaire (4 semaines)", S)
    trend_rows = [["Semaine", "Clicks", "Impressions", "CTR", "Position"]]
    best_clicks = max((r[2]["clicks"] for r in data["weekly"]), default=0)
    for wk_from, wk_to, r in data["weekly"]:
        trend_rows.append([
            f"{wk_from.strftime('%d/%m')} → {wk_to.strftime('%d/%m')}",
            f"{r['clicks']:,.0f}".replace(",", " "),
            f"{r['impressions']:,.0f}".replace(",", " "),
            f"{r['ctr'] * 100:.2f}%",
            f"{r['position']:.1f}",
        ])
    trend_ts = TableStyle(table_base_style() + header_row_style())
    for i, (_, _, r) in enumerate(data["weekly"], 1):
        if r["clicks"] == best_clicks:
            trend_ts.add("BACKGROUND", (0, i), (-1, i), colors.HexColor("#fff0f0"))
            trend_ts.add("FONTNAME",   (1, i), (1, i),  "Helvetica-Bold")
            trend_ts.add("TEXTCOLOR",  (1, i), (1, i),  ACCENT)
    t = Table(trend_rows, colWidths=[W*0.32, W*0.17, W*0.20, W*0.15, W*0.16], repeatRows=1)
    t.setStyle(trend_ts)
    story.append(t)

    # ── Top pages
    story += section("Top 15 Pages par Clicks", S)
    pages_sorted = sorted(data["cur_pages"].items(), key=lambda x: x[1]["clicks"], reverse=True)[:15]
    page_rows = [["URL", "Clicks", "CTR", "Pos.", "Impr.", "Δ Clicks"]]
    for url, d in pages_sorted:
        slug = url.replace("https://www.superprof.fr/ressources", "")
        prev_d = data["prev_pages"].get(url, {})
        delta_c = f"{d['clicks'] - prev_d['clicks']:+.0f}" if prev_d else "NEW"
        page_rows.append([slug or "/", f"{d['clicks']:.0f}", f"{d['ctr']*100:.1f}%",
                           f"{d['position']:.1f}", f"{d['impressions']:.0f}", delta_c])

    page_ts = TableStyle(table_base_style() + header_row_style() + [("FONTSIZE", (0,0),(-1,-1), 7.5)])
    for i, (_, d) in enumerate(pages_sorted, 1):
        ctr = d["ctr"] * 100
        if ctr < 1.0:
            page_ts.add("TEXTCOLOR", (2, i), (2, i), RED)
            page_ts.add("FONTNAME",  (2, i), (2, i), "Helvetica-Bold")
        delta_val = page_rows[i][5]
        if delta_val.startswith("+"):
            page_ts.add("TEXTCOLOR", (5, i), (5, i), GREEN)
        elif delta_val.startswith("-"):
            page_ts.add("TEXTCOLOR", (5, i), (5, i), RED)

    t = Table(page_rows, colWidths=[W*0.40, W*0.09, W*0.09, W*0.09, W*0.12, W*0.13], repeatRows=1)
    t.setStyle(page_ts)
    story.append(t)

    # ── Quick wins CTR
    story += section("Quick Wins — CTR Critique (< 3%, > 500 impr.)", S)
    qw = [(url, d) for url, d in data["cur_pages"].items()
          if d["ctr"] < 0.03 and d["impressions"] > 500]
    qw.sort(key=lambda x: x[1]["impressions"], reverse=True)

    if qw:
        qw_rows = [["Priorité", "URL", "Impr.", "CTR", "Pos.", "Clks pot.*"]]
        for url, d in qw[:10]:
            slug = url.replace("https://www.superprof.fr/ressources", "") or "/"
            impr = d["impressions"]
            ctr  = d["ctr"] * 100
            pot  = f"~{int(impr * 0.03)}"
            prio = "URGENT" if ctr < 0.5 else ("Haute" if ctr < 1.5 else "Moyenne")
            qw_rows.append([prio, slug, f"{impr:.0f}", f"{ctr:.1f}%", f"{d['position']:.1f}", pot])

        qw_ts = TableStyle(table_base_style() + header_row_style() + [("FONTSIZE", (0,0),(-1,-1), 7.5)])
        for i, (url, d) in enumerate(qw[:10], 1):
            prio = qw_rows[i][0]
            c = RED if prio == "URGENT" else (ORANGE if prio == "Haute" else YELLOW)
            qw_ts.add("TEXTCOLOR", (0, i), (0, i), c)
            qw_ts.add("FONTNAME",  (0, i), (0, i), "Helvetica-Bold")
            qw_ts.add("TEXTCOLOR", (3, i), (3, i), RED)
            qw_ts.add("TEXTCOLOR", (5, i), (5, i), GREEN)
            qw_ts.add("FONTNAME",  (5, i), (5, i), "Helvetica-Bold")

        t = Table(qw_rows, colWidths=[W*0.12, W*0.40, W*0.10, W*0.08, W*0.08, W*0.14], repeatRows=1)
        t.setStyle(qw_ts)
        story.append(t)
        story.append(Paragraph("* Estimation à CTR 3%", S["caption"]))
    else:
        story.append(Paragraph("Aucun quick win détecté ce mois-ci.", S["body"]))

    # ── Top keywords
    story += section("Top Keywords par Impressions", S)
    kw_rows = [["Mot-clé", "Impr.", "Clicks", "CTR", "Position"]]
    for row in data["keywords"]:
        kw_rows.append([
            row["keys"][0],
            f"{row['impressions']:.0f}",
            f"{row['clicks']:.0f}",
            f"{row['ctr']*100:.1f}%",
            f"{row['position']:.1f}",
        ])
    kw_ts = TableStyle(table_base_style() + header_row_style())
    t = Table(kw_rows, colWidths=[W*0.42, W*0.14, W*0.12, W*0.12, W*0.14], repeatRows=1)
    t.setStyle(kw_ts)
    story.append(t)

    # ── Footer
    story.append(Spacer(1, 0.6 * cm))
    story.append(hr())
    story.append(Paragraph(
        f"Rapport généré automatiquement le {date.today().strftime('%d/%m/%Y')} "
        f"— Source : Google Search Console API — Propriété : {PROPERTY}",
        S["small"]
    ))

    doc.build(story)


# ══════════════════════════════════════════
# Main
# ══════════════════════════════════════════

def main():
    today     = date.today()
    date_to   = today.strftime("%Y-%m-%d")
    date_from = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    date_from_prev = (today - timedelta(days=60)).strftime("%Y-%m-%d")
    date_to_prev   = (today - timedelta(days=31)).strftime("%Y-%m-%d")

    period_label = f"{(today - timedelta(days=30)).strftime('%d %b')} → {today.strftime('%d %b %Y')}"
    prev_label   = f"Période précédente : {(today - timedelta(days=60)).strftime('%d %b')} → {(today - timedelta(days=31)).strftime('%d %b %Y')}"

    print(f"[GSC] Connexion au service account...")
    service = build_service()

    print(f"[GSC] Récupération des données ({date_from} → {date_to})...")
    cur        = get_global(service, date_from, date_to)
    prev       = get_global(service, date_from_prev, date_to_prev)
    cur_pages  = get_pages(service, date_from, date_to)
    prev_pages = get_pages(service, date_from_prev, date_to_prev)
    keywords   = get_keywords(service, date_from, date_to)
    weekly     = get_weekly(service, today)

    data = dict(cur=cur, prev=prev, cur_pages=cur_pages,
                prev_pages=prev_pages, keywords=keywords, weekly=weekly)

    month_str = today.strftime("%Y-%m")
    out_path  = LOCAL_DIR / f"superprof_ressources_gsc_{month_str}.pdf"

    print(f"[PDF] Génération → {out_path}")
    generate_pdf(data, out_path, period_label, prev_label)

    print(f"[OK] Rapport sauvegardé : {out_path}")
    subprocess.run(["open", str(out_path)])
    return str(out_path)


if __name__ == "__main__":
    main()
