"""
Chatbot com IA da Bzu Tech (Google Gemini API + Fallback Inteligente Local).

Combina:
1. Extração de parâmetros operacionais a partir de mensagens em linguagem natural;
2. Cálculos determinísticos de Dispositivos, Payback e ROI via `roi_engine.py`;
3. Geração consultiva via Google Gemini (`google-genai`) quando `GEMINI_API_KEY` estiver configurada,
   ou motor conversacional local inteligente quando rodar sem chave de API.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .catalog import DISPOSITIVOS_BZU, SEGMENTOS
from .roi_engine import analisar_operacao, formatar_brl


def _carregar_env_local() -> None:
    """Carrega variáveis de um arquivo .env na raiz do projeto se ainda não estiverem no ambiente."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


def _parse_valor_monetario(texto: str) -> Optional[float]:
    """Converte strings como '20.000', '18 mil', '15k', '12.500,50' em float."""
    t = texto.lower().strip()
    multiplicador = 1.0
    if "milh" in t:
        multiplicador = 1_000_000.0
    elif re.search(r"\bmil\b|\bk\b", t):
        multiplicador = 1_000.0

    m = re.search(r"(\d[\d\.,]*)", t)
    if not m:
        return None
    raw = m.group(1)
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    elif raw.count(".") == 1 and len(raw.split(".")[1]) == 3:
        raw = raw.replace(".", "")
    elif raw.count(".") > 1:
        raw = raw.replace(".", "")

    try:
        return float(raw) * multiplicador
    except ValueError:
        return None


def extrair_parametros_mensagem(mensagem: str, contexto_atual: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extrai dados operacionais mencionados pelo usuário em linguagem natural
    e mescla com o contexto já existente da sessão.
    """
    ctx: Dict[str, Any] = dict(contexto_atual or {})
    texto = mensagem.lower()

    # Segmento
    if any(k in texto for k in ("autocentro", "oficina", "mecânic", "mecanic", "elevador", "automotiv")):
        ctx["segmento"] = "autocentro"
    elif any(k in texto for k in ("indústr", "industr", "fábric", "fabric", "manufat", "planta")):
        ctx["segmento"] = "industria"
    elif any(k in texto for k in ("frota", "caminh", "veícul", "veicul", "caminhões", "transporte")):
        ctx["segmento"] = "frotas"
    elif any(k in texto for k in ("logíst", "logist", "galpão", "galpao", "armaz", "estoque", "doca")):
        ctx["segmento"] = "logistica"
    elif any(k in texto for k in ("predial", "prédio", "predio", "edifício", "edificio", "condomín", "loja", "shopping")):
        ctx["segmento"] = "predial"

    # Maturidade de coleta de dados
    if any(k in texto for k in ("não colet", "nao colet", "nenhum dado", "sem dados", "nada hoje")):
        ctx["coleta_atual"] = "nao-coletamos"
    elif any(k in texto for k in ("planilha", "excel", "papel", "manual")):
        ctx["coleta_atual"] = "planilha-manual"
    elif any(k in texto for k in ("já temos sensor", "ja temos sensor", "sensoriamento")):
        ctx["coleta_atual"] = "sensoriamento"
    elif any(k in texto for k in ("já usamos ia", "ja usamos ia", "inteligência artificial", "analytics")):
        ctx["coleta_atual"] = "ia"

    # Dor principal
    if any(k in texto for k in ("energia", "conta de luz", "elétric", "eletric", "kwh")):
        ctx["principal_dor"] = "energia"
    elif any(k in texto for k in ("parada", "quebra", "manutenção", "manutencao", "downtime", "vibra")):
        ctx["principal_dor"] = "paradas"
    elif any(k in texto for k in ("combustível", "combustivel", "rota", "rastreamento")):
        ctx["principal_dor"] = "frota"

    # Endpoint mencionado explicitamente
    m_ep = re.search(r"\b(ep\s?111|ep\s?300|ep\s?400|ep\s?600)\b", texto)
    if m_ep:
        ctx["endpoint_preferido"] = m_ep.group(1).replace(" ", "").upper()

    # Quantidade de dispositivos / equipamentos / máquinas / baias / veículos
    m_qtd = re.search(
        r"(\d{1,4})\s*(dispositivos?|sensores?|equipamentos?|máquinas?|maquinas?|pontos?|ativos?|baias?|elevadores?|veículos?|veiculos?|caminhões?|caminhoes?|motores?)",
        texto,
    )
    if m_qtd:
        qtd = int(m_qtd.group(1))
        if 1 <= qtd <= 2000:
            ctx["qtd_dispositivos"] = qtd

    # Custo mensal de energia
    m_energia = re.search(
        r"(?:energia|luz|el[eé]trica)[^0-9]{0,25}(?:r\$\s*)?(\d[\d\.,]*(?:\s*(?:mil|k))?)|(?:r\$\s*)?(\d[\d\.,]*(?:\s*(?:mil|k))?)\s*(?:reais\s*)?(?:de|em|com)\s*(?:energia|luz|conta de luz)",
        texto,
    )
    if m_energia:
        val_str = m_energia.group(1) or m_energia.group(2)
        val = _parse_valor_monetario(val_str)
        if val and val >= 200:
            ctx["custo_energia_mensal"] = val

    # Custo mensal de manutenção / paradas
    m_manut = re.search(
        r"(?:manuten[çc][ãa]o|paradas?)[^0-9]{0,25}(?:r\$\s*)?(\d[\d\.,]*(?:\s*(?:mil|k))?)|(?:r\$\s*)?(\d[\d\.,]*(?:\s*(?:mil|k))?)\s*(?:reais\s*)?(?:de|em|com)\s*(?:manuten[çc][ãa]o|paradas?)",
        texto,
    )
    if m_manut:
        val_str = m_manut.group(1) or m_manut.group(2)
        val = _parse_valor_monetario(val_str)
        if val and val >= 200:
            ctx["custo_manutencao_mensal"] = val

    return ctx


def _montar_system_prompt(simulacao: Dict[str, Any]) -> str:
    catalogo_resumido = [
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

    return (
        "Você é o Consultor de IA da Bzu Tech (plataforma IoT para máxima eficiência operacional).\n"
        "Seu papel é ajudar empreendedores e investidores a analisar os dados da operação, "
        "recomendar os dispositivos IoT ideais da Bzu Tech e explicar claramente o Payback e o ROI.\n\n"
        "REGRAS IMPORTANTES:\n"
        "1. Responda sempre em português do Brasil, em tom consultivo, objetivo e voltado para decisão de investimento.\n"
        "2. USE SEMPRE OS NÚMEROS EXATOS calculados pelo motor financeiro abaixo (não invente contas divergentes).\n"
        "3. Deixe claro que os valores são estimativas de simulação baseadas nos parâmetros atuais e podem ser refinados "
        "se o usuário informar quantidade de ativos, segmento, conta de energia ou gasto com manutenção.\n"
        "4. Organize a resposta com tópicos claros usando Markdown simples (negrito e listas curtas).\n"
        "5. Ao final, se algum dado importante (ex.: conta de energia mensal ou número de equipamentos) ainda não foi informado, "
        "faça 1 pergunta curta para refinar a simulação.\n\n"
        f"CATÁLOGO BZU TECH:\n{json.dumps(catalogo_resumido, ensure_ascii=False)}\n\n"
        f"SIMULAÇÃO ATUAL CALCULADA PELO MOTOR PYTHON:\n{json.dumps(simulacao, ensure_ascii=False)}\n"
    )


def _chamar_gemini(
    mensagem: str,
    simulacao: Dict[str, Any],
    historico: Optional[List[Dict[str, str]]] = None,
) -> Optional[str]:
    """Chama a API do Google Gemini se GEMINI_API_KEY e `google-genai` estiverem disponíveis."""
    _carregar_env_local()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"

    contents: List[Dict[str, Any]] = []
    for item in (historico or [])[-8:]:
        role = "model" if item.get("role") in ("assistant", "model", "bot") else "user"
        text = (item.get("content") or item.get("text") or "").strip()
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": mensagem}]})

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=_montar_system_prompt(simulacao),
                temperature=0.35,
            ),
        )
        texto = (getattr(response, "text", None) or "").strip()
        return texto or None
    except Exception:
        return None


def _resposta_fallback_local(mensagem: str, simulacao: Dict[str, Any]) -> str:
    """
    Motor conversacional local (sem depender de API externa).
    Responde sobre dispositivos específicos, payback/ROI ou entrega o diagnóstico completo.
    """
    texto = mensagem.lower().strip()
    param = simulacao["parametros"]
    fin = simulacao["financeiro"]
    fmt = simulacao["formatado"]
    mix = simulacao["dispositivos_sugeridos"]

    # 1. Pergunta sobre um endpoint específico
    m_ep = re.search(r"\b(ep\s?111|ep\s?300|ep\s?400|ep\s?600)\b", texto)
    if m_ep and any(k in texto for k in ("o que", "qual", "sobre", "detalhe", "serve", "faz", "preço", "preco", "custo")):
        codigo = m_ep.group(1).replace(" ", "").upper()
        ep = DISPOSITIVOS_BZU[codigo]
        apps = "\n".join(f"- {a}" for a in ep["aplicacoes"])
        vars_m = ", ".join(ep["variaveis_monitoradas"])
        return (
            f"**{ep['nome']}**\n\n"
            f"{ep['resumo']}\n\n"
            f"- **Variáveis monitoradas:** {vars_m}\n"
            f"- **Custo de referência:** {formatar_brl(ep['custo_unitario_brl'])} (hardware) + "
            f"{formatar_brl(ep['mensalidade_saas_brl'])}/mês (SaaS)\n"
            f"- **Redução média estimada:** ~{round(ep['reducao_energia_pct'])}% em energia e "
            f"~{round(ep['reducao_paradas_pct'])}% em paradas\n\n"
            f"**Principais aplicações:**\n{apps}\n\n"
            f"Com o seu cenário atual ({param['qtd_dispositivos']} dispositivos), o ROI projetado em 12 meses é de "
            f"**{fmt['roi_12m']}** com payback de **{fmt['payback']}**. Quer simular outra quantidade ou informar sua conta de energia?"
        )

    # 2. Saudação simples sem dados
    if re.fullmatch(r"(oi|ol[áa]|bom dia|boa tarde|boa noite|e a[ií]|hello|hi)[!.\s]*", texto):
        return (
            "Olá! Sou o **Consultor de IA da Bzu Tech**. Posso analisar sua operação e calcular:\n\n"
            "- **Dispositivos IoT sugeridos** (`EP111`, `EP300`, `EP400` e `EP600`)\n"
            "- **Economia mensal e anual estimada**\n"
            "- **Payback aproximado** e **ROI em 12 meses** para o investidor\n\n"
            "Me conte um pouco sobre a sua operação — por exemplo: *\"Tenho um autocentro com 40 equipamentos, "
            "gasto R$ 15 mil de energia por mês e controlo tudo em planilha manual\"*."
        )

    # 3. Foco em Payback e ROI
    if any(k in texto for k in ("payback", "roi", "retorno", "investimento", "lucro", "quanto custa", "viabilidade")) and not any(
        k in texto for k in ("dispositivo", "sensor", "endpoint", "recomenda", "suger")
    ):
        return (
            f"**Análise Financeira — {param['segmento_rotulo']} ({param['qtd_dispositivos']} dispositivos)**\n\n"
            f"- **Investimento inicial (CAPEX):** {fmt['investimento_inicial']} (hardware, instalação e {simulacao['qtd_gateways']} gateway(s))\n"
            f"- **Mensalidade plataforma (OPEX):** {fmt['opex_mensal']}/mês (pacote **{simulacao['pacote_recomendado']}**)\n"
            f"- **Economia estimada:** {fmt['economia_mensal']}/mês (**{fmt['economia_anual']}/ano**)\n"
            f"- **Payback aproximado:** **{fmt['payback']}** (~{fin['payback_meses']} meses)\n"
            f"- **ROI em 12 meses:** **{fmt['roi_12m']}** (lucro líquido estimado de {fmt['lucro_liquido_12m']})\n\n"
            f"Se quiser deixar o cálculo ainda mais preciso, me informe seu **gasto mensal com energia elétrica** "
            f"ou com **manutenção corretiva**."
        )

    # 4. Resposta consultiva completa (diagnóstico + dispositivos + payback + ROI)
    linhas_disp = "\n".join(
        f"- **{d['quantidade']}x {d['codigo']}** ({d['categoria']}) — {d['percentual_mix']}% do mix"
        for d in mix
    )

    dica_refino = ""
    if not param.get("custo_energia_mensal"):
        dica_refino = (
            "\n\nPara refinar ainda mais o cálculo, você pode me dizer qual é a sua **conta mensal de energia** "
            "ou seu **gasto médio com manutenção/paradas**."
        )

    return (
        f"**Diagnóstico da Operação — {param['segmento_rotulo']}**\n"
        f"Cenário analisado com **{param['qtd_dispositivos']} pontos monitorados** "
        f"(coleta atual: *{param['coleta_rotulo']}* | pacote **{simulacao['pacote_recomendado']}**).\n\n"
        f"**Dispositivos Bzu Tech sugeridos:**\n{linhas_disp}\n\n"
        f"**Projeção para o Investidor (12 meses):**\n"
        f"- **Investimento inicial (CAPEX):** {fmt['investimento_inicial']}\n"
        f"- **Economia anual estimada:** **{fmt['economia_anual']}** ({fmt['economia_mensal']}/mês)\n"
        f"- **Payback aproximado:** **{fmt['payback']}**\n"
        f"- **ROI em 12 meses:** **{fmt['roi_12m']}**\n"
        f"- **Redução média de energia:** **{fmt['reducao_energia']}**"
        f"{dica_refino}"
    )


def responder_chat(
    mensagem: str,
    contexto: Optional[Dict[str, Any]] = None,
    historico: Optional[List[Dict[str, str]]] = None,
) -> Tuple[str, Dict[str, Any], Dict[str, Any], str]:
    """
    Processa uma mensagem do usuário e retorna:
      (resposta_texto, simulacao_atualizada, contexto_atualizado, modo_ia)
    onde `modo_ia` é `"gemini"` ou `"local"`.
    """
    contexto_atualizado = extrair_parametros_mensagem(mensagem, contexto)
    simulacao = analisar_operacao(contexto_atualizado)

    resposta_gemini = _chamar_gemini(mensagem, simulacao, historico)
    if resposta_gemini:
        return resposta_gemini, simulacao, contexto_atualizado, "gemini"

    resposta_local = _resposta_fallback_local(mensagem, simulacao)
    return resposta_local, simulacao, contexto_atualizado, "local"


def enriquecer_analises_com_ia(simulacao: Dict[str, Any]) -> Dict[str, Any]:
    """
    Quando a GEMINI_API_KEY está ativa, pede ao Gemini para personalizar os 4 textos
    dos cartões de detalhe da tela /resultado/ mantendo os números exatos.
    Em caso de indisponibilidade ou ausência de chave, retorna a simulação original.
    """
    _carregar_env_local()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return simulacao

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return simulacao

    prompt = (
        "Com base na simulação IoT Bzu Tech abaixo, gere um JSON válido com exatamente 4 chaves: "
        '"economia", "roi", "payback", "eficiencia".\n'
        "Cada valor deve ser uma frase consultiva curta (25 a 45 palavras) em português do Brasil "
        "explicando o indicador para o investidor, usando os números exatos da simulação.\n"
        f"SIMULAÇÃO:\n{json.dumps(simulacao, ensure_ascii=False)}"
    )

    try:
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )
        dados_ia = json.loads((getattr(response, "text", None) or "").strip())
        if isinstance(dados_ia, dict) and all(k in dados_ia for k in ("economia", "roi", "payback", "eficiencia")):
            simulacao["analises"] = {k: str(dados_ia[k]).strip() for k in ("economia", "roi", "payback", "eficiencia")}
            simulacao["modo_ia"] = "gemini"
    except Exception:
        pass

    return simulacao
