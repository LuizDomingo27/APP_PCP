"""Tokens visuais e CSS global.

Direção: ferramenta operacional industrial — densa, silenciosa, escaneável.
A paleta reproduz a dos painéis que o time já usa (verde-escuro, vermelho,
laranja), porque a adoção depende de reconhecerem a tela no primeiro dia.

Sem fonte externa e sem biblioteca de gráfico: donuts são SVG inline e barras
são CSS. Nada de dependência para floreio visual.
"""

from __future__ import annotations

# Tokens expostos ao Python para os componentes SVG usarem a mesma paleta do CSS.
VERDE_ESCURO = "#12301E"
VERDE = "#2E7D32"
VERDE_CLARO = "#4CAF50"
VERMELHO = "#D32027"
LARANJA = "#F26522"
AZUL = "#1A3A8F"
CINZA_TRILHA = "#E3E6E3"

CSS = f"""
<style>
:root {{
  --verde-escuro: {VERDE_ESCURO};
  --verde-escuro-2: #1B4429;
  --verde: {VERDE};
  --verde-claro: {VERDE_CLARO};
  --vermelho: {VERMELHO};
  --laranja: {LARANJA};
  --azul: {AZUL};
  --tinta: #16211A;
  --tinta-fraca: #5C6B60;
  --tinta-tenue: #8B9A90;
  --superficie: #FFFFFF;
  --fundo: #F4F6F4;
  --borda: #DFE4E0;
  --trilha: {CINZA_TRILHA};

  --r-card: 14px;
  --r-interno: 8px;
  --pad-card: 16px;
  --sombra: 0 1px 2px rgba(18,48,30,.06), 0 4px 12px rgba(18,48,30,.05);
  --sombra-alta: 0 2px 4px rgba(18,48,30,.08), 0 12px 28px rgba(18,48,30,.10);
}}

html {{ -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }}

.stApp {{ background: var(--fundo); }}

/* O Streamlit hospeda o botão de recolher/expandir a barra lateral DENTRO do
   header. Esconder o header inteiro levava o botão junto — depois de fechar a
   sidebar não havia mais como reabri-la. Aqui o header continua no fluxo,
   transparente e inerte a cliques; só o que não serve é removido. */
header[data-testid="stHeader"] {{
  background: transparent; box-shadow: none; pointer-events: none;
  height: 3.25rem;
}}
header[data-testid="stHeader"] button {{ pointer-events: auto; }}
[data-testid="stToolbarActions"], [data-testid="stAppDeployButton"],
[data-testid="stStatusWidget"], [data-testid="stDecoration"],
#MainMenu, footer {{ display: none !important; }}

/* Alvo de 40px e contraste sobre o fundo claro — o controle da sidebar é o
   único elemento de navegação persistente da tela. */
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapseButton"] {{
  visibility: visible; color: var(--verde-escuro);
  min-width: 40px; min-height: 40px; border-radius: var(--r-interno);
  display: flex; align-items: center; justify-content: center;
  transition-property: background-color, color;
  transition-duration: 150ms; transition-timing-function: ease-out;
}}
[data-testid="stExpandSidebarButton"] span,
[data-testid="stSidebarCollapseButton"] span {{ color: inherit !important; }}
[data-testid="stExpandSidebarButton"]:hover,
[data-testid="stSidebarCollapseButton"]:hover {{
  background: rgba(18,48,30,.07); color: var(--verde);
}}

/* Respiro abaixo do header: o primeiro cartão não pode encostar no topo da
   janela nem passar por baixo do controle da sidebar. */
[data-testid="stMain"] .block-container {{
  padding: 4.4rem 1.6rem 3rem !important; max-width: 1560px;
}}

.pcp, .pcp * {{
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  box-sizing: border-box;
}}
/* Todo número que muda precisa de largura estável. */
.pcp .num {{ font-variant-numeric: tabular-nums; font-feature-settings: "tnum"; }}

/* ---------------------------------------------------------------- cabeçalho */
.pcp-topo {{
  background: linear-gradient(100deg, var(--verde-escuro), var(--verde-escuro-2));
  border-radius: var(--r-card);
  padding: 18px 22px;
  display: flex; align-items: center; gap: 20px; flex-wrap: wrap;
  margin-bottom: 14px;
  box-shadow: var(--sombra-alta);
}}
/* Streamlit estiliza h1/h2/h3 dentro do markdown com especificidade maior que
   uma classe simples; por isso o seletor é reforçado e o tamanho é fixado. */
.pcp h1.pcp-topo__titulo {{
  color: #fff !important; font-size: 1.4rem !important; font-weight: 800;
  letter-spacing: -.02em; margin: 0 !important; padding: 0 !important;
  text-wrap: balance; line-height: 1.15;
}}
.pcp .pcp-topo__sub {{
  color: var(--verde-claro); font-size: .78rem; font-weight: 700;
  letter-spacing: .09em; text-transform: uppercase; margin-top: 3px;
}}
.pcp-topo__dir {{ margin-left: auto; display: flex; gap: 10px; flex-wrap: wrap; }}

/* Carimbo do snapshot: como cada um sobe a própria planilha, a data da base
   precisa estar sempre à vista. É o detalhe que evita discussão de número. */
.pcp-selo {{
  background: rgba(255,255,255,.09);
  border: 1px solid rgba(255,255,255,.16);
  border-radius: var(--r-interno);
  padding: 7px 13px; min-height: 40px;
  display: flex; flex-direction: column; justify-content: center;
}}
.pcp-selo__rot {{
  color: rgba(255,255,255,.62); font-size: .6rem; font-weight: 700;
  letter-spacing: .1em; text-transform: uppercase;
}}
.pcp-selo__val {{ color: #fff; font-size: .92rem; font-weight: 700; }}

/* ------------------------------------------------------------------- cards  */
.pcp-kpis {{
  display: grid; gap: 10px; margin-bottom: 14px;
  /* 182px comporta 7 dígitos ('1.234.567') sem quebrar a linha. */
  grid-template-columns: repeat(auto-fit, minmax(182px, 1fr));
}}
/* Faixa curta (só o contexto da competência): sem esticar cada cartão até um
   terço da tela quando são poucos. */
.pcp-kpis--contexto {{
  /* O limite é da faixa inteira, não de cada cartão: com 4 cartões, capar a
     coluna em px os empurrava para uma segunda linha em telas médias. */
  max-width: 1180px;
}}
.pcp-kpi {{
  background: var(--superficie); border: 1px solid var(--borda);
  border-radius: var(--r-card); padding: var(--pad-card);
  display: flex; align-items: center; gap: 12px; min-height: 84px;
  box-shadow: var(--sombra);
  transition-property: transform, box-shadow, border-color;
  transition-duration: 160ms; transition-timing-function: ease-out;
}}
.pcp-kpi:hover {{ transform: translateY(-1px); box-shadow: var(--sombra-alta); }}
.pcp-kpi__icone {{
  width: 38px; height: 38px; flex: 0 0 38px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
}}
.pcp-kpi__corpo {{ min-width: 0; }}
.pcp-kpi__rot {{
  font-size: .61rem; font-weight: 700; letter-spacing: .07em;
  text-transform: uppercase; color: var(--tinta-fraca);
  line-height: 1.25; text-wrap: pretty;
}}
.pcp-kpi__val {{
  font-size: 1.42rem; font-weight: 800; color: var(--tinta);
  letter-spacing: -.03em; line-height: 1.1; margin-top: 2px;
  /* Número é unidade indivisível: quebrar '645.939' em duas linhas é erro de
     leitura, não de estética. */
  white-space: nowrap;
}}
.pcp-kpi__un {{ font-size: .66rem; color: var(--tinta-tenue); font-weight: 600; }}
.pcp-kpi--alerta .pcp-kpi__val {{ color: var(--vermelho); }}
.pcp-kpi--atencao .pcp-kpi__val {{ color: var(--laranja); }}
.pcp-kpi--ok .pcp-kpi__val {{ color: var(--verde); }}

/* ------------------------------------------------------------------ painéis */
.pcp-painel {{
  background: var(--superficie); border: 1px solid var(--borda);
  border-radius: var(--r-card); box-shadow: var(--sombra);
  overflow: hidden; height: 100%;
}}
.pcp-painel__topo {{
  background: var(--verde-escuro); color: #fff;
  padding: 11px 16px; font-size: .8rem; font-weight: 700;
  letter-spacing: .07em; text-transform: uppercase;
}}
/* Radius concêntrico: o corpo respeita o padding do painel.
   `container-type` permite que o conteúdo reaja à largura da COLUNA, não à da
   janela — o painel vive dentro de um `st.columns` e a viewport não diz nada
   sobre o espaço real que ele tem. */
.pcp-painel__corpo {{ padding: var(--pad-card); container-type: inline-size; }}

.pcp-legenda {{ display: flex; flex-direction: column; gap: 12px; }}
.pcp-legenda__item {{ display: flex; align-items: flex-start; gap: 9px; }}
.pcp-legenda__ponto {{
  width: 10px; height: 10px; border-radius: 50%; margin-top: 5px; flex: 0 0 10px;
}}
.pcp-legenda__rot {{ font-size: .78rem; font-weight: 700; color: var(--tinta); }}
.pcp-legenda__val {{ font-size: .95rem; font-weight: 800; color: var(--tinta); }}
.pcp-legenda__obs {{ font-size: .7rem; color: var(--tinta-tenue); font-weight: 600; }}

/* --------------------------------------------------------------- detratores */
/* Colunas fixas somavam mais que a largura do painel e a coluna de impacto
   era decepada pelo `overflow:hidden`. Fracionárias com piso zero encolhem e
   quebram o texto em vez de cortar. */
.pcp-det {{
  display: grid;
  grid-template-columns:
    minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1.5fr) minmax(0, 1.2fr);
  gap: 14px; align-items: center;
  padding: 15px 0; border-bottom: 1px solid var(--borda);
}}
/* Coluna estreita: o nome toma a linha inteira e o resto se distribui abaixo,
   em vez de espremer quatro colunas em 340px. */
@container (max-width: 520px) {{
  .pcp-det {{ grid-template-columns: 1fr 1fr; gap: 10px 14px; }}
  .pcp-det__nome {{ grid-column: 1 / -1; }}
  /* Empilhado, o cabeçalho de colunas deixa de descrever a grade. */
  .pcp-det--cab {{ display: none; }}
}}
.pcp-det:last-child {{ border-bottom: 0; }}
.pcp-det__nome {{ display: flex; align-items: center; gap: 11px; }}
.pcp-det__tit {{ font-size: .86rem; font-weight: 800; line-height: 1.2; }}
.pcp-det__desc {{ font-size: .69rem; color: var(--tinta-fraca); text-wrap: pretty; }}
.pcp-det__qtd {{ font-size: 1.32rem; font-weight: 800; letter-spacing: -.02em; }}
.pcp-det__un {{ font-size: .63rem; color: var(--tinta-tenue); font-weight: 600; }}
.pcp-barra {{
  height: 15px; background: var(--trilha); border-radius: 999px; overflow: hidden;
}}
.pcp-barra__preench {{
  height: 100%; border-radius: 999px;
  transition-property: width; transition-duration: 420ms;
  transition-timing-function: cubic-bezier(.22,.61,.36,1);
}}
.pcp-det__impacto {{
  font-size: .63rem; font-weight: 800; letter-spacing: .05em;
  text-transform: uppercase;
}}
.pcp-det__nota {{ font-size: .67rem; color: var(--tinta-fraca); text-wrap: pretty; }}

/* ------------------------------------------------- linha com barra (M4/M5/M6) */
.pcp-lb {{
  display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 2fr) auto;
  gap: 12px; align-items: center; padding: 9px 0;
  border-bottom: 1px solid var(--borda);
}}
.pcp-lb:last-child {{ border-bottom: 0; }}
/* Coluna estreita (o painel vive dentro de st.columns): rótulo em cima, barra
   e número dividindo a linha de baixo. */
@container (max-width: 420px) {{
  .pcp-lb {{ grid-template-columns: minmax(0, 1fr) auto; }}
  .pcp-lb__rot {{ grid-column: 1 / -1; }}
}}
.pcp-lb__rot {{
  font-size: .78rem; color: var(--tinta); line-height: 1.25; text-wrap: pretty;
}}
.pcp-lb__obs {{ font-size: .66rem; color: var(--tinta-tenue); font-weight: 600; }}
.pcp-lb__val {{ font-size: .92rem; font-weight: 800; white-space: nowrap; }}
.pcp-lb--destaque {{ background: #F7F9F7; }}

.pcp-chip {{
  display: inline-block; border: 1px solid; border-radius: 999px;
  padding: 2px 9px; font-size: .63rem; font-weight: 800;
  letter-spacing: .04em; text-transform: uppercase; white-space: nowrap;
}}

.pcp-par {{ padding: 7px 0; border-bottom: 1px solid var(--borda); }}
.pcp-par:last-child {{ border-bottom: 0; }}
.pcp-par__rot {{
  font-size: .61rem; font-weight: 700; letter-spacing: .07em;
  text-transform: uppercase; color: var(--tinta-fraca);
}}
.pcp-par__val {{ font-size: 1.05rem; font-weight: 800; color: var(--tinta); }}

/* ------------------------------------------------------------------- avisos */
.pcp-nota {{
  border-radius: var(--r-interno); padding: 13px 15px;
  display: flex; gap: 11px; align-items: flex-start;
  font-size: .8rem; line-height: 1.5; text-wrap: pretty;
}}
.pcp-nota--info  {{ background: #EEF4EF; border: 1px solid #CFE0D4; color: #1F4630; }}
.pcp-nota--aviso {{ background: #FFF4EC; border: 1px solid #FBD9C2; color: #7A3A10; }}
.pcp-nota--erro  {{ background: #FDEDEC; border: 1px solid #F6C9C6; color: #8A1B20; }}
.pcp-nota--ok    {{ background: #EDF7EE; border: 1px solid #C6E4C9; color: #1B5E20; }}
.pcp-nota b {{ font-weight: 800; }}

/* -------------------------------------------------------------------- tabela */
.pcp-tab {{ width: 100%; border-collapse: collapse; font-size: .79rem; }}
.pcp-tab th {{
  background: var(--verde-escuro); color: #fff; padding: 9px 10px;
  font-size: .6rem; font-weight: 700; letter-spacing: .06em;
  text-transform: uppercase; text-align: right; white-space: nowrap;
}}
.pcp-tab th:first-child {{ text-align: left; }}
.pcp-tab td {{
  padding: 8px 10px; text-align: right; border-bottom: 1px solid var(--borda);
  font-variant-numeric: tabular-nums; white-space: nowrap;
}}
.pcp-tab td:first-child {{ text-align: left; font-weight: 600; }}
.pcp-tab tr.g td {{ font-weight: 800; background: #F7F9F7; }}
.pcp-tab tr.sub td:first-child {{ padding-left: 26px; font-weight: 500; color: var(--tinta-fraca); }}
.pcp-tab tr.t td {{
  font-weight: 800; background: var(--verde-escuro); color: #fff; border-bottom: 0;
}}
.pcp-tab tbody tr:not(.t):hover td {{ background: #F1F5F2; }}

/* ------------------------------------------------------------ design system */
.ds-section-head {{ margin: 30px 0 12px; max-width: 820px; }}
.ds-section-head h2 {{
  margin: 3px 0 6px !important; padding: 0 !important; color: var(--tinta);
  font-size: 1.35rem !important; line-height: 1.2; letter-spacing: -.025em;
}}
.ds-section-head p {{
  margin: 0; color: var(--tinta-fraca); font-size: .84rem; line-height: 1.55;
}}
.ds-eyebrow {{
  color: var(--verde); font-size: .62rem; font-weight: 800;
  letter-spacing: .12em; text-transform: uppercase;
}}
.ds-principles, .ds-decision-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(205px, 1fr)); gap: 10px;
}}
.ds-principles article, .ds-decision-grid article {{
  background: var(--superficie); border: 1px solid var(--borda);
  border-radius: var(--r-card); padding: 18px; box-shadow: var(--sombra);
}}
.ds-principles article > span, .ds-decision-grid article > span {{
  color: var(--verde); font-size: .6rem; font-weight: 800; letter-spacing: .1em;
}}
.ds-principles h3, .ds-decision-grid h3 {{
  color: var(--tinta); font-size: .92rem; margin: 10px 0 5px;
}}
.ds-principles p, .ds-decision-grid p {{
  color: var(--tinta-fraca); font-size: .73rem; line-height: 1.5; margin: 0;
}}
.ds-flow {{
  display: grid; grid-template-columns: repeat(6, minmax(128px, 1fr));
  border: 1px solid var(--borda); border-radius: var(--r-card); overflow-x: auto;
  background: var(--superficie); box-shadow: var(--sombra);
}}
.ds-flow__step {{ padding: 18px 15px; min-width: 128px; position: relative; }}
.ds-flow__step:not(:last-child) {{ border-right: 1px solid var(--borda); }}
.ds-flow__step:not(:last-child)::after {{
  content: "›"; position: absolute; right: -7px; top: 36%; z-index: 1;
  width: 14px; height: 20px; background: #fff; color: var(--verde);
  font-size: 1.1rem; text-align: center;
}}
.ds-flow__step span {{
  display: block; color: var(--verde); font-size: .58rem; font-weight: 800;
  letter-spacing: .1em; margin-bottom: 10px;
}}
.ds-flow__step strong {{ display: block; font-size: .8rem; color: var(--tinta); }}
.ds-flow__step small {{ display: block; color: var(--tinta-tenue); font-size: .64rem; margin-top: 3px; }}
.ds-anatomy {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  border-radius: var(--r-card); overflow: hidden; border: 1px solid var(--borda);
}}
.ds-anatomy > div {{ background: #fff; padding: 15px; border-right: 1px solid var(--borda); }}
.ds-anatomy b {{ color: var(--verde); font-size: .58rem; display: block; }}
.ds-anatomy strong {{ color: var(--tinta); font-size: .76rem; display: block; margin: 6px 0 3px; }}
.ds-anatomy span {{ color: var(--tinta-fraca); font-size: .68rem; line-height: 1.4; display: block; }}
.ds-color-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }}
.ds-color {{
  display: flex; background: #fff; border: 1px solid var(--borda);
  border-radius: var(--r-card); overflow: hidden; min-height: 112px;
}}
.ds-color__swatch {{ width: 64px; flex: 0 0 64px; }}
.ds-color__body {{ padding: 13px; min-width: 0; }}
.ds-color__name {{ font-size: .78rem; font-weight: 800; color: var(--tinta); }}
.ds-color code, .ds-color span {{ font-size: .61rem; color: var(--tinta-tenue); }}
.ds-color code {{ margin-right: 8px; }}
.ds-color p {{ margin: 7px 0 0; font-size: .67rem; color: var(--tinta-fraca); line-height: 1.35; }}
.ds-type-grid, .ds-token-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px;
}}
.ds-type-grid article, .ds-token-grid article {{
  background: #fff; border: 1px solid var(--borda); border-radius: var(--r-card); padding: 18px;
}}
.ds-type-grid small, .ds-token-grid small {{ color: var(--verde); font-size: .58rem; font-weight: 800; letter-spacing: .08em; }}
.ds-type-display {{ font-size: 1.4rem; font-weight: 800; line-height: 1.15; margin-top: 16px; }}
.ds-type-number {{ font-size: 1.45rem; font-weight: 800; margin-top: 16px; }}
.ds-type-number i {{ font-size: .68rem; font-style: normal; color: var(--tinta-tenue); }}
.ds-type-panel {{
  background: var(--verde-escuro); color: #fff; margin: 15px -18px -18px;
  padding: 12px 18px; font-size: .72rem; font-weight: 700; letter-spacing: .07em;
}}
.ds-type-grid p {{ font-size: .78rem; line-height: 1.55; color: var(--tinta-fraca); margin: 13px 0 0; }}
.ds-token-grid p {{ margin: 11px 0 0; color: var(--tinta-fraca); font-size: .68rem; }}
.ds-space {{ height: 42px; display: flex; align-items: end; gap: 6px; margin-top: 12px; }}
.ds-space i {{ display: block; height: 26px; background: var(--verde); border-radius: 3px; opacity: .82; }}
.ds-radius {{ display: flex; gap: 12px; margin-top: 12px; }}
.ds-radius i {{ display: block; width: 58px; height: 34px; border: 2px solid var(--verde); border-radius: 8px; }}
.ds-radius i:last-child {{ border-radius: 14px; }}
.ds-border {{ height: 36px; border: 1px solid var(--borda); margin-top: 12px; }}
.ds-shadow {{ height: 36px; background: #fff; box-shadow: var(--sombra-alta); border-radius: 8px; margin-top: 12px; }}
.ds-icon-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(112px, 1fr)); gap: 8px; }}
.ds-icon {{
  background: #fff; border: 1px solid var(--borda); border-radius: var(--r-interno);
  padding: 12px; display: flex; align-items: center; gap: 9px;
}}
.ds-icon__glyph {{
  width: 34px; height: 34px; border-radius: 50%; background: #EEF4EF;
  display: flex; align-items: center; justify-content: center; flex: 0 0 34px;
}}
.ds-icon code {{ font-size: .62rem; color: var(--tinta-fraca); }}
.ds-state-grid, .ds-breakpoints, .ds-do-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px;
}}
.ds-state-grid article, .ds-breakpoints article, .ds-do-grid article {{
  background: #fff; border: 1px solid var(--borda); border-radius: var(--r-card); padding: 17px;
}}
.ds-state {{ width: 10px; height: 10px; border-radius: 50%; display: block; }}
.ds-state--loading {{ background: var(--azul); box-shadow: 0 0 0 5px #E8ECF7; }}
.ds-state--empty {{ background: var(--tinta-tenue); box-shadow: 0 0 0 5px #EFF1EF; }}
.ds-state--error {{ background: var(--vermelho); box-shadow: 0 0 0 5px #FDEDEC; }}
.ds-state--success {{ background: var(--verde); box-shadow: 0 0 0 5px #EDF7EE; }}
.ds-state-grid h3 {{ font-size: .8rem; margin: 14px 0 4px; }}
.ds-state-grid p, .ds-breakpoints p, .ds-do-grid p {{ margin: 0; color: var(--tinta-fraca); font-size: .69rem; line-height: 1.45; }}
.ds-breakpoints b {{ color: var(--verde); font-size: .65rem; }}
.ds-breakpoints strong {{ display: block; color: var(--tinta); font-size: .8rem; margin: 8px 0 4px; }}
.ds-checklist {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 8px; }}
.ds-checklist div {{ background: #fff; border: 1px solid var(--borda); border-radius: 8px; padding: 12px; display: flex; gap: 9px; align-items: center; }}
.ds-checklist b {{ color: var(--verde); }}
.ds-checklist span {{ font-size: .72rem; color: var(--tinta); }}
.ds-table-wrap {{ background: #fff; border: 1px solid var(--borda); border-radius: var(--r-card); overflow-x: auto; box-shadow: var(--sombra); }}
.ds-table {{ width: 100%; border-collapse: collapse; min-width: 780px; }}
.ds-table th {{
  background: var(--verde-escuro); color: #fff; text-align: left; padding: 11px;
  font-size: .58rem; text-transform: uppercase; letter-spacing: .07em;
}}
.ds-table td {{ padding: 12px 11px; border-bottom: 1px solid var(--borda); color: var(--tinta-fraca); font-size: .7rem; line-height: 1.4; }}
.ds-table tbody tr:last-child td {{ border-bottom: 0; }}
.ds-table tbody tr:hover td {{ background: #F7F9F7; }}
.ds-table strong {{ color: var(--tinta); }}
.ds-index {{ color: var(--verde); font-size: .6rem; font-weight: 800; }}
.ds-tag {{
  display: inline-block; padding: 3px 8px; background: #EEF4EF; color: var(--verde-escuro);
  border-radius: 999px; font-size: .58rem; font-weight: 800; text-transform: uppercase;
}}
.ds-do-grid article {{ border-left: 3px solid; }}
.ds-do-grid article > b {{ font-size: .58rem; letter-spacing: .08em; }}
.ds-do-grid strong {{ display: block; color: var(--tinta); margin: 10px 0 5px; font-size: .78rem; }}
.ds-do {{ border-left-color: var(--verde) !important; }} .ds-do > b {{ color: var(--verde); }}
.ds-dont {{ border-left-color: var(--vermelho) !important; }} .ds-dont > b {{ color: var(--vermelho); }}

/* ----------------------------------------- arquitetura de desenvolvimento */
.ds-arch-map {{
  background: #fff; border: 1px solid var(--borda); border-radius: var(--r-card);
  box-shadow: var(--sombra); overflow: hidden;
}}
.ds-arch-map__rule {{
  display: flex; align-items: center; gap: 13px; padding: 12px 16px;
  background: var(--verde-escuro); color: #fff;
}}
.ds-arch-map__rule b {{ font-size: .68rem; white-space: nowrap; }}
.ds-arch-map__rule span {{ font-size: .67rem; opacity: .78; line-height: 1.4; }}
.ds-arch-flow {{
  display: grid; grid-template-columns: repeat(5, minmax(145px, 1fr));
  padding: 18px; overflow-x: auto; gap: 22px;
}}
.ds-arch-flow__node {{
  min-width: 145px; min-height: 118px; position: relative; padding: 15px;
  display: flex; flex-direction: column; border: 1px solid var(--borda);
  border-radius: 10px; background: #F8FAF8;
}}
.ds-arch-flow__node:not(:last-child)::after {{
  content: "→"; position: absolute; right: -18px; top: 43px; color: var(--verde);
  font-size: 1rem; font-weight: 800;
}}
.ds-arch-flow__node > span {{ color: var(--verde); font-size: .56rem; font-weight: 800; letter-spacing: .1em; }}
.ds-arch-flow__node strong {{ color: var(--tinta); font-size: .82rem; margin-top: 9px; }}
.ds-arch-flow__node small {{ color: var(--tinta-fraca); font-size: .63rem; margin: 2px 0 9px; }}
.ds-arch-flow__node code {{ color: var(--verde); font-size: .59rem; margin-top: auto; line-height: 1.35; }}
.ds-arch-map__rails {{ display: grid; grid-template-columns: 1fr 1fr; border-top: 1px solid var(--borda); }}
.ds-arch-map__rails > div {{ padding: 11px 16px; display: flex; align-items: center; gap: 10px; }}
.ds-arch-map__rails > div:first-child {{ border-right: 1px solid var(--borda); }}
.ds-arch-map__rails b {{ font-size: .64rem; color: var(--tinta); }}
.ds-arch-map__rails code {{ font-size: .58rem; color: var(--verde); }}
.ds-arch-map__rails span {{ margin-left: auto; color: var(--tinta-tenue); font-size: .6rem; }}

.ds-arch-layers {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
.ds-arch-layer {{
  background: #fff; border: 1px solid var(--borda); border-radius: var(--r-card);
  padding: 17px; box-shadow: var(--sombra); min-width: 0;
}}
.ds-arch-layer header {{ display: flex; gap: 10px; align-items: flex-start; }}
.ds-arch-layer header > span {{
  display: flex; align-items: center; justify-content: center; width: 28px; height: 28px;
  flex: 0 0 28px; border-radius: 8px; background: #EEF4EF; color: var(--verde);
  font-size: .58rem; font-weight: 800;
}}
.ds-arch-layer h3 {{ color: var(--tinta); font-size: .82rem; margin: 0 0 2px; }}
.ds-arch-layer header code {{ display: block; color: var(--verde); font-size: .57rem; line-height: 1.35; }}
.ds-arch-layer > p {{ color: var(--tinta-fraca); font-size: .68rem; line-height: 1.5; margin: 12px 0; }}
.ds-mini-flow {{
  display: grid; grid-template-columns: minmax(0, 1fr) 12px minmax(0, 1fr) 12px minmax(0, 1fr);
  gap: 5px; align-items: stretch; margin-top: 14px;
}}
.ds-mini-flow > div {{
  min-width: 0; background: #F7F9F7; border: 1px solid #E7ECE8; border-radius: 7px;
  padding: 8px;
}}
.ds-mini-flow > div.ds-mini-flow__core {{ background: #EEF4EF; border-color: #D4E4D6; }}
.ds-mini-flow small {{ display: block; color: var(--tinta-tenue); font-size: .48rem; font-weight: 800; letter-spacing: .07em; }}
.ds-mini-flow b {{ display: block; color: var(--tinta); font-size: .58rem; line-height: 1.35; margin-top: 4px; overflow-wrap: anywhere; }}
.ds-mini-flow i {{ align-self: center; color: var(--verde); font-size: .7rem; font-style: normal; text-align: center; }}
.ds-arch-layer footer {{ border-top: 1px solid var(--borda); padding-top: 10px; display: grid; grid-template-columns: 58px 1fr; gap: 8px; }}
.ds-arch-layer footer b {{ color: var(--vermelho); font-size: .56rem; text-transform: uppercase; letter-spacing: .06em; }}
.ds-arch-layer footer span {{ color: var(--tinta-fraca); font-size: .62rem; line-height: 1.4; }}

.ds-change-route {{ margin-bottom: 10px; }}
.ds-change-route__question {{
  width: min(520px, 100%); margin: 0 auto 22px; padding: 16px; position: relative;
  border-radius: 10px; background: var(--verde-escuro); color: #fff; text-align: center;
}}
.ds-change-route__question::after {{
  content: ""; position: absolute; width: 1px; height: 23px; background: #AEBBB2;
  left: 50%; bottom: -23px;
}}
.ds-change-route__question small {{ display: block; color: #9FD0A3; font-size: .52rem; font-weight: 800; letter-spacing: .1em; }}
.ds-change-route__question strong {{ display: block; font-size: .75rem; line-height: 1.4; margin-top: 5px; }}
.ds-change-route__branches {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; position: relative; padding-top: 13px; }}
.ds-change-route__branches::before {{
  content: ""; position: absolute; top: 0; left: 12.5%; right: 12.5%; height: 1px; background: #AEBBB2;
}}
.ds-change-route__branches article {{
  position: relative; background: #fff; border: 1px solid var(--borda); border-radius: 10px; padding: 14px;
}}
.ds-change-route__branches article::before {{
  content: ""; position: absolute; width: 1px; height: 13px; background: #AEBBB2; left: 50%; top: -14px;
}}
.ds-change-route__branches span {{ color: var(--verde); font-size: .5rem; font-weight: 800; letter-spacing: .08em; }}
.ds-change-route__branches b {{ display: block; color: var(--tinta); font-size: .76rem; margin: 7px 0 2px; }}
.ds-change-route__branches code {{ color: var(--verde); font-size: .56rem; line-height: 1.35; }}
.ds-change-route__branches p {{ color: var(--tinta-fraca); font-size: .61rem; line-height: 1.4; margin: 9px 0 0; }}
.ds-change-table .ds-table {{ min-width: 1040px; }}
.ds-change-table .ds-table th:nth-child(1) {{ width: 17%; }}
.ds-change-table .ds-table th:nth-child(2) {{ width: 20%; }}
.ds-change-table code {{ color: var(--verde); font-size: .61rem; line-height: 1.5; }}

.ds-impl-flow {{ display: grid; grid-template-columns: repeat(6, minmax(145px, 1fr)); gap: 20px; overflow-x: auto; padding: 2px; }}
.ds-impl-step {{
  min-width: 145px; min-height: 176px; position: relative; background: #fff;
  border: 1px solid var(--borda); border-radius: var(--r-card); padding: 15px;
}}
.ds-impl-step:not(:last-child)::after {{
  content: "→"; position: absolute; right: -17px; top: 75px; color: var(--verde); font-weight: 800;
}}
.ds-impl-step > span {{
  display: flex; width: 27px; height: 27px; align-items: center; justify-content: center;
  background: #EEF4EF; color: var(--verde); border-radius: 50%; font-size: .6rem; font-weight: 800;
}}
.ds-impl-step h3 {{ color: var(--tinta); font-size: .73rem; margin: 12px 0 5px; }}
.ds-impl-step p {{ color: var(--tinta-fraca); font-size: .61rem; line-height: 1.45; margin: 0; }}
.ds-impl-step small {{
  display: block; position: absolute; left: 15px; right: 15px; bottom: 14px;
  border-top: 1px solid var(--borda); padding-top: 8px; color: var(--verde);
  font-size: .52rem; font-weight: 800; text-transform: uppercase; letter-spacing: .06em;
}}

.ds-layers {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }}
.ds-layers article {{ background: #fff; border: 1px solid var(--borda); border-radius: var(--r-card); padding: 18px; display: flex; gap: 13px; }}
.ds-layers article > span {{ color: var(--verde); font-size: .6rem; font-weight: 800; }}
.ds-layers h3 {{ font-size: .84rem; margin: 0 0 4px; }}
.ds-layers code {{ font-size: .64rem; color: var(--verde); }}
.ds-layers p {{ font-size: .69rem; color: var(--tinta-fraca); line-height: 1.45; margin: 8px 0 0; }}
.ds-release {{ background: #fff; border: 1px solid var(--borda); border-radius: var(--r-card); overflow: hidden; }}
.ds-release > div {{ display: flex; gap: 13px; padding: 13px 16px; border-bottom: 1px solid var(--borda); }}
.ds-release > div:last-child {{ border-bottom: 0; }}
.ds-release span {{
  display: flex; width: 24px; height: 24px; flex: 0 0 24px; align-items: center;
  justify-content: center; border-radius: 50%; background: #EEF4EF; color: var(--verde);
  font-size: .62rem; font-weight: 800;
}}
.ds-release p {{ margin: 2px 0 0; font-size: .72rem; color: var(--tinta-fraca); }}
.ds-release b {{ color: var(--tinta); }}

@media (max-width: 900px) {{
  .ds-layers {{ grid-template-columns: 1fr; }}
  .ds-flow {{ grid-template-columns: repeat(6, 140px); }}
  .ds-arch-layers {{ grid-template-columns: 1fr; }}
  .ds-change-route__branches {{ grid-template-columns: repeat(2, 1fr); padding-top: 0; }}
  .ds-change-route__branches::before, .ds-change-route__branches article::before,
  .ds-change-route__question::after {{ display: none; }}
  .ds-arch-map__rails {{ grid-template-columns: 1fr; }}
  .ds-arch-map__rails > div:first-child {{ border-right: 0; border-bottom: 1px solid var(--borda); }}
}}

@media (max-width: 600px) {{
  .ds-mini-flow {{ grid-template-columns: 1fr; }}
  .ds-mini-flow i {{ transform: rotate(90deg); }}
  .ds-change-route__branches {{ grid-template-columns: 1fr; }}
  .ds-arch-map__rule {{ align-items: flex-start; flex-direction: column; gap: 3px; }}
  .ds-arch-map__rails span {{ display: none; }}
}}

/* ------------------------------------------------------------- controles ST */
.stButton > button {{
  min-height: 42px; border-radius: var(--r-interno); font-weight: 700;
  transition-property: transform, background-color, box-shadow, border-color;
  transition-duration: 150ms; transition-timing-function: ease-out;
}}
.stButton > button:active {{ transform: scale(.97); }}
section[data-testid="stSidebar"] {{ background: var(--superficie); border-right: 1px solid var(--borda); }}
/* A sidebar tem seu próprio recuo: o do conteúdo principal precisa livrar o
   header, o dela não. */
section[data-testid="stSidebar"] .block-container {{
  padding: 1.4rem 1rem 2rem !important;
}}

/* CAUSA RAIZ DA SOBREPOSIÇÃO ENTRE CARTÕES — não remover sem ler.
   O Streamlit aplica `margin-bottom:-16px` no stMarkdownContainer para cancelar
   a margem que o <p> do markdown gera. O HTML destes painéis é feito de <div>:
   não existe <p>, não há margem para cancelar, e o -16px puxava cada bloco para
   CIMA do anterior. O gap de 8,8px do stVerticalBlock não cobria isso, então a
   faixa de KPIs invadia 7,2px do cartão de cabeçalho — em todas as abas. */
div[data-testid="stMarkdownContainer"]:has(> .pcp) {{ margin-bottom: 0 !important; }}

/* Encostar o último elemento vale DENTRO do painel, onde o markdown injeta
   parágrafo. No nível dos cartões a regra anterior era ampla demais: pegava
   `.pcp-topo` e `.pcp-kpis` e anulava o respiro entre as faixas. */
.pcp-painel__corpo > *:last-child, .pcp-nota p:last-child {{ margin-bottom: 0; }}

div[data-testid="stVerticalBlock"] {{ gap: .55rem; }}

/* Upload: alvo grande e estado de arrasto legível. */
section[data-testid="stFileUploaderDropzone"] {{
  border: 1.5px dashed #BFCCC3; border-radius: var(--r-card);
  background: var(--superficie); min-height: 96px;
  transition-property: border-color, background-color;
  transition-duration: 150ms; transition-timing-function: ease-out;
}}
section[data-testid="stFileUploaderDropzone"]:hover {{
  border-color: var(--verde); background: #F6FAF7;
}}

@media (prefers-reduced-motion: reduce) {{
  .pcp *, .stButton > button {{ transition-duration: 1ms !important; }}
}}
</style>
"""


def aplicar(st) -> None:
    """Injeta o CSS global. Chamado uma vez, no início do app."""
    st.markdown(CSS, unsafe_allow_html=True)
