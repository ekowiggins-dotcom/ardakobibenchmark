from __future__ import annotations

import ast
from pathlib import Path


class _RemovePageConfig(ast.NodeTransformer):
    def visit_Expr(self, node: ast.Expr) -> ast.AST | None:
        call = node.value
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "set_page_config"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "st"
        ):
            return None
        return self.generic_visit(node)


def run_streamlit_page_without_page_config(path: str | Path) -> None:
    """Run an existing Streamlit page inside a custom navigation shell.

    Streamlit permits `st.set_page_config` only once. The analyst pages already
    call it, so the executive shell removes that one top-level call before
    executing the page source. The page logic itself remains shared.
    """

    page_path = Path(path).resolve()
    source = page_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(page_path))
    tree = _RemovePageConfig().visit(tree)
    ast.fix_missing_locations(tree)
    globals_dict = {
        "__file__": str(page_path),
        "__name__": "__main__",
        "__package__": None,
    }
    exec(compile(tree, str(page_path), "exec"), globals_dict)
