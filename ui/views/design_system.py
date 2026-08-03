"""Catálogo vivo do design system do PCP Follow Up.

A página usa os mesmos construtores que documenta. Assim, mudanças nos tokens
e componentes aparecem aqui automaticamente e a documentação não vira uma
segunda implementação do produto.
"""

from __future__ import annotations

import streamlit as st

from .. import components as c
from ..theme import AZUL, CINZA_TRILHA, LARANJA, VERDE, VERDE_CLARO, VERDE_ESCURO, VERMELHO


_CORES = (
    ("Verde profundo", VERDE_ESCURO, "Estrutura", "Cabeçalhos, navegação e totais"),
    ("Verde ação", VERDE, "Sucesso", "Metas, progresso e ações positivas"),
    ("Verde vivo", VERDE_CLARO, "Confirmação", "Feedback de conclusão"),
    ("Laranja", LARANJA, "Atenção", "Risco que ainda permite ação"),
    ("Vermelho", VERMELHO, "Crítico", "Bloqueio, atraso e falha"),
    ("Azul", AZUL, "Série", "Comparação e categorias auxiliares"),
    ("Trilha", CINZA_TRILHA, "Base", "Progresso restante e divisores"),
    ("Fundo", "#F4F6F4", "Canvas", "Plano de fundo da aplicação"),
)

_TELAS = (
    ("01", "Carregar planilha", "A base está válida?", "Upload, validação, histórico e variação", "Entrada"),
    ("02", "Carteira Geral", "Quanto falta programar?", "KPIs, performance, restrições e TOC", "Diagnóstico"),
    ("03", "Detratores", "O que mais bloqueia?", "Ranking por impacto e oportunidade", "Prioridade"),
    ("04", "Fluxo Produtivo", "Onde o volume está?", "Funil, etapas e leitura operacional", "Fluxo"),
    ("05", "Full Kit & MP", "O material está aderente?", "Componentes, aderência e simulação", "Decisão"),
    ("06", "Prazos & Deadline", "O que está em risco?", "Faixas, semáforo e pedidos", "Risco"),
    ("07", "Programação Semanal", "O que entra na agenda?", "Janelas, disponibilidade e itens", "Execução"),
    ("08", "Evolução Histórica", "Estamos melhorando?", "Curvas, velocidade e projeção", "Tendência"),
    ("09", "Exportar", "Como compartilhar?", "Excel e relatório imprimível", "Saída"),
)

# Mapa técnico mantido junto do catálogo visual. A intenção é responder duas
# perguntas de manutenção sem exigir que a pessoa reconstrua a arquitetura
# lendo o repositório inteiro: "quem é responsável por isto?" e "onde mudo?".
_CAMADAS_ARQUITETURA = (
    (
        "01",
        "Entrada & navegação",
        "app.py",
        "Inicializa o Streamlit, registra telas, monta a sidebar, escolhe a carga ativa e cria o recorte global de filtros.",
        "Depende de ui e pcp.rules; nenhuma camada interna deve importar app.py.",
        "Interação + carga ativa",
        "Tela escolhida + recorte global",
    ),
    (
        "02",
        "Apresentação",
        "ui/views/*.py · ui/components.py · ui/theme.py · ui/format.py",
        "Compõe telas, componentes, tokens visuais e formatação pt-BR. Exibe decisões; não redefine cálculos de negócio.",
        "Views recebem Carga + Filtros e consultam regras puras. Dados externos passam por components.escapar().",
        "Carga + Filtros + resultado de rules",
        "Decisão operacional legível",
    ),
    (
        "03",
        "Estado da interface",
        "ui/state.py",
        "Guarda cargas na sessão, define a carga ativa, recupera histórico local e traduz seleções da sidebar em Filtros.",
        "É a ponte Streamlit → aplicação. Chama loader; não lê XLSX nem calcula KPI diretamente.",
        "Upload + seleções da sidebar",
        "Carga ativa + Filtros",
    ),
    (
        "04",
        "Aplicação",
        "pcp/loader.py",
        "Orquestra ingestão, tipagem, cache e montagem da Carga; também compara snapshots e monta a evolução histórica.",
        "É o único ponto que coordena ingest, transform, schema, rules e cache no mesmo fluxo.",
        "Caminho do arquivo ou cache",
        "Carga canônica + série histórica",
    ),
    (
        "05",
        "Domínio",
        "pcp/rules.py",
        "Concentra filtros, KPIs e regras de carteira, detratores, fluxo, Full Kit, prazos e programação semanal.",
        "Funções puras: recebem DataFrames + Filtros e devolvem valores/objetos de domínio, sem Streamlit ou HTML.",
        "Bases canônicas + Filtros",
        "KPIs + diagnósticos + agenda",
    ),
    (
        "06",
        "Contrato & entrada de dados",
        "pcp/schema.py · pcp/ingest.py · pcp/transform.py · pcp/errors.py",
        "Define colunas e aliases, lê o XLSX, converte tipos, valida domínios e produz erros acionáveis.",
        "Schema é a fonte do contrato; ingest preserva o bruto; transform entrega bases canônicas ao domínio.",
        "Planilha XLSX bruta",
        "DataFrames tipados ou PCPError",
    ),
    (
        "07",
        "Persistência & saídas",
        "pcp/cache.py · pcp/export.py · ui/report.py",
        "Acelera cargas com Parquet e transforma o mesmo recorte do app em Excel ou relatório HTML imprimível.",
        "Cache não pode alterar corretude. Exportações reutilizam rules e nunca criam uma segunda regra de negócio.",
        "Carga + Filtros + resultados",
        "Parquet + Excel + relatório HTML",
    ),
    (
        "08",
        "Qualidade transversal",
        "tests/test_unidade.py · tests/test_ui.py · tests/test_planilha_real.py",
        "Protege matemática, limites, falhas, segurança do HTML, integração entre camadas e compatibilidade com a planilha real.",
        "Toda mudança de contrato ou regra nasce com teste de regressão no nível mais baixo capaz de comprová-la.",
        "Mudança + comportamento esperado",
        "Evidência automatizada de qualidade",
    ),
)

_MAPA_MUDANCAS = (
    ("Regra de negócio ou KPI", "pcp/rules.py", "Altere a função de domínio e seu dataclass; cubra cenário normal, limite e saldo zero em tests/test_unidade.py.", "Views, exportações e evolução que consomem o resultado."),
    ("Filtro global", "pcp/rules.py · ui/state.py · app.py", "Adicione o campo em Filtros e _mascara, traduza a seleção em montar_filtros e exponha a dimensão na sidebar.", "Todas as regras que usam _mascara; opções derivadas da base."),
    ("Coluna, alias ou aba da planilha", "pcp/schema.py", "Atualize o contrato da base; ajuste transform.py se o tipo/domínio for novo e ingest.py somente se a estrutura física mudar.", "Invalide _VERSAO_CACHE em pcp/cache.py quando o dado canônico armazenado mudar."),
    ("Validação ou mensagem de arquivo", "pcp/transform.py · pcp/errors.py", "Valide perto da origem e devolva PCPError acionável; apresente-o em ui/views/upload.py com escape.", "Upload, cache e teste com arquivo/célula inválida."),
    ("Cálculo histórico ou comparação", "pcp/loader.py", "Mude a montagem/ordenação da série e preserve snapshot + competência como contexto explícito.", "ui/views/evolucao.py e testes com dois ou mais snapshots."),
    ("Nova tela operacional", "ui/views/<tela>.py · app.py", "Crie render(Carga, Filtros, período), registre em PAGINAS/_VIEWS e mantenha a matemática em rules.py.", "ui/report.py, pcp/export.py e _TELAS deste catálogo quando a jornada também for exportável/documentada."),
    ("Layout, cor ou responsividade", "ui/theme.py", "Altere tokens/CSS global; evite estilo isolado na view e confira desktop, largura intermediária e móvel.", "Design System e todos os componentes que usam o token."),
    ("Componente reutilizável", "ui/components.py", "Implemente o construtor, escape argumentos vindos da planilha e documente uma instância real nesta página.", "ui/theme.py para CSS e tests/test_ui.py para limites/segurança."),
    ("Formatação de número, data ou período", "ui/format.py", "Centralize a convenção pt-BR e mantenha valores ausentes como travessão, nunca como NaN/NaT.", "Todas as views, tabelas e exportações que exibem o campo."),
    ("Sessão, carga ativa ou histórico local", "ui/state.py · pcp/loader.py", "Estado de interação fica em state; ciclo de vida e série de Carga ficam em loader.", "Upload, filtros laterais, Evolução Histórica e cache."),
    ("Excel ou relatório para compartilhar", "pcp/export.py · ui/report.py · ui/views/exportar.py", "Monte a saída a partir de Carga + Filtros e reutilize rules; a view apenas oferece as ações de download.", "Nome de arquivo, escape, impressão e fechamento dos totais."),
    ("Desempenho da carga", "pcp/ingest.py · pcp/cache.py", "Meça antes; otimize leitura/cache sem mudar o contrato canônico nem transformar falha em resultado vazio.", "hash, versão do cache, histórico local e teste com a planilha real."),
)


def _titulo(secao: str, titulo: str, descricao: str) -> str:
    return (
        '<div class="pcp ds-section-head">'
        f'<div class="ds-eyebrow">{c.escapar(secao)}</div>'
        f'<h2>{c.escapar(titulo)}</h2><p>{c.escapar(descricao)}</p></div>'
    )


def _cores() -> str:
    itens = "".join(
        '<article class="ds-color">'
        f'<div class="ds-color__swatch" style="background:{hexadecimal}"></div>'
        '<div class="ds-color__body">'
        f'<div class="ds-color__name">{c.escapar(nome)}</div>'
        f'<code>{hexadecimal}</code><span>{c.escapar(papel)}</span>'
        f'<p>{c.escapar(uso)}</p></div></article>'
        for nome, hexadecimal, papel, uso in _CORES
    )
    return f'<div class="pcp ds-color-grid">{itens}</div>'


def _iconografia() -> str:
    nomes = ("carteira", "prancheta", "pct", "agenda", "doc", "camisa", "pessoa", "peca", "caixa", "alerta", "foguete", "relogio", "alvo")
    itens = "".join(
        '<div class="ds-icon">'
        f'<div class="ds-icon__glyph">{c.icone(nome, VERDE_ESCURO, 22)}</div>'
        f'<code>{nome}</code></div>'
        for nome in nomes
    )
    return f'<div class="pcp ds-icon-grid">{itens}</div>'


def _fluxo() -> str:
    etapas = (
        ("01", "Ingerir", "Planilha .xlsx"),
        ("02", "Validar", "Schema + tipos"),
        ("03", "Contextualizar", "Competência + filtros"),
        ("04", "Diagnosticar", "KPIs + restrições"),
        ("05", "Decidir", "Prioridade + agenda"),
        ("06", "Compartilhar", "Excel + relatório"),
    )
    itens = "".join(
        '<div class="ds-flow__step">'
        f'<span>{numero}</span><strong>{c.escapar(titulo)}</strong>'
        f'<small>{c.escapar(detalhe)}</small></div>'
        for numero, titulo, detalhe in etapas
    )
    return f'<div class="pcp ds-flow">{itens}</div>'


def _matriz_telas() -> str:
    linhas = "".join(
        '<tr>'
        f'<td><span class="ds-index">{numero}</span></td>'
        f'<td><strong>{c.escapar(tela)}</strong></td>'
        f'<td>{c.escapar(pergunta)}</td><td>{c.escapar(saida)}</td>'
        f'<td><span class="ds-tag">{c.escapar(momento)}</span></td></tr>'
        for numero, tela, pergunta, saida, momento in _TELAS
    )
    return (
        '<div class="pcp ds-table-wrap"><table class="ds-table">'
        '<thead><tr><th>#</th><th>Tela</th><th>Pergunta principal</th>'
        f'<th>Entrega</th><th>Momento</th></tr></thead><tbody>{linhas}</tbody></table></div>'
    )


def _visao_geral() -> None:
    st.markdown(
        _titulo(
            "Princípios",
            "Uma interface para decidir, não apenas observar",
            "O sistema reduz a distância entre o número da planilha e a ação do PCP. Cada tela responde uma pergunta operacional e fecha com próximo passo.",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="pcp ds-principles">'
        '<article><span>01</span><h3>Verdade visível</h3><p>Competência, unidade e data da base permanecem à vista. Nenhum número perde o contexto.</p></article>'
        '<article><span>02</span><h3>Densidade com hierarquia</h3><p>Muitos dados cabem na tela, mas títulos, pesos e espaços definem uma ordem inequívoca de leitura.</p></article>'
        '<article><span>03</span><h3>Cor tem significado</h3><p>Verde confirma; laranja pede atenção; vermelho exige ação. Cor nunca entra apenas como decoração.</p></article>'
        '<article><span>04</span><h3>Exato antes do efeito</h3><p>Gráficos mostram proporção e sempre preservam o valor numérico que sustenta a decisão.</p></article>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(_titulo("Arquitetura", "Jornada operacional ponta a ponta", "A sequência acompanha o trabalho real: receber a base, confiar nela, encontrar o bloqueio, programar e comunicar."), unsafe_allow_html=True)
    st.markdown(_fluxo(), unsafe_allow_html=True)

    st.markdown(_titulo("Anatomia", "Estrutura constante de uma tela", "Repetição intencional reduz aprendizagem e mantém o foco na decisão, mesmo quando o indicador muda."), unsafe_allow_html=True)
    st.markdown(
        '<div class="pcp ds-anatomy">'
        '<div><b>01</b><strong>Contexto</strong><span>Título, unidade, competência e snapshot</span></div>'
        '<div><b>02</b><strong>Síntese</strong><span>KPIs essenciais em leitura horizontal</span></div>'
        '<div><b>03</b><strong>Diagnóstico</strong><span>Painéis que explicam composição e causa</span></div>'
        '<div><b>04</b><strong>Orientação</strong><span>Nota semântica traduz dado em ação</span></div>'
        '<div><b>05</b><strong>Evidência</strong><span>Tabela detalhada fecha com total</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )


def _fundamentos() -> None:
    st.markdown(_titulo("Fundamentos", "Cores e papéis semânticos", "A paleta nasce do chão de fábrica: sóbria na estrutura, inequívoca nos estados e econômica nos destaques."), unsafe_allow_html=True)
    st.markdown(_cores(), unsafe_allow_html=True)
    st.markdown(c.nota("<b>Regra de contraste.</b> Use branco somente sobre o verde profundo. Nos fundos claros, mantenha texto escuro; vermelho, laranja e verde vivo funcionam como sinal, não como texto corrido.", "info", "alvo"), unsafe_allow_html=True)

    st.markdown(_titulo("Tipografia", "Sistema tipográfico compacto", "Inter é a referência; a pilha nativa mantém desempenho e disponibilidade offline. Números variáveis usam algarismos tabulares."), unsafe_allow_html=True)
    st.markdown(
        '<div class="pcp ds-type-grid">'
        '<article><small>TÍTULO DE TELA · 22 PX / 800</small><div class="ds-type-display">Follow Up · Carteira Geral</div></article>'
        '<article><small>VALOR DE KPI · 23 PX / 800</small><div class="ds-type-number num">574.934 <i>peças</i></div></article>'
        '<article><small>TÍTULO DE PAINEL · 13 PX / 700</small><div class="ds-type-panel">PRINCIPAIS RESTRIÇÕES</div></article>'
        '<article><small>TEXTO OPERACIONAL · 13 PX / 400–700</small><p>A leitura explica o que mudou, por que importa e qual é a próxima ação.</p></article>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(_titulo("Escala", "Espaço, raio, borda e elevação", "A unidade-base é 4 px. O ritmo mais usado é 8 / 12 / 16 / 24 / 32, suficiente para densidade sem aperto."), unsafe_allow_html=True)
    st.markdown(
        '<div class="pcp ds-token-grid">'
        '<article><small>ESPAÇAMENTO</small><div class="ds-space"><i style="width:8px"></i><i style="width:12px"></i><i style="width:16px"></i><i style="width:24px"></i><i style="width:32px"></i></div><p>Micro → seção</p></article>'
        '<article><small>RAIOS</small><div class="ds-radius"><i></i><i></i></div><p>8 px interno · 14 px card</p></article>'
        '<article><small>BORDA</small><div class="ds-border"></div><p>1 px · #DFE4E0</p></article>'
        '<article><small>ELEVAÇÃO</small><div class="ds-shadow"></div><p>Base discreta · hover elevado</p></article>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(_titulo("Iconografia", "Traço único, função clara", "Ícones têm 24 × 24 de base, stroke 1,9 e sempre acompanham um rótulo ou contexto legível."), unsafe_allow_html=True)
    st.markdown(_iconografia(), unsafe_allow_html=True)


def _componentes() -> None:
    st.markdown(_titulo("Componentes", "Cabeçalho e contexto", "Toda tela começa dizendo onde o usuário está e de qual recorte os números vieram."), unsafe_allow_html=True)
    st.markdown(c.cabecalho("Follow Up · Carteira Geral", "Oficinas Jeans · Setembro/2026", [("Atualizado em", "31/07/2026")]), unsafe_allow_html=True)

    st.markdown(_titulo("Componentes", "Cartões de indicador", "Use de 3 a 9 cartões. O tom comunica estado; o valor permanece o elemento dominante."), unsafe_allow_html=True)
    st.markdown(
        c.faixa_kpis([
            c.kpi("Carteira total", "574.934", "peças", "carteira"),
            c.kpi("Programado", "494.563", "peças", "prancheta", "ok"),
            c.kpi("Sem MP", "49.163", "peças", "camisa", "atencao"),
            c.kpi("Sem AVI", "45.777", "peças", "doc", "alerta"),
        ]),
        unsafe_allow_html=True,
    )

    esquerda, direita = st.columns([1, 1], gap="small")
    with esquerda:
        corpo = (
            '<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">'
            f'{c.donut(.86, VERDE, "86%", "programado", tamanho=150)}'
            '<div class="pcp-legenda">'
            f'{c.item_legenda(VERDE, "PROGRAMADO", "494.563 peças", "86% da carteira")}'
            f'{c.item_legenda(VERMELHO, "A PROGRAMAR", "80.371 peças", "14% da carteira")}'
            '</div></div>'
        )
        st.markdown(c.painel("Proporção + valor exato", corpo), unsafe_allow_html=True)
    with direita:
        linhas = (
            c.linha_barra("Sem MP", "49.163", .61, LARANJA, "61% do saldo", destaque=True)
            + c.linha_barra("Sem AVI", "45.777", .57, VERMELHO, "57% do saldo")
            + c.linha_barra("Disponível", "16.674", .21, VERDE, "ação imediata")
        )
        st.markdown(c.painel("Ranking e progresso", linhas), unsafe_allow_html=True)

    st.markdown(_titulo("Feedback", "Mensagens que orientam", "A mensagem sempre combina estado, fato e próximo passo. Evite alertas genéricos ou sem saída."), unsafe_allow_html=True)
    for texto, tipo, icone in (
        ("<b>Informação.</b> Contextualiza a operação sem interromper o fluxo.", "info", "doc"),
        ("<b>Atenção.</b> Existe risco, mas ainda há janela para agir.", "aviso", "relogio"),
        ("<b>Crítico.</b> O prazo passou ou a entrada não pode ser processada.", "erro", "alerta"),
        ("<b>Concluído.</b> A planilha foi validada e os painéis estão liberados.", "ok", "alvo"),
    ):
        st.markdown(c.nota(texto, tipo, icone), unsafe_allow_html=True)

    st.markdown(_titulo("Dados", "Tabela com hierarquia e fechamento", "Cabeçalho escuro fixa a estrutura; grupo, subgrupo e total usam pesos distintos. Números ficam alinhados e tabulares."), unsafe_allow_html=True)
    st.markdown(
        c.painel(
            "Carteira por TOC e Grupo",
            c.tabela(
                ["TOC / Grupo", "Carteira", "Programado", "%", "A programar"],
                [
                    ("g", ["MTO", "340.200", "297.100", "87%", "43.100"]),
                    ("sub", ["Jeans", "204.120", "181.440", "89%", "22.680"]),
                    ("sub", ["Sarja", "136.080", "115.660", "85%", "20.420"]),
                    ("g", ["MTA", "234.734", "197.463", "84%", "37.271"]),
                    ("t", ["TOTAL", "574.934", "494.563", "86%", "80.371"]),
                ],
            ),
        ),
        unsafe_allow_html=True,
    )


def _padroes_estados() -> None:
    st.markdown(_titulo("Interação", "Filtros e ações", "Filtros alteram o recorte inteiro e ficam na lateral; ações pertencem ao conteúdo e usam verbos explícitos."), unsafe_allow_html=True)
    a, b, c_col = st.columns([1, 1, 1], gap="small")
    with a:
        st.selectbox("Competência", ["Setembro/2026", "Outubro/2026"], key="ds_competencia")
    with b:
        st.selectbox("Grupo", ["Todos", "Jeans", "Sarja"], key="ds_grupo")
    with c_col:
        st.text_input("Busca por pedido", placeholder="Ex.: 102845", key="ds_busca")
    acao, secundaria, desabilitada = st.columns(3, gap="small")
    with acao:
        st.button("Exportar análise", type="primary", use_container_width=True, key="ds_primary")
    with secundaria:
        st.button("Limpar filtros", use_container_width=True, key="ds_secondary")
    with desabilitada:
        st.button("Sem dados disponíveis", disabled=True, use_container_width=True, key="ds_disabled")

    st.markdown(_titulo("Estados", "O sistema nunca fica em silêncio", "Carregamento, vazio, erro e sucesso explicam o que ocorreu e preservam um caminho claro para continuar."), unsafe_allow_html=True)
    st.markdown(
        '<div class="pcp ds-state-grid">'
        '<article><span class="ds-state ds-state--loading"></span><h3>Carregando</h3><p>Nomeie a tarefa: “Lendo e validando a planilha…”.</p></article>'
        '<article><span class="ds-state ds-state--empty"></span><h3>Vazio</h3><p>Explique o filtro ou entrada que precisa mudar.</p></article>'
        '<article><span class="ds-state ds-state--error"></span><h3>Erro</h3><p>Mostre causa legível e uma ação de recuperação.</p></article>'
        '<article><span class="ds-state ds-state--success"></span><h3>Sucesso</h3><p>Confirme o resultado e libere a próxima etapa.</p></article>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(_titulo("Responsividade", "Comportamento por largura", "A ordem de leitura é preservada; componentes reorganizam antes de comprimir texto ou cortar números."), unsafe_allow_html=True)
    st.markdown(
        '<div class="pcp ds-breakpoints">'
        '<article><b>≥ 1200 px</b><strong>Operação ampla</strong><p>KPIs em faixa e até três painéis lado a lado.</p></article>'
        '<article><b>768–1199 px</b><strong>Análise compacta</strong><p>Grids reduzem colunas; tabelas mantêm rolagem horizontal.</p></article>'
        '<article><b>&lt; 768 px</b><strong>Consulta móvel</strong><p>Cartões empilham, rótulos quebram e números permanecem inteiros.</p></article>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(_titulo("Acessibilidade", "Regras não negociáveis", "A interface precisa continuar compreensível com teclado, zoom, leitor de tela e preferência por menos movimento."), unsafe_allow_html=True)
    st.markdown(
        '<div class="pcp ds-checklist">'
        '<div><b>✓</b><span>Alvo interativo mínimo de 40 px</span></div>'
        '<div><b>✓</b><span>Cor acompanhada de rótulo, valor ou ícone</span></div>'
        '<div><b>✓</b><span>Foco nativo preservado nos controles</span></div>'
        '<div><b>✓</b><span>Números nunca quebram entre linhas</span></div>'
        '<div><b>✓</b><span>SVGs informativos recebem nome acessível</span></div>'
        '<div><b>✓</b><span>Animações respeitam reduced motion</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )


def _fluxos_e2e() -> None:
    st.markdown(_titulo("Cobertura E2E", "Mapa completo do produto", "Cada rota existe para responder uma pergunta. A combinação forma um ciclo diário que começa na base e termina na comunicação."), unsafe_allow_html=True)
    st.markdown(_matriz_telas(), unsafe_allow_html=True)

    st.markdown(_titulo("Leitura", "Como escolher o padrão certo", "Comece pela intenção do usuário; o componente é consequência da pergunta, não o ponto de partida."), unsafe_allow_html=True)
    st.markdown(
        '<div class="pcp ds-decision-grid">'
        '<article><span>QUANTO?</span><h3>KPI</h3><p>Um valor principal, unidade e contexto curto.</p></article>'
        '<article><span>QUAL PROPORÇÃO?</span><h3>Donut</h3><p>Uma parte contra o todo, sempre com número exato.</p></article>'
        '<article><span>QUAL ORDEM?</span><h3>Barra / ranking</h3><p>Itens comparáveis, ordenados por impacto.</p></article>'
        '<article><span>O QUE MUDOU?</span><h3>Série / diff</h3><p>Snapshots comparáveis no tempo.</p></article>'
        '<article><span>QUAL DETALHE?</span><h3>Tabela</h3><p>Evidência operacional, hierarquia e total.</p></article>'
        '<article><span>O QUE FAZER?</span><h3>Nota</h3><p>Interpretação, gravidade e próximo passo.</p></article>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(_titulo("Conteúdo", "Vocabulário do produto", "Rótulos são curtos, concretos e consistentes com o processo produtivo. A interface fala a língua de quem programa."), unsafe_allow_html=True)
    st.markdown(
        '<div class="pcp ds-do-grid">'
        '<article class="ds-do"><b>FAÇA</b><strong>“Sem MP · 49.163 peças”</strong><p>Nomeia a condição e quantifica o impacto.</p></article>'
        '<article class="ds-dont"><b>EVITE</b><strong>“Há um problema”</strong><p>Não informa causa, escala nem próximo passo.</p></article>'
        '<article class="ds-do"><b>FAÇA</b><strong>“Verifique o filtro de competência.”</strong><p>Entrega uma saída recuperável.</p></article>'
        '<article class="ds-dont"><b>EVITE</b><strong>“Erro inesperado.”</strong><p>Sem contexto, o usuário não sabe como continuar.</p></article>'
        '</div>',
        unsafe_allow_html=True,
    )


def _diagrama_sistema() -> str:
    """Fluxo de dados real, da planilha até a decisão e o compartilhamento."""
    etapas = (
        ("01", "XLSX", "Fonte externa", "schema · ingest · transform"),
        ("02", "Carga", "Modelo canônico", "loader · cache"),
        ("03", "Regras", "Decisão calculada", "rules"),
        ("04", "Interface", "Decisão apresentada", "app · state · views"),
        ("05", "Saídas", "Decisão compartilhada", "export · report"),
    )
    blocos = "".join(
        '<div class="ds-arch-flow__node">'
        f'<span>{numero}</span><strong>{c.escapar(nome)}</strong>'
        f'<small>{c.escapar(papel)}</small><code>{c.escapar(arquivos)}</code></div>'
        for numero, nome, papel, arquivos in etapas
    )
    return (
        '<div class="pcp ds-arch-map">'
        '<div class="ds-arch-map__rule"><b>Regra de dependência</b>'
        '<span>A camada de cima pode chamar a de baixo. O domínio nunca conhece Streamlit, HTML ou arquivos.</span></div>'
        f'<div class="ds-arch-flow">{blocos}</div>'
        '<div class="ds-arch-map__rails">'
        '<div><b>Estado</b><code>ui/state.py</code><span>mantém o contexto entre interações</span></div>'
        '<div><b>Qualidade</b><code>tests/</code><span>protege todas as fronteiras</span></div>'
        '</div></div>'
    )


def _camadas_tecnicas() -> str:
    """Cartões com um pequeno diagrama de contexto para cada camada."""
    itens = "".join(
        '<article class="ds-arch-layer">'
        '<header>'
        f'<span>{numero}</span><div><h3>{c.escapar(nome)}</h3>'
        f'<code>{c.escapar(arquivos)}</code></div></header>'
        '<div class="ds-mini-flow">'
        f'<div><small>RECEBE</small><b>{c.escapar(entrada)}</b></div><i>→</i>'
        f'<div class="ds-mini-flow__core"><small>RESPONSABILIDADE</small><b>{c.escapar(nome)}</b></div><i>→</i>'
        f'<div><small>ENTREGA</small><b>{c.escapar(saida)}</b></div></div>'
        f'<p>{c.escapar(responsabilidade)}</p>'
        f'<footer><b>Fronteira</b><span>{c.escapar(fronteira)}</span></footer>'
        '</article>'
        for numero, nome, arquivos, responsabilidade, fronteira, entrada, saida
        in _CAMADAS_ARQUITETURA
    )
    return f'<div class="pcp ds-arch-layers">{itens}</div>'


def _matriz_mudancas() -> str:
    linhas = "".join(
        '<tr>'
        f'<td><strong>{c.escapar(objetivo)}</strong></td>'
        f'<td><code>{c.escapar(onde)}</code></td>'
        f'<td>{c.escapar(como)}</td>'
        f'<td>{c.escapar(impacto)}</td></tr>'
        for objetivo, onde, como, impacto in _MAPA_MUDANCAS
    )
    return (
        '<div class="pcp ds-table-wrap ds-change-table"><table class="ds-table">'
        '<thead><tr><th>Quero mudar</th><th>Comece aqui</th>'
        '<th>Como implementar</th><th>Confira também</th></tr></thead>'
        f'<tbody>{linhas}</tbody></table></div>'
    )


def _diagrama_decisao() -> str:
    return (
        '<div class="pcp ds-change-route">'
        '<div class="ds-change-route__question"><small>COMECE PELA PERGUNTA</small>'
        '<strong>O comportamento muda o número ou só a forma de apresentá-lo?</strong></div>'
        '<div class="ds-change-route__branches">'
        '<article><span>NÚMERO / DECISÃO</span><b>Domínio</b><code>pcp/rules.py</code>'
        '<p>Regra pura → teste unitário → consumidores</p></article>'
        '<article><span>DADO DE ENTRADA</span><b>Contrato</b><code>pcp/schema.py</code>'
        '<p>Schema → tipagem → cache → regra</p></article>'
        '<article><span>APARÊNCIA / LEITURA</span><b>Interface</b><code>ui/theme.py · ui/components.py</code>'
        '<p>Token/componente → view → catálogo</p></article>'
        '<article><span>ARQUIVO GERADO</span><b>Saída</b><code>pcp/export.py · ui/report.py</code>'
        '<p>Mesmo recorte → mesma regra → novo formato</p></article>'
        '</div></div>'
    )


def _roteiro_mudanca() -> str:
    passos = (
        ("1", "Localize a fonte", "Identifique planilha, filtro, regra ou interação que inicia o comportamento.", "Entrada conhecida"),
        ("2", "Fixe o contrato", "Escreva o teste que descreve o resultado esperado e o caso limite.", "Falha reproduzida"),
        ("3", "Mude no dono", "Implemente na camada responsável; evite compensar o erro em uma view posterior.", "Regra única"),
        ("4", "Propague o resultado", "Atualize consumidores, textos, exportações e cache somente quando forem afetados.", "Impacto controlado"),
        ("5", "Valide as fronteiras", "Rode testes unitários, UI e planilha real; confira vazio, erro e dados extremos.", "Evidência verde"),
        ("6", "Documente aqui", "Atualize o mapa quando nascer módulo, camada, tela ou padrão reutilizável.", "Arquitetura atual"),
    )
    itens = "".join(
        '<div class="ds-impl-step">'
        f'<span>{numero}</span><div><h3>{c.escapar(titulo)}</h3>'
        f'<p>{c.escapar(detalhe)}</p><small>{c.escapar(saida)}</small></div></div>'
        for numero, titulo, detalhe, saida in passos
    )
    return f'<div class="pcp ds-impl-flow">{itens}</div>'


def _arquitetura_desenvolvimento() -> None:
    st.markdown(
        _titulo(
            "Arquitetura de desenvolvimento",
            "Do arquivo à decisão, com um dono para cada mudança",
            "Este mapa descreve o código que existe hoje. Use-o para localizar a camada responsável antes de implementar uma funcionalidade ou correção.",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(_diagrama_sistema(), unsafe_allow_html=True)

    st.markdown(
        _titulo(
            "Camadas",
            "Responsabilidade, entrada e saída de cada seção",
            "Cada diagrama abaixo mostra o contrato da camada. A fronteira indica o que deve permanecer fora dela.",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(_camadas_tecnicas(), unsafe_allow_html=True)

    st.markdown(
        _titulo(
            "Mapa de manutenção",
            "Quero mudar uma funcionalidade: onde começo?",
            "Escolha o tipo de mudança. A segunda coluna aponta o dono; as demais evitam que a alteração fique incompleta ou duplicada.",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(_diagrama_decisao(), unsafe_allow_html=True)
    st.markdown(_matriz_mudancas(), unsafe_allow_html=True)

    st.markdown(
        _titulo(
            "Implementação",
            "Fluxo seguro para evoluir o app",
            "A sequência mantém contrato, regra, apresentação e documentação sincronizados, sem exigir mudanças em camadas que não foram afetadas.",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(_roteiro_mudanca(), unsafe_allow_html=True)


def _governanca() -> None:
    _arquitetura_desenvolvimento()

    st.markdown(_titulo("Processo", "Checklist antes de publicar uma mudança", "O sistema evolui quando a mudança é reutilizável, acessível e comprovada no contexto real de uso."), unsafe_allow_html=True)
    st.markdown(
        '<div class="pcp ds-release">'
        '<div><span>1</span><p><b>Defina o papel.</b> Qual problema recorrente o padrão resolve?</p></div>'
        '<div><span>2</span><p><b>Reutilize tokens.</b> Não crie cor, raio ou espaço isolado na view.</p></div>'
        '<div><span>3</span><p><b>Cubra estados.</b> Loading, vazio, erro, sucesso e conteúdo extremo.</p></div>'
        '<div><span>4</span><p><b>Teste segurança.</b> Dados da planilha sempre passam por escape.</p></div>'
        '<div><span>5</span><p><b>Valide responsividade.</b> Números, tabelas e controles não podem cortar.</p></div>'
        '<div><span>6</span><p><b>Atualize este catálogo.</b> Um padrão novo só existe quando está documentado aqui.</p></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        c.nota(
            '<b>Critério de aceite.</b> Uma alteração está pronta quando funciona com dados reais, explica seus estados, preserva acessibilidade e aparece nesta página usando o mesmo componente do produto.',
            "ok",
            "alvo",
        ),
        unsafe_allow_html=True,
    )


def render() -> None:
    st.markdown(
        c.cabecalho(
            "Design System · PCP Follow Up",
            "Fonte de verdade visual, operacional e técnica",
            [("Versão", "1.1"), ("Cobertura", "Design + código"), ("Status", "Estável")],
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        c.faixa_kpis(
            [
                c.kpi("Jornadas", "9", "telas de produto", "prancheta", "ok"),
                c.kpi("Componentes", "13", "construtores vivos", "peca"),
                c.kpi("Arquitetura", "8", "camadas mapeadas", "alvo"),
                c.kpi("Manutenção", "12", "tipos de mudança", "agenda", "atencao"),
            ],
            "contexto",
        ),
        unsafe_allow_html=True,
    )

    abas = st.tabs(["Visão geral", "Fundamentos", "Componentes", "Padrões & estados", "Fluxos E2E", "Arquitetura & governança"])
    with abas[0]:
        _visao_geral()
    with abas[1]:
        _fundamentos()
    with abas[2]:
        _componentes()
    with abas[3]:
        _padroes_estados()
    with abas[4]:
        _fluxos_e2e()
    with abas[5]:
        _governanca()
