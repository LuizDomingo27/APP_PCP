"""M5 — Painel Full Kit & Matéria-Prima.

Sai do "temos 49.163 peças sem MP" para "são estes componentes, com estes
pedidos de compra, com esta previsão". O ganho sobre a planilha é o caminho até
o item: o número do painel atual não diz em que porta bater.

O simulador responde à pergunta que o PCP faz toda manhã — *se o full kit deste
componente chegar, libera quantas peças?* — e mostra também o que **não** é
liberado, porque MP raramente é a única trava.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pcp import Carga
from pcp.rules import Filtros, FullKit, full_kit, simular_chegada

from .. import components as c
from .. import format as fmt
from ..theme import AZUL, LARANJA, VERDE, VERMELHO

# Quantos componentes entram no ranking visual. O resto continua na tabela.
_TOP_COMPONENTES = 8


def render(carga: Carga, filtros: Filtros, titulo_periodo: str) -> None:
    fk = full_kit(carga.mp, filtros)

    st.markdown(
        c.cabecalho(
            "Full Kit & Matéria-Prima",
            f"{carga.unidade} · {titulo_periodo}",
            [("Atualizado em", carga.rotulo_snapshot)],
        ),
        unsafe_allow_html=True,
    )

    if fk.saldo_pendente == 0:
        st.markdown(
            c.nota(
                "Não há saldo pendente neste recorte — nenhum componente a acompanhar.",
                "ok",
                "alvo",
            ),
            unsafe_allow_html=True,
        )
        return

    st.markdown(_faixa(fk), unsafe_allow_html=True)

    esquerda, direita = st.columns([1.35, 1.0], gap="small")
    with esquerda:
        st.markdown(_ranking(fk), unsafe_allow_html=True)
    with direita:
        st.markdown(_aderencia(fk), unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    _simulador(carga, filtros, fk)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown(_tabela(fk), unsafe_allow_html=True)


def _faixa(fk: FullKit) -> str:
    return c.faixa_kpis(
        [
            c.kpi("Saldo Pendente", fmt.numero(fk.saldo_pendente), "peças", "agenda"),
            c.kpi("Bloqueado por MP", fmt.numero(fk.bloqueado), "à receber", "camisa", "alerta"),
            c.kpi("% Bloqueado", fmt.pct_programado(fk.pct_bloqueado), "do pendente", "pct", "alerta"),
            c.kpi("MP Em Casa", fmt.numero(fk.liberado), "peças", "caixa", "ok"),
            c.kpi("Com Pedido de Compra", fmt.numero(fk.com_pedido), "peças", "doc", "atencao"),
            c.kpi("Sem Pedido", fmt.numero(fk.sem_pedido), "nada a caminho", "alerta", "alerta"),
            c.kpi("Previsão Aderente", fmt.numero(fk.aderente), "peças", "alvo", "ok"),
            c.kpi("Previsão Não Aderente", fmt.numero(fk.nao_aderente), "peças", "relogio", "alerta"),
        ]
    )


def _ranking(fk: FullKit) -> str:
    """Componentes ordenados pelo saldo que travam — a fila de cobrança."""
    bloqueando = fk.itens[fk.itens["saldo_bloqueado"] > 0].head(_TOP_COMPONENTES)
    if bloqueando.empty:
        return c.painel(
            "Componentes que travam a programação",
            '<div class="pcp-lb__obs">Nenhum componente com MP a receber neste recorte.</div>',
        )

    maior = float(bloqueando["saldo_bloqueado"].max()) or 1.0
    linhas = []
    for i, item in enumerate(bloqueando.itertuples()):
        linhas.append(
            c.linha_barra(
                item.componente,
                fmt.numero(item.saldo_bloqueado),
                item.saldo_bloqueado / maior,
                VERMELHO if i == 0 else LARANJA,
                _observacao(item),
                destaque=i == 0,
            )
        )
    return c.painel(
        f"Componentes que travam a programação · top {len(bloqueando)}", "".join(linhas)
    )


def _observacao(item) -> str:
    """Previsão e diagnóstico do PCP na mesma linha do componente."""
    partes = [item.descricao[:44]] if item.descricao else []
    if pd.notna(item.previsao):
        partes.append(f"previsto {fmt.data(item.previsao)}")
    elif item.pedidos:
        partes.append("pedido sem data")
    else:
        partes.append("sem pedido de compra")
    if item.analise:
        partes.append(item.analise[:28])
    return " · ".join(partes)


def _aderencia(fk: FullKit) -> str:
    """Aderência da previsão de MP — quanto do bloqueio tem data confiável."""
    base = fk.bloqueado or 1.0
    corpo = (
        f'<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">'
        f"{c.donut(fk.aderente / base, VERDE, fmt.pct_programado(fk.aderente / base), 'aderente')}"
        f'<div class="pcp-legenda">'
        f"{c.item_legenda(VERDE, 'ADERENTE', fmt.numero(fk.aderente) + ' peças', 'previsão confiável')}"
        f"{c.item_legenda(VERMELHO, 'NÃO ADERENTE', fmt.numero(fk.nao_aderente) + ' peças', 'previsão furada')}"
        f"{c.item_legenda(AZUL, 'SEM PEDIDO', fmt.numero(fk.sem_pedido) + ' peças', 'nada comprado ainda')}"
        f"</div></div>"
    )
    return c.painel("Aderência da Previsão de MP", corpo)


def _simulador(carga: Carga, filtros: Filtros, fk: FullKit) -> None:
    """Interativo: precisa de widget do Streamlit, não sai como HTML puro."""
    bloqueando = fk.itens[fk.itens["saldo_bloqueado"] > 0]
    if bloqueando.empty:
        return

    st.markdown(
        c.painel(
            "Simulador de Full Kit",
            '<div class="pcp-lb__obs">Selecione os componentes cuja matéria-prima '
            "chegaria e veja quantas peças entram na programação — e quantas "
            "continuam travadas por outro motivo.</div>",
        ),
        unsafe_allow_html=True,
    )

    opcoes = bloqueando["componente"].tolist()
    escolhidos = st.multiselect(
        "Componentes que chegariam",
        opcoes,
        default=opcoes[:1],
        format_func=lambda x: f"{x} · {fmt.numero(_saldo_de(bloqueando, x))} peças",
    )

    s = simular_chegada(carga.mp, filtros, escolhidos)
    if not escolhidos:
        return

    st.markdown(
        c.faixa_kpis(
            [
                c.kpi("Disponível Hoje", fmt.numero(s.disponivel_hoje), "peças", "caixa"),
                c.kpi("Depois da Chegada", fmt.numero(s.disponivel_depois), "peças", "foguete", "ok"),
                c.kpi("Ganho", fmt.sinal(s.ganho), "peças liberadas", "alvo",
                      "ok" if s.ganho else "atencao"),
                c.kpi("Continua Travado", fmt.numero(s.travado_por_outros), "peças",
                      "alerta", "alerta"),
            ],
            variante="contexto",
        ),
        unsafe_allow_html=True,
    )

    if s.motivos:
        motivos = " · ".join(
            f"<b>{fmt.numero(v)}</b> {k.lower()}" for k, v in s.motivos.items()
        )
        st.markdown(
            c.nota(
                f"Das <b>{fmt.numero(s.saldo_alvo)}</b> peças destes componentes, "
                f"<b>{fmt.numero(s.ganho)}</b> entrariam na programação. O resto "
                f"continua parado por outro motivo: {motivos}. Liberar a MP sozinha "
                f"não resolve esse saldo.",
                "aviso" if s.ganho else "erro",
                "peca",
            ),
            unsafe_allow_html=True,
        )


def _saldo_de(itens: pd.DataFrame, componente: str) -> float:
    linha = itens.loc[itens["componente"] == componente, "saldo_bloqueado"]
    return float(linha.iloc[0]) if not linha.empty else 0.0


# O status chega normalizado da regra (sem acento, maiúsculo) para comparação
# ser confiável. Na tela ele volta escrito como se lê em português.
_ADERENCIA = {"ADERENTE": "Aderente", "NAO ADERENTE": "Não aderente", "": "—"}

_CABECALHOS = [
    "Componente", "Descrição", "Bloqueado", "Estoque", "Reserva",
    "Pedido de compra", "Previsão", "Aderência",
]


def _tabela(fk: FullKit) -> str:
    linhas = []
    for item in fk.itens.itertuples():
        classe = "g" if item.saldo_bloqueado > 0 else ""
        pedido = item.pedidos[0].split(" - ")[0] if item.pedidos else "—"
        linhas.append(
            (
                classe,
                [
                    item.componente,
                    item.descricao[:38] or "—",
                    fmt.numero(item.saldo_bloqueado),
                    fmt.numero(item.estoque),
                    fmt.numero(item.reserva),
                    pedido,
                    fmt.data(item.previsao) if pd.notna(item.previsao) else "—",
                    _ADERENCIA.get(item.status, item.status.title() or "—"),
                ],
            )
        )
    return c.painel(
        "Todos os componentes do recorte", c.tabela(_CABECALHOS, linhas)
    )
