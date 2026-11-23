"""
Catálogo configurável de dispositivos IoT Bzu Tech, segmentos e perfis de maturidade.

Os valores abaixo são referências realistas de mercado para simulação de ROI e Payback.
Basta editar este arquivo para atualizar preços, especificações ou taxas de economia
quando os dados comerciais oficiais da Bzu Tech estiverem disponíveis.
"""

from __future__ import annotations

from typing import Any, Dict, List

DISPOSITIVOS_BZU: Dict[str, Dict[str, Any]] = {
    "EP111": {
        "codigo": "EP111",
        "nome": "Endpoint EP111 — Monitoramento Ambiental e Utilidades",
        "categoria": "Ambiente, Temperatura e Consumo Básico",
        "resumo": "Sensor compacto de baixa potência para monitoramento contínuo de temperatura, umidade, abertura/status e consumo em pontos críticos.",
        "aplicacoes": [
            "Monitoramento de temperatura e umidade em oficinas, estoques e câmaras",
            "Detecção de equipamentos ligados fora do expediente",
            "Controle de utilidades básicas (água, ar comprimido e climatização)",
        ],
        "variaveis_monitoradas": [
            "Temperatura",
            "Umidade",
            "Status liga/desliga",
            "Alertas de anomalia",
        ],
        "custo_unitario_brl": 420.0,
        "instalacao_unitaria_brl": 120.0,
        "mensalidade_saas_brl": 29.0,
        "economia_mensal_base_brl": 185.0,
        "reducao_energia_pct": 14.0,
        "reducao_paradas_pct": 12.0,
        "segmentos_ideais": ["predial", "autocentro", "logistica"],
        "dores_ideais": ["energia", "visibilidade", "clima"],
    },
    "EP300": {
        "codigo": "EP300",
        "nome": "Endpoint EP300 — Telemetria de Máquinas e Energia",
        "categoria": "Energia Elétrica e Produtividade de Equipamentos",
        "resumo": "Dispositivo versátil para medição de corrente/energia elétrica, horímetro e ciclo de operação de elevadores automotivos, compressores e máquinas.",
        "aplicacoes": [
            "Monitoramento de consumo elétrico por máquina ou circuito",
            "Controle de ociosidade e tempo útil de baias/elevadores em autocentros",
            "Detecção de picos de demanda e sobrecargas elétricas",
        ],
        "variaveis_monitoradas": [
            "Corrente e potência elétrica (kW/kWh)",
            "Tempo de operação e ociosidade",
            "Fator de potência e picos de carga",
        ],
        "custo_unitario_brl": 680.0,
        "instalacao_unitaria_brl": 180.0,
        "mensalidade_saas_brl": 42.0,
        "economia_mensal_base_brl": 310.0,
        "reducao_energia_pct": 19.0,
        "reducao_paradas_pct": 22.0,
        "segmentos_ideais": ["autocentro", "industria", "predial"],
        "dores_ideais": ["energia", "produtividade", "visibilidade"],
    },
    "EP400": {
        "codigo": "EP400",
        "nome": "Endpoint EP400 — Manutenção Preditiva e Vibração",
        "categoria": "Saúde de Ativos e Manutenção Preditiva",
        "resumo": "Sensor industrial avançado para vibração, temperatura de superfície e assinatura mecânica, evitando paradas não planejadas.",
        "aplicacoes": [
            "Monitoramento preditivo de motores, compressores e bombas",
            "Detecção precoce de desalinhamento, folgas e desgaste de rolamentos",
            "Redução de manutenção corretiva emergencial em linhas contínuas",
        ],
        "variaveis_monitoradas": [
            "Vibração triaxial (RMS / frequência)",
            "Temperatura de carcaça/mancal",
            "Ciclos de falha e alertas preditivos",
        ],
        "custo_unitario_brl": 950.0,
        "instalacao_unitaria_brl": 240.0,
        "mensalidade_saas_brl": 55.0,
        "economia_mensal_base_brl": 430.0,
        "reducao_energia_pct": 16.0,
        "reducao_paradas_pct": 35.0,
        "segmentos_ideais": ["industria", "autocentro"],
        "dores_ideais": ["paradas", "manutencao", "produtividade"],
    },
    "EP600": {
        "codigo": "EP600",
        "nome": "Endpoint EP600 — Gateway Multiprotocolo e Telemetria de Frotas/Operação",
        "categoria": "Alta Capacidade, Frotas e Integração Industrial",
        "resumo": "Dispositivo robusto com conectividade celular/LoRaWAN e múltiplas entradas para frotas, logística e plantas de grande porte.",
        "aplicacoes": [
            "Rastreamento e telemetria avançada de frotas e veículos de serviço",
            "Consolidação de múltiplos ativos e sensores em galpões logísticos",
            "Integração com ERPs e dashboards corporativos em tempo real",
        ],
        "variaveis_monitoradas": [
            "Telemetria veicular / GPS / consumo de combustível",
            "Múltiplas entradas analógicas e digitais (Modbus/CAN)",
            "Disponibilidade operacional em tempo real",
        ],
        "custo_unitario_brl": 1250.0,
        "instalacao_unitaria_brl": 290.0,
        "mensalidade_saas_brl": 68.0,
        "economia_mensal_base_brl": 540.0,
        "reducao_energia_pct": 21.0,
        "reducao_paradas_pct": 30.0,
        "segmentos_ideais": ["frotas", "logistica", "industria"],
        "dores_ideais": ["frota", "logistica", "paradas", "energia"],
    },
}

# Custo de referência por gateway/concentrador (1 gateway para cada 25 dispositivos)
CUSTO_GATEWAY_BRL = 1650.0
DISPOSITIVOS_POR_GATEWAY = 25

# Fatores de ajuste conforme a maturidade atual de coleta de dados
# Empresas que não coletam dados hoje tendem a capturar maior ganho marginal ao implantar IoT.
FATOR_COLETA: Dict[str, Dict[str, Any]] = {
    "nao-coletamos": {
        "rotulo": "Não coletamos dados atualmente",
        "multiplicador_economia": 1.18,
        "bonus_energia_pct": 2.5,
        "descricao": "Alto potencial de ganho rápido ao eliminar pontos cegos operacionais e desperdícios invisíveis.",
    },
    "planilha-manual": {
        "rotulo": "Controle por planilha manual",
        "multiplicador_economia": 1.10,
        "bonus_energia_pct": 1.5,
        "descricao": "Ganho expressivo em velocidade de decisão, redução de retrabalho manual e alertas em tempo real.",
    },
    "sensoriamento": {
        "rotulo": "Já possui sensoriamento parcial",
        "multiplicador_economia": 0.92,
        "bonus_energia_pct": 0.0,
        "descricao": "Foco em unificação de dados, cobertura de ativos críticos e manutenção preditiva.",
    },
    "ia": {
        "rotulo": "Já utiliza IA / analytics",
        "multiplicador_economia": 0.88,
        "bonus_energia_pct": 0.0,
        "descricao": "Otimização fina alimentando modelos existentes com telemetria IoT de alta frequência.",
    },
}

SEGMENTOS: Dict[str, Dict[str, Any]] = {
    "autocentro": {
        "rotulo": "Autocentros e Serviços Automotivos",
        "multiplicador_economia": 1.05,
        "foco": "produtividade de baias, compressores, energia elétrica e gestão de equipamentos automotivos",
        "mix_padrao": [("EP300", 0.55), ("EP111", 0.30), ("EP400", 0.15)],
    },
    "industria": {
        "rotulo": "Indústria e Manufatura",
        "multiplicador_economia": 1.12,
        "foco": "energia, utilidades industriais e prevenção de paradas não planejadas",
        "mix_padrao": [("EP400", 0.45), ("EP300", 0.40), ("EP600", 0.15)],
    },
    "frotas": {
        "rotulo": "Frotas e Mobilidade",
        "multiplicador_economia": 1.08,
        "foco": "telemetria veicular, redução de combustível, manutenção preventiva e disponibilidade",
        "mix_padrao": [("EP600", 0.70), ("EP300", 0.30)],
    },
    "logistica": {
        "rotulo": "Logística e Armazenagem",
        "multiplicador_economia": 1.04,
        "foco": "controle ambiental, docas, energia de refrigeração e rastreamento de ativos",
        "mix_padrao": [("EP600", 0.40), ("EP111", 0.40), ("EP300", 0.20)],
    },
    "predial": {
        "rotulo": "Automação Predial e Facilities",
        "multiplicador_economia": 0.98,
        "foco": "eficiência energética em HVAC, iluminação, reservatórios e utilidades",
        "mix_padrao": [("EP111", 0.50), ("EP300", 0.50)],
    },
}


def listar_dispositivos() -> List[Dict[str, Any]]:
    """Retorna a lista de dispositivos do catálogo Bzu Tech."""
    return list(DISPOSITIVOS_BZU.values())
