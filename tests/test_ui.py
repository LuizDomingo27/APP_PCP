"""Testes da camada de interface (partes puras, sem Streamlit em execução)."""

from __future__ import annotations

import pandas as pd
import pytest

from pcp.rules import KPIs
from ui import components as c
from ui import format as fmt
from ui.views.detratores import DETRATORES, _classificar, _faixa, _ordenados

# --------------------------------------------------------------------------
# Formatação pt-BR
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [(574934, "574.934"), (1000, "1.000"), (0, "0"), (16674, "16.674"), (None, "—")],
)
def test_numero_usa_separador_brasileiro(valor, esperado):
    assert fmt.numero(valor) == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"), [(0.8602, "86%"), (0.0261, "3%"), (1.0, "100%"), (None, "—")]
)
def test_percentual(valor, esperado):
    assert fmt.pct(valor) == esperado


def test_variacao_tem_sinal_explicito():
    assert fmt.sinal(12400) == "+12.400"
    assert fmt.sinal(-3200) == "−3.200"
    assert fmt.sinal(0) == "0"


def test_competencia_em_portugues():
    assert fmt.competencia(2026, 9) == "Setembro/2026"


# --------------------------------------------------------------------------
# Componentes
# --------------------------------------------------------------------------


def test_donut_respeita_limites_da_fracao():
    """Fração fora de 0..1 não pode gerar arco inválido."""
    for fracao in (-0.5, 0.0, 0.5, 1.0, 2.0):
        svg = c.donut(fracao, "#2E7D32", "86%")
        assert svg.startswith("<svg") and "stroke-dasharray" in svg


def test_donut_sem_legenda_centraliza_o_numero():
    assert 'y="88"' in c.donut(0.5, "#000", "50%")
    assert 'y="84"' in c.donut(0.5, "#000", "50%", "programado")


def test_barra_limita_largura_a_100_por_cento():
    assert "width:100.0%" in c.barra(3.0, "#000")
    assert "width:0.0%" in c.barra(-1.0, "#000")


def test_componentes_escapam_html_do_dado():
    """Descrição de material vem da planilha e pode conter < ou &."""
    assert "<script>" not in c.kpi("<script>x</script>", "1", "peças", "doc")
    assert "&lt;script&gt;" in c.kpi("<script>x</script>", "1", "peças", "doc")


def test_tabela_monta_classes_de_linha():
    html = c.tabela(["A", "B"], [("g", ["MTO", "1"]), ("t", ["TOTAL", "2"])])
    assert 'class="g"' in html and 'class="t"' in html


def test_css_neutraliza_a_margem_negativa_do_streamlit():
    """Guarda de regressão para a sobreposição entre cartões.

    O Streamlit aplica `margin-bottom:-16px` no stMarkdownContainer para
    cancelar a margem do <p> do markdown. Nosso HTML não tem <p>, então o -16px
    puxava cada bloco para cima do anterior. Se esta regra sair do CSS, os
    cartões voltam a se sobrepor em todas as abas.
    """
    from ui import theme

    assert 'div[data-testid="stMarkdownContainer"]:has(> .pcp)' in theme.CSS
    assert "margin-bottom: 0 !important" in theme.CSS


def test_cada_toc_recebe_uma_cor_distinta():
    """A base tem mais TOCs que MTO/MTA; repetir cor apaga a leitura."""
    cores = c.cores_toc(["MTO", "MTA", "DCO", "XPT"])
    assert cores["MTO"] != cores["DCO"]
    assert len(set(cores.values())) == 4


def test_icone_desconhecido_nao_quebra():
    assert c.icone("nao_existe").startswith("<svg")


def test_design_system_cobre_todas_as_telas_de_produto():
    """A documentação viva não pode perder uma jornada da navegação."""
    from ui.views.design_system import _TELAS, _matriz_telas

    assert len(_TELAS) == 9
    html = _matriz_telas()
    for _numero, tela, _pergunta, _saida, _momento in _TELAS:
        assert c.escapar(tela) in html


def test_design_system_usa_os_tokens_reais_de_cor():
    from ui import theme
    from ui.views.design_system import _CORES

    catalogo = {nome: hexadecimal for nome, hexadecimal, _papel, _uso in _CORES}
    assert catalogo["Verde profundo"] == theme.VERDE_ESCURO
    assert catalogo["Vermelho"] == theme.VERMELHO


def test_arquitetura_documenta_todas_as_camadas_com_diagrama():
    from ui.views.design_system import _CAMADAS_ARQUITETURA, _camadas_tecnicas

    assert len(_CAMADAS_ARQUITETURA) == 8
    html = _camadas_tecnicas()
    assert html.count('class="ds-arch-layer"') == len(_CAMADAS_ARQUITETURA)
    assert html.count("RECEBE") == len(_CAMADAS_ARQUITETURA)
    assert html.count("RESPONSABILIDADE") == len(_CAMADAS_ARQUITETURA)
    assert html.count("ENTREGA") == len(_CAMADAS_ARQUITETURA)
    for _numero, nome, arquivos, *_resto in _CAMADAS_ARQUITETURA:
        assert c.escapar(nome) in html
        assert c.escapar(arquivos) in html


def test_mapa_de_manutencao_aponta_regra_de_negocio_para_dominio():
    from ui.views.design_system import _MAPA_MUDANCAS, _matriz_mudancas

    html = _matriz_mudancas()
    assert len(_MAPA_MUDANCAS) >= 10
    assert "Regra de negócio ou KPI" in html
    assert "pcp/rules.py" in html
    assert "Como implementar" in html
    assert "Confira também" in html


# --------------------------------------------------------------------------
# Regra de classificação dos detratores
# --------------------------------------------------------------------------


def _kpis(**ajustes) -> KPIs:
    base = dict(
        carteira_total=574934, programado=494563, a_programar=80371,
        sem_avi=45777, sem_mp=49163, sem_prototipo=2100,
        mp_prot_sem_avi=15343, disponivel_para_programar=16674,
    )
    return KPIs(**{**base, **ajustes})


def test_ranking_ordena_por_volume_e_deixa_oportunidade_por_ultimo():
    ordem = [d.chave for d, _, _ in _ordenados(_kpis())]
    assert ordem[0] == "sem_mp"          # 49.163
    assert ordem[1] == "sem_avi"         # 45.777
    assert ordem[-1] == "disponivel_para_programar"


def test_ranking_acompanha_os_numeros_e_nao_e_fixo():
    """Se Sem AVI passar Sem MP, o topo do ranking precisa mudar."""
    ordem = [d.chave for d, _, _ in _ordenados(_kpis(sem_mp=1000))]
    assert ordem[0] == "sem_avi"


def test_maior_detrator_recebe_rotulo_de_maior_impacto():
    detrator = next(d for d in DETRATORES if d.chave == "sem_mp")
    impacto, _ = _classificar(0, detrator, 0.61)
    assert impacto == "Maior impacto"


def test_oportunidade_nunca_e_tratada_como_bloqueio():
    detrator = next(d for d in DETRATORES if d.oportunidade)
    impacto, _ = _classificar(0, detrator, 0.21)
    assert impacto == "Oportunidade"


def test_percentuais_do_painel_batem_com_a_imagem_de_referencia():
    k = _kpis()
    assert fmt.pct(k.pct_do_saldo(k.sem_mp)) == "61%"
    assert fmt.pct(k.pct_do_saldo(k.sem_avi)) == "57%"
    assert fmt.pct(k.pct_do_saldo(k.sem_prototipo)) == "3%"
    assert fmt.pct(k.pct_do_saldo(k.mp_prot_sem_avi)) == "19%"
    assert fmt.pct(k.pct_do_saldo(k.disponivel_para_programar)) == "21%"


def test_faixa_de_detratores_nao_repete_o_ranking():
    """Cada detrator aparece uma vez só na tela — no ranking, não em cartão."""
    faixa = _faixa(_kpis())
    for rotulo in ("SEM AVI", "SEM MP", "SEM PROTÓTIPO", "MP + PROT"):
        assert rotulo not in faixa.upper(), f"'{rotulo}' duplicado entre faixa e ranking"
    assert "A Programar" in faixa, "o contexto da competência precisa ficar"


def test_saldo_zero_nao_divide_por_zero():
    k = _kpis(a_programar=0)
    assert k.pct_do_saldo(k.sem_mp) == 0.0
    assert all(fracao == 0.0 for _, _, fracao in _ordenados(k))


# --------------------------------------------------------------------------
# Telas da Fase 3 (M4, M5, M6)
# --------------------------------------------------------------------------


def test_data_nao_mostra_nat_na_tela():
    """Componente sem previsão de entrega existe: 'NaT' seria vazamento técnico."""
    assert fmt.data(pd.NaT) == "—"
    assert fmt.data(None) == "—"
    assert fmt.data(pd.Timestamp("2026-07-31")) == "31/07/2026"


def test_linha_barra_indenta_por_nivel():
    """A indentação é o que mostra que o funil ramifica."""
    raiz = c.linha_barra("Carteira", "100", 1.0, "#000")
    filho = c.linha_barra("Programado", "90", 0.9, "#000", nivel=2)
    assert "padding-left" not in raiz
    assert "padding-left:28px" in filho


def test_linha_barra_escapa_dado_da_planilha():
    html = c.linha_barra("<b>x</b>", "1", 0.5, "#000", "<i>obs</i>")
    assert "<b>x</b>" not in html and "&lt;b&gt;" in html


def test_toda_faixa_de_prazo_tem_cor():
    """Faixa nova sem cor cairia no fallback e apagaria o semáforo."""
    from pcp.rules import FAIXAS_PRAZO, SEM_DATA
    from ui.views.prazos import _CORES

    for rotulo, _ in FAIXAS_PRAZO:
        assert rotulo in _CORES, f"faixa '{rotulo}' sem cor definida"
    assert SEM_DATA in _CORES


def test_toda_situacao_de_semana_tem_cor():
    """Situação nova sem cor cairia no fallback e apagaria o semáforo da agenda."""
    from pcp import rules
    from ui.views.semanal import _CORES

    for situacao in (rules.VENCIDA, rules.ESTA_SEMANA, rules.PROXIMA_SEMANA,
                     rules.FUTURA, rules.SEM_SEMANA):
        assert situacao in _CORES, f"situação '{situacao}' sem cor definida"


def test_tabela_semanal_fecha_com_uma_linha_de_total():
    """O total é o que amarra a tela ao KPI 'Disponível para Programar'."""
    from pcp import rules
    from ui.views import semanal as v

    mp = pd.DataFrame(
        {
            "mes": pd.array([9, 9], dtype="Int64"),
            "parte_peca": ["CORPO", "CORPO"],
            "referencia": ["R0", "R1"],
            "material": ["M0", "M1"],
            "saldo_a_programar": [1_500.0, 500.0],
            "prototipo": ["SIM", "SIM"],
            "programar": ["SIM", "SIM"],
            "status_avi": ["SIM", "NAO"],
            "situacao_mp": ["EM CASA", "A RECEBER"],
            "data_recomendacao": [pd.Timestamp("2026-07-24"), pd.Timestamp("2026-08-05")],
        }
    )
    ps = rules.programacao_semanal(mp, rules.Filtros(mes=9), pd.Timestamp("2026-07-31"))

    html = v._tabela_semanas(ps)
    assert 'class="t"' in html, "sem linha de total a tabela não fecha com o KPI"
    assert "20/07 a 26/07" in html and "03/08 a 09/08" in html
    assert "1.500" in html                       # o disponível da janela vencida
    assert "Vencida" in html and "Próxima semana" in html


def test_tela_semanal_nao_mostra_nat_em_item_sem_data():
    from pcp import rules
    from ui.views import semanal as v

    mp = pd.DataFrame(
        {
            "mes": pd.array([9], dtype="Int64"),
            "parte_peca": ["CORPO"],
            "referencia": ["R0"],
            "material": ["M0"],
            "saldo_a_programar": [100.0],
            "prototipo": ["SIM"],
            "programar": ["SIM"],
            "status_avi": ["SIM"],
            "situacao_mp": ["EM CASA"],
            "data_recomendacao": [pd.NaT],
        }
    )
    ps = rules.programacao_semanal(mp, rules.Filtros(mes=9), pd.Timestamp("2026-07-31"))

    html = v._tabela_itens(ps)
    assert "NaT" not in html
    assert rules.SEM_SEMANA in html


def test_aderencia_volta_acentuada_para_a_tela():
    """A regra normaliza sem acento para comparar; a tela não pode exibir assim."""
    from ui.views.fullkit import _ADERENCIA

    assert _ADERENCIA["NAO ADERENTE"] == "Não aderente"


def test_serie_com_um_ponto_so_nao_quebra_o_desenho():
    """Um snapshot é o caso normal no primeiro dia de uso."""
    svg = c.serie_linha([500.0], "#2E7D32")
    assert svg.startswith("<svg") and "<circle" in svg


def test_serie_constante_nao_divide_por_zero():
    svg = c.serie_linha([100.0, 100.0, 100.0], "#2E7D32")
    assert "NaN" not in svg and "inf" not in svg.lower()


def test_serie_vazia_devolve_aviso_e_nao_svg():
    assert "<svg" not in c.serie_linha([], "#2E7D32")


def _evolucao(**ajustes):
    """Série de dois snapshots pronta para os construtores da tela do M7.

    Existe porque a planilha de referência tem um snapshot só: sem isto, os
    blocos de curva e projeção nunca seriam renderizados em teste.
    """
    from pcp.loader import INDICADORES_SERIE, Evolucao

    base = {i: [100.0, 80.0] for i in INDICADORES_SERIE}
    base["programado"] = [400.0, 500.0]
    base["a_programar"] = [300.0, 200.0]
    serie = pd.DataFrame(
        {
            "snapshot": [pd.Timestamp("2026-09-01"), pd.Timestamp("2026-09-11")],
            "arquivo": ["a.xlsx", "b.xlsx"],
            **base,
            "pct_programado": [0.57, 0.71],
        }
    )
    padrao = dict(
        serie=serie,
        velocidade=10.0,
        dias_uteis_restantes=20.0,
        data_projetada=pd.Timestamp("2026-10-01"),
        fim_competencia=pd.Timestamp("2026-09-30"),
    )
    return Evolucao(**{**padrao, **ajustes})


def test_tela_de_evolucao_desenha_uma_curva_por_indicador():
    from ui.views.evolucao import _CURVAS, _curvas

    html = _curvas(_evolucao())
    assert html.count("<svg") == len(_CURVAS)
    for _, rotulo, _cor in _CURVAS:
        assert rotulo in html


def test_projecao_atrasada_e_apresentada_como_atraso():
    from ui.views.evolucao import _leitura, _projecao

    atrasada = _evolucao()
    assert "dias de atraso" in _projecao(atrasada)
    assert "depois</b> do fim do mês" in _leitura(atrasada)


def test_projecao_dentro_do_mes_e_apresentada_como_folga():
    from ui.views.evolucao import _leitura, _projecao

    no_prazo = _evolucao(data_projetada=pd.Timestamp("2026-09-20"), dias_uteis_restantes=9.0)
    assert "dias de folga" in _projecao(no_prazo)
    assert "folga" in _leitura(no_prazo)


def test_sem_ritmo_a_tela_diz_que_nao_da_para_projetar():
    from ui.views.evolucao import _projecao

    parada = _evolucao(velocidade=0.0, dias_uteis_restantes=None, data_projetada=None)
    assert "inventar data" in _projecao(parada)


def test_tabela_da_evolucao_fecha_com_a_linha_de_variacao():
    from ui.views.evolucao import _tabela

    html = _tabela(_evolucao())
    assert "VARIAÇÃO" in html
    assert "+100" in html and "−100" in html      # programado sobe, saldo cai


def test_nome_de_arquivo_exportado_carrega_unidade_periodo_e_snapshot():
    from types import SimpleNamespace

    from ui.report import nome_arquivo

    carga = SimpleNamespace(unidade="Oficinas Jeans", rotulo_snapshot="31/07/2026")
    assert (
        nome_arquivo(carga, "Setembro/2026", "xlsx")
        == "follow-up_oficinas-jeans_setembro-2026_31-07-2026.xlsx"
    )


def test_relatorio_cobre_todos_os_paineis_da_navegacao():
    """Bloco novo na navegação sem entrada aqui sairia de fora da impressão."""
    from ui.report import BLOCOS

    assert set(BLOCOS) == {
        "carteira", "detratores", "fluxo", "fullkit", "prazos", "semanal",
    }


# --------------------------------------------------------------------------
# Fronteira de escape — a planilha não escreve HTML
# --------------------------------------------------------------------------
#
# Toda a UI é montada com `unsafe_allow_html=True`, e `nota()`/`painel()`
# recebem HTML por construção. Logo, o que vem de fora (célula da planilha,
# nome do arquivo enviado, texto de exceção) só é seguro se passar por
# `escapar()` no caminho — é isso que estes testes prendem.


def test_aviso_de_dominio_nao_executa_html_vindo_da_planilha():
    """Célula → tipar → diagnóstico → tela, com o valor cru no meio do caminho."""
    from pcp import schema, transform
    from ui.views.upload import _bloco_aviso

    diag = transform.Diagnostico()
    transform.tipar(
        schema.BASE_MP,
        pd.DataFrame({"prototipo": ["SIM", "<img src=x onerror=alert(1)>"]}),
        diag,
    )
    html = _bloco_aviso(diag.avisos[0])

    # Maiúscula porque `normalizar_flag` passou por ali — e não protege nada.
    assert "&lt;IMG SRC=X ONERROR=ALERT(1)&gt;" in html
    assert "<IMG" not in html


def test_mensagem_de_erro_nao_executa_html_vindo_do_arquivo():
    """`AbaAusenteError` repete os nomes de aba que estavam no .xlsx."""
    from pcp.errors import AbaAusenteError
    from ui.views.upload import _bloco_erro

    erro = AbaAusenteError("BASE CPG", ["<script>alert(1)</script>"])
    html = _bloco_erro("Não consegui ler esta planilha", str(erro))

    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<br>" in html  # a quebra de linha da mensagem continua funcionando


def test_relatorio_baixado_nao_carrega_script_da_planilha():
    """O .html sai da máquina por e-mail e abre em `file://`, fora do Streamlit.

    `unidade` é lida da coluna 'Fábrica' e `arquivo` é o nome do upload: quem
    monta a planilha escolhe os dois.
    """
    from types import SimpleNamespace

    from ui.report import pagina

    carga = SimpleNamespace(
        unidade="Jeans</title><script>alert(1)</script>",
        rotulo_snapshot="31/07/2026",
        arquivo="<img src=x onerror=alert(2)>.xlsx",
    )
    html = pagina(carga, None, "Setembro/2026", escolhidos=[])

    # O que desarma o payload é o `<` virar entidade: sem abrir tag, o resto é
    # texto. `html.escape` não mexe em '=', então procurar 'onerror=' aqui
    # acusaria a versão já corrigida.
    assert "<script>alert(1)</script>" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=alert(2)&gt;.xlsx" in html


def test_relatorio_sem_blocos_de_kpi_nao_calcula_kpi():
    """`filtros=None` só sobrevive se nenhuma regra for chamada à toa."""
    from types import SimpleNamespace

    from ui.report import _conteudo

    carga = SimpleNamespace(unidade="Jeans", rotulo_snapshot="31/07/2026", arquivo="x.xlsx")
    assert _conteudo(carga, None, []) == ""
