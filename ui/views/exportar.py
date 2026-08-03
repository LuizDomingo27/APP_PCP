"""M9 — Exportação.

Dois formatos, cada um para um uso real da rotina:

* **Excel** — o detalhamento em dado, uma aba por bloco de tela, já com o
  recorte de filtros aplicado. Substitui o "abrir a planilha, filtrar e copiar"
  antes da reunião, sem a chance de copiar o filtro errado.
* **Relatório imprimível** — os painéis como estão na tela, em HTML autocontido.
  Abrir e imprimir (Ctrl+P → Salvar como PDF) gera o PDF da reunião. O porquê de
  não gerar o PDF direto está em `ui/report.py`: um PDF fiel exigiria navegador
  headless ou um segundo layout em ReportLab, que divergiria do painel na
  primeira mudança de CSS.
"""

from __future__ import annotations

import streamlit as st

from pcp import Carga, export, loader
from pcp.rules import Filtros

from .. import components as c
from .. import format as fmt
from .. import report, state


def render(carga: Carga, filtros: Filtros, titulo_periodo: str) -> None:
    st.markdown(
        c.cabecalho(
            "Exportar",
            f"{carga.unidade} · {titulo_periodo}",
            [("Atualizado em", carga.rotulo_snapshot)],
        ),
        unsafe_allow_html=True,
    )

    st.markdown(_contexto(carga, filtros, titulo_periodo), unsafe_allow_html=True)

    escolhidos = st.multiselect(
        "Blocos no relatório imprimível",
        list(report.BLOCOS),
        default=list(report.BLOCOS),
        format_func=lambda chave: report.BLOCOS[chave],
    )

    esquerda, direita = st.columns(2, gap="small")
    with esquerda:
        _botao_excel(carga, filtros, titulo_periodo)
    with direita:
        _botao_relatorio(carga, filtros, titulo_periodo, escolhidos)

    st.markdown(
        c.nota(
            "O relatório sai em HTML autocontido — abra o arquivo e use "
            "<b>Ctrl+P → Salvar como PDF</b> para a versão da reunião. O layout "
            "de impressão (paisagem A4, sem quebra no meio de um painel) já vai "
            "no arquivo.",
            "info",
            "doc",
        ),
        unsafe_allow_html=True,
    )


def _contexto(carga: Carga, filtros: Filtros, titulo_periodo: str) -> str:
    """O que exatamente vai no arquivo — o filtro ativo é parte do conteúdo."""
    ativos = filtros.dimensoes_ativas()
    recorte = " · ".join(f"{k}: {v}" for k, v in ativos.items()) if ativos else "sem filtro adicional"
    return c.faixa_kpis(
        [
            c.kpi("Competência", titulo_periodo, "recorte exportado", "agenda"),
            c.kpi("Snapshot", carga.rotulo_snapshot, "data da base", "relogio"),
            c.kpi("Filtros Ativos", fmt.numero(len(ativos)), recorte[:38], "prancheta"),
            c.kpi("Linhas na Base", fmt.numero(len(carga.cpg)), "BASE CPG", "doc"),
        ],
        variante="contexto",
    )


def _botao_excel(carga: Carga, filtros: Filtros, titulo_periodo: str) -> None:
    """O arquivo é montado no clique, não a cada rerun.

    Gerar o .xlsx no corpo da view custaria ~1s a cada troca de filtro, para um
    arquivo que na maioria das vezes ninguém baixa.
    """
    if st.button("Gerar planilha de detalhamento (.xlsx)", use_container_width=True):
        serie = loader.serie_historica(state.cargas() or [carga], filtros)
        st.session_state["pcp_excel"] = (
            export.excel(carga, filtros, titulo_periodo, serie),
            report.nome_arquivo(carga, titulo_periodo, "xlsx"),
        )

    guardado = st.session_state.get("pcp_excel")
    if guardado:
        conteudo, nome = guardado
        st.download_button(
            f"Baixar {nome}",
            data=conteudo,
            file_name=nome,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def _botao_relatorio(
    carga: Carga, filtros: Filtros, titulo_periodo: str, escolhidos: list[str]
) -> None:
    if st.button("Gerar relatório dos painéis (.html)", use_container_width=True):
        st.session_state["pcp_relatorio"] = (
            report.pagina(carga, filtros, titulo_periodo, escolhidos),
            report.nome_arquivo(carga, titulo_periodo, "html"),
        )

    guardado = st.session_state.get("pcp_relatorio")
    if guardado:
        conteudo, nome = guardado
        st.download_button(
            f"Baixar {nome}",
            data=conteudo.encode("utf-8"),
            file_name=nome,
            mime="text/html",
            use_container_width=True,
        )
