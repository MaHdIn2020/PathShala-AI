"""Safe AST-based arithmetic verifier for primary-school math questions (no eval())."""
import ast
import operator

_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯×÷−", "0123456789*/-")
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        val = _eval_node(node.operand)
        return val if isinstance(node.op, ast.UAdd) else -val
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
            raise ZeroDivisionError("division by zero")
        return _OPS[type(node.op)](left, right)
    raise ValueError("unsupported expression")


def safe_eval_expr(expr: str) -> float | int | None:
    """Safely evaluate a basic arithmetic expression (supports Bangla digits ০-৯ and ×/÷)."""
    clean = (expr or "").translate(_BN_DIGITS).strip()
    if not clean or len(clean) > 80:
        return None
    try:
        tree = ast.parse(clean, mode="eval")
        val = _eval_node(tree.body)
        if isinstance(val, float) and val.is_integer():
            return int(val)
        return round(val, 4) if isinstance(val, float) else val
    except Exception:
        return None
