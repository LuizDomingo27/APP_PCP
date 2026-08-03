"""Componentes visuais reutilizáveis.

Retornam string HTML em vez de escrever na tela: mantém as views declarativas
e permite compor blocos antes de um único `st.markdown`, o que evita o
"piscar" de múltiplas escritas do Streamlit.

Gráficos são SVG inline — sem biblioteca de chart para um donut e uma barra.
"""

from __future__ import annotations

import html
from math import pi

from . import format as fmt
from .theme import AZUL, CINZA_TRILHA, LARANJA, VERDE, VERDE_CLARO, VERMELHO

# Ícones: traço único, 24x24, herdam a cor do contexto via `currentColor`.
_ICONES = {
    "carteira": "M3 7h18v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Zm3-4h12v4H6V3Z",
    "prancheta": "M9 3h6v3H9V3Zm-3 3h12v15H6V6Zm3 5h6M9 15h4",
    "pct": "M19 5 5 19M7.5 8a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Zm9 13a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z",
    "agenda": "M4 5h16v16H4V5Zm0 5h16M8 3v4m8-4v4",
    "doc": "M13 3H6v18h12V8l-5-5Zm0 0v5h5",
    "camisa": "M8 3 5 5v5h3v11h8V10h3V5l-3-2-4 2-4-2Z",
    "pessoa": "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-8 9a8 8 0 0 1 16 0",
    "peca": "M9 3h6v3h3v4h3v6h-3v5H9v-3H6v-4H3V8h3V3Z",
    "caixa": "m12 2 9 5v10l-9 5-9-5V7l9-5Zm0 0v20m9-15-9 5-9-5",
    "alerta": "M12 3 2 20h20L12 3Zm0 6v5m0 3v.5",
    "foguete": "M5 15c-1 3 0 5 0 5s2 1 5 0m-5-5 4 4M14 4c4-2 7-1 7-1s1 3-1 7l-6 6-6-6 6-6Z",
    "relogio": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-14v5l3 2",
    "alvo": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-4a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0-4a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z",
}


def icone(nome: str, cor: str = "currentColor", tamanho: int = 19) -> str:
    caminho = _ICONES.get(nome, _ICONES["doc"])
    return (
        f'<svg width="{tamanho}" height="{tamanho}" viewBox="0 0 24 24" fill="none" '
        f'stroke="{cor}" stroke-width="1.9" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true"><path d="{caminho}"/></svg>'
    )


def escapar(texto: object) -> str:
    """Neutraliza HTML de um valor que não é do nosso código.

    `nota()` e o corpo de `painel()` recebem HTML por construção — é o que
    permite negrito e quebra de linha no texto das telas. Quem passa conteúdo de
    origem externa (célula da planilha, nome do arquivo enviado, texto de uma
    exceção) precisa passar por aqui antes: sem isso uma célula com
    `<img src=x onerror=...>` vira script executando na tela.
    """
    return html.escape(str(texto))


_e = escapar


# --------------------------------------------------------------------------
# Cabeçalho
# --------------------------------------------------------------------------


def cabecalho(titulo: str, subtitulo: str, selos: list[tuple[str, str]]) -> str:
    chips = "".join(
        f'<div class="pcp-selo"><div class="pcp-selo__rot">{_e(r)}</div>'
        f'<div class="pcp-selo__val num">{_e(v)}</div></div>'
        for r, v in selos
    )
    return (
        f'<div class="pcp"><div class="pcp-topo"><div>'
        f'<h1 class="pcp-topo__titulo">{_e(titulo)}</h1>'
        f'<div class="pcp-topo__sub">{_e(subtitulo)}</div></div>'
        f'<div class="pcp-topo__dir">{chips}</div></div></div>'
    )


# --------------------------------------------------------------------------
# KPIs
# --------------------------------------------------------------------------

_TONS = {
    "alerta": VERMELHO,
    "atencao": LARANJA,
    "ok": VERDE,
    "neutro": "#12301E",
}


def kpi(rotulo: str, valor: str, unidade: str, nome_icone: str, tom: str = "neutro") -> str:
    cor = _TONS.get(tom, _TONS["neutro"])
    return (
        f'<div class="pcp-kpi pcp-kpi--{_e(tom)}">'
        f'<div class="pcp-kpi__icone" style="background:{cor}14">'
        f"{icone(nome_icone, cor)}</div>"
        f'<div class="pcp-kpi__corpo"><div class="pcp-kpi__rot">{_e(rotulo)}</div>'
        f'<div class="pcp-kpi__val num">{_e(valor)}</div>'
        f'<div class="pcp-kpi__un">{_e(unidade)}</div></div></div>'
    )


def faixa_kpis(cartoes: list[str], variante: str = "") -> str:
    """`variante='contexto'` para faixas curtas, que não devem esticar."""
    extra = f" pcp-kpis--{_e(variante)}" if variante else ""
    return f'<div class="pcp"><div class="pcp-kpis{extra}">{"".join(cartoes)}</div></div>'


# --------------------------------------------------------------------------
# Donut em SVG
# --------------------------------------------------------------------------


def donut(
    fracao: float,
    cor: str,
    texto_centro: str,
    legenda_centro: str = "",
    cor_resto: str = CINZA_TRILHA,
    tamanho: int = 176,
) -> str:
    """Anel de proporção. `fracao` entre 0 e 1."""
    fracao = max(0.0, min(1.0, float(fracao)))
    raio, espessura = 62, 22
    circunferencia = 2 * pi * raio
    preenchido = circunferencia * fracao

    # Sem legenda o número fica opticamente centrado; com legenda, sobe.
    y_valor = 84 if legenda_centro else 88
    legenda = (
        f'<text x="80" y="99" text-anchor="middle" font-size="10" fill="#8B9A90" '
        f'font-weight="600">{_e(legenda_centro)}</text>'
        if legenda_centro
        else ""
    )
    def anel(cor_traco: str, tracejado: str = "") -> str:
        return (
            f'<circle cx="80" cy="80" r="{raio}" fill="none" stroke="{cor_traco}" '
            f'stroke-width="{espessura}" stroke-linecap="butt"{tracejado}/>'
        )

    return (
        f'<svg width="{tamanho}" height="{tamanho}" viewBox="0 0 160 160" role="img" '
        f'aria-label="{_e(texto_centro)} {_e(legenda_centro)}">'
        f'<g transform="rotate(-90 80 80)">{anel(cor_resto)}'
        f'{anel(cor, f" stroke-dasharray=\"{preenchido:.2f} {circunferencia:.2f}\"")}'
        f'</g><text x="80" y="{y_valor}" text-anchor="middle" font-size="27" '
        f'font-weight="800" fill="#16211A" '
        f'style="font-variant-numeric:tabular-nums">{_e(texto_centro)}</text>'
        f"{legenda}</svg>"
    )


def item_legenda(cor: str, rotulo: str, valor: str, observacao: str = "") -> str:
    obs = f'<div class="pcp-legenda__obs">{_e(observacao)}</div>' if observacao else ""
    return (
        f'<div class="pcp-legenda__item">'
        f'<span class="pcp-legenda__ponto" style="background:{cor}"></span><div>'
        f'<div class="pcp-legenda__rot" style="color:{cor}">{_e(rotulo)}</div>'
        f'<div class="pcp-legenda__val num">{_e(valor)}</div>{obs}</div></div>'
    )


# --------------------------------------------------------------------------
# Painéis, notas e barras
# --------------------------------------------------------------------------


def painel(titulo: str, corpo_html: str) -> str:
    return (
        f'<div class="pcp"><div class="pcp-painel">'
        f'<div class="pcp-painel__topo">{_e(titulo)}</div>'
        f'<div class="pcp-painel__corpo">{corpo_html}</div></div></div>'
    )


def nota(texto_html: str, tipo: str = "info", nome_icone: str = "alerta") -> str:
    """Aviso em destaque. **O texto entra como HTML** — veja `escapar()`."""
    cores = {"info": VERDE, "aviso": LARANJA, "erro": VERMELHO, "ok": VERDE_CLARO}
    return (
        f'<div class="pcp"><div class="pcp-nota pcp-nota--{_e(tipo)}">'
        f'<div style="flex:0 0 auto;margin-top:1px">'
        f'{icone(nome_icone, cores.get(tipo, VERDE), 18)}</div>'
        f"<div>{texto_html}</div></div></div>"
    )


def barra(fracao: float, cor: str) -> str:
    largura = max(0.0, min(1.0, float(fracao))) * 100
    return (
        f'<div class="pcp-barra"><div class="pcp-barra__preench" '
        f'style="width:{largura:.1f}%;background:{cor}"></div></div>'
    )


def linha_detrator(
    titulo: str,
    descricao: str,
    nome_icone: str,
    cor: str,
    quantidade: float,
    fracao: float,
    impacto: str,
    nota_impacto: str,
) -> str:
    return (
        f'<div class="pcp-det"><div class="pcp-det__nome">'
        f'<div class="pcp-kpi__icone" style="background:{cor}14;flex:0 0 38px">'
        f"{icone(nome_icone, cor)}</div><div>"
        f'<div class="pcp-det__tit" style="color:{cor}">{_e(titulo)}</div>'
        f'<div class="pcp-det__desc">{_e(descricao)}</div></div></div>'
        f'<div><div class="pcp-det__qtd num" style="color:{cor}">'
        f"{_e(fmt.numero(quantidade))}</div>"
        f'<div class="pcp-det__un">peças</div></div>'
        f'<div>{barra(fracao, cor)}'
        f'<div class="pcp-det__un num" style="margin-top:5px">'
        f"{_e(fmt.pct(fracao))} do saldo pendente</div></div>"
        f'<div><div class="pcp-det__impacto" style="color:{cor}">{_e(impacto)}</div>'
        f'<div class="pcp-det__nota">{_e(nota_impacto)}</div></div></div>'
    )


def linha_barra(
    rotulo: str,
    valor: str,
    fracao: float,
    cor: str,
    observacao: str = "",
    destaque: bool = False,
    nivel: int = 0,
) -> str:
    """Linha rótulo → barra → valor.

    É a forma de ler uma lista ordenada (etapas do fluxo, faixas de prazo,
    componentes que travam) sem gráfico: a barra dá a proporção, o número dá o
    valor exato, e a ordem já é a resposta.
    """
    peso = "800" if destaque else "700"
    obs = f'<div class="pcp-lb__obs">{_e(observacao)}</div>' if observacao else ""
    # Recuo por nível: o funil ramifica (Processo e Embalado saem do mesmo
    # Programado) e a indentação é o que mostra isso sem desenhar árvore.
    recuo = f"padding-left:{nivel * 14}px;" if nivel else ""
    ramo = '<span style="color:#8B9A90">└ </span>' if nivel else ""
    return (
        f'<div class="pcp-lb{" pcp-lb--destaque" if destaque else ""}">'
        f'<div class="pcp-lb__rot" style="font-weight:{peso};{recuo}">'
        f"{ramo}{_e(rotulo)}{obs}</div>"
        f"<div>{barra(fracao, cor)}</div>"
        f'<div class="pcp-lb__val num" style="color:{cor}">{_e(valor)}</div></div>'
    )


def serie_linha(
    valores: list[float],
    cor: str,
    rotulos: list[str] | None = None,
    largura: int = 560,
    altura: int = 150,
) -> str:
    """Curva de um indicador ao longo dos snapshots, em SVG inline.

    Mesma decisão do donut: não vale uma biblioteca de gráficos para desenhar
    uma linha. Casos que quebrariam o desenho e são tratados aqui: série com um
    ponto só (vira marcador) e série constante (denominador zero na escala).
    """
    if not valores:
        return '<div class="pcp-lb__obs">Sem série para exibir.</div>'

    pad_x, pad_y = 10, 16
    largura_util = largura - 2 * pad_x
    altura_util = altura - 2 * pad_y
    menor, maior = min(valores), max(valores)
    faixa = (maior - menor) or 1.0

    def ponto(i: int, v: float) -> tuple[float, float]:
        x = pad_x + (largura_util * i / (len(valores) - 1) if len(valores) > 1 else largura_util / 2)
        return x, pad_y + altura_util * (1 - (v - menor) / faixa)

    pontos = [ponto(i, v) for i, v in enumerate(valores)]
    caminho = " ".join(
        f"{'M' if i == 0 else 'L'}{x:.1f} {y:.1f}" for i, (x, y) in enumerate(pontos)
    )
    area = (
        f'<path d="{caminho} L{pontos[-1][0]:.1f} {altura - pad_y} '
        f'L{pontos[0][0]:.1f} {altura - pad_y} Z" fill="{cor}" opacity=".10"/>'
        if len(pontos) > 1
        else ""
    )
    marcadores = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#fff" stroke="{cor}" stroke-width="2.5"/>'
        for x, y in pontos
    )
    eixo = ""
    if rotulos:
        eixo = "".join(
            f'<text x="{x:.1f}" y="{altura - 2}" text-anchor="middle" font-size="9" '
            f'fill="#8B9A90" font-weight="600">{_e(rotulo)}</text>'
            for (x, _), rotulo in zip(pontos, rotulos, strict=True)
        )
    return (
        f'<svg viewBox="0 0 {largura} {altura}" width="100%" height="{altura}" '
        f'role="img" aria-label="Evolução do indicador" '
        f'preserveAspectRatio="none">{area}'
        f'<path d="{caminho}" fill="none" stroke="{cor}" stroke-width="2.5" '
        f'stroke-linecap="round" stroke-linejoin="round"/>{marcadores}{eixo}</svg>'
    )


def par(rotulo: str, valor: str, cor: str = "") -> str:
    """Rótulo + valor em bloco, para resumos dentro de painel."""
    estilo = f' style="color:{cor}"' if cor else ""
    return (
        f'<div class="pcp-par"><div class="pcp-par__rot">{_e(rotulo)}</div>'
        f'<div class="pcp-par__val num"{estilo}>{_e(valor)}</div></div>'
    )


# --------------------------------------------------------------------------
# Tabela
# --------------------------------------------------------------------------


def tabela(cabecalhos: list[str], linhas: list[tuple[str, list[str]]]) -> str:
    """`linhas` = [(classe_css, [celulas...])]. Classes: 'g', 'sub', 't', ''."""
    ths = "".join(f"<th>{_e(c)}</th>" for c in cabecalhos)
    corpo = "".join(
        f'<tr class="{_e(classe)}">'
        + "".join(f'<td class="num">{_e(c)}</td>' for c in celulas)
        + "</tr>"
        for classe, celulas in linhas
    )
    return (
        f'<div class="pcp" style="overflow-x:auto">'
        f'<table class="pcp-tab"><thead><tr>{ths}</tr></thead>'
        f"<tbody>{corpo}</tbody></table></div>"
    )


# MTO e MTA têm cor fixa porque o time já as reconhece dos painéis atuais.
# Existem outros TOCs na base (DCO, por exemplo) e eles não podem herdar a cor
# de MTO — dois pontos verdes na legenda não distinguem nada. O catálogo não é
# fixo no código: a paleta extra é distribuída na ordem em que aparecerem.
CORES_TOC = {"MTO": VERDE, "MTA": AZUL}
_PALETA_TOC_EXTRA = (LARANJA, VERMELHO, "#6A4C93", "#00838F", "#8D6E63")


def cores_toc(tocs: list[str]) -> dict[str, str]:
    """Uma cor distinta por TOC, na ordem recebida."""
    extras = iter(_PALETA_TOC_EXTRA)
    return {toc: CORES_TOC.get(toc) or next(extras, "#5C6B60") for toc in tocs}
