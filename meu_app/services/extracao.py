"""
Extração de parâmetros operacionais a partir de texto livre (chat ou descrição da operação).

Módulo independente para evitar import circular entre `roi_engine` e `chatbot`.
As expressões regulares são compiladas uma única vez (melhor desempenho por requisição).
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

_RE_EP = re.compile(r"\b(ep\s?111|ep\s?300|ep\s?400|ep\s?600)\b")
_RE_QTD = re.compile(
    r"(\d{1,4})\s*(dispositivos?|sensores?|equipamentos?|máquinas?|maquinas?|pontos?|ativos?|baias?|"
    r"elevadores?|veículos?|veiculos?|caminhões?|caminhoes?|motores?|compressores?)"
)
_VALOR = r"(\d[\d\.,]*(?:\s*(?:mil|k))?)"
_RE_ENERGIA = re.compile(
    rf"(?:energia|luz|el[eé]trica)[^0-9]{{0,25}}(?:r\$\s*)?{_VALOR}"
    rf"|(?:r\$\s*)?{_VALOR}\s*(?:reais\s*)?(?:de|em|com|na|no)\s*(?:energia|luz|conta de luz)"
)
_RE_MANUT = re.compile(
    rf"(?:manuten[çc][ãa]o|paradas?)[^0-9]{{0,25}}(?:r\$\s*)?{_VALOR}"
    rf"|(?:r\$\s*)?{_VALOR}\s*(?:reais\s*)?(?:de|em|com)\s*(?:manuten[çc][ãa]o|paradas?)"
)
_RE_NUM = re.compile(r"(\d[\d\.,]*)")
_RE_MIL = re.compile(r"\bmil\b|\bk\b|\dk\b")


def _contem(texto: str, termos) -> bool:
    return any(t in texto for t in termos)


def parse_valor_monetario(texto: str) -> Optional[float]:
    """Converte '20.000', '18 mil', '15k', '12.500,50' em float."""
    t = texto.lower().strip()
    mult = 1_000_000.0 if "milh" in t else (1_000.0 if _RE_MIL.search(t) else 1.0)
    m = _RE_NUM.search(t)
    if not m:
        return None
    raw = m.group(1).rstrip(".,")
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    elif raw.count(".") > 1 or (raw.count(".") == 1 and len(raw.split(".")[1]) == 3):
        raw = raw.replace(".", "")
    try:
        return float(raw) * mult
    except ValueError:
        return None


def extrair_parametros_mensagem(mensagem: str, contexto_atual: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Extrai dados operacionais do texto e mescla com o contexto existente."""
    ctx: Dict[str, Any] = dict(contexto_atual or {})
    texto = (mensagem or "").lower()
    if not texto.strip():
        return ctx

    # Segmento
    if _contem(texto, ("autocentro", "oficina", "mecânic", "mecanic", "elevador", "automotiv", "funilaria")):
        ctx["segmento"] = "autocentro"
    elif _contem(texto, ("indústr", "industr", "fábric", "fabric", "manufat", "planta")):
        ctx["segmento"] = "industria"
    elif _contem(texto, ("frota", "caminh", "veícul", "veicul", "transporte")):
        ctx["segmento"] = "frotas"
    elif _contem(texto, ("logíst", "logist", "galpão", "galpao", "armaz", "estoque", "doca")):
        ctx["segmento"] = "logistica"
    elif _contem(texto, ("predial", "prédio", "predio", "edifício", "edificio", "condomín", "shopping")):
        ctx["segmento"] = "predial"

    # Maturidade de coleta de dados
    if _contem(texto, ("não colet", "nao colet", "nenhum dado", "sem dados", "nada hoje", "não medimos", "nao medimos")):
        ctx["coleta_atual"] = "nao-coletamos"
    elif _contem(texto, ("planilha", "excel", "papel", "caderno")):
        ctx["coleta_atual"] = "planilha-manual"
    elif _contem(texto, ("já temos sensor", "ja temos sensor", "sensoriamento", "temos sensores")):
        ctx["coleta_atual"] = "sensoriamento"
    elif _contem(texto, ("já usamos ia", "ja usamos ia", "inteligência artificial", "analytics")):
        ctx["coleta_atual"] = "ia"

    # Modo / regime de operação
    if _contem(texto, ("24/7", "24h", "24 horas", "contínu", "continu", "ininterrupt", "três turnos", "tres turnos", "3 turnos")):
        ctx["modo_operacao"] = "continuo"
    elif _contem(texto, ("dois turnos", "2 turnos", "16h", "16 horas")):
        ctx["modo_operacao"] = "dois-turnos"
    elif _contem(texto, ("horário comercial", "horario comercial", "um turno", "1 turno", "8h às", "8h as")):
        ctx["modo_operacao"] = "comercial"

    # Dor principal
    if _contem(texto, ("energia", "conta de luz", "elétric", "eletric", "kwh")):
        ctx["principal_dor"] = "energia"
    elif _contem(texto, ("parada", "quebra", "manutenção", "manutencao", "downtime", "vibra")):
        ctx["principal_dor"] = "paradas"
    elif _contem(texto, ("combustível", "combustivel", "rota", "rastreamento")):
        ctx["principal_dor"] = "frota"

    m_ep = _RE_EP.search(texto)
    if m_ep:
        ctx["endpoint_preferido"] = m_ep.group(1).replace(" ", "").upper()

    m_qtd = _RE_QTD.search(texto)
    if m_qtd:
        qtd = int(m_qtd.group(1))
        if 1 <= qtd <= 2000:
            ctx["qtd_dispositivos"] = qtd

    m_en = _RE_ENERGIA.search(texto)
    if m_en:
        val = parse_valor_monetario(m_en.group(1) or m_en.group(2))
        if val and val >= 200:
            ctx["custo_energia_mensal"] = val

    m_ma = _RE_MANUT.search(texto)
    if m_ma:
        val = parse_valor_monetario(m_ma.group(1) or m_ma.group(2))
        if val and val >= 200:
            ctx["custo_manutencao_mensal"] = val

    return ctx
