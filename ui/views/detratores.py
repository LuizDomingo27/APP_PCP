"""M3 — Painel Detratores.

O ranking é derivado dos números, não digitado à mão como na planilha: se a
ordem dos detratores mudar, o rótulo de impacto de cada linha muda junto.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from pcp import Carga
from pcp.rules import Filtros, KPIs, kpis

from .. import components as c
from .. import format as fmt
from ..theme import LARANJA, VERDE, VERMELHO


@dataclass(frozen=True)
class Detrator:
    chave: str
    titulo: str
    descricao: str
    icone: str
    cor: str
    oportunidade: bool = False


DETRATORES = (
    Detrator("sem_mp", "SEM MP", "Falta de Mostruário de Peça", "camisa", LARANJA),
    Detrator("sem_avi", "SEM AVI", "Falta de Análise de Viabilidade", "pessoa", VERMELHO),
    Detrator("sem_prototipo", "SEM PROTÓTIPO", "Falta de Protótipo Aprovado", "doc", VERMELHO),
    Detrator("mp_prot_sem_avi", "MP + PROT. (SEM AVI)", "Aguardando AVI", "peca", LARANJA),
    Detrator("disponivel_para_programar", "DISP. PARA PROGRAMAR", "Pronto para programar",
             "caixa", VERDE, oportunidade=True),
)


def render(carga: Carga, filtros: Filtros, titulo_periodo: str) -> None:
    k = kpis(carga.cpg, carga.mp, filtros)

    st.markdown(
        c.cabecalho(
            "Detratores · Follow Up Carteira Geral",
            f"{carga.unidade} · {titulo_periodo}",
            # Só o carimbo da base. O saldo pendente já é cartão na faixa abaixo.
            [("Atualizado em", carga.rotulo_snapshot)],
        ),
        unsafe_allow_html=True,
    )

    if k.a_programar == 0:
        st.markdown(
            c.nota(
                "Não há saldo pendente neste recorte — nenhum detrator a analisar.",
                "ok",
                "alvo",
            ),
            unsafe_allow_html=True,
        )
        return

    st.markdown(_faixa(k), unsafe_allow_html=True)
    st.markdown(_ranking(k), unsafe_allow_html=True)


def _faixa(k: KPIs) -> str:
    """Apenas o contexto da competência.

    Os cinco detratores ficam de fora de propósito: o ranking logo abaixo traz
    cada um com valor, participação e impacto. Repetir o mesmo número duas
    vezes na mesma tela é ruído — o olho passa a procurar a diferença.
    """
    return c.faixa_kpis(
        [
            c.kpi("Carteira Total", fmt.numero(k.carteira_total), "peças", "pessoa"),
            c.kpi("Programado", fmt.numero(k.programado), "peças", "prancheta", "ok"),
            c.kpi("% Programado", fmt.pct_programado(k.pct_programado), "do total", "pct", "ok"),
            c.kpi("A Programar", fmt.numero(k.a_programar), "peças", "agenda", "atencao"),
        ],
        variante="contexto",
    )


def _classificar(posicao: int, detrator: Detrator, fracao: float) -> tuple[str, str]:
    """Rótulo de impacto derivado do ranking, não fixo por detrator."""
    if detrator.oportunidade:
        return "Oportunidade", "Peças liberadas para programação imediata."
    if posicao == 0:
        return "Maior impacto", "Principal detrator da programação, maior impacto no saldo pendente."
    if fracao >= 0.40:
        return "Alto impacto", "Segunda maior restrição, concentra parte relevante do pendente."
    if fracao >= 0.10:
        return "Médio impacto", "Impacto moderado sobre o saldo a programar."
    return "Baixo impacto", "Peso reduzido no saldo pendente."


def _ordenados(k: KPIs) -> list[tuple[Detrator, float, float]]:
    valores = k.as_dict()
    bloqueios = [d for d in DETRATORES if not d.oportunidade]
    bloqueios.sort(key=lambda d: valores[d.chave], reverse=True)
    oportunidades = [d for d in DETRATORES if d.oportunidade]
    return [
        (d, valores[d.chave], k.pct_do_saldo(valores[d.chave]))
        for d in (*bloqueios, *oportunidades)
    ]


def _ranking(k: KPIs) -> str:
    linhas = []
    for posicao, (detrator, valor, fracao) in enumerate(_ordenados(k)):
        impacto, nota = _classificar(posicao, detrator, fracao)
        linhas.append(
            c.linha_detrator(
                detrator.titulo, detrator.descricao, detrator.icone, detrator.cor,
                valor, fracao, impacto, nota,
            )
        )
    cabecalho = (
        '<div class="pcp-det pcp-det--cab" style="padding-top:0">'
        '<div class="pcp-kpi__rot">Detrator</div>'
        '<div class="pcp-kpi__rot">Peças</div>'
        '<div class="pcp-kpi__rot">% do saldo pendente</div>'
        '<div class="pcp-kpi__rot">Impacto</div></div>'
    )
    return c.painel("Detratores · Resumo Simplificado", cabecalho + "".join(linhas))


