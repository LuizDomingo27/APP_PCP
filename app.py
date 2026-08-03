"""Aplicação de PCP — ponto de entrada.

Camada de interface. Depende de `pcp` (domínio) e de `ui`; nunca o contrário.
"""

from __future__ import annotations

import streamlit as st

from pcp import rules
from ui import components as c
from ui import format as fmt
from ui import state, theme
from ui.views import (
    carteira,
    design_system,
    detratores,
    evolucao,
    exportar,
    fluxo,
    fullkit,
    prazos,
    semanal,
    upload,
)

# Ordem deliberada: paridade com a planilha primeiro (F2), ganho novo depois
# (F3). O time abre nas telas que já reconhece e desce para as que não existiam.
PAGINAS = {
    "Carregar planilha": "upload",
    "Carteira Geral": "carteira",
    "Detratores": "detratores",
    "Fluxo Produtivo": "fluxo",
    "Full Kit & MP": "fullkit",
    "Prazos & Deadline": "prazos",
    "Programação Semanal": "semanal",
    "Evolução Histórica": "evolucao",
    "Exportar": "exportar",
    "Design System": "design_system",
}

_VIEWS = {
    "carteira": carteira.render,
    "detratores": detratores.render,
    "fluxo": fluxo.render,
    "fullkit": fullkit.render,
    "prazos": prazos.render,
    "semanal": semanal.render,
    "evolucao": evolucao.render,
    "exportar": exportar.render,
    "design_system": design_system.render,
}

_DIMENSOES_SIDEBAR = [
    ("familia", "Família"),
    ("departamento", "Grupo"),
    ("tipo_produto", "Produto"),
    ("toc", "TOC"),
    ("quinzena", "Quinzena"),
]


def main() -> None:
    st.set_page_config(
        page_title="PCP · Follow Up",
        page_icon="🧵",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    theme.aplicar(st)

    pagina = _barra_lateral_topo()
    carga = state.carga_ativa()

    # O Design System documenta o produto e precisa continuar acessível mesmo
    # antes da primeira carga — ele também orienta os estados de entrada e erro.
    if pagina == "design_system":
        design_system.render()
        return

    if pagina == "upload" or carga is None:
        if carga is None and pagina != "upload":
            st.markdown(
                c.nota(
                    "Nenhuma planilha carregada. Suba o arquivo do dia em "
                    "<b>Carregar planilha</b> para liberar os painéis.",
                    "info",
                    "foguete",
                ),
                unsafe_allow_html=True,
            )
        upload.render()
        return

    competencia, filtros = _filtros(carga)
    titulo = fmt.competencia(*competencia) if competencia else "Todas as competências"

    _VIEWS[pagina](carga, filtros, titulo)


def _barra_lateral_topo() -> str:
    with st.sidebar:
        st.markdown(
            '<div class="pcp" style="padding:4px 0 14px">'
            '<div style="font-size:.68rem;font-weight:800;letter-spacing:.14em;'
            'color:#2E7D32;text-transform:uppercase">PCP</div>'
            '<div style="font-size:1.08rem;font-weight:800;color:#16211A;'
            'letter-spacing:-.02em;line-height:1.2">Follow Up<br>Programação</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        escolha = st.radio("Painel", list(PAGINAS), label_visibility="collapsed")
    return PAGINAS[escolha]


def _filtros(carga) -> tuple[tuple[int, int] | None, rules.Filtros]:
    """Filtros derivados do arquivo carregado — nada de lista fixa no código."""
    with st.sidebar:
        st.markdown("---")

        if len(state.cargas()) > 1:
            nomes = [c_.arquivo for c_ in state.cargas()]
            atual = st.selectbox(
                "Planilha", nomes, index=nomes.index(carga.arquivo)
            )
            if atual != carga.arquivo:
                st.session_state[state.CHAVE_ATIVA] = atual
                st.rerun()

        competencias = carga.competencias
        competencia = None
        if competencias:
            rotulos = [fmt.competencia(a, m) for a, m in competencias]
            padrao = _competencia_padrao(carga, competencias)
            escolha = st.selectbox("Competência", rotulos, index=padrao)
            competencia = competencias[rotulos.index(escolha)]

        valores: dict[str, str] = {}
        for chave, rotulo in _DIMENSOES_SIDEBAR:
            opcoes = _opcoes(carga, chave)
            if not opcoes:
                continue
            valores[chave] = st.selectbox(rotulo, [state.TODOS, *opcoes])

        st.markdown("---")
        # `unidade` vem da coluna 'Fábrica' da planilha e `arquivo` é o nome do
        # upload: nenhum dos dois é texto nosso, então nenhum dos dois entra
        # cru num bloco marcado com `unsafe_allow_html`.
        st.markdown(
            f'<div class="pcp" style="font-size:.68rem;color:#8B9A90;'
            f'line-height:1.6"><b>{c.escapar(carga.unidade)}</b><br>'
            f"Base de {c.escapar(carga.rotulo_snapshot)}<br>"
            f"{c.escapar(carga.arquivo)}</div>",
            unsafe_allow_html=True,
        )

    return competencia, state.montar_filtros(valores, competencia)


def _competencia_padrao(carga, competencias: list[tuple[int, int]]) -> int:
    """Abre na competência com maior saldo a programar.

    É onde está o trabalho do PCP. Abrir pela maior carteira levava a um mês
    passado já 100% programado, sem nada a decidir.

    Se a heurística não puder rodar, a tela cai na última competência **e diz
    isso**: um `except: pass` aqui deixaria o app abrindo no mês errado sem
    ninguém desconfiar, que é o zero silencioso que o projeto combate.
    """
    try:
        pendentes = [
            rules.carteira(carga.cpg, rules.Filtros(mes=m, ano=a))[2]
            for a, m in competencias
        ]
    except (KeyError, ValueError, TypeError) as exc:
        st.warning(
            f"Não consegui identificar a competência com maior saldo a "
            f"programar ({exc}). Abrindo na última do arquivo — confira o "
            f"filtro de Competência antes de usar os números."
        )
        return len(competencias) - 1

    if any(pendentes):
        return pendentes.index(max(pendentes))
    return len(competencias) - 1


def _opcoes(carga, chave: str) -> list[str]:
    base = carga.cpg if chave in carga.cpg.columns else carga.mp
    return rules.valores_de(base, chave)


if __name__ == "__main__":
    main()
