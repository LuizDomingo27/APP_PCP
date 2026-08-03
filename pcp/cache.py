"""Cache local em Parquet.

Decisão do time: sem banco de dados. O cache é um diretório de arquivos na
máquina de quem usa — reler uma planilha já processada custa milissegundos em
vez de reprocessar 139 MB de XML.

A chave é o hash do conteúdo do arquivo, não o nome: renomear a planilha não
invalida o cache, e editar o conteúdo invalida mesmo com o nome igual.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_TAMANHO_BLOCO = 8 * 1024 * 1024
_VERSAO_CACHE = 2  # subir invalida tudo quando o contrato/tratamento mudar


def diretorio_padrao() -> Path:
    return Path.home() / ".pcp_cache"


def hash_arquivo(caminho: str | Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as fh:
        while bloco := fh.read(_TAMANHO_BLOCO):
            h.update(bloco)
    return h.hexdigest()[:16]


@dataclass(frozen=True)
class EntradaCache:
    chave: str
    metadados: dict


class CacheParquet:
    """Persistência local das bases já tratadas."""

    def __init__(self, raiz: str | Path | None = None) -> None:
        self.raiz = Path(raiz) if raiz else diretorio_padrao()
        self.raiz.mkdir(parents=True, exist_ok=True)

    def _pasta(self, chave: str) -> Path:
        return self.raiz / f"v{_VERSAO_CACHE}_{chave}"

    def gravar(
        self, chave: str, bases: dict[str, pd.DataFrame], metadados: dict
    ) -> EntradaCache:
        pasta = self._pasta(chave)
        temporaria = pasta.with_suffix(".tmp")
        shutil.rmtree(temporaria, ignore_errors=True)
        temporaria.mkdir(parents=True, exist_ok=True)
        try:
            for nome, df in bases.items():
                df.to_parquet(temporaria / f"{_slug(nome)}.parquet", index=False)
            meta = {
                **metadados,
                "chave": chave,
                "versao_cache": _VERSAO_CACHE,
                "carregado_em": datetime.now(timezone.utc).isoformat(),
                "abas": list(bases),
            }
            (temporaria / "metadados.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            # Troca atômica: nunca deixa cache pela metade para o próximo leitor.
            shutil.rmtree(pasta, ignore_errors=True)
            temporaria.rename(pasta)
        except Exception:
            shutil.rmtree(temporaria, ignore_errors=True)
            raise
        return EntradaCache(chave, meta)

    def ler(self, chave: str) -> tuple[dict[str, pd.DataFrame], EntradaCache] | None:
        pasta = self._pasta(chave)
        arquivo_meta = pasta / "metadados.json"
        if not arquivo_meta.exists():
            return None
        try:
            meta = json.loads(arquivo_meta.read_text(encoding="utf-8"))
            bases = {
                nome: pd.read_parquet(pasta / f"{_slug(nome)}.parquet")
                for nome in meta.get("abas", [])
            }
        except OSError:
            # Falha de I/O é quase sempre transitória no Windows: arquivo em uso
            # por antivírus, pasta em sincronização de nuvem, disco ocupado.
            # Apagar aqui destruiria para sempre um ponto da série do M7 — que
            # não tem como ser reconstruído sem o .xlsx original de 139 MB.
            # Devolve vazio (o app reprocessa) e tenta de novo na próxima vez.
            return None
        except Exception:
            # Conteúdo ilegível ou de contrato antigo: aí sim não serve mais, e
            # reprocessar a planilha é a única saída.
            shutil.rmtree(pasta, ignore_errors=True)
            return None
        return bases, EntradaCache(chave, meta)

    def listar(self) -> list[EntradaCache]:
        """Histórico local disponível, do mais recente para o mais antigo."""
        entradas: list[EntradaCache] = []
        for pasta in self.raiz.glob(f"v{_VERSAO_CACHE}_*"):
            arquivo_meta = pasta / "metadados.json"
            if not arquivo_meta.exists():
                continue
            try:
                meta = json.loads(arquivo_meta.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            entradas.append(EntradaCache(meta.get("chave", pasta.name), meta))
        return sorted(
            entradas, key=lambda e: e.metadados.get("carregado_em", ""), reverse=True
        )


def _slug(nome: str) -> str:
    return nome.lower().replace(" ", "_")
