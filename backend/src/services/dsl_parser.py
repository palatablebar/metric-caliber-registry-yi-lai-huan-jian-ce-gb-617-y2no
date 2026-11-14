"""算法 A｜指标 DSL 解析器。

语法（一个指标一行文本）：

    name = agg(field) [ - agg(field) ] [where cond] [group by dim, dim]

- 聚合只允许 sum / count / distinct_count / avg；
- 聚合参数可以是 `dwd.order.amount` 这样的数仓字段、`*`（仅 count），
  或 `@gmv` 这样对另一个指标的引用（推导出依赖边）；
- 不合法输入返回结构化错误：code + message + position/column + snippet。

解析是纯函数、确定性：同一段 DSL 两次解析结果逐字相等，不访问数据库与网络。
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from src.constants.limits import MAX_DSL_LENGTH

AGGREGATIONS = ("sum", "count", "distinct_count", "avg")
# count 之外不接受 `*`
STAR_AGGRS = ("count",)
COMPARISONS = {"=", "<>", "!=", ">=", "<=", ">", "<"}
COND_KEYWORDS = {"in", "like", "between", "is", "not", "null", "and", "or"}

TOKEN_RE = re.compile(
    r"""
      (?P<ws>\s+)
    | (?P<string>'[^']*')
    | (?P<number>\d+(?:\.\d+)?)
    | (?P<at>@)
    | (?P<ident>[A-Za-z_][A-Za-z0-9_.]*)
    | (?P<op><>|!=|>=|<=|[=<>+\-*(),])
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    pos: int


class ParseFailure(Exception):
    """解析失败：位置是 0 基字符下标，column = position + 1。"""

    def __init__(self, code: str, message: str, position: int):
        self.code = code
        self.message = message
        self.position = max(0, int(position))
        super().__init__(message)


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0
    while index < len(text):
        match = TOKEN_RE.match(text, index)
        if match is None:
            raise ParseFailure("SYNTAX", f"无法识别的字符 “{text[index]}”", index)
        kind = match.lastgroup or ""
        if kind != "ws":
            tokens.append(Token(kind=kind, value=match.group(0), pos=index))
        index = match.end()
    return tokens


def _fail_from(code: str, message: str, tokens: list[Token], index: int, text: str) -> ParseFailure:
    if index < len(tokens):
        return ParseFailure(code, message, tokens[index].pos)
    return ParseFailure(code, message, len(text))


def _snippet(text: str, position: int, width: int = 28) -> str:
    start = max(0, position - 8)
    return text[start : start + width]


def _error_result(text: str, failure: ParseFailure, declared_name: str | None) -> dict:
    return {
        "status": "error",
        "name": declared_name,
        "aggs": [],
        "fields": [],
        "filters": [],
        "dims": [],
        "deps": [],
        "expression": "",
        "where_text": "",
        "signature": "",
        "token_count": 0,
        "error": {
            "code": failure.code,
            "message": failure.message,
            "position": failure.position,
            "column": failure.position + 1,
            "snippet": _snippet(text, failure.position),
        },
    }


def _normalize_condition(tokens: list[Token]) -> tuple[list[str], str]:
    """把 where 后面的 token 切成单条条件（按 and / or 分割）。"""
    groups: list[list[Token]] = [[]]
    depth = 0
    for token in tokens:
        if token.value == "(":
            depth += 1
        if token.value == ")":
            depth -= 1
        if depth == 0 and token.kind == "ident" and token.value.lower() in ("and", "or"):
            groups.append([])
            continue
        groups[-1].append(token)
    conditions: list[str] = []
    for group in groups:
        if not group:
            continue
        text = ""
        for token in group:
            if token.value in (",", ")"):
                text = text.rstrip() + token.value
            elif token.value == "(":
                text = (text.rstrip() + " (") if text else "("
            elif token.kind == "op" and token.value in COMPARISONS:
                text = text.rstrip() + f" {token.value} "
            else:
                glue = "" if (not text or text.endswith("(")) else " "
                text = text.rstrip() + glue + token.value
        conditions.append(re.sub(r"\s+", " ", text).strip())
    where_text = " ".join(token.value for token in tokens)
    return conditions, re.sub(r"\s+", " ", where_text).strip()


def _signature(aggs, fields, filters, dims, deps) -> str:
    payload = {
        "aggs": sorted(set(aggs)),
        "fields": sorted(set(fields)),
        "filters": sorted({item.lower() for item in filters}),
        "dims": sorted(set(dims)),
        "deps": sorted(set(deps)),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return digest[:16]


def parse_dsl(text: str, metric_code: str | None = None) -> dict:
    """解析一段指标 DSL；返回 dict（含 status / 结构化字段 / error）。"""
    raw = (text or "").strip()
    declared_name: str | None = None
    try:
        if not raw:
            raise ParseFailure("EMPTY_DSL", "DSL 为空，至少需要一个聚合表达式", 0)
        if len(raw) > MAX_DSL_LENGTH:
            raise ParseFailure("DSL_TOO_LONG", f"DSL 超过 {MAX_DSL_LENGTH} 字符", MAX_DSL_LENGTH)
        tokens = tokenize(raw)
        if not tokens:
            raise ParseFailure("EMPTY_DSL", "DSL 为空，至少需要一个聚合表达式", 0)

        # 括号配对先整体检查，避免后面报出误导性位置
        depth = 0
        for token in tokens:
            if token.value == "(":
                depth += 1
            elif token.value == ")":
                depth -= 1
                if depth < 0:
                    raise ParseFailure("UNBALANCED_PAREN", "出现多余的右括号", token.pos)
        if depth != 0:
            raise ParseFailure("UNBALANCED_PAREN", f"还有 {depth} 个左括号没有闭合", len(raw))

        if tokens[0].kind != "ident":
            raise _fail_from("SYNTAX", "DSL 必须以指标标识符开头，例如 gmv = sum(dwd.order.amount)", tokens, 0, raw)
        declared_name = tokens[0].value
        cursor = 1
        if cursor >= len(tokens) or tokens[cursor].value != "=":
            raise _fail_from("SYNTAX", "指标标识符后必须跟 “=”", tokens, cursor, raw)
        cursor += 1

        aggs: list[str] = []
        fields: list[str] = []
        deps: list[str] = []
        terms: list[str] = []
        while True:
            if cursor >= len(tokens):
                raise ParseFailure("SYNTAX", "缺少聚合表达式", len(raw))
            head = tokens[cursor]
            if head.kind != "ident":
                raise _fail_from("SYNTAX", "这里需要一个聚合函数", tokens, cursor, raw)
            agg = head.value
            if agg not in AGGREGATIONS:
                raise ParseFailure(
                    "UNKNOWN_AGG",
                    f"未知聚合函数 “{agg}”，允许：{', '.join(AGGREGATIONS)}",
                    head.pos,
                )
            aggs.append(agg)
            cursor += 1
            if cursor >= len(tokens) or tokens[cursor].value != "(":
                raise _fail_from("SYNTAX", f"{agg} 后面必须跟左括号", tokens, cursor, raw)
            cursor += 1
            if cursor >= len(tokens):
                raise ParseFailure("UNBALANCED_PAREN", f"{agg}( 没有闭合", len(raw))
            arg = tokens[cursor]
            arg_text = ""
            if arg.kind == "op" and arg.value == "*":
                if agg not in STAR_AGGRS:
                    raise ParseFailure("SYNTAX", f"{agg} 不接受 * 参数", arg.pos)
                arg_text = "*"
                cursor += 1
            elif arg.kind == "at":
                cursor += 1
                if cursor >= len(tokens) or tokens[cursor].kind != "ident":
                    raise _fail_from("SYNTAX", "@ 后面必须跟被引用的指标标识符", tokens, cursor, raw)
                ref = tokens[cursor].value
                if metric_code and ref == metric_code:
                    raise ParseFailure("SELF_REFERENCE", f"指标 {metric_code} 不能引用自己", arg.pos)
                if ref == declared_name:
                    raise ParseFailure("SELF_REFERENCE", f"指标 {declared_name} 不能引用自己", arg.pos)
                deps.append(ref)
                arg_text = f"@{ref}"
                cursor += 1
            elif arg.kind == "ident":
                fields.append(arg.value)
                arg_text = arg.value
                cursor += 1
            else:
                raise _fail_from("SYNTAX", "聚合参数需要字段名或 @指标引用", tokens, cursor, raw)
            if cursor >= len(tokens) or tokens[cursor].value != ")":
                raise _fail_from("SYNTAX", f"{agg}({arg_text} 缺少右括号", tokens, cursor, raw)
            cursor += 1
            terms.append(f"{agg}({arg_text})")
            if cursor < len(tokens) and tokens[cursor].kind == "op" and tokens[cursor].value in ("+", "-"):
                terms.append(tokens[cursor].value)
                cursor += 1
                continue
            break

        filters: list[str] = []
        where_text = ""
        dims: list[str] = []
        if cursor < len(tokens) and tokens[cursor].kind == "ident" and tokens[cursor].value.lower() == "where":
            where_pos = tokens[cursor].pos
            cursor += 1
            cond_tokens: list[Token] = []
            while cursor < len(tokens):
                token = tokens[cursor]
                if (
                    token.kind == "ident"
                    and token.value.lower() == "group"
                    and cursor + 1 < len(tokens)
                    and tokens[cursor + 1].kind == "ident"
                    and tokens[cursor + 1].value.lower() == "by"
                ):
                    break
                cond_tokens.append(token)
                cursor += 1
            if not cond_tokens:
                raise ParseFailure("SYNTAX", "where 后面缺少过滤条件", where_pos)
            has_compare = any(
                token.kind in ("op", "string", "number") and token.value in COMPARISONS
                for token in cond_tokens
            ) or any(token.kind == "ident" and token.value.lower() in COND_KEYWORDS for token in cond_tokens)
            if not has_compare:
                raise ParseFailure("SYNTAX", "where 后面缺少比较条件（例如 order_status='paid'）", cond_tokens[0].pos)
            filters, where_text = _normalize_condition(cond_tokens)

        if cursor < len(tokens) and tokens[cursor].kind == "ident" and tokens[cursor].value.lower() == "group":
            group_pos = tokens[cursor].pos
            cursor += 1
            if cursor >= len(tokens) or tokens[cursor].kind != "ident" or tokens[cursor].value.lower() != "by":
                raise ParseFailure("SYNTAX", "group 后面必须跟 by", group_pos)
            cursor += 1
            while True:
                if cursor >= len(tokens) or tokens[cursor].kind != "ident":
                    raise _fail_from("SYNTAX", "group by 需要至少一个维度字段", tokens, cursor, raw)
                dims.append(tokens[cursor].value)
                cursor += 1
                if cursor < len(tokens) and tokens[cursor].value == ",":
                    cursor += 1
                    continue
                break

        if cursor != len(tokens):
            raise _fail_from("SYNTAX", f"无法解析的剩余内容 “{tokens[cursor].value}”", tokens, cursor, raw)
        has_star = any(term.endswith("(*)") for term in terms)
        if not fields and not deps and not has_star:
            raise ParseFailure("NO_FIELD", "至少要引用一个字段或指标", len(raw))

        expression = " ".join(terms)
        if where_text:
            expression += f" where {where_text}"
        if dims:
            expression += f" group by {', '.join(dims)}"
        return {
            "status": "ok",
            "name": declared_name,
            "aggs": aggs,
            "fields": fields,
            "filters": filters,
            "dims": dims,
            "deps": deps,
            "expression": expression,
            "where_text": where_text,
            "group_by": dims,
            "signature": _signature(aggs, fields, filters, dims, deps),
            "token_count": len(tokens),
            "error": None,
        }
    except ParseFailure as failure:
        return _error_result(raw, failure, declared_name)


def parse_ok(result: dict) -> bool:
    return bool(result) and result.get("status") == "ok"
