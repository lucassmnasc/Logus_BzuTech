"""
Motor de análise operacional e cálculo financeiro (ROI, Payback e Economia) para IoT Bzu Tech.

Mantém toda a matemática financeira determinística e auditável em Python,
servindo tanto à tela de resultados quanto como ferramenta de suporte ao chatbot de IA.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from .catalog import (
    CUSTO_GATEWAY_BRL,
    DISPOSITIVOS_BZU,
    DISPOSITIVOS_POR_GATEWAY,
    FATOR_COLETA,
    SEGMENTOS,
)


def _normalizar_segmento(segmento: Optional[str]) -> str:
    if not segmento:
        return "autocentro"
    s = segmento.strip().lower()
    if any(k in s for k in ("auto", "oficina", "mecan", "veic", "pneu", "revis")):
        return "autocentro"
    if any(k in s for k in ("ind", "fabr", "manuf", "planta", "maquin", "produc")):
        return "industria"
    if any(k in s for k in ("frot", "caminh", "transp", "mobil", "carro", "moto")):
        return "frotas"
    if any(k in s for k in ("log", "galp", "estoq", "armaz", "cd", "centro de distrib")):
        return "logistica"
    if any(k in s for k in ("pred", "edif", "facilit", "comerc", "loja", "shop", "escrit")):
        return "predial"
    return s if s in SEGMENTOS else "autocentro"


def _normalizar_coleta(coleta: Optional[str]) -> str:
    if not coleta:
        return "planilha-manual"
    c = coleta.strip().lower()
    if c in FATOR_COLETA:
        return c
    if any(k in c for k in ("nao", "não", "nada", "nenhum", "manualmente nao")):
        return "nao-coletamos"
    if any(k in c for k in ("planil", "excel", "papel", "manual")):
        return "planilha-manual"
    if any(k in c for k in ("sensor", "iot", "telemetr")):
        return "sensoriamento"
    if any(k in c for k in ("ia", "intelig", "analytics", "bi")):
        return "ia"
    return "planilha-manual"


def _normalizar_endpoint(endpoint: Optional[str]) -> Optional[str]:
    if not endpoint:
        return None
    ep = endpoint.strip().upper()
    return ep if ep in DISPOSITIVOS_BZU else None


def _definir_pacote(qtd_dispositivos: int) -> Dict[str, Any]:
    if qtd_dispositivos <= 20:
        return {
            "nome": "Starter IoT",
            "cobertura_pct": min(95, 55 + qtd_dispositivos),
            "desconto_volume": 0.0,
        }
    if qtd_dispositivos <= 150:
        return {
            "nome": "Business IoT",
            "cobertura_pct": min(95, 65 + int((qtd_dispositivos - 20) * 0.2)),
            "desconto_volume": 0.08,
        }
    return {
        "nome": "Enterprise IoT",
        "cobertura_pct": min(98, 85 + int((qtd_dispositivos - 150) * 0.03)),
        "desconto_volume": 0.15,
    }


def _sugerir_mix_dispositivos(
    qtd_dispositivos: int,
    segmento_key: str,
    endpoint_preferido: Optional[str] = None,
    principal_dor: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Define a composição recomendada de dispositivos Bzu Tech.
    Se o usuário escolheu um endpoint específico na interface, ele lidera o mix (65%)
    e é complementado pelos dispositivos ideais do segmento/dor.
    """
    mix_proporcoes: List[Tuple[str, float]] = list(SEGMENTOS[segmento_key]["mix_padrao"])

    # Ajuste pela dor principal declarada pelo investidor
    if principal_dor:
        dor = principal_dor.lower()
        if any(k in dor for k in ("energ", "luz", "eletric", "conta")):
            mix_proporcoes = [("EP300", 0.60), ("EP111", 0.25), ("EP400", 0.15)]
        elif any(k in dor for k in ("parad", "quebr", "manut", "downtime", "vibr")):
            mix_proporcoes = [("EP400", 0.55), ("EP300", 0.30), ("EP600", 0.15)]
        elif any(k in dor for k in ("frot", "combust", "rota", "veic")):
            mix_proporcoes = [("EP600", 0.70), ("EP300", 0.30)]

    # Se o usuário selecionou um endpoint específico, prioriza-o no mix
    if endpoint_preferido and endpoint_preferido in DISPOSITIVOS_BZU:
        outros = [(cod, prop) for cod, prop in mix_proporcoes if cod != endpoint_preferido]
        if not outros:
            mix_proporcoes = [(endpoint_preferido, 1.0)]
        else:
            soma_outros = sum(prop for _, prop in outros) or 1.0
            mix_proporcoes = [(endpoint_preferido, 0.65)] + [
                (cod, 0.35 * (prop / soma_outros)) for cod, prop in outros
            ]

    # Distribui a quantidade inteira garantindo que a soma feche exatamente em qtd_dispositivos
    sugestoes: List[Dict[str, Any]] = []
    alocados = 0

    for idx, (codigo, prop) in enumerate(mix_proporcoes):
        if idx == len(mix_proporcoes) - 1:
            qtd = max(0, qtd_dispositivos - alocados)
        else:
            qtd = max(1 if qtd_dispositivos >= len(mix_proporcoes) else 0, round(qtd_dispositivos * prop))
            qtd = min(qtd, qtd_dispositivos - alocados)
        if qtd <= 0:
            continue
        alocados += qtd
        spec = DISPOSITIVOS_BZU[codigo]
        sugestoes.append(
            {
                "codigo": codigo,
                "nome": spec["nome"],
                "categoria": spec["categoria"],
                "resumo": spec["resumo"],
                "quantidade": qtd,
                "percentual_mix": round((qtd / qtd_dispositivos) * 100),
                "custo_unitario_brl": spec["custo_unitario_brl"],
                "mensalidade_saas_brl": spec["mensalidade_saas_brl"],
                "aplicacoes": spec["aplicacoes"],
                "variaveis_monitoradas": spec["variaveis_monitoradas"],
            }
        )

    # Caso extremo (ex.: qtd_dispositivos == 1)
    if not sugestoes:
        codigo = endpoint_preferido or mix_proporcoes[0][0]
        spec = DISPOSITIVOS_BZU[codigo]
        sugestoes.append(
            {
                "codigo": codigo,
                "nome": spec["nome"],
                "categoria": spec["categoria"],
                "resumo": spec["resumo"],
                "quantidade": qtd_dispositivos,
                "percentual_mix": 100,
                "custo_unitario_brl": spec["custo_unitario_brl"],
                "mensalidade_saas_brl": spec["mensalidade_saas_brl"],
                "aplicacoes": spec["aplicacoes"],
                "variaveis_monitoradas": spec["variaveis_monitoradas"],
            }
        )

    return sugestoes


def formatar_brl(valor: float) -> str:
    """Formata número em moeda brasileira (ex.: R$ 356.400)."""
    inteiro = round(valor)
    return f"R$ {inteiro:,.0f}".replace(",", ".")


def analisar_operacao(dados: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calcula dispositivos recomendados, investimento, economia, ROI (12 meses) e Payback.

    Parâmetros aceitos em `dados` (todos opcionais com defaults inteligentes):
      - qtd_dispositivos / dispositivos (int): quantidade de ativos/pontos monitorados
      - segmento (str): autocentro, industria, frotas, logistica, predial
      - coleta_atual / coleta (str): nao-coletamos, planilha-manual, ia, sensoriamento
      - endpoint / endpoint_preferido (str): EP111, EP300, EP400, EP600
      - custo_energia_mensal (float): conta mensal de energia em R$
      - custo_manutencao_mensal (float): gasto mensal com manutenção/paradas em R$
      - principal_dor (str): energia, paradas, frota, visibilidade, produtividade
      - empresa (str): nome da empresa do investidor
    """
    raw_qtd = dados.get("qtd_dispositivos", dados.get("dispositivos", 80))
    try:
        qtd_dispositivos = max(1, min(2000, int(float(raw_qtd))))
    except (TypeError, ValueError):
        qtd_dispositivos = 80

    segmento_key = _normalizar_segmento(dados.get("segmento"))
    coleta_key = _normalizar_coleta(dados.get("coleta_atual", dados.get("coleta")))
    endpoint_pref = _normalizar_endpoint(dados.get("endpoint_preferido", dados.get("endpoint")))
    principal_dor = (dados.get("principal_dor") or "").strip()

    def _to_float(val: Any) -> Optional[float]:
        if val in (None, "", 0, "0"):
            return None
        try:
            num = float(str(val).replace("R$", "").replace(".", "").replace(",", ".").strip())
            return num if num > 0 else None
        except ValueError:
            return None

    custo_energia_mensal = _to_float(dados.get("custo_energia_mensal"))
    custo_manutencao_mensal = _to_float(dados.get("custo_manutencao_mensal"))

    seg_info = SEGMENTOS[segmento_key]
    coleta_info = FATOR_COLETA[coleta_key]
    pacote = _definir_pacote(qtd_dispositivos)

    mix = _sugerir_mix_dispositivos(
        qtd_dispositivos=qtd_dispositivos,
        segmento_key=segmento_key,
        endpoint_preferido=endpoint_pref,
        principal_dor=principal_dor,
    )

    # Cálculo de custos (CAPEX + OPEX) com desconto de volume do pacote
    fator_desc = 1.0 - pacote["desconto_volume"]
    qtd_gateways = max(1, math.ceil(qtd_dispositivos / DISPOSITIVOS_POR_GATEWAY))

    capex_dispositivos = 0.0
    opex_mensal = 0.0
    economia_mensal_padrao = 0.0
    soma_red_energia = 0.0
    soma_red_paradas = 0.0

    for item in mix:
        spec = DISPOSITIVOS_BZU[item["codigo"]]
        q = item["quantidade"]
        capex_dispositivos += q * (spec["custo_unitario_brl"] + spec["instalacao_unitaria_brl"]) * fator_desc
        opex_mensal += q * spec["mensalidade_saas_brl"] * fator_desc
        economia_mensal_padrao += q * spec["economia_mensal_base_brl"]
        soma_red_energia += q * spec["reducao_energia_pct"]
        soma_red_paradas += q * spec["reducao_paradas_pct"]

    capex_gateways = qtd_gateways * CUSTO_GATEWAY_BRL * fator_desc
    investimento_inicial = capex_dispositivos + capex_gateways
    opex_anual = opex_mensal * 12.0
    investimento_total_12m = investimento_inicial + opex_anual

    # Taxas médias ponderadas do mix
    reducao_energia_pct = min(
        32.0,
        (soma_red_energia / qtd_dispositivos) + coleta_info["bonus_energia_pct"],
    )
    reducao_paradas_pct = min(45.0, soma_red_paradas / qtd_dispositivos)

    # Economia mensal: combina dados reais informados pelo cliente (se houver) com o benchmark por dispositivo
    multiplicador = seg_info["multiplicador_economia"] * coleta_info["multiplicador_economia"]
    economia_mensal_benchmark = economia_mensal_padrao * multiplicador

    if custo_energia_mensal or custo_manutencao_mensal:
        econ_energia = (custo_energia_mensal or 0.0) * (reducao_energia_pct / 100.0)
        econ_manutencao = (custo_manutencao_mensal or 0.0) * (reducao_paradas_pct / 100.0)
        # Se o cliente só informou um dos dois custos, soma uma parcela conservadora do benchmark operacional
        if custo_energia_mensal and custo_manutencao_mensal:
            economia_mensal = econ_energia + econ_manutencao + (economia_mensal_benchmark * 0.25)
        else:
            economia_mensal = econ_energia + econ_manutencao + (economia_mensal_benchmark * 0.55)
    else:
        economia_mensal = economia_mensal_benchmark

    economia_anual = economia_mensal * 12.0
    ganho_liquido_mensal = economia_mensal - opex_mensal
    lucro_liquido_12m = economia_anual - investimento_total_12m

    # ROI em 12 meses (%)
    roi_12m_pct = (lucro_liquido_12m / investimento_total_12m) * 100.0 if investimento_total_12m > 0 else 0.0

    # Payback em meses (tempo para recuperar o CAPEX com o ganho líquido mensal)
    if ganho_liquido_mensal > 0:
        payback_meses = investimento_inicial / ganho_liquido_mensal
    else:
        payback_meses = 36.0

    payback_arredondado = max(1, round(payback_meses))
    economia_energia_arredondada = round(reducao_energia_pct)
    roi_arredondado = round(roi_12m_pct)

    codigos_str = ", ".join(f"{item['quantidade']}x {item['codigo']}" for item in mix)

    # Textos analíticos detalhados para a tela de resultado
    analises = {
        "economia": (
            f"Com {qtd_dispositivos} pontos monitorados ({codigos_str}) no segmento de "
            f"{seg_info['rotulo'].lower()}, estima-se uma economia de {formatar_brl(economia_mensal)}/mês "
            f"({formatar_brl(economia_anual)}/ano). Como o cenário atual é '{coleta_info['rotulo']}', "
            f"{coleta_info['descricao'].lower()}"
        ),
        "roi": (
            f"Considerando investimento inicial de {formatar_brl(investimento_inicial)} "
            f"(hardware, {qtd_gateways} gateway(s) e instalação) mais {formatar_brl(opex_anual)}/ano "
            f"de plataforma SaaS ({pacote['nome']}), o retorno líquido em 12 meses é de "
            f"{formatar_brl(lucro_liquido_12m)}, resultando em ROI de {roi_arredondado}%."
        ),
        "payback": (
            f"Com ganho líquido mensal estimado em {formatar_brl(ganho_liquido_mensal)} "
            f"(economia mensal já descontando a mensalidade SaaS de {formatar_brl(opex_mensal)}), "
            f"o capital investido retorna em aproximadamente {payback_meses:.1f} meses."
        ),
        "eficiencia": (
            f"O mix recomendado prioriza {seg_info['foco']}, projetando redução média de "
            f"{economia_energia_arredondada}% no consumo energético e até {round(reducao_paradas_pct)}% "
            f"menos paradas corretivas não planejadas."
        ),
    }

    return {
        "parametros": {
            "qtd_dispositivos": qtd_dispositivos,
            "segmento": segmento_key,
            "segmento_rotulo": seg_info["rotulo"],
            "coleta_atual": coleta_key,
            "coleta_rotulo": coleta_info["rotulo"],
            "endpoint_preferido": endpoint_pref or "",
            "principal_dor": principal_dor,
            "custo_energia_mensal": custo_energia_mensal,
            "custo_manutencao_mensal": custo_manutencao_mensal,
            "empresa": dados.get("empresa") or "",
        },
        "pacote_recomendado": pacote["nome"],
        "cobertura_pct": pacote["cobertura_pct"],
        "qtd_gateways": qtd_gateways,
        "dispositivos_sugeridos": mix,
        "financeiro": {
            "investimento_inicial_brl": round(investimento_inicial, 2),
            "opex_mensal_brl": round(opex_mensal, 2),
            "opex_anual_brl": round(opex_anual, 2),
            "investimento_total_12m_brl": round(investimento_total_12m, 2),
            "economia_mensal_brl": round(economia_mensal, 2),
            "economia_anual_brl": round(economia_anual, 2),
            "ganho_liquido_mensal_brl": round(ganho_liquido_mensal, 2),
            "lucro_liquido_12m_brl": round(lucro_liquido_12m, 2),
            "roi_12m_pct": roi_arredondado,
            "payback_meses": round(payback_meses, 1),
            "payback_meses_int": payback_arredondado,
            "reducao_energia_pct": economia_energia_arredondada,
            "reducao_paradas_pct": round(reducao_paradas_pct),
        },
        "formatado": {
            "investimento_inicial": formatar_brl(investimento_inicial),
            "opex_mensal": formatar_brl(opex_mensal),
            "economia_mensal": formatar_brl(economia_mensal),
            "economia_anual": formatar_brl(economia_anual),
            "lucro_liquido_12m": formatar_brl(lucro_liquido_12m),
            "roi_12m": f"{roi_arredondado}%",
            "payback": f"{payback_arredondado} {'mês' if payback_arredondado == 1 else 'meses'}",
            "reducao_energia": f"{economia_energia_arredondada}%",
        },
        "subtitulo_cenario": f"Cenário para {seg_info['rotulo'].lower()}, priorizando {seg_info['foco']}.",
        "analises": analises,
    }
