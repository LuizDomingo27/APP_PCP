"""M10 — Painel Programação Semanal.

O painel principal diz *quanto* está disponível para programar. Este diz
**quando**: as 16.674 peças liberadas não são um lote único — parte já passou
da semana em que deveria entrar, parte é da semana que vem e parte só abre em
agosto. Programar tudo junto é o que estoura a capacidade de uma semana e deixa
a seguinte vazia.

A régua é `Data de Recomendação` da BASE MP contra a data do snapshot, e a
regra de disponibilidade é a mesma do painel principal — a soma das semanas
fecha com o KPI 'Disponível para Programar'. Ver `rules.ProgramacaoSemanal`.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pcp import Carga
from pcp.rules import (
    ESTA_SEMANA,
    FUTURA,
    PROXIMA_SEMANA,
    SEM_SEMANA,
    VENCIDA,
    Filtros,
    ProgramacaoSemanal,
    programacao_semanal,
)

from .. import components as c
from .. import format as fmt
from ..theme import AZUL, LARANJA, VERDE, VERDE_CLARO, VERMELHO

# Cor por situação da semana: o mesmo semáforo do M6, aplicado à janela de
# programação em vez do prazo de entrega.
_CORES = {
    VENCIDA: VERMELHO,
    ESTA_SEMANA: LARANJA,
    PROXIMA_SEMANA: VERDE,
    FUTURA: VERDE_CLARO,
    SEM_SEMANA: AZUL,
}

_LINHAS_ITENS = 20


def render(carga: Carga, filtros: Filtros, titulo_periodo: str) -> None:
    ps = programacao_semanal(carga.mp, filtros, carga.data_snapshot)

    st.markdown(
        c.cabecalho(
            "Programação Semanal · Disponível para Programar",
            f"{carga.unidade} · {titulo_periodo}",
            [("Atualizado em", carga.rotulo_snapshot)],
        ),
        unsafe_allow_html=True,
    )

    if ps.saldo == 0:
        st.markdown(
            c.nota(
                "Não há saldo pendente neste recorte — nenhuma semana a programar.",
                "ok",
                "alvo",
            ),
            unsafe_allow_html=True,
        )
        return

    st.markdown(_faixa(ps), unsafe_allow_html=True)

    esquerda, direita = st.columns([1.3, 1.0], gap="small")
    with esquerda:
        st.markdown(_agenda(ps), unsafe_allow_html=True)
    with direita:
        st.markdown(_liberacao(ps), unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown(_leitura(ps), unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown(_tabela_semanas(ps), unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown(_tabela_itens(ps), unsafe_allow_html=True)


def _faixa(ps: ProgramacaoSemanal) -> str:
    return c.faixa_kpis(
        [
            c.kpi("Disponível", fmt.numero(ps.disponivel), "peças liberadas", "caixa", "ok"),
            c.kpi("Janela Vencida", fmt.numero(ps.vencido), "peças", "alerta", "alerta"),
            c.kpi("Esta Semana", fmt.numero(ps.nesta_semana), "peças", "agenda", "atencao"),
            c.kpi("Próxima Semana", fmt.numero(ps.proxima_semana), "peças", "relogio"),
            c.kpi("Semanas com Saldo", fmt.numero(ps.semanas_com_disponivel), "na agenda", "prancheta"),
            c.kpi("% Disponível", fmt.pct_programado(ps.pct_disponivel), "do pendente", "pct"),
            c.kpi("Travado", fmt.numero(ps.travado), "peças", "peca", "alerta"),
        ]
    )


def _agenda(ps: ProgramacaoSemanal) -> str:
    """Uma barra por semana — a agenda inteira numa olhada.

    A barra é o **disponível**, não o saldo: é o que efetivamente pode virar
    ordem de produção naquela semana. O saldo total da semana vai na observação,
    para a diferença não sumir da tela.
    """
    maior = float(ps.semanas["disponivel"].max()) or 1.0
    linhas = "".join(
        c.linha_barra(
            f"{linha.semana} · {linha.periodo}",
            fmt.numero(linha.disponivel),
            linha.disponivel / maior,
            _CORES.get(linha.situacao, AZUL),
            f"{linha.situacao} · {fmt.numero(linha.saldo)} pendentes, "
            f"{fmt.numero(linha.travado)} travadas",
            destaque=linha.situacao == VENCIDA and linha.disponivel > 0,
        )
        for linha in ps.semanas.itertuples()
    )
    return c.painel(
        f"Agenda de programação · régua de {fmt.data(ps.referencia)}", linhas
    )


def _liberacao(ps: ProgramacaoSemanal) -> str:
    """Quanto do pendente já está liberado — o teto do que dá para programar."""
    corpo = (
        f'<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">'
        f"{c.donut(ps.pct_disponivel, VERDE, fmt.pct_programado(ps.pct_disponivel), 'liberado')}"
        f'<div class="pcp-legenda">'
        f"{c.item_legenda(VERDE, 'DISPONÍVEL', fmt.numero(ps.disponivel) + ' peças', 'protótipo, MP e AVI ok')}"
        f"{c.item_legenda(VERMELHO, 'TRAVADO', fmt.numero(ps.travado) + ' peças', 'depende de destravar antes')}"
        f"{c.item_legenda(LARANJA, 'JANELA VENCIDA', fmt.numero(ps.vencido) + ' peças', 'liberado e fora do programa')}"
        f"</div></div>"
    )
    return c.painel("Situação do Saldo Pendente", corpo)


def _leitura(ps: ProgramacaoSemanal) -> str:
    """Conclusão por regra — muda com o recorte, não é texto fixo."""
    pico = ps.pico
    if ps.disponivel == 0:
        return c.nota(
            "Nenhuma peça liberada neste recorte: todo o saldo pendente depende "
            "de protótipo, matéria-prima ou AVI antes de entrar na programação.",
            "erro",
            "alerta",
        )
    if ps.vencido > 0:
        texto = (
            f"<b>{fmt.numero(ps.vencido)}</b> peças estão liberadas e a semana em "
            f"que deveriam ser programadas já passou — não há trava, só falta "
            f"programar. São as primeiras da fila, à frente das "
            f"<b>{fmt.numero(ps.nesta_semana)}</b> desta semana."
        )
        return c.nota(texto, "erro", "alerta")
    if pico:
        periodo, valor = pico
        texto = (
            f"Nenhuma janela vencida. A semana mais carregada é "
            f"<b>{periodo}</b>, com <b>{fmt.numero(valor)}</b> peças liberadas de "
            f"um total de <b>{fmt.numero(ps.disponivel)}</b> — é nela que a "
            f"capacidade precisa estar reservada."
        )
        return c.nota(texto, "aviso", "agenda")
    return c.nota(
        f"<b>{fmt.numero(ps.disponivel)}</b> peças liberadas sem data recomendada "
        "na base — sem data não há semana, e elas ficam fora da agenda.",
        "aviso",
        "doc",
    )


_CABECALHOS_SEMANA = [
    "Semana", "Período", "Situação", "Disponível", "% Disp.",
    "Sem MP", "Sem Protótipo", "Sem AVI", "Saldo da Semana",
]


def _tabela_semanas(ps: ProgramacaoSemanal) -> str:
    """A tabela que se leva para a reunião: o que dá para programar em cada semana.

    A linha de total existe para fechar com o painel principal: a soma da coluna
    'Disponível' é o KPI 'Disponível para Programar'.
    """
    linhas = [
        (
            "g" if linha.situacao in (VENCIDA, ESTA_SEMANA) else "",
            [
                linha.semana,
                linha.periodo,
                linha.situacao,
                fmt.numero(linha.disponivel),
                fmt.pct(linha.pct_disponivel),
                fmt.numero(linha.sem_mp),
                fmt.numero(linha.sem_prototipo),
                fmt.numero(linha.sem_avi),
                fmt.numero(linha.saldo),
            ],
        )
        for linha in ps.semanas.itertuples()
    ]
    linhas.append(
        (
            "t",
            [
                "Total",
                f"{len(ps.semanas)} semanas",
                "—",
                fmt.numero(ps.disponivel),
                fmt.pct(ps.pct_disponivel),
                "—",
                "—",
                "—",
                fmt.numero(ps.saldo),
            ],
        )
    )
    return c.painel(
        "Saldo pendente por semana de programação",
        c.tabela(_CABECALHOS_SEMANA, linhas),
    )


_CABECALHOS_ITENS = [
    "Referência", "Material", "Descrição", "Família", "Grupo", "TOC",
    "Quinzena", "Recomendado", "Semana", "Situação", "Peças",
]


def _tabela_itens(ps: ProgramacaoSemanal) -> str:
    """O detalhe do que está disponível, da semana mais atrasada para a folgada."""
    if ps.itens.empty:
        return c.painel(
            "Itens disponíveis para programar",
            '<div class="pcp-lb__obs">Nenhuma peça liberada neste recorte.</div>',
        )

    linhas = [
        (
            "g" if item.situacao in (VENCIDA, ESTA_SEMANA) else "",
            [
                item.referencia or "—",
                item.material or "—",
                item.descricao_material[:38] or "—",
                item.familia or "—",
                item.departamento or "—",
                item.toc or "—",
                item.quinzena or "—",
                fmt.data(item.recomendado) if pd.notna(item.recomendado) else "—",
                f"{item.semana} · {item.periodo}" if item.semana != "—" else SEM_SEMANA,
                item.situacao,
                fmt.numero(item.saldo_a_programar),
            ],
        )
        for item in ps.itens.head(_LINHAS_ITENS).itertuples()
    ]
    titulo = (
        f"Itens disponíveis para programar · {min(_LINHAS_ITENS, len(ps.itens))} "
        f"de {fmt.numero(len(ps.itens))}"
    )
    return c.painel(titulo, c.tabela(_CABECALHOS_ITENS, linhas))
