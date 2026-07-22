"""Scoped file toolkit: read broadly, write only to allowlisted paths. No deletes."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from agno.tools import Toolkit

from config import BOOK_ROOT, GUIDE_DIR, REPO_ROOT


class ScopedFileTools(Toolkit):
    """File tools with a path jail.

    - Reads: any path under read_roots (default: book/, content/guide/, data/)
    - Writes / appends: only paths in write_allowlist (exact files or dirs)
    - No delete, no shell
    """

    def __init__(
        self,
        write_allowlist: Sequence[Path],
        read_roots: Sequence[Path] | None = None,
        agent_label: str = "agent",
        **kwargs,
    ):
        self.agent_label = agent_label
        self.write_allowlist = [p.resolve() for p in write_allowlist]
        self.read_roots = [
            p.resolve()
            for p in (
                read_roots
                or (
                    BOOK_ROOT,
                    GUIDE_DIR,
                    REPO_ROOT / "data",
                )
            )
        ]
        tools = [
            self.list_dir,
            self.read_file,
            self.write_own,
            self.append_own,
        ]
        super().__init__(name=f"scoped_files_{agent_label}", tools=tools, **kwargs)

    def _resolve_readable(self, path: str) -> Path:
        raw = Path(path)
        if not raw.is_absolute():
            # Prefer book-relative, then repo-relative
            candidates = [BOOK_ROOT / raw, REPO_ROOT / raw, Path.cwd() / raw]
        else:
            candidates = [raw]
        for c in candidates:
            resolved = c.resolve()
            if any(self._is_under(resolved, root) for root in self.read_roots):
                return resolved
        raise PermissionError(
            f"Read denied for {path!r}. Allowed roots: {[str(r) for r in self.read_roots]}"
        )

    def _resolve_writable(self, path: str) -> Path:
        raw = Path(path)
        if not raw.is_absolute():
            candidates = [BOOK_ROOT / raw, Path.cwd() / raw]
        else:
            candidates = [raw]
        for c in candidates:
            resolved = c.resolve()
            if self._is_write_allowed(resolved):
                return resolved
        raise PermissionError(
            f"Write denied for {path!r} ({self.agent_label}). "
            f"Allowed: {[str(p) for p in self.write_allowlist]}. Deletes are never allowed."
        )

    @staticmethod
    def _is_under(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _is_write_allowed(self, path: Path) -> bool:
        for allowed in self.write_allowlist:
            if path == allowed:
                return True
            # Directory allowlist: any file under that directory
            if not allowed.suffix or allowed.exists() and allowed.is_dir():
                if self._is_under(path, allowed):
                    return True
            # Treat suffix-less paths as directories even if not created yet
            if not allowed.suffix and self._is_under(path, allowed):
                return True
        return False

    def list_dir(self, directory: str = ".") -> str:
        """List files in a readable directory (relative to book/ or absolute under roots)."""
        try:
            path = self._resolve_readable(directory)
        except PermissionError as e:
            return f"ERROR: {e}"
        if not path.exists():
            return f"ERROR: path does not exist: {path}"
        if path.is_file():
            return str(path)
        lines: list[str] = []
        for child in sorted(path.iterdir()):
            kind = "dir" if child.is_dir() else "file"
            lines.append(f"{kind}\t{child.relative_to(BOOK_ROOT) if self._is_under(child, BOOK_ROOT) else child}")
        return "\n".join(lines) if lines else "(empty)"

    def read_file(self, path: str) -> str:
        """Read a text file under allowed roots."""
        try:
            target = self._resolve_readable(path)
        except PermissionError as e:
            return f"ERROR: {e}"
        if not target.exists():
            return f"ERROR: file not found: {target}"
        if not target.is_file():
            return f"ERROR: not a file: {target}"
        try:
            return target.read_text(encoding="utf-8")
        except Exception as e:
            return f"ERROR reading {target}: {e}"

    def write_own(self, path: str, content: str) -> str:
        """Create or overwrite a file in this agent's write allowlist. Cannot delete."""
        try:
            target = self._resolve_writable(path)
        except PermissionError as e:
            return f"ERROR: {e}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to {target}"

    def append_own(self, path: str, content: str) -> str:
        """Append to a file in this agent's write allowlist. Cannot delete."""
        try:
            target = self._resolve_writable(path)
        except PermissionError as e:
            return f"ERROR: {e}"
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended {len(content)} characters to {target}"
