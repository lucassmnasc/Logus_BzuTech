"""
Bizu AI — chatbot inteligente da Bzu Tech (Google Gemini API + motor preditivo local).

1. Extrai parâmetros operacionais da mensagem em linguagem natural;
2. Calcula dispositivos, Payback e ROI de forma determinística via `roi_engine`;
3. Gera a resposta consultiva com Gemini (se `GEMINI_API_KEY` estiver configurada) ou localmente.

Otimizações: cliente Gemini reutilizado entre requisições, timeout curto nas chamadas,
cache das análises por parâmetros e prompt do catálogo montado uma única vez.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .catalog import DISPOSITIVOS_BZU
from .extracao import extrair_parametros_mensagem, parse_valor_monetario  # noqa: F401 (reexport)
from .roi_engine import analisar_operacao, formatar_brl

logger = logging.getLogger(__name__)

NOME_IA = "LOGUS AI"
_TIMEOUT_MS = int(os.environ.get("GEMINI_TIMEOUT_MS", "20000"))


@lru_cache(maxsize=1)
def _carregar_env_local() -> None:
    """Carrega o .env da raiz do projeto uma única vez por processo."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


def _modelo() -> str:
    return os.environ.get("GEMINI_MODEL", "").strip() or "gemini-2.5-flash"


@lru_cache(maxsize=1)
def _cliente_gemini():
    """Cria (uma vez) o cliente Gemini. Retorna None se não houver chave ou SDK."""
    _carregar_env_local()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None
    try:
        return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=_timeout_ms()))
    except Exception:  # pragma: no cover - depende de rede/SDK
        logger.exception("Falha ao inicializar o cliente Gemini")
        return None


@lru_cache(maxsize=1)
def _catalogo_json() -> str:
    catalogo = [
        {
            "codigo": d["codigo"],
            "nome": d["nome"],
            "categoria": d["categoria"],
            "custo_unitario_brl": d["custo_unitario_brl"],
            "mensalidade_saas_brl": d["mensalidade_saas_brl"],
            "aplicacoes": d["aplicacoes"],
        }
        for d in DISPOSITIVOS_BZU.values()
    ]
    return json.dumps(catalogo, ensure_ascii=False)


def _config_extra(types) -> Dict[str, Any]:
    """Gemini 2.5 Flash 'pensa' por padrão e consome max_output_tokens, cortando a resposta."""
    if "flash" in _modelo():
        return {"thinking_config": types.ThinkingConfig(thinking_budget=0)}
    return {}


def _texto_resposta(response) -> Optional[str]:
    try:
        texto = (response.text or "").strip()
    except Exception:
        return None
    return texto or None


def _simulacao_resumida(sim: Dict[str, Any]) -> str:
    """Envia ao modelo só o essencial (prompt menor = resposta mais rápida)."""
    resumo = {
        "parametros": sim["parametros"],
        "pacote": sim["pacote_recomendado"],
        "gateways": sim["qtd_gateways"],
        "dispositivos": [
            {"codigo": d["codigo"], "quantidade": d["quantidade"], "categoria": d["categoria"]}
            for d in sim["dispositivos_sugeridos"]
        ],
        "financeiro": sim["financeiro"],
        "formatado": sim["formatado"],
    }
    return json.dumps(resumo, ensure_ascii=False)


def _montar_system_prompt(simulacao: Dict[str, Any], tem_dados: bool = True) -> str:
    empresa = simulacao["parametros"].get("empresa") or "a empresa do usuário"
    aviso = (
        ""
        if tem_dados
        else "ATENÇÃO: o usuário ainda NÃO informou dados da operação. A simulação abaixo é um cenário "
        "de referência; não a apresente como a operação dele. Peça os dados antes de citar números.\n\n"
    )
    return (
        f"Você é a {NOME_IA}, assistente de inteligência artificial da Bzu Tech "
        "(plataforma IoT para máxima eficiência operacional).\n"
        "Ajude empreendedores e investidores a analisar os dados da operação, recomendar os dispositivos "
        "IoT Bzu Tech ideais e explicar claramente o Payback e o ROI.\n\n"
        "REGRAS:\n"
        "1. Responda em português do Brasil, tom consultivo, objetivo e voltado à decisão de investimento.\n"
        f"2. Trate a empresa pelo nome ({empresa}) e considere o modo de operação informado.\n"
        "3. USE SEMPRE OS NÚMEROS EXATOS da simulação abaixo; não refaça contas.\n"
        "4. Deixe claro que são estimativas e podem ser refinadas com mais dados.\n"
        "5. Use Markdown simples (negrito e listas curtas). Seja conciso (até ~200 palavras).\n"
        "6. Se faltar um dado importante (conta de energia, nº de equipamentos, turnos), faça 1 pergunta curta no final.\n\n"
        f"{aviso}CATÁLOGO BZU TECH:\n{_catalogo_json()}\n\n"
        f"SIMULAÇÃO ATUAL (motor Python):\n{_simulacao_resumida(simulacao)}\n"
    )


def _chamar_gemini(
    mensagem: str,
    simulacao: Dict[str, Any],
    historico: Optional[List[Dict[str, str]]] = None,
    tem_dados: bool = True,
) -> Optional[str]:
    client = _cliente_gemini()
    if client is None:
        return None
    from google.genai import types

    contents: List[Dict[str, Any]] = []
    for item in (historico or [])[-6:]:
        if not isinstance(item, dict):
            continue
        role = "model" if item.get("role") in ("assistant", "model", "bot") else "user"
        text = str(item.get("content") or item.get("text") or "").strip()[:2000]
        if not text or (not contents and role == "model"):
            continue
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"][0]["text"] += "\n\n" + text
        else:
            contents.append({"role": role, "parts": [{"text": text}]})
    if contents and contents[-1]["role"] == "user":
        contents.pop()
    contents.append({"role": "user", "parts": [{"text": mensagem[:4000]}]})

    try:
        response = client.models.generate_content(
            model=_modelo(),
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=_montar_system_prompt(simulacao, tem_dados),
                temperature=0.35,
                max_output_tokens=900,
                **_config_extra(types),
            ),
        )
        return _texto_resposta(response)
    except Exception:
        logger.warning("Gemini indisponível; usando motor local.", exc_info=True)
        return None


def _resposta_fallback_local(mensagem: str, simulacao: Dict[str, Any], tem_dados: bool = True) -> str:
    """Motor conversacional local (sem API externa)."""
    texto = mensagem.lower().strip()
    param = simulacao["parametros"]
    fin = simulacao["financeiro"]
    fmt = simulacao["formatado"]
    mix = simulacao["dispositivos_sugeridos"]
    empresa = param.get("empresa") or ""
    titulo = f"{empresa} — {param['segmento_rotulo']}" if empresa else param["segmento_rotulo"]

    # 1. Pergunta sobre um endpoint específico
    m_ep = _RE_EP.search(texto)
    if m_ep and any(k in texto for k in ("o que", "qual", "sobre", "detalhe", "serve", "faz", "preço", "preco", "custo")):
        ep = DISPOSITIVOS_BZU[m_ep.group(1).replace(" ", "").upper()]
        apps = "\n".join(f"- {a}" for a in ep["aplicacoes"])
        cenario = (
            f"No cenário atual ({param['qtd_dispositivos']} dispositivos), o ROI em 12 meses é **{fmt['roi_12m']}** "
            f"com payback de **{fmt['payback']}**."
            if tem_dados
            else "Me conte sobre sua operação para eu calcular o ROI e o payback com esse endpoint."
        )
        return (
            f"**{ep['nome']}**\n\n{ep['resumo']}\n\n"
            f"- **Variáveis monitoradas:** {', '.join(ep['variaveis_monitoradas'])}\n"
            f"- **Custo de referência:** {formatar_brl(ep['custo_unitario_brl'])} (hardware) + "
            f"{formatar_brl(ep['mensalidade_saas_brl'])}/mês (SaaS)\n"
            f"- **Redução média estimada:** ~{round(ep['reducao_energia_pct'])}% em energia e "
            f"~{round(ep['reducao_paradas_pct'])}% em paradas\n\n"
            f"**Principais aplicações:**\n{apps}\n\n{cenario}"
        )

    # 2. Comparação entre endpoints
    if "diferen" in texto or "compar" in texto:
        linhas = "\n".join(
            f"- **{d['codigo']}** — {d['categoria']}: {formatar_brl(d['custo_unitario_brl'])} + "
            f"{formatar_brl(d['mensalidade_saas_brl'])}/mês"
            for d in DISPOSITIVOS_BZU.values()
        )
        return f"**Comparativo dos endpoints Bzu Tech**\n\n{linhas}\n\nQuer que eu indique o melhor mix para a sua operação?"

    # 3. Saudação
    if _RE_SAUDACAO.fullmatch(texto) or (not tem_dados and len(texto) < 25 and _RE_SAUDACAO.match(texto)):
        return (
            f"Olá! Sou a **{NOME_IA}**. Posso analisar sua operação e calcular:\n\n"
            "- **Dispositivos IoT sugeridos** (`EP111`, `EP300`, `EP400` e `EP600`)\n"
            "- **Economia mensal e anual estimada**\n"
            "- **Payback** e **ROI em 12 meses** para o investidor\n\n"
            "Descreva como funciona sua operação — segmento, turnos, quantidade de equipamentos, "
            "conta de energia e como vocês coletam dados hoje."
        )

    if not tem_dados:
        titulo = f"Cenário de referência ({param['segmento_rotulo']})"

    # 4. Foco financeiro
    if any(k in texto for k in ("payback", "roi", "retorno", "investimento", "lucro", "quanto custa", "viabilidade")) and not any(
        k in texto for k in ("dispositivo", "sensor", "endpoint", "recomenda", "suger")
    ):
        return (
            f"**Análise Financeira — {titulo} ({param['qtd_dispositivos']} dispositivos)**\n\n"
            f"- **Modo de operação:** {param['modo_rotulo']}\n"
            f"- **Investimento inicial (CAPEX):** {fmt['investimento_inicial']} ({simulacao['qtd_gateways']} gateway(s) inclusos)\n"
            f"- **Mensalidade (OPEX):** {fmt['opex_mensal']}/mês — pacote **{simulacao['pacote_recomendado']}**\n"
            f"- **Economia estimada:** {fmt['economia_mensal']}/mês (**{fmt['economia_anual']}/ano**)\n"
            f"- **Payback aproximado:** **{fmt['payback']}** (~{fin['payback_meses']} meses)\n"
            f"- **ROI em 12 meses:** **{fmt['roi_12m']}** (lucro líquido de {fmt['lucro_liquido_12m']})\n\n"
            + (
                "Informe seu **gasto mensal com energia** ou **manutenção** para deixar o cálculo mais preciso."
                if tem_dados
                else "*Valores ilustrativos.* Descreva sua operação para eu calcular os números reais."
            )
        )

    # 5. Diagnóstico completo
    linhas_disp = "\n".join(
        f"- **{d['quantidade']}x {d['codigo']}** ({d['categoria']}) — {d['percentual_mix']}% do mix" for d in mix
    )
    dica = (
        "\n\nPara refinar, me diga sua **conta mensal de energia** ou o **gasto médio com manutenção**."
        if not param.get("custo_energia_mensal")
        else ""
    )
    if not tem_dados:
        dica = "\n\n*Valores ilustrativos.* Descreva sua operação (segmento, nº de equipamentos, conta de energia) para eu calcular os números reais."
    return (
        f"**Diagnóstico da Operação — {titulo}**\n"
        f"{param['qtd_dispositivos']} pontos monitorados · {param['modo_rotulo']} · "
        f"coleta atual: *{param['coleta_rotulo']}* · pacote **{simulacao['pacote_recomendado']}**\n\n"
        f"**Dispositivos Bzu Tech sugeridos:**\n{linhas_disp}\n\n"
        f"**Projeção para o investidor (12 meses):**\n"
        f"- **Investimento inicial:** {fmt['investimento_inicial']}\n"
        f"- **Economia anual estimada:** **{fmt['economia_anual']}** ({fmt['economia_mensal']}/mês)\n"
        f"- **Payback aproximado:** **{fmt['payback']}**\n"
        f"- **ROI em 12 meses:** **{fmt['roi_12m']}**\n"
        f"- **Redução média de energia:** **{fmt['reducao_energia']}**"
        f"{dica}"
    )


_CHAVES_OPERACAO = (
    "qtd_dispositivos",
    "dispositivos",
    "segmento",
    "coleta_atual",
    "modo_operacao",
    "endpoint_preferido",
    "custo_energia_mensal",
    "custo_manutencao_mensal",
    "principal_dor",
    "empresa",
    "descricao_operacao",
)


def _tem_dados_operacao(ctx: Dict[str, Any]) -> bool:
    return any(ctx.get(k) not in (None, "", 0) for k in _CHAVES_OPERACAO)


def responder_chat(
    mensagem: str,
    contexto: Optional[Dict[str, Any]] = None,
    historico: Optional[List[Dict[str, str]]] = None,
) -> Tuple[str, Optional[Dict[str, Any]], Dict[str, Any], str]:
    """Retorna (resposta, simulacao | None, contexto_atualizado, modo_ia)."""
    contexto_atualizado = extrair_parametros_mensagem(mensagem, contexto)
    tem_dados = _tem_dados_operacao(contexto_atualizado)
    simulacao_calculo = analisar_operacao(contexto_atualizado)
    simulacao_retorno = simulacao_calculo if tem_dados else None

    resposta = _chamar_gemini(mensagem, simulacao_calculo, historico, tem_dados)
    if resposta:
        return resposta, simulacao_retorno, contexto_atualizado, "gemini"
    resposta = _resposta_fallback_local(mensagem, simulacao_calculo, tem_dados)
    return resposta, simulacao_retorno, contexto_atualizado, "local"


_CACHE_ANALISES: "OrderedDict[str, str]" = OrderedDict()
_CACHE_MAX = 128


def _analises_ia_cache(simulacao_json: str) -> Optional[str]:
    """Cache por simulação; falhas não são cacheadas (a próxima chamada tenta de novo)."""
    if simulacao_json in _CACHE_ANALISES:
        _CACHE_ANALISES.move_to_end(simulacao_json)
        return _CACHE_ANALISES[simulacao_json]
    bruto = _gerar_analises(simulacao_json)
    if bruto:
        _CACHE_ANALISES[simulacao_json] = bruto
        if len(_CACHE_ANALISES) > _CACHE_MAX:
            _CACHE_ANALISES.popitem(last=False)
    return bruto


def _gerar_analises(simulacao_json: str) -> Optional[str]:
    client = _cliente_gemini()
    if client is None:
        return None
    from google.genai import types

    prompt = (
        "Com base na simulação IoT Bzu Tech abaixo, gere um JSON válido com exatamente 4 chaves: "
        '"economia", "roi", "payback", "eficiencia".\n'
        "Cada valor deve ser uma frase consultiva (25 a 45 palavras) em português do Brasil, citando o nome "
        "da empresa e o modo de operação quando existirem e usando os números exatos.\n"
        f"SIMULAÇÃO:\n{simulacao_json}"
    )
    try:
        response = client.models.generate_content(
            model=_modelo(),
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
                max_output_tokens=1200,
                **_config_extra(types),
            ),
        )
        return _texto_resposta(response)
    except Exception:
        logger.warning("Gemini indisponível para enriquecer análises.", exc_info=True)
        return None


def enriquecer_analises_com_ia(simulacao: Dict[str, Any]) -> Dict[str, Any]:
    """Personaliza os 4 textos da tela /resultado/ com Gemini (mantendo os números)."""
    bruto = _analises_ia_cache(_simulacao_resumida(simulacao))
    if not bruto:
        return simulacao
    try:
        dados = json.loads(bruto)
    except ValueError:
        return simulacao
    chaves = ("economia", "roi", "payback", "eficiencia")
    if isinstance(dados, dict) and all(k in dados for k in chaves):
        simulacao["analises"] = {k: str(dados[k]).strip() for k in chaves}
        simulacao["modo_ia"] = "gemini"
    return simulacao
