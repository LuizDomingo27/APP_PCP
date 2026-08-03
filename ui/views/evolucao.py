"""M7 — Painel Evolução Histórica.

Escopo ajustado pela decisão "sem banco de dados" (PLANO_APP_PCP.md §3): a
série não é do time, é **desta máquina**. Cada planilha aberta aqui vira um
ponto permanente no cache local, e o painel monta a curva a partir dele. Duas
consequências que a tela precisa deixar explícitas:

* com um snapshot só não existe variação medível — o painel diz isso em vez de
  desenhar uma linha reta e fingir tendência;
* a velocidade de programação é medida na janela inteira (primeiro contra
  último snapshot), não no último par, senão um dia sem carga derruba a
  projeção a zero.
"""

from __future__ import annotations

import streamlit as st

from pcp import Carga, loader
from pcp.loader import INDICADORES_SERIE, Evolucao
from pcp.rules import Filtros

from .. import components as c
from .. import format as fmt
from .. import state
from ..theme import AZUL, LARANJA, VERDE, VERMELHO

# Indicadores que ganham curva própria, com a cor que já têm nos outros painéis.
_CURVAS = (
    ("programado", "Programado", VERDE),
    ("a_programar", "A Programar", LARANJA),
    ("sem_mp", "Sem MP", VERMELHO),
    ("disponivel_para_programar", "Disponível para Programar", AZUL),
)

_ROTULOS = {
    "carteira_total": "Carteira Total",
    "programado": "Programado",
    "a_programar": "A Programar",
    "sem_avi": "Sem AVI",
    "sem_mp": "Sem MP",
    "sem_prototipo": "Sem Protótipo",
    "mp_prot_sem_avi": "MP + Prot (sem AVI)",
    "disponivel_para_programar": "Disp. para Programar",
}


def render(carga: Carga, filtros: Filtros, titulo_periodo: str) -> None:
    cargas = _cargas_da_serie(carga)
    e = loader.evolucao(cargas, filtros)

    st.markdown(
        c.cabecalho(
            "Evolução Histórica",
            f"{carga.unidade} · {titulo_periodo}",
            [("Atualizado em", carga.rotulo_snapshot),
             ("Snapshots", fmt.numero(e.pontos))],
        ),
        unsafe_allow_html=True,
    )

    _avisar_cache_ilegivel()

    if not e.suficiente:
        _sem_serie(e)
        return

    st.markdown(_faixa(e), unsafe_allow_html=True)

    esquerda, direita = st.columns([1.5, 1.0], gap="small")
    with esquerda:
        st.markdown(_curvas(e), unsafe_allow_html=True)
    with direita:
        st.markdown(_projecao(e), unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown(_leitura(e), unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown(_tabela(e), unsafe_allow_html=True)


def _cargas_da_serie(ativa: Carga) -> list[Carga]:
    """Sessão + cache local, sem repetir o mesmo arquivo.

    O cache é o que dá histórico sem o usuário guardar .xlsx de 139 MB; a
    sessão entra porque uma planilha recém-carregada precisa aparecer na curva
    no mesmo instante.
    """
    da_sessao = state.cargas()
    nomes = {c_.arquivo for c_ in da_sessao}
    do_cache = [c_ for c_ in state.historico_local() if c_.arquivo not in nomes]
    todas = [*da_sessao, *do_cache]
    return todas or [ativa]


def _avisar_cache_ilegivel() -> None:
    """Cache quebrado não pode se disfarçar de 'faltam snapshots'.

    Sem isto a tela abaixo manda carregar a planilha de outro dia, o usuário
    carrega, e a curva continua igual — porque o problema nunca esteve nele.
    """
    motivo = state.erro_historico_local()
    if not motivo:
        return
    st.markdown(
        c.nota(
            "Não consegui ler o histórico guardado nesta máquina, então a curva "
            "mostra só as planilhas carregadas nesta sessão. Motivo: <b>"
            + c.escapar(motivo)
            + "</b>.",
            "aviso",
        ),
        unsafe_allow_html=True,
    )


def _sem_serie(e: Evolucao) -> None:
    """Um ponto não é série — e dizer isso vale mais que desenhar uma reta."""
    st.markdown(
        c.nota(
            "A curva precisa de <b>pelo menos dois snapshots</b> de datas "
            "diferentes. Hoje há <b>"
            + fmt.numero(e.pontos)
            + "</b>. Carregue a planilha de outro dia em <b>Carregar planilha</b>: "
            "cada arquivo aberto nesta máquina fica guardado no cache local e "
            "vira um ponto permanente aqui — não é preciso manter os .xlsx.",
            "info",
            "foguete",
        ),
        unsafe_allow_html=True,
    )
    if not e.serie.empty:
        st.markdown(_tabela(e), unsafe_allow_html=True)


def _faixa(e: Evolucao) -> str:
    velocidade = (
        fmt.sinal(e.velocidade, 0) if e.velocidade is not None else "—"
    )
    atraso = e.dias_de_atraso
    return c.faixa_kpis(
        [
            c.kpi("Snapshots na Série", fmt.numero(e.pontos), "datas distintas", "agenda"),
            c.kpi("Velocidade", velocidade, "peças programadas/dia", "foguete",
                  "ok" if (e.velocidade or 0) > 0 else "alerta"),
            c.kpi("Saldo a Programar", fmt.numero(e.serie["a_programar"].iloc[-1]),
                  "no último snapshot", "prancheta", "atencao"),
            c.kpi("Projeção de Fechamento",
                  fmt.data(e.data_projetada) if e.data_projetada is not None else "—",
                  "no ritmo atual", "alvo",
                  _tom_projecao(atraso)),
            c.kpi("Fim da Competência",
                  fmt.data(e.fim_competencia) if e.fim_competencia is not None else "—",
                  "prazo do mês", "relogio"),
        ],
        variante="contexto",
    )


def _tom_projecao(atraso: float | None) -> str:
    if atraso is None:
        return "neutro"
    return "alerta" if atraso > 0 else "ok"


def _curvas(e: Evolucao) -> str:
    rotulos = [d.strftime("%d/%m") for d in e.serie["snapshot"]]
    blocos = []
    for chave, rotulo, cor in _CURVAS:
        valores = [float(v) for v in e.serie[chave]]
        variacao = e.variacao(chave) or 0.0
        blocos.append(
            f'<div style="margin-bottom:14px">'
            f'<div class="pcp-lb__rot" style="display:flex;justify-content:space-between;'
            f'align-items:baseline;font-weight:800">'
            f"<span>{rotulo}</span>"
            f'<span class="num" style="color:{cor}">{fmt.numero(valores[-1])} '
            f'<span style="font-size:.7rem;color:#8B9A90">({fmt.sinal(variacao)})</span></span>'
            f"</div>{c.serie_linha(valores, cor, rotulos)}</div>"
        )
    return c.painel("Curva dos Indicadores", "".join(blocos))


def _projecao(e: Evolucao) -> str:
    """A pergunta da reunião: no ritmo atual, o mês fecha no prazo?"""
    if e.velocidade is None or e.velocidade <= 0:
        corpo = c.nota(
            "A programação não avançou entre os snapshots (velocidade zero ou "
            "negativa). Sem avanço não há ritmo para projetar — projetar aqui "
            "seria inventar data.",
            "aviso",
            "relogio",
        )
        return c.painel("Projeção de Fechamento", corpo)

    atraso = e.dias_de_atraso
    itens = [
        c.par("Velocidade medida", f"{fmt.numero(e.velocidade)} peças/dia"),
        c.par("Dias para zerar o saldo",
              fmt.numero(e.dias_uteis_restantes, 1) if e.dias_uteis_restantes else "—"),
        c.par("Data projetada", fmt.data(e.data_projetada)),
    ]
    if e.fim_competencia is not None:
        cor = VERMELHO if (atraso or 0) > 0 else VERDE
        texto = (
            f"{fmt.numero(abs(atraso))} dias de atraso" if (atraso or 0) > 0
            else f"{fmt.numero(abs(atraso or 0))} dias de folga"
        )
        itens.append(c.par("Contra o fim da competência", texto, cor))
    return c.painel("Projeção de Fechamento", "".join(itens))


def _leitura(e: Evolucao) -> str:
    """Conclusão por regra — muda com a série, não é texto fixo."""
    dias = int((e.serie["snapshot"].iloc[-1] - e.serie["snapshot"].iloc[0]).days)
    variacao_mp = e.variacao("sem_mp") or 0.0
    variacao_saldo = e.variacao("a_programar") or 0.0

    partes = [
        f"Em <b>{fmt.numero(dias)} dias</b> de série, o saldo a programar "
        f"{'caiu' if variacao_saldo < 0 else 'subiu'} "
        f"<b>{fmt.numero(abs(variacao_saldo))}</b> peças e o bloqueio por MP "
        f"{'caiu' if variacao_mp < 0 else 'subiu'} "
        f"<b>{fmt.numero(abs(variacao_mp))}</b>."
    ]
    if e.data_projetada is not None and e.fim_competencia is not None:
        atraso = e.dias_de_atraso or 0
        if atraso > 0:
            partes.append(
                f"No ritmo atual a competência fecha em <b>{fmt.data(e.data_projetada)}</b>, "
                f"<b>{fmt.numero(atraso)} dias depois</b> do fim do mês — é preciso "
                f"acelerar a liberação para recuperar."
            )
            tipo, icone = "erro", "alerta"
        else:
            partes.append(
                f"No ritmo atual a competência fecha em <b>{fmt.data(e.data_projetada)}</b>, "
                f"dentro do mês, com <b>{fmt.numero(abs(atraso))} dias</b> de folga."
            )
            tipo, icone = "ok", "alvo"
    else:
        tipo, icone = "info", "relogio"
    return c.nota(" ".join(partes), tipo, icone)


def _tabela(e: Evolucao) -> str:
    cabecalhos = ["Snapshot", *[_ROTULOS[i] for i in INDICADORES_SERIE], "% Prog."]
    linhas = []
    for item in e.serie.itertuples():
        linhas.append(
            (
                "",
                [
                    fmt.data(item.snapshot),
                    *[fmt.numero(getattr(item, i)) for i in INDICADORES_SERIE],
                    fmt.pct_programado(item.pct_programado),
                ],
            )
        )
    if e.suficiente:
        linhas.append(
            (
                "t",
                [
                    "VARIAÇÃO",
                    *[fmt.sinal(e.variacao(i) or 0.0) for i in INDICADORES_SERIE],
                    "—",
                ],
            )
        )
    return c.painel("Série por Snapshot", c.tabela(cabecalhos, linhas))
