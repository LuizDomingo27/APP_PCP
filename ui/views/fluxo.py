"""M4 — Painel Fluxo Produtivo.

Esta tela não tem equivalente na planilha: o bloco AH:AY que deveria mostrar
isso retorna zero em 100% das células desde que a BASE CPG ganhou colunas
(CORRECAO_FLUXO_PRODUTIVO.md). Tudo aqui é informação que a equipe hoje não vê.

Por isso a tela fecha com uma leitura do gargalo, em vez de só exibir números
novos: a etapa que concentra o maior WIP do recorte.
"""

from __future__ import annotations

import streamlit as st

from pcp import Carga, schema
from pcp.rules import Filtros, FluxoProdutivo, fluxo_produtivo

from .. import components as c
from .. import format as fmt
from ..theme import AZUL, VERDE, VERDE_CLARO, VERMELHO


def render(carga: Carga, filtros: Filtros, titulo_periodo: str) -> None:
    f = fluxo_produtivo(carga.cpg, filtros)

    st.markdown(
        c.cabecalho(
            "Fluxo Produtivo · Evolução por Etapa",
            f"{carga.unidade} · {titulo_periodo}",
            [("Atualizado em", carga.rotulo_snapshot)],
        ),
        unsafe_allow_html=True,
    )

    if f.em_processo == 0 and f.wip_total == 0:
        st.markdown(
            c.nota(
                "Nenhuma peça em processo neste recorte. Verifique a competência "
                "na barra lateral — o fluxo só existe onde já houve programação.",
                "aviso",
            ),
            unsafe_allow_html=True,
        )
        return

    st.markdown(_faixa(f), unsafe_allow_html=True)

    esquerda, direita = st.columns([1.15, 1.0], gap="small")
    with esquerda:
        st.markdown(_funil(f), unsafe_allow_html=True)
    with direita:
        st.markdown(_etapas(f), unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown(_leitura(f), unsafe_allow_html=True)


def _faixa(f: FluxoProdutivo) -> str:
    return c.faixa_kpis(
        [
            c.kpi("Em Processo", fmt.numero(f.em_processo), "peças", "prancheta"),
            c.kpi("WIP nas Etapas", fmt.numero(f.wip_total), "peças", "peca", "ok"),
            c.kpi("Aguardando Entrada", fmt.numero(f.aguardando_entrada), "peças",
                  "relogio", "atencao"),
            c.kpi("Embalado", fmt.numero(f.embalado), "peças", "caixa"),
            c.kpi("Faturado", fmt.numero(f.faturado), "peças", "doc", "ok"),
            c.kpi("Recebido CD", fmt.numero(f.recebido_cd), "peças", "carteira", "ok"),
            c.kpi("Total Minutos", fmt.numero(f.tempo_total), "carga produtiva", "relogio"),
            c.kpi("Evolução", fmt.pct_programado(f.evolucao), "faturado / carteira",
                  "pct", "atencao"),
        ]
    )


def _funil(f: FluxoProdutivo) -> str:
    """Do pedido ao CD, cada estágio como fração da carteira.

    A indentação carrega a informação: 'Em Processo' e 'Embalado' são dois
    ramos do mesmo 'Programado', não degraus de uma escada. Sem isso, uma
    competência já encerrada — onde quase tudo está embalado e quase nada em
    processo — parecia um funil quebrado.
    """
    estagios = f.funil()
    base = estagios[0][1] or 1.0
    linhas = "".join(
        c.linha_barra(
            rotulo,
            fmt.numero(valor),
            valor / base,
            VERDE if nivel <= 2 else VERDE_CLARO,
            fmt.pct_programado(valor / base) + " da carteira",
            nivel=nivel,
        )
        for rotulo, valor, nivel in estagios
    )
    return c.painel("Funil de Conversão", linhas)


def _etapas(f: FluxoProdutivo) -> str:
    """WIP por etapa, na ordem real de produção.

    A ordem é a do fluxo, não a do volume: o operador procura a etapa pelo lugar
    dela na linha. O gargalo ganha destaque no lugar onde ele está.
    """
    if not f.etapas:
        return c.painel(
            "WIP por Etapa",
            '<div class="pcp-lb__obs">Nenhuma etapa com volume neste recorte.</div>',
        )

    maior = max(f.etapas.values()) or 1.0
    gargalo = f.gargalo[0] if f.gargalo else ""
    linhas = []
    for chave, valor in f.etapas.items():
        rotulo = _rotulo(chave)
        e_gargalo = rotulo == gargalo
        linhas.append(
            c.linha_barra(
                rotulo,
                fmt.numero(valor),
                valor / maior,
                VERMELHO if e_gargalo else AZUL,
                (
                    f"{fmt.pct_programado(valor / f.wip_total)} do WIP"
                    + (" · gargalo" if e_gargalo else "")
                ),
                destaque=e_gargalo,
            )
        )
    return c.painel("WIP por Etapa · ordem de produção", "".join(linhas))


def _rotulo(chave: str) -> str:
    return schema.ROTULO_ETAPA.get(chave, chave)


def _leitura(f: FluxoProdutivo) -> str:
    """Conclusão gerada por regra: o gargalo é sempre o maior WIP do recorte."""
    if not f.gargalo:
        return ""
    nome, valor = f.gargalo
    participacao = valor / f.wip_total if f.wip_total else 0.0
    ordenadas = sorted(f.etapas.values(), reverse=True)
    segunda = ordenadas[1] if len(ordenadas) > 1 else 0.0
    vezes = f" — {fmt.numero(valor / segunda, 1)}× a segunda etapa" if segunda else ""

    return c.nota(
        f"<b>GARGALO:</b> a etapa <b>{nome}</b> concentra "
        f"<b>{fmt.numero(valor)}</b> peças, <b>{fmt.pct_programado(participacao)}</b> "
        f"de todo o WIP{vezes}.",
        "erro",
        "alerta",
    )
