"""Terms, atoms, literals, parsing and unification.

Everything in the reasoner is built on these few definitions.

* A term is a constant or a variable.
  - constant: lowercase name (ali, s_a1) or an integer (20261002)
  - variable: name that starts with an uppercase letter or "_" (X, Owner)
* An atom is a predicate applied to terms, for example owns(ali, car_ali).
  Atoms are stored as plain tuples ("owns", "ali", "car_ali") so they are
  hashable and can live in Python sets.
* A literal is something that can appear in a rule body:
  - a positive atom            owns(X, V)
  - a built-in comparison      E >= D,  X \\= Y
  - a negated atom             not loses(X, S)   (negation as failure)

The KB has no function symbols, so unification only ever binds a variable
to a constant or to another variable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional, Union

Term = Union[str, int]
Atom = tuple            # (predicate, arg1, arg2, ...)
Substitution = dict     # variable name -> term


class ParseError(ValueError):
    """Raised when a clause or atom is written in invalid syntax."""


class ReasoningError(RuntimeError):
    """Raised when a rule cannot be evaluated (for example an unbound comparison)."""


# --------------------------------------------------------------------------
# Terms
# --------------------------------------------------------------------------

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INT = re.compile(r"^-?\d+$")


def is_var(term: Term) -> bool:
    """A variable is a string that starts with an uppercase letter or '_'."""
    return isinstance(term, str) and (term[0].isupper() or term[0] == "_")


def parse_term(text: str) -> Term:
    text = text.strip()
    if _INT.match(text):
        return int(text)
    if _NAME.match(text):
        return text
    raise ParseError(f"invalid term: {text!r}")


def format_term(term: Term) -> str:
    return str(term)


# --------------------------------------------------------------------------
# Atoms
# --------------------------------------------------------------------------

_ATOM = re.compile(r"^\s*([a-z][A-Za-z0-9_]*)\s*(?:\((.*)\))?\s*$")


def parse_atom(text: str) -> Atom:
    """Parse 'owns(ali, car_ali)' into ('owns', 'ali', 'car_ali')."""
    match = _ATOM.match(text)
    if not match:
        raise ParseError(f"invalid atom: {text!r}")
    predicate, args = match.group(1), match.group(2)
    if args is None or not args.strip():
        return (predicate,)
    return (predicate, *(parse_term(a) for a in _split_top_level(args)))


def format_atom(atom: Atom) -> str:
    if len(atom) == 1:
        return atom[0]
    return f"{atom[0]}({', '.join(format_term(t) for t in atom[1:])})"


def atom_vars(atom: Atom) -> list[str]:
    return [t for t in atom[1:] if is_var(t)]


def is_ground(atom: Atom) -> bool:
    return not atom_vars(atom)


def signature(atom: Atom) -> str:
    """Predicate indicator in Prolog style, e.g. owns/2."""
    return f"{atom[0]}/{len(atom) - 1}"


# --------------------------------------------------------------------------
# Literals
# --------------------------------------------------------------------------

# Longest operators first so that ">=" is not read as ">".
BUILTIN_OPERATORS = (">=", "=<", "\\=", ">", "<")

_BUILTIN_SYMBOLS = {">=": "≥", "=<": "≤", "\\=": "≠", ">": ">", "<": "<"}


@dataclass(frozen=True)
class Literal:
    """One element of a rule body.

    kind is "atom", "builtin" or "not".
    For "builtin", atom holds (operator, left, right).
    """

    kind: str
    atom: Atom

    @staticmethod
    def positive(atom: Atom) -> "Literal":
        return Literal("atom", atom)

    @property
    def predicate(self) -> str:
        return self.atom[0]

    def variables(self) -> list[str]:
        terms = self.atom[1:]
        return [t for t in terms if is_var(t)]

    def substitute(self, subst: Substitution) -> "Literal":
        return Literal(self.kind, substitute(self.atom, subst))

    def to_text(self) -> str:
        if self.kind == "builtin":
            op, left, right = self.atom
            return f"{format_term(left)} {op} {format_term(right)}"
        if self.kind == "not":
            return f"not {format_atom(self.atom)}"
        return format_atom(self.atom)

    def to_prolog(self) -> str:
        if self.kind == "not":
            return f"\\+ {format_atom(self.atom)}"
        return self.to_text()

    def to_fol(self) -> str:
        """Render in first-order logic notation (variables in lowercase)."""
        def term(t: Term) -> str:
            return t.lower() if is_var(t) else format_term(t)

        if self.kind == "builtin":
            op, left, right = self.atom
            return f"{term(left)} {_BUILTIN_SYMBOLS[op]} {term(right)}"
        body = self.atom[0]
        if len(self.atom) > 1:
            body += "(" + ", ".join(term(t) for t in self.atom[1:]) + ")"
        return f"¬{body}" if self.kind == "not" else body

    def __str__(self) -> str:
        return self.to_text()


def parse_literal(text: str) -> Literal:
    text = text.strip()
    for prefix in ("not ", "\\+ "):
        if text.startswith(prefix):
            return Literal("not", parse_atom(text[len(prefix):]))
    depth = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0:
            for op in BUILTIN_OPERATORS:
                if text.startswith(op, i):
                    left, right = text[:i], text[i + len(op):]
                    return Literal("builtin", (op, parse_term(left), parse_term(right)))
    return Literal.positive(parse_atom(text))


def parse_clause(text: str) -> tuple[Optional[Atom], list[Literal]]:
    """Parse a Horn clause written in Prolog syntax.

    'head.'               -> fact
    'head :- b1, b2.'     -> rule
    ':- b1, b2.'          -> denial (goal) clause, returns head None
    """
    text = " ".join(text.strip().split())
    if text.endswith("."):
        text = text[:-1]
    if ":-" in text:
        head_text, body_text = text.split(":-", 1)
        head = parse_atom(head_text) if head_text.strip() else None
        body = [parse_literal(part) for part in _split_top_level(body_text)]
        if not body:
            raise ParseError(f"empty rule body: {text!r}")
        return head, body
    return parse_atom(text), []


def parse_query(text: str) -> list[Literal]:
    """Parse a goal such as 'can_allocate(ali, S)' or 'a(X), b(X)'."""
    text = text.strip().rstrip(".")
    if text.startswith("?-"):
        text = text[2:]
    return [parse_literal(part) for part in _split_top_level(text)]


def _split_top_level(text: str) -> list[str]:
    """Split on commas that are not inside parentheses."""
    parts, depth, current = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if "".join(current).strip():
        parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


# --------------------------------------------------------------------------
# Substitution and unification
# --------------------------------------------------------------------------

def resolve(term: Term, subst: Substitution) -> Term:
    """Follow variable bindings until reaching a constant or a free variable."""
    while is_var(term) and term in subst:
        term = subst[term]
    return term


def substitute(atom: Atom, subst: Substitution) -> Atom:
    return (atom[0], *(resolve(t, subst) for t in atom[1:]))


def unify_terms(a: Term, b: Term, subst: Substitution) -> Optional[Substitution]:
    a, b = resolve(a, subst), resolve(b, subst)
    if a == b:
        return subst
    if is_var(a):
        return {**subst, a: b}
    if is_var(b):
        return {**subst, b: a}
    return None   # two different constants never unify


def unify(x: Atom, y: Atom, subst: Optional[Substitution] = None) -> Optional[Substitution]:
    """Most general unifier of two atoms, extending subst. None if they clash."""
    subst = {} if subst is None else subst
    if x[0] != y[0] or len(x) != len(y):
        return None
    for a, b in zip(x[1:], y[1:]):
        subst = unify_terms(a, b, subst)
        if subst is None:
            return None
    return subst


def is_variant(x: Atom, y: Atom) -> bool:
    """True when two atoms are equal up to renaming of variables."""
    if x[0] != y[0] or len(x) != len(y):
        return False
    forward, backward = {}, {}
    for a, b in zip(x[1:], y[1:]):
        if is_var(a) and is_var(b):
            if forward.setdefault(a, b) != b or backward.setdefault(b, a) != a:
                return False
        elif a != b:
            return False
    return True


def evaluate_builtin(literal: Literal, subst: Substitution) -> bool:
    """Evaluate a comparison. Both sides must be bound when it is reached."""
    op, left, right = literal.atom
    left, right = resolve(left, subst), resolve(right, subst)
    if is_var(left) or is_var(right):
        raise ReasoningError(
            f"comparison {literal.to_text()} reached with an unbound variable; "
            "put the literals that bind it earlier in the rule body")
    if op == "\\=":
        return left != right
    if not (isinstance(left, int) and isinstance(right, int)):
        raise ReasoningError(f"{literal.to_text()} compares non-numbers {left!r}, {right!r}")
    return {">=": left >= right, "=<": left <= right,
            ">": left > right, "<": left < right}[op]


def binding_text(subst: Substitution, variables: Iterable[str]) -> str:
    """Readable bindings such as {X=ali, S=s_a1} for the listed variables."""
    shown = [f"{v}={format_term(resolve(v, subst))}" for v in variables
             if not is_var(resolve(v, subst))]
    return "{" + ", ".join(shown) + "}"
