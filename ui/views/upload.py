"""M1 — Upload e validação.

Porta de entrada diária. Valida antes de aceitar e mostra o diff contra a carga
anterior, para que número estranho apareça aqui e não na reunião.
"""

from __future__ import annotations

import streamlit as st

from pcp import Carga, comparar, rules

from .. import components as c
from .. import format as fmt
from .. import state

_ROTULOS = {
    "carteira_total": "Carteira Total",
    "programado": "Programado",
    "a_programar": "A Programar",
    "sem_avi": "Sem AVI",
    "sem_mp": "Sem MP",
    "sem_prototipo": "Sem Protótipo",
    "mp_prot_sem_avi": "MP + Prot (sem AVI)",
    "disponivel_para_programar": "Disponível para Programar",
}


def render() -> None:
    st.markdown(
        c.cabecalho(
            "Carregar planilha do dia",
            "Follow Up · Oficina Jeans, Tear, Malha e Polo",
            [("Formato", ".xlsx"), ("Origem", "Follow Up")],
        ),
        unsafe_allow_html=True,
    )

    arquivo = st.file_uploader(
        "Arraste o arquivo de Follow Up ou clique para selecionar",
        type=["xlsx"],
        help="A unidade produtiva é lida da própria planilha, não escolhida aqui.",
    )

    if arquivo is not None:
        with st.spinner("Lendo e validando a planilha…"):
            resultado = state.carregar_upload(arquivo)
        _aplicar(resultado)

    _locais()
    _historico()


def _locais() -> None:
    """Atalho para planilhas já presentes na pasta do aplicativo."""
    disponiveis = state.planilhas_locais()
    if not disponiveis:
        return
    st.markdown(
        '<div class="pcp" style="font-size:.72rem;font-weight:700;color:#5C6B60;'
        'letter-spacing:.06em;text-transform:uppercase;margin:14px 0 6px">'
        "Ou use um arquivo da pasta do aplicativo</div>",
        unsafe_allow_html=True,
    )
    # Em linhas de até três. O `zip` contra `st.columns(min(len, 3))` que havia
    # aqui parava na terceira coluna: da quarta planilha em diante o botão
    # simplesmente não era desenhado, sem nenhum aviso na tela.
    for inicio in range(0, len(disponiveis), 3):
        bloco = disponiveis[inicio : inicio + 3]
        for coluna, caminho in zip(st.columns(len(bloco)), bloco, strict=True):
            with coluna:
                tamanho = caminho.stat().st_size / 1e6
                if st.button(
                    f"{caminho.name}  ·  {tamanho:.0f} MB",
                    key=f"local_{caminho.name}",
                    use_container_width=True,
                ):
                    with st.spinner(f"Lendo {caminho.name}…"):
                        resultado = state.carregar_caminho(caminho)
                    _aplicar(resultado)


def _bloco_erro(titulo: str, mensagem: str) -> str:
    """A mensagem de erro carrega pedaço do arquivo do usuário.

    `AbaAusenteError` lista os nomes de aba encontrados e `TipoInvalidoError`
    traz amostra de célula — conteúdo que ninguém controla, entrando num bloco
    marcado com `unsafe_allow_html`. Escapa primeiro, quebra linha depois.
    """
    return c.nota(
        f"<b>{c.escapar(titulo)}</b><br>"
        + c.escapar(mensagem).replace("\n", "<br>"),
        "erro",
        "alerta",
    )


def _bloco_aviso(aviso: str) -> str:
    """O aviso de domínio cita o valor cru da célula que saiu do esperado.

    `normalizar_flag` põe em maiúscula, o que não desarma nada: HTML não
    distingue caixa, e `<IMG SRC=X ONERROR=...>` executa igual.
    """
    return c.nota(c.escapar(aviso), "aviso")


def _aplicar(resultado) -> None:
    if not resultado.ok:
        st.markdown(
            _bloco_erro(resultado.titulo_erro, resultado.erro),
            unsafe_allow_html=True,
        )
        return

    carga: Carga = resultado.carga
    anterior = state.carga_anterior()
    state.registrar(carga)

    origem = "cache local" if carga.veio_do_cache else "leitura completa"
    st.markdown(
        c.nota(
            f"<b>Planilha validada.</b> {fmt.numero(len(carga.cpg))} linhas na BASE CPG "
            f"e {fmt.numero(len(carga.mp))} na BASE MP, em {carga.segundos:.1f}s "
            f"({origem}).",
            "ok",
            "alvo",
        ),
        unsafe_allow_html=True,
    )

    st.markdown(
        c.faixa_kpis(
            [
                c.kpi("Unidade", carga.unidade, "lida do arquivo", "camisa", "ok"),
                c.kpi("Snapshot da base", carga.rotulo_snapshot, "data do extrato", "agenda"),
                c.kpi("Competências", fmt.numero(len(carga.competencias)), "ano/mês", "prancheta"),
                c.kpi("Avisos", fmt.numero(len(carga.diagnostico.avisos)),
                      "verificações", "alerta",
                      "atencao" if carga.diagnostico.avisos else "ok"),
            ]
        ),
        unsafe_allow_html=True,
    )

    for aviso in carga.diagnostico.avisos:
        st.markdown(_bloco_aviso(aviso), unsafe_allow_html=True)

    if anterior is not None:
        _diff(anterior, carga)


def _diff(anterior, atual) -> None:
    """Diff de KPIs contra a carga anterior — pega salto estranho antes da reunião."""
    competencia = atual.competencias[-1] if atual.competencias else None
    if competencia is None:
        return
    ano, mes = competencia
    filtros = rules.Filtros(mes=mes, ano=ano)

    try:
        tabela = comparar(anterior, atual, filtros)
    except Exception as exc:
        st.markdown(
            c.nota(
                "Não consegui comparar com a carga anterior: "
                + c.escapar(exc),
                "aviso",
            ),
            unsafe_allow_html=True,
        )
        return

    linhas = [
        (
            "",
            [
                _ROTULOS.get(linha["Indicador"], linha["Indicador"]),
                fmt.numero(linha[anterior.rotulo_snapshot]),
                fmt.numero(linha[atual.rotulo_snapshot]),
                fmt.sinal(linha["Variação"]),
            ],
        )
        for _, linha in tabela.iterrows()
    ]
    st.markdown(
        c.painel(
            f"O que mudou desde {anterior.rotulo_snapshot} · {fmt.competencia(ano, mes)}",
            c.tabela(
                ["Indicador", anterior.rotulo_snapshot, atual.rotulo_snapshot, "Variação"],
                linhas,
            ),
        ),
        unsafe_allow_html=True,
    )


def _historico() -> None:
    carregadas = state.cargas()
    if not carregadas:
        st.markdown(
            c.nota(
                "Nenhuma planilha carregada ainda. Suba o arquivo do dia para "
                "liberar os painéis. Carregando mais de uma data, a aba de "
                "upload mostra a variação entre elas.",
                "info",
                "foguete",
            ),
            unsafe_allow_html=True,
        )
        return

    linhas = [
        (
            "t" if c_.arquivo == (state.carga_ativa().arquivo if state.carga_ativa() else "") else "",
            [c_.arquivo, c_.unidade, c_.rotulo_snapshot, fmt.numero(len(c_.cpg)), fmt.numero(len(c_.mp))],
        )
        for c_ in carregadas
    ]
    st.markdown(
        c.painel(
            "Planilhas carregadas nesta sessão",
            c.tabela(["Arquivo", "Unidade", "Snapshot", "Linhas CPG", "Linhas MP"], linhas),
        ),
        unsafe_allow_html=True,
    )
    if st.button("Limpar sessão", help="Remove as planilhas carregadas desta sessão."):
        state.esquecer_tudo()
        st.rerun()
