"""Núcleo da aplicação de PCP — Oficina Jeans, Tear, Malha e Polo.

Camadas (a de cima nunca é importada pela de baixo):

    loader     orquestração da carga
    cache      persistência local em Parquet
    rules      motor de regras (puro, sem I/O)
    transform  tipagem e normalização
    ingest     leitura da planilha em streaming
    schema     contrato de colunas
    errors     exceções de domínio
"""

from .errors import (
    AbaAusenteError,
    ArquivoInvalidoError,
    ColunaAusenteError,
    DadoVazioError,
    PCPError,
    TipoInvalidoError,
)
from . import export
from .loader import Carga, Evolucao, carregar, comparar, evolucao, historico_local, serie_historica
from .rules import (
    Filtros,
    FluxoProdutivo,
    FullKit,
    KPIs,
    Prazos,
    ProgramacaoSemanal,
    Simulacao,
    fluxo_produtivo,
    full_kit,
    kpis,
    kpis_por_dimensao,
    prazos,
    programacao_semanal,
    simular_chegada,
)

__all__ = [
    "AbaAusenteError",
    "ArquivoInvalidoError",
    "Carga",
    "ColunaAusenteError",
    "DadoVazioError",
    "Evolucao",
    "Filtros",
    "FluxoProdutivo",
    "FullKit",
    "KPIs",
    "PCPError",
    "Prazos",
    "ProgramacaoSemanal",
    "Simulacao",
    "TipoInvalidoError",
    "carregar",
    "comparar",
    "evolucao",
    "export",
    "fluxo_produtivo",
    "historico_local",
    "serie_historica",
    "full_kit",
    "kpis",
    "kpis_por_dimensao",
    "prazos",
    "programacao_semanal",
    "simular_chegada",
]
