"""M6 — Painel Prazos & Deadline.

Reconstrói a aba PRAZOS com uma régua honesta: `Data Lib Recomendada` contra a
**data do snapshot da base**. O plano previa comparar com `Data de Recomendação`
da BASE MP, mas conferindo o dado as duas colunas carregam a mesma data para o
mesmo material — comparar uma com a outra não mede prazo nenhum. O que decide é
quanto falta de hoje até a data recomendada. Ver `rules.Prazos`.

Só entra saldo **ainda não programado**: prazo estourado só é acionável enquanto
existe peça a programar.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pcp import Carga
from pcp.rules import FAIXAS_PRAZO, SEM_DATA, Filtros, Prazos, prazos

from .. import components as c
from .. import format as fmt
from ..theme import AZUL, LARANJA, VERDE, VERDE_CLARO, VERMELHO

# Cor por faixa: o semáforo é o próprio conteúdo da tela.
_CORES = {
    "Estourado": VERMELHO,
    "Crítico · até 7 dias": LARANJA,
    "Atenção · 8 a 15 dias": "#C9A227",
    "Programável · 16 a 30 dias": VERDE,
    "Folga · acima de 30 dias": VERDE_CLARO,
    SEM_DATA: AZUL,
}

_LINHAS_TABELA = 15


def render(carga: Carga, filtros: Filtros, titulo_periodo: str) -> None:
    p = prazos(carga.cpg, filtros, carga.data_snapshot)

    st.markdown(
        c.cabecalho(
            "Prazos & Deadline · Saldo a Programar",
            f"{carga.unidade} · {titulo_periodo}",
            [("Atualizado em", carga.rotulo_snapshot)],
        ),
        unsafe_allow_html=True,
    )

    if p.total == 0:
        st.markdown(
            c.nota(
                "Não há saldo a programar neste recorte — nenhum prazo em aberto.",
                "ok",
                "alvo",
            ),
            unsafe_allow_html=True,
        )
        return

    st.markdown(_faixa(p), unsafe_allow_html=True)

    esquerda, direita = st.columns([1.3, 1.0], gap="small")
    with esquerda:
        st.markdown(_distribuicao(p), unsafe_allow_html=True)
    with direita:
        st.markdown(_semaforo(p), unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown(_leitura(p), unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown(_tabela(p), unsafe_allow_html=True)


def _faixa(p: Prazos) -> str:
    critico = p.faixas.get("Crítico · até 7 dias", 0.0)
    return c.faixa_kpis(
        [
            c.kpi("A Programar", fmt.numero(p.total), "peças", "agenda"),
            c.kpi("Prazo Estourado", fmt.numero(p.estourado), "peças", "alerta", "alerta"),
            c.kpi("% Estourado", fmt.pct_programado(p.pct_estourado), "do pendente", "pct", "alerta"),
            c.kpi("Maior Atraso", fmt.numero(p.dias_atraso_max), "dias", "relogio", "alerta"),
            c.kpi("Vence em 7 dias", fmt.numero(critico), "peças", "relogio", "atencao"),
            c.kpi("Dentro do Prazo", fmt.numero(p.no_prazo), "peças", "alvo", "ok"),
            c.kpi("Sem Data", fmt.numero(p.faixas.get(SEM_DATA, 0.0)), "peças", "doc"),
        ]
    )


def _distribuicao(p: Prazos) -> str:
    """Saldo pendente por urgência, na ordem do semáforo."""
    rotulos = [rotulo for rotulo, _ in FAIXAS_PRAZO] + [SEM_DATA]
    maior = max(p.faixas.values()) or 1.0
    linhas = "".join(
        c.linha_barra(
            rotulo,
            fmt.numero(p.faixas.get(rotulo, 0.0)),
            p.faixas.get(rotulo, 0.0) / maior,
            _CORES.get(rotulo, AZUL),
            fmt.pct_programado(p.faixas.get(rotulo, 0.0) / p.total) + " do pendente",
            destaque=rotulo == "Estourado" and p.estourado > 0,
        )
        for rotulo in rotulos
        if p.faixas.get(rotulo, 0.0) > 0
    )
    return c.painel(
        f"Distribuição por Urgência · régua de {fmt.data(p.referencia)}", linhas
    )


def _semaforo(p: Prazos) -> str:
    corpo = (
        f'<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">'
        f"{c.donut(p.pct_estourado, VERMELHO, fmt.pct_programado(p.pct_estourado), 'estourado')}"
        f'<div class="pcp-legenda">'
        f"{c.item_legenda(VERMELHO, 'ESTOURADO', fmt.numero(p.estourado) + ' peças', 'data de liberação já passou')}"
        f"{c.item_legenda(VERDE, 'DENTRO DO PRAZO', fmt.numero(p.no_prazo) + ' peças', 'ainda dá tempo')}"
        f"</div></div>"
    )
    return c.painel("Situação do Saldo Pendente", corpo)


def _leitura(p: Prazos) -> str:
    """Conclusão por regra — muda com o recorte, não é texto fixo."""
    critico = p.faixas.get("Crítico · até 7 dias", 0.0)
    if p.estourado > 0:
        texto = (
            f"<b>{fmt.numero(p.estourado)}</b> peças "
            f"(<b>{fmt.pct_programado(p.pct_estourado)}</b> do saldo pendente) já "
            f"passaram da data recomendada de liberação, com atraso de até "
            f"<b>{fmt.numero(p.dias_atraso_max)} dias</b>. São as primeiras da fila: "
            f"cada dia parado aqui sai direto do prazo de entrega no CD."
        )
        tipo, icone = "erro", "alerta"
    elif critico > 0:
        texto = (
            f"Nenhum prazo estourado. <b>{fmt.numero(critico)}</b> peças vencem nos "
            f"próximos 7 dias e precisam entrar na programação desta semana."
        )
        tipo, icone = "aviso", "relogio"
    else:
        texto = (
            "Nenhum prazo estourado e nada vencendo em 7 dias neste recorte — "
            "a programação está com folga."
        )
        tipo, icone = "ok", "alvo"
    return c.nota(texto, tipo, icone)


_CABECALHOS = ["Pedido", "Família", "Grupo", "TOC", "Lib. Recomendada",
               "Entrega CD", "A Programar", "Dias", "Situação"]


def _tabela(p: Prazos) -> str:
    """Os pedidos mais atrasados primeiro — é por onde o PCP começa o dia."""
    linhas = []
    for item in p.itens.head(_LINHAS_TABELA).itertuples():
        dias = getattr(item, "dias", None)
        atrasado = pd.notna(dias) and dias < 0
        linhas.append(
            (
                "g" if atrasado else "",
                [
                    str(getattr(item, "pedido", "—")),
                    str(getattr(item, "familia", "—")),
                    str(getattr(item, "departamento", "—")),
                    str(getattr(item, "toc", "—")),
                    fmt.data(getattr(item, "data_lib_recomendada", None)),
                    fmt.data(getattr(item, "entrega_cd", None)),
                    fmt.numero(item.a_programar),
                    "—" if pd.isna(dias) else fmt.sinal(int(dias)),
                    item.faixa.split(" · ")[0],
                ],
            )
        )
    titulo = (
        f"Pedidos pendentes · {min(_LINHAS_TABELA, len(p.itens))} mais urgentes "
        f"de {fmt.numero(len(p.itens))}"
    )
    return c.painel(titulo, c.tabela(_CABECALHOS, linhas))
