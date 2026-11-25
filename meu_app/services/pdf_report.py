"""Geração do relatório PDF da Bizu AI (ReportLab)."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from io import BytesIO
from typing import Any, Dict
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .roi_engine import formatar_brl

ROXO = colors.HexColor("#610f6e")
ROXO_VIVO = colors.HexColor("#bb1dd4")
LILAS = colors.HexColor("#f3d9fa")
TEAL = colors.HexColor("#12a19b")
ESCURO = colors.HexColor("#0b0f19")
CINZA = colors.HexColor("#5b5b6b")


def nome_arquivo(simulacao: Dict[str, Any]) -> str:
    empresa = simulacao.get("parametros", {}).get("empresa") or "operacao"
    slug = unicodedata.normalize("NFKD", empresa).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9]+", "_", slug).strip("_") or "operacao"
    return f"Bizu_AI_Relatorio_{slug[:40]}.pdf"


def _estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("titulo", parent=base["Title"], fontName="Helvetica-Bold", fontSize=20,
                                 textColor=ESCURO, alignment=TA_LEFT, spaceAfter=2),
        "sub": ParagraphStyle("sub", parent=base["Normal"], fontSize=10, textColor=CINZA, leading=14),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13,
                             textColor=ROXO, spaceBefore=12, spaceAfter=6),
        "corpo": ParagraphStyle("corpo", parent=base["Normal"], fontSize=9.5, leading=13.5, textColor=ESCURO),
        "pequeno": ParagraphStyle("pequeno", parent=base["Normal"], fontSize=8, leading=11, textColor=CINZA),
        "kpi_rot": ParagraphStyle("kpi_rot", parent=base["Normal"], fontSize=8, textColor=CINZA, leading=10),
        "kpi_val": ParagraphStyle("kpi_val", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=15,
                                  textColor=ROXO, leading=18),
    }


def _p(texto: Any, estilo) -> Paragraph:
    return Paragraph(escape(str(texto if texto not in (None, "") else "—")), estilo)


def _cabecalho_rodape(canvas, doc):
    largura, altura = A4
    canvas.saveState()
    canvas.setFillColor(ESCURO)
    canvas.rect(0, altura - 22 * mm, largura, 22 * mm, fill=1, stroke=0)
    canvas.setFillColor(ROXO_VIVO)
    canvas.rect(0, altura - 23.2 * mm, largura, 1.2 * mm, fill=1, stroke=0)
    # marca
    canvas.setFillColor(ROXO_VIVO)
    canvas.circle(20 * mm, altura - 11 * mm, 5 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawCentredString(20 * mm, altura - 12.4 * mm, "B")
    canvas.setFont("Helvetica-Bold", 14)
    canvas.drawString(28 * mm, altura - 10 * mm, "Bizu AI")
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(LILAS)
    canvas.drawString(28 * mm, altura - 15 * mm, "Diagnóstico IoT · Bzu Tech")
    canvas.drawRightString(largura - 15 * mm, altura - 12 * mm, datetime.now().strftime("Gerado em %d/%m/%Y %H:%M"))
    # rodapé
    canvas.setFillColor(CINZA)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(15 * mm, 10 * mm, "Estimativas de simulação — valores sujeitos a validação técnica e comercial da Bzu Tech.")
    canvas.drawRightString(largura - 15 * mm, 10 * mm, f"Página {doc.page}")
    canvas.restoreState()


def _tabela(dados, larguras, cabecalho=True):
    t = Table(dados, colWidths=larguras, hAlign="LEFT")
    estilo = [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1 if cabecalho else 0), (-1, -1), [colors.white, colors.HexColor("#faf3fc")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#e6d3ec")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if cabecalho:
        estilo += [
            ("BACKGROUND", (0, 0), (-1, 0), ROXO),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(estilo))
    return t


def _grafico_fluxo(fluxo):
    d = Drawing(170 * mm, 62 * mm)
    ch = VerticalBarChart()
    ch.x, ch.y = 14 * mm, 8 * mm
    ch.width, ch.height = 150 * mm, 46 * mm
    ch.data = [[v / 1000.0 for v in fluxo]]
    ch.categoryAxis.categoryNames = [f"M{m}" for m in range(len(fluxo))]
    ch.categoryAxis.labels.fontSize = 7
    ch.valueAxis.labels.fontSize = 7
    ch.valueAxis.labelTextFormat = lambda v: f"{v:,.0f}k".replace(",", ".")
    ch.bars[0].fillColor = ROXO_VIVO
    ch.bars[0].strokeColor = None
    for i, v in enumerate(fluxo):
        if v >= 0:
            ch.bars[(0, i)].fillColor = TEAL
    d.add(ch)
    d.add(String(14 * mm, 58 * mm, "Fluxo de caixa acumulado (R$ mil) — roxo: recuperando investimento · verde: lucro",
                 fontSize=7.5, fillColor=CINZA))
    return d


def gerar_pdf(simulacao: Dict[str, Any]) -> bytes:
    """Gera o relatório PDF completo da simulação e retorna os bytes."""
    est = _estilos()
    p = simulacao["parametros"]
    fin = simulacao["financeiro"]
    fmt = simulacao["formatado"]
    empresa = p.get("empresa") or "Sua operação"

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=30 * mm, bottomMargin=18 * mm,
        title=f"Bizu AI — Relatório {empresa}", author="Bizu AI · Bzu Tech",
    )
    larg = A4[0] - 30 * mm
    h = []

    h.append(_p(f"Relatório de oportunidade IoT — {empresa}", est["titulo"]))
    h.append(_p(simulacao.get("subtitulo_cenario", ""), est["sub"]))
    h.append(Spacer(1, 8))

    # KPIs
    kpis = [
        ("Economia anual estimada", fmt["economia_anual"]),
        ("ROI em 12 meses", fmt["roi_12m"]),
        ("Payback aproximado", fmt["payback"]),
        ("Investimento inicial", fmt["investimento_inicial"]),
    ]
    cel = [[[_p(r, est["kpi_rot"]), _p(v, est["kpi_val"])] for r, v in kpis]]
    tk = Table(cel, colWidths=[larg / 4] * 4)
    tk.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#faf3fc")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#e0b8ea")),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#e0b8ea")),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    h.append(tk)

    # Dados da empresa
    h.append(_p("Dados da empresa e da operação", est["h2"]))
    energia = formatar_brl(p["custo_energia_mensal"]) + "/mês" if p.get("custo_energia_mensal") else "Não informado"
    manut = formatar_brl(p["custo_manutencao_mensal"]) + "/mês" if p.get("custo_manutencao_mensal") else "Não informado"
    linhas = [
        ["Empresa", p.get("empresa") or "—", "Responsável", p.get("responsavel") or "—"],
        ["Segmento", p["segmento_rotulo"], "Cidade/UF", p.get("cidade") or "—"],
        ["Modo de operação", p["modo_rotulo"], "Coleta de dados atual", p["coleta_rotulo"]],
        ["Pontos monitorados", str(p["qtd_dispositivos"]), "Pacote recomendado", simulacao["pacote_recomendado"]],
        ["Conta de energia", energia, "Gasto com manutenção", manut],
    ]
    linhas = [[_p(c, est["corpo"]) for c in l] for l in linhas]
    t = _tabela(linhas, [larg * 0.18, larg * 0.32, larg * 0.2, larg * 0.3], cabecalho=False)
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold")]))
    h.append(t)
    if p.get("descricao_operacao"):
        h.append(Spacer(1, 6))
        h.append(_p("Descrição da operação informada:", est["pequeno"]))
        for par in str(p["descricao_operacao"]).splitlines():
            if par.strip():
                h.append(_p(par.strip(), est["corpo"]))

    # Dispositivos
    h.append(_p("Dispositivos Bzu Tech sugeridos", est["h2"]))
    disp = [["Endpoint", "Categoria", "Qtd.", "Mix", "Hardware (un.)", "SaaS (un./mês)"]]
    for d in simulacao["dispositivos_sugeridos"]:
        disp.append([
            d["codigo"], _p(d["categoria"], est["corpo"]), str(d["quantidade"]), f"{d['percentual_mix']}%",
            formatar_brl(d["custo_unitario_brl"]), formatar_brl(d["mensalidade_saas_brl"]),
        ])
    h.append(_tabela(disp, [larg * 0.12, larg * 0.38, larg * 0.08, larg * 0.08, larg * 0.17, larg * 0.17]))
    h.append(Spacer(1, 4))
    h.append(_p(f"Inclui {simulacao['qtd_gateways']} gateway(s) e cobertura estimada de {simulacao['cobertura_pct']}% dos ativos.", est["pequeno"]))

    # Financeiro
    h.append(_p("Projeção financeira para o investidor", est["h2"]))
    fin_rows = [
        ["Indicador", "Valor"],
        ["Investimento inicial (CAPEX)", fmt["investimento_inicial"]],
        ["Mensalidade da plataforma (OPEX)", fmt["opex_mensal"] + "/mês"],
        ["Economia mensal estimada", fmt["economia_mensal"]],
        ["Ganho líquido mensal", formatar_brl(fin["ganho_liquido_mensal_brl"])],
        ["Economia anual estimada", fmt["economia_anual"]],
        ["Lucro líquido em 12 meses", fmt["lucro_liquido_12m"]],
        ["ROI em 12 meses", fmt["roi_12m"]],
        ["Payback", f"{fin['payback_meses']} meses"],
        ["Redução média de energia", fmt["reducao_energia"]],
        ["Redução de paradas não planejadas", f"{fin['reducao_paradas_pct']}%"],
    ]
    h.append(_tabela(fin_rows, [larg * 0.6, larg * 0.4]))
    if simulacao.get("fluxo_caixa"):
        h.append(Spacer(1, 8))
        h.append(KeepTogether([_grafico_fluxo(simulacao["fluxo_caixa"])]))

    # Análises
    h.append(_p("Análise da Bizu AI", est["h2"]))
    rotulos = {"economia": "Economia", "roi": "ROI", "payback": "Payback", "eficiencia": "Eficiência energética"}
    for chave, rot in rotulos.items():
        txt = simulacao.get("analises", {}).get(chave)
        if txt:
            h.append(Paragraph(f"<b>{rot}:</b> {escape(str(txt))}", est["corpo"]))
            h.append(Spacer(1, 4))

    h.append(Spacer(1, 10))
    h.append(_p(
        "Metodologia: valores de referência do catálogo Bzu Tech ajustados por segmento, modo de operação e "
        "maturidade de coleta de dados. Quando informados, a conta de energia e o gasto com manutenção são "
        "considerados diretamente no cálculo.", est["pequeno"]))

    doc.build(h, onFirstPage=_cabecalho_rodape, onLaterPages=_cabecalho_rodape)
    return buffer.getvalue()
