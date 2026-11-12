"""Diff ligne à ligne entre deux fichiers (lignes ajoutées / supprimées)."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class DiffResult:
    removed: list[tuple[int, str]]   # (n° de ligne dans l'ancien fichier, texte)
    added: list[tuple[int, str]]     # (n° de ligne dans le nouveau fichier, texte)


def diff_lines(old: list[str], new: list[str]) -> DiffResult:
    """Compare deux listes de lignes et renvoie ce qui a été retiré et ajouté.

    Une ligne modifiée apparaît comme une suppression + un ajout (comme `diff`).
    autojunk=False : sinon difflib ignore les lignes très fréquentes, ce qui
    fausserait le résultat sur des logs répétitifs.
    """
    matcher = SequenceMatcher(None, old, new, autojunk=False)
    removed, added = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("delete", "replace"):
            removed.extend((i + 1, old[i]) for i in range(i1, i2))
        if tag in ("insert", "replace"):
            added.extend((j + 1, new[j]) for j in range(j1, j2))
    return DiffResult(removed=removed, added=added)


def format_diff(result: DiffResult, old_name: str, new_name: str) -> str:
    """Texte lisible : « - [l.12] … » pour les suppressions, « + [l.40] … » pour les ajouts."""
    out = [f"--- {old_name}", f"+++ {new_name}",
           f"# {len(result.removed)} ligne(s) supprimée(s), {len(result.added)} ligne(s) ajoutée(s)"]
    out += [f"- [l.{n}] {text}" for n, text in result.removed]
    out += [f"+ [l.{n}] {text}" for n, text in result.added]
    return "\n".join(out) + "\n"
