"""M2 — Painel Carteira Geral.

Réplica do painel que o time já usa, com os números vivos e filtráveis.
A fidelidade visual é deliberada: a adoção depende de reconhecerem a tela.
"""

from __future__ import annotations

import streamlit as st

from pcp import Carga
from pcp.rules import Filtros, KPIs, kpis, kpis_por_dimensao

from .. import components as c
from .. import format as fmt
from ..theme import CINZA_TRILHA, LARANJA, VERDE, VERMELHO


def render(carga: Carga, filtros: Filtros, titulo_periodo: str) -> None:
    k = kpis(carga.cpg, carga.mp, filtros)

    st.markdown(
        c.cabecalho(
            "Follow Up · Carteira Geral",
            f"{carga.unidade} · {titulo_periodo}",
            # Só o carimbo da base. O nome do arquivo já fica no rodapé da
            # barra lateral e ocupava metade do cabeçalho.
            [("Atualizado em", carga.rotulo_snapshot)],
        ),
        unsafe_allow_html=True,
    )

    if k.carteira_total == 0:
        st.markdown(
            c.nota(
                "Nenhuma peça encontrada para este recorte. Verifique os filtros "
                "na barra lateral — em especial a competência.",
                "aviso",
            ),
            unsafe_allow_html=True,
        )
        return

    st.markdown(_faixa(k), unsafe_allow_html=True)

    esquerda, meio, direita = st.columns([1.05, 1.25, 1.0], gap="small")
    with esquerda:
        st.markdown(_performance(k), unsafe_allow_html=True)
    with meio:
        st.markdown(_restricoes(k), unsafe_allow_html=True)
    with direita:
        st.markdown(_disponivel(carga, filtros, k), unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown(_tabela_toc(carga, filtros, k), unsafe_allow_html=True)


def _faixa(k: KPIs) -> str:
    return c.faixa_kpis(
        [
            c.kpi("Carteira Total", fmt.numero(k.carteira_total), "peças", "pessoa"),
            c.kpi("Programado", fmt.numero(k.programado), "peças", "prancheta", "ok"),
            c.kpi("% Programado", fmt.pct_programado(k.pct_programado), "do total", "pct", "ok"),
            c.kpi("A Programar", fmt.numero(k.a_programar), "peças", "agenda"),
            c.kpi("Sem AVI", fmt.numero(k.sem_avi), "peças", "doc", "alerta"),
            c.kpi("Sem MP", fmt.numero(k.sem_mp), "peças", "camisa", "atencao"),
            c.kpi("Sem Protótipo", fmt.numero(k.sem_prototipo), "peças", "pessoa", "alerta"),
            c.kpi("MP + Prot (sem AVI)", fmt.numero(k.mp_prot_sem_avi), "peças", "peca", "atencao"),
            c.kpi("Disp. para Programar", fmt.numero(k.disponivel_para_programar), "peças", "caixa", "ok"),
        ]
    )


def _performance(k: KPIs) -> str:
    corpo = (
        f'<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">'
        f"{c.donut(k.pct_programado, VERDE, fmt.pct_programado(k.pct_programado), 'programado')}"
        f'<div class="pcp-legenda">'
        f"{c.item_legenda(VERDE, 'PROGRAMADO', fmt.numero(k.programado) + ' peças', fmt.pct_programado(k.pct_programado))}"
        f"{c.item_legenda(VERMELHO, 'A PROGRAMAR', fmt.numero(k.a_programar) + ' peças', fmt.pct_programado(1 - k.pct_programado))}"
        f"</div></div>"
    )
    return c.painel("Performance Geral", corpo)


_RESTRICOES = [
    ("sem_avi", "Sem AVI", "doc", VERMELHO),
    ("sem_mp", "Sem MP", "camisa", LARANJA),
    ("sem_prototipo", "Sem Protótipo", "pessoa", VERMELHO),
    ("mp_prot_sem_avi", "MP + Prot", "peca", LARANJA),
    ("disponivel_para_programar", "Disp. Programar", "caixa", VERDE),
]


def _restricoes(k: KPIs) -> str:
    valores = k.as_dict()
    colunas = "".join(
        f'<div style="text-align:center;flex:1;min-width:98px">'
        f'<div style="display:flex;justify-content:center;margin-bottom:5px">'
        f"{c.icone(ic, cor, 21)}</div>"
        f'<div style="font-size:.62rem;font-weight:800;color:{cor};'
        f'letter-spacing:.04em;text-transform:uppercase;text-wrap:balance">{rot}</div>'
        f'<div class="num" style="font-size:1.18rem;font-weight:800;color:{cor};'
        f'margin:3px 0">{fmt.numero(valores[chave])}</div>'
        f"{c.donut(k.pct_do_saldo(valores[chave]), cor, fmt.pct(k.pct_do_saldo(valores[chave])), tamanho=92)}"
        f'<div style="font-size:.6rem;color:#8B9A90;font-weight:600;margin-top:2px">'
        f"do saldo a programar</div></div>"
        for chave, rot, ic, cor in _RESTRICOES
    )
    maior = max(_RESTRICOES[:4], key=lambda r: valores[r[0]])
    alerta = c.nota(
        f"O maior bloqueio operacional é <b>{maior[1]}</b>, impactando "
        f"<b>{fmt.numero(valores[maior[0]])}</b> peças "
        f"({fmt.pct(k.pct_do_saldo(valores[maior[0]]))} do pendente).",
        "erro",
        "alerta",
    )
    corpo = (
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">{colunas}</div>'
        f"{alerta}"
    )
    return c.painel("Principais Restrições (a programar)", corpo)


def _disponivel(carga: Carga, filtros: Filtros, k: KPIs) -> str:
    """Quanto do disponível para programação está em cada TOC."""
    por_toc = kpis_por_dimensao(carga.cpg, carga.mp, filtros, "toc")
    disponivel = {
        linha["TOC"]: float(linha["disponivel_para_programar"])
        for _, linha in por_toc.iterrows()
    }
    total = k.disponivel_para_programar
    ordenado = sorted(disponivel.items(), key=lambda kv: -kv[1])

    # O anel mostra a participação do TOC líder; a legenda carrega a quebra
    # completa. A base tem mais TOCs que os dois do painel antigo (MTO/MTA),
    # então colorir o restante como se fosse um único TOC seria mentira.
    lider = ordenado[0][1] if ordenado else 0.0
    fracao = (lider / total) if total else 0.0

    cores = c.cores_toc([toc for toc, _ in ordenado])
    itens = "".join(
        c.item_legenda(
            cores[toc],
            toc,
            f"{fmt.numero(valor)} peças",
            fmt.pct(valor / total if total else 0),
        )
        for toc, valor in ordenado
    )
    corpo = (
        f'<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">'
        f"{c.donut(fracao, VERDE, fmt.numero(total), 'peças', cor_resto=CINZA_TRILHA)}"
        f'<div class="pcp-legenda">{itens}</div></div>'
        f'<div style="margin-top:12px">'
        # O total já está no centro do anel e na legenda; aqui entra só a
        # leitura que nenhum dos dois dá — o peso sobre o pendente.
        + c.nota(
            f"Equivale a <b>{fmt.pct(k.pct_do_saldo(total))}</b> do saldo pendente, "
            f"liberado para programação imediata.",
            "ok",
            "foguete",
        )
        + "</div>"
    )
    return c.painel("Disponível para Programação", corpo)


_COLUNAS_TABELA = [
    ("carteira_total", "Carteira Total"),
    ("programado", "Programado"),
    ("pct_programado", "%"),
    ("a_programar", "A Programar"),
    ("sem_avi", "Sem AVI"),
    ("sem_mp", "Sem MP"),
    ("sem_prototipo", "Sem Protótipo"),
    ("mp_prot_sem_avi", "MP + Prot"),
    ("disponivel_para_programar", "Disp. Programar"),
]


def _tabela_toc(carga: Carga, filtros: Filtros, total: KPIs) -> str:
    """TOC × Grupo — a tabela central do painel, com os dois níveis."""
    por_toc = kpis_por_dimensao(carga.cpg, carga.mp, filtros, "toc")
    linhas: list[tuple[str, list[str]]] = []

    for _, grupo in por_toc.iterrows():
        toc = grupo["TOC"]
        linhas.append(("g", [toc] + _celulas(grupo)))
        recorte = Filtros(**{**filtros.__dict__, "toc": toc})
        for _, sub in kpis_por_dimensao(carga.cpg, carga.mp, recorte, "departamento").iterrows():
            linhas.append(("sub", [sub["Grupo"]] + _celulas(sub)))

    linhas.append(
        ("t", ["TOTAL"] + _celulas({**total.as_dict(), "pct_programado": total.pct_programado}))
    )
    return c.painel(
        "Carteira por TOC e Grupo",
        c.tabela(["TOC / Grupo"] + [rot for _, rot in _COLUNAS_TABELA], linhas),
    )


def _celulas(linha) -> list[str]:
    return [
        fmt.pct(linha[chave]) if chave == "pct_programado" else fmt.numero(linha[chave])
        for chave, _ in _COLUNAS_TABELA
    ]
