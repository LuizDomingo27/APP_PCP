"""Testes de integração contra a planilha real.

Travam os valores validados contra a ANALISE GERENCIAL. Se um destes quebrar,
a regressão é de regra de negócio — não ajuste o número esperado sem antes
entender o que mudou na base.

Referência: 'Follow Up Oficina Jeans 2026 ATUAL.xlsx', snapshot 2026-07-31,
competência 9/2026. Pulam automaticamente se o arquivo não estiver presente.
"""

from __future__ import annotations

import io
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from pcp import carregar, export, loader, rules
from pcp.cache import CacheParquet
from pcp.rules import Filtros

PLANILHA = Path(__file__).resolve().parent.parent / "Follow Up Oficina Jeans 2026 ATUAL.xlsx"
COMPETENCIA = Filtros(mes=9, ano=2026)

pytestmark = pytest.mark.skipif(
    not PLANILHA.exists(), reason=f"planilha de referência ausente: {PLANILHA.name}"
)

# Valores conferidos célula a célula contra a ANALISE GERENCIAL.
KPIS_ESPERADOS = {
    "carteira_total": 574_934,
    "programado": 494_563,
    "a_programar": 80_371,
    "sem_avi": 45_777,
    "sem_mp": 49_163,
    "sem_prototipo": 2_100,
    "mp_prot_sem_avi": 15_343,
    "disponivel_para_programar": 16_674,
}

# Bloco de fluxo produtivo corrigido. A planilha mostra ZERO em todos estes
# campos por ler colunas erradas — ver CORRECAO_FLUXO_PRODUTIVO.md.
FLUXO_ESPERADO = {
    "etapa_corte": 32_805,
    "etapa_customizacao": 17_953,
    "etapa_costura": 20_039,
    "etapa_oficina": 215_002,
    "etapa_logistica": 50_552,
    "etapa_lavanderia": 23_526,
    "etapa_acabamento": 14_025,
    "etapa_embalagem": 685,
}


@pytest.fixture(scope="module")
def carga(tmp_path_factory):
    cache = CacheParquet(tmp_path_factory.mktemp("cache"))
    return carregar(PLANILHA, cache=cache)


@pytest.fixture(scope="module")
def kpis(carga):
    return rules.kpis(carga.cpg, carga.mp, COMPETENCIA)


# --------------------------------------------------------------------------
# Ingestão
# --------------------------------------------------------------------------


def test_linhas_fantasma_nao_entram_na_base(carga):
    """A BASE MP tem fórmula arrastada até a linha 1.048.362."""
    assert len(carga.mp) < 2_000, "linhas vazias vazaram para a base"
    assert len(carga.cpg) == 11_615


def test_unidade_e_snapshot_vem_do_arquivo(carga):
    assert carga.unidade == "Oficinas Jeans"
    assert carga.rotulo_snapshot == "31/07/2026"


def test_carga_nao_gerou_avisos_de_dominio(carga):
    assert carga.diagnostico.fora_de_dominio == {}, carga.diagnostico.avisos


# --------------------------------------------------------------------------
# Os 8 KPIs do painel
# --------------------------------------------------------------------------


@pytest.mark.parametrize(("indicador", "esperado"), KPIS_ESPERADOS.items())
def test_kpi_bate_com_a_analise_gerencial(kpis, indicador, esperado):
    assert kpis.as_dict()[indicador] == pytest.approx(esperado, abs=0.5)


def test_percentual_programado(kpis):
    assert kpis.pct_programado == pytest.approx(0.8602, abs=1e-4)


def test_peso_dos_detratores_sobre_o_saldo(kpis):
    """Percentuais exibidos no painel de detratores."""
    assert kpis.pct_do_saldo(kpis.sem_mp) == pytest.approx(0.6117, abs=1e-4)
    assert kpis.pct_do_saldo(kpis.sem_avi) == pytest.approx(0.5696, abs=1e-4)


# --------------------------------------------------------------------------
# Quebras por dimensão
# --------------------------------------------------------------------------


def test_quebra_por_toc_reconcilia_com_o_total(carga, kpis):
    tabela = rules.kpis_por_dimensao(carga.cpg, carga.mp, COMPETENCIA, "toc")
    assert set(tabela["TOC"]) == {"MTA", "MTO"}
    assert tabela["carteira_total"].sum() == pytest.approx(kpis.carteira_total, abs=0.5)


def test_mto_e_mta_batem_com_a_tabela_do_painel(carga):
    tabela = rules.kpis_por_dimensao(carga.cpg, carga.mp, COMPETENCIA, "toc")
    por_toc = tabela.set_index("TOC")
    assert por_toc.loc["MTO", "carteira_total"] == pytest.approx(273_700, abs=0.5)
    assert por_toc.loc["MTA", "carteira_total"] == pytest.approx(301_234, abs=0.5)
    assert por_toc.loc["MTO", "disponivel_para_programar"] == pytest.approx(16_674, abs=0.5)


def test_quebra_por_grupo_reconcilia(carga, kpis):
    tabela = rules.kpis_por_dimensao(carga.cpg, carga.mp, COMPETENCIA, "departamento")
    assert tabela["carteira_total"].sum() == pytest.approx(kpis.carteira_total, abs=0.5)


# --------------------------------------------------------------------------
# Fluxo produtivo corrigido
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fluxo(carga):
    return rules.fluxo_produtivo(carga.cpg, COMPETENCIA)


@pytest.mark.parametrize(("etapa", "esperado"), FLUXO_ESPERADO.items())
def test_etapa_do_fluxo_corrigido(fluxo, etapa, esperado):
    assert fluxo.etapas[etapa] == pytest.approx(esperado, abs=0.5)


def test_wip_total_e_gargalo(fluxo):
    assert fluxo.wip_total == pytest.approx(374_587, abs=0.5)
    nome, valor = fluxo.gargalo
    assert nome == "Oficina"
    assert valor == pytest.approx(215_002, abs=0.5)


def test_aguardando_entrada_em_processo(fluxo):
    """Indicador novo, derivado de Processo - soma(etapas)."""
    assert fluxo.aguardando_entrada == pytest.approx(150_401, abs=0.5)


def test_identidade_programado_igual_processo_mais_embalado(carga):
    """Validada linha a linha em 284/284 registros da competência."""
    m = (carga.cpg["mes"] == 9) & (carga.cpg["ano"] == 2026)
    recorte = carga.cpg.loc[m]
    diferenca = (
        recorte["programado"] - (recorte["processo"] + recorte["embalado"])
    ).abs()
    assert diferenca.max() < 0.5


def test_bloco_de_fluxo_reconcilia_com_o_kpi_de_carteira(fluxo, kpis):
    """Prova de que o mapeamento corrigido está certo."""
    assert fluxo.carteira_total == pytest.approx(kpis.carteira_total, abs=0.5)


def test_tempo_total_deixou_de_ser_zero(fluxo):
    """Na planilha, TOTAL MINUTOS retorna 0 por ler a coluna 'DCO'."""
    assert fluxo.tempo_total == pytest.approx(10_398_437, rel=1e-4)


def test_funil_respeita_a_hierarquia_de_cada_ramo(fluxo):
    """Todo estágio precisa caber dentro do pai — é o que prova o mapeamento.

    O funil ramifica: 'Em Processo' e 'Embalado' saem do mesmo 'Programado'.
    Comparar em cascata linear daria falso negativo em competência encerrada.
    """
    valores = {rotulo: valor for rotulo, valor, _ in fluxo.funil()}
    assert valores["Programado"] <= valores["Carteira Ajustada"]
    assert valores["Em Processo"] <= valores["Programado"]
    assert valores["Nas etapas (WIP)"] <= valores["Em Processo"]
    assert valores["Faturado"] <= valores["Embalado"]
    assert valores["Recebido CD"] <= valores["Faturado"]


def test_wip_mais_fila_de_entrada_fecham_o_em_processo(fluxo):
    valores = {rotulo: valor for rotulo, valor, _ in fluxo.funil()}
    assert valores["Nas etapas (WIP)"] + valores["Aguardando entrada"] == pytest.approx(
        valores["Em Processo"], abs=0.5
    )


def test_identidade_programado_fecha_na_competencia_corrente(fluxo):
    assert fluxo.conferencia_programado == pytest.approx(0, abs=0.5)


def test_residuo_de_competencia_encerrada_e_o_faturado(carga):
    """10/2026 não fecha a identidade — e o resíduo é exatamente o Faturado.

    Trava a leitura que a tela faz: ali a peça faturada já saiu do Embalado, o
    fluxo está encerrado e isso não é divergência de dado.
    """
    f = rules.fluxo_produtivo(carga.cpg, Filtros(mes=10, ano=2026))
    assert f.conferencia_programado != pytest.approx(0, abs=0.5)
    assert f.conferencia_programado == pytest.approx(f.faturado, abs=0.5)


# --------------------------------------------------------------------------
# M5 · Full Kit & Matéria-Prima
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fullkit(carga):
    return rules.full_kit(carga.mp, COMPETENCIA)


def test_bloqueio_por_mp_bate_com_o_detrator_sem_mp(fullkit, kpis):
    """O painel de Full Kit não pode contar MP diferente do painel principal."""
    assert fullkit.bloqueado == pytest.approx(kpis.sem_mp, abs=0.5)


def test_saldo_do_full_kit_fecha_entre_bloqueado_e_liberado(fullkit):
    assert fullkit.bloqueado + fullkit.liberado == pytest.approx(
        fullkit.saldo_pendente, abs=0.5
    )


def test_itens_reconciliam_com_o_bloqueio_total(fullkit):
    """Nenhuma peça pode sumir ou aparecer na quebra por componente."""
    assert fullkit.itens["saldo_bloqueado"].sum() == pytest.approx(
        fullkit.bloqueado, abs=0.5
    )


def test_pedido_de_compra_separa_bloqueio_com_e_sem_compra(fullkit):
    assert fullkit.com_pedido == pytest.approx(41_458, abs=0.5)
    assert fullkit.sem_pedido == pytest.approx(7_705, abs=0.5)
    assert fullkit.com_pedido + fullkit.sem_pedido == pytest.approx(
        fullkit.bloqueado, abs=0.5
    )


def test_aderencia_da_previsao_de_mp(fullkit):
    assert fullkit.aderente == pytest.approx(15_328, abs=0.5)
    assert fullkit.nao_aderente == pytest.approx(33_835, abs=0.5)


def test_estoque_do_componente_nao_e_multiplicado_pelas_referencias(carga, fullkit):
    """`Estoque Geral Disponível` se repete em toda linha do componente.

    Somar em vez de pegar o valor do componente inflaria o estoque na proporção
    do número de referências que o usam — e o painel diria que há material onde
    não há.
    """
    componente = fullkit.itens.iloc[0]["componente"]
    linhas = carga.mp[carga.mp["componente"] == componente]
    assert fullkit.itens.iloc[0]["estoque"] == pytest.approx(
        linhas["estoque_disponivel"].max(), abs=0.5
    )
    assert len(linhas) > 1, "escolha um componente com mais de uma linha"


def test_simulador_nao_promete_mais_do_que_a_regra_libera(carga, fullkit, kpis):
    """MP não é a única trava: o ganho nunca pode ser o saldo bloqueado inteiro."""
    todos = fullkit.itens["componente"].tolist()
    s = rules.simular_chegada(carga.mp, COMPETENCIA, todos)

    assert s.disponivel_hoje == pytest.approx(kpis.disponivel_para_programar, abs=0.5)
    assert s.ganho == pytest.approx(7_130, abs=0.5)
    assert s.ganho < fullkit.bloqueado
    assert s.travado_por_outros == pytest.approx(42_033, abs=0.5)
    assert "Não liberado para programar" in s.motivos


def test_simulador_sem_selecao_nao_muda_nada(carga, kpis):
    s = rules.simular_chegada(carga.mp, COMPETENCIA, [])
    assert s.ganho == 0.0
    assert s.disponivel_depois == pytest.approx(kpis.disponivel_para_programar, abs=0.5)


# --------------------------------------------------------------------------
# M6 · Prazos & Deadline
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def prazo(carga):
    return rules.prazos(carga.cpg, COMPETENCIA, carga.data_snapshot)


def test_prazos_cobrem_todo_o_saldo_a_programar(prazo, kpis):
    """A soma das faixas é o próprio saldo pendente do painel — sem sobra."""
    assert prazo.total == pytest.approx(kpis.a_programar, abs=0.5)


def test_saldo_com_prazo_estourado(prazo):
    assert prazo.estourado == pytest.approx(17_436, abs=0.5)
    assert prazo.dias_atraso_max == pytest.approx(7, abs=0.5)
    assert prazo.pct_estourado == pytest.approx(0.2169, abs=1e-4)


def test_faixas_de_urgencia_da_competencia(prazo):
    assert prazo.faixas["Crítico · até 7 dias"] == pytest.approx(20_483, abs=0.5)
    assert prazo.faixas["Atenção · 8 a 15 dias"] == pytest.approx(41_279, abs=0.5)
    assert prazo.faixas["Programável · 16 a 30 dias"] == pytest.approx(1_173, abs=0.5)


def test_estourado_e_no_prazo_particionam_o_pendente(prazo):
    sem_data = prazo.faixas[rules.SEM_DATA]
    assert prazo.estourado + prazo.no_prazo + sem_data == pytest.approx(
        prazo.total, abs=0.5
    )


def test_itens_de_prazo_vem_do_mais_atrasado_para_o_menos(prazo):
    dias = prazo.itens["dias"].dropna().tolist()
    assert dias == sorted(dias)
    assert dias[0] < 0, "o topo da lista precisa ser o pedido mais atrasado"


def test_prazo_ignora_pedido_ja_programado(carga, prazo):
    """Só entra quem tem saldo a programar — o resto não é acionável."""
    assert (prazo.itens["a_programar"] > 0).all()


# --------------------------------------------------------------------------
# M10 · Programação semanal
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def semanal(carga):
    return rules.programacao_semanal(carga.mp, COMPETENCIA, carga.data_snapshot)


def test_agenda_semanal_fecha_com_o_kpi_de_disponivel(semanal, kpis):
    """A soma das semanas é o próprio KPI do painel — sem terceiro número."""
    assert semanal.disponivel == pytest.approx(kpis.disponivel_para_programar, abs=0.5)


def test_disponivel_da_competencia_esta_espalhado_em_quatro_semanas(semanal):
    """O KPI parece um lote único; são quatro janelas, e a maior é a de agosto."""
    assert semanal.semanas_com_disponivel == 4
    assert semanal.pico == ("03/08 a 09/08", 11_251.0)


def test_janela_vencida_e_o_que_ficou_fora_do_programa(semanal):
    assert semanal.vencido == pytest.approx(2_001, abs=0.5)
    assert semanal.nesta_semana == pytest.approx(2_700, abs=0.5)
    assert semanal.proxima_semana == pytest.approx(11_251, abs=0.5)


def test_semana_do_snapshot_e_a_de_27_de_julho(semanal):
    """31/07/2026 é sexta: a semana da fábrica abriu na segunda, 27/07."""
    atual = semanal.semanas[semanal.semanas["situacao"] == rules.ESTA_SEMANA]
    assert atual["periodo"].tolist() == ["27/07 a 02/08"]
    assert atual["semana"].tolist() == ["S31"]


def test_saldo_da_agenda_fecha_com_o_pendente_do_full_kit(carga, semanal):
    """Mesmo corte (linhas CORPO): agenda e Full Kit não podem divergir."""
    fk = rules.full_kit(carga.mp, COMPETENCIA)
    assert semanal.saldo == pytest.approx(fk.saldo_pendente, abs=0.5)
    assert semanal.disponivel + semanal.travado == pytest.approx(semanal.saldo, abs=0.5)


def test_itens_disponiveis_somam_o_disponivel_da_agenda(semanal):
    assert semanal.itens["saldo_a_programar"].sum() == pytest.approx(
        semanal.disponivel, abs=0.5
    )
    assert len(semanal.itens) == 9


def test_itens_disponiveis_vem_do_mais_atrasado_para_o_menos(semanal):
    datas = semanal.itens["recomendado"].dropna().tolist()
    assert datas == sorted(datas)
    assert datas[0] < semanal.referencia, "o topo precisa ser a janela já vencida"


def test_aba_de_disponivel_sai_pronta_para_a_reuniao(carga):
    tabela = export.abas(carga, COMPETENCIA, "Setembro/2026")["Disponível por Semana"]
    assert tabela["Peças disponíveis"].sum() == pytest.approx(16_674, abs=0.5)
    assert tabela["Situação"].iloc[0] == rules.VENCIDA


# --------------------------------------------------------------------------
# M7 · Evolução histórica
# --------------------------------------------------------------------------


def test_serie_de_um_snapshot_nao_projeta_nada(carga):
    """Um ponto não é série: projetar data aqui seria inventar ritmo."""
    e = loader.evolucao([carga], COMPETENCIA)
    assert e.pontos == 1
    assert not e.suficiente
    assert e.velocidade is None
    assert e.data_projetada is None
    assert e.fim_competencia == pd.Timestamp("2026-09-30")


def test_serie_reproduz_os_kpis_do_painel(carga, kpis):
    serie = loader.serie_historica([carga], COMPETENCIA)
    assert len(serie) == 1
    for indicador in loader.INDICADORES_SERIE:
        assert serie[indicador].iloc[0] == pytest.approx(
            kpis.as_dict()[indicador], abs=0.5
        )


def test_mesmo_snapshot_carregado_duas_vezes_conta_uma(carga):
    """Dois pontos na mesma data achatariam a velocidade para infinito."""
    copia = replace(carga, arquivo="copia.xlsx")
    assert len(loader.serie_historica([carga, copia], COMPETENCIA)) == 1


def test_historico_local_le_o_que_o_cache_guardou(tmp_path):
    cache = CacheParquet(tmp_path / "hist")
    carregar(PLANILHA, cache=cache)

    recuperadas = loader.historico_local(cache)
    assert len(recuperadas) == 1
    assert recuperadas[0].unidade == "Oficinas Jeans"
    assert recuperadas[0].rotulo_snapshot == "31/07/2026"
    assert recuperadas[0].arquivo == PLANILHA.name


# --------------------------------------------------------------------------
# M9 · Exportação
# --------------------------------------------------------------------------


def test_excel_traz_uma_aba_por_bloco_de_tela(carga):
    openpyxl = pytest.importorskip("openpyxl")
    conteudo = export.excel(carga, COMPETENCIA, "Setembro/2026")

    livro = openpyxl.load_workbook(io.BytesIO(conteudo))
    assert livro.sheetnames == [
        "Resumo", "Carteira por TOC", "Carteira por Grupo",
        "Fluxo Produtivo", "Full Kit", "Prazos",
        "Programação Semanal", "Disponível por Semana",
    ]


def test_excel_carimba_o_snapshot_e_repete_os_kpis(carga, kpis):
    """Arquivo exportado sem data de base vira discussão de número na reunião."""
    openpyxl = pytest.importorskip("openpyxl")
    conteudo = export.excel(carga, COMPETENCIA, "Setembro/2026")

    aba = openpyxl.load_workbook(io.BytesIO(conteudo))["Resumo"]
    valores = {linha[0]: linha[1] for linha in aba.iter_rows(values_only=True)}
    assert valores["Snapshot da base"] == "31/07/2026"
    assert valores["Competência"] == "Setembro/2026"
    assert valores["Carteira Total"] == pytest.approx(kpis.carteira_total, abs=0.5)
    assert valores["Sem MP"] == pytest.approx(kpis.sem_mp, abs=0.5)


def test_excel_respeita_o_filtro_ativo(carga):
    """O recorte da tela precisa ir junto — exportar o total seria outro número."""
    openpyxl = pytest.importorskip("openpyxl")
    recorte = Filtros(mes=9, ano=2026, toc="MTO")
    conteudo = export.excel(carga, recorte, "Setembro/2026")

    aba = openpyxl.load_workbook(io.BytesIO(conteudo))["Resumo"]
    valores = {linha[0]: linha[1] for linha in aba.iter_rows(values_only=True)}
    assert valores["Filtro · toc"] == "MTO"
    assert valores["Carteira Total"] == pytest.approx(273_700, abs=0.5)


def test_aba_de_prazos_sai_ordenada_pelo_mais_atrasado(carga):
    tabela = export.abas(carga, COMPETENCIA, "Setembro/2026")["Prazos"]
    assert tabela["Dias até o prazo"].iloc[0] == -7


# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------


def test_cache_devolve_os_mesmos_numeros_e_mais_rapido(tmp_path):
    cache = CacheParquet(tmp_path / "c")
    primeira = carregar(PLANILHA, cache=cache)
    segunda = carregar(PLANILHA, cache=cache)

    assert not primeira.veio_do_cache
    assert segunda.veio_do_cache
    assert segunda.segundos < primeira.segundos
    assert (
        rules.kpis(segunda.cpg, segunda.mp, COMPETENCIA).as_dict()
        == rules.kpis(primeira.cpg, primeira.mp, COMPETENCIA).as_dict()
    )


