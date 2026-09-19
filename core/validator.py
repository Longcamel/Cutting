"""输入校验与结果自检（详细设计 §3.1，纯函数，无状态）。

错误码对应 i18n 词条 err.<code>（§9 错误码表）。
"""

from dataclasses import dataclass

from .models import Part, Solution, StockSpec
from .statistics import _cuts_per_bar

MAX_NAME_LEN = 50  # R5：零件名称长度上限（mm无关，字符数）


@dataclass
class Issue:
    """校验问题。code 对应 i18n 词条 err.<code>；row>=0 表示出错零件下标/Excel行号。"""

    code: str  # 见 §9 错误码表，如 "E003"
    row: int = -1  # 出错的零件下标/Excel行号，-1=全局
    detail: str = ""  # 供日志，不直接显示


def validate_input(parts: list[Part], stock: StockSpec) -> list[Issue]:
    """计算前校验。返回空列表=通过。

    R1 parts 非空 -> E001
    R2 每个 part.length>=1 且 part.qty>=1 -> E002（row=下标）
    R3 stock.length>=1 且 stock.kerf>=0 -> E002
    R4 每个零件可切出：length<=stock.length 且
       (length+kerf<=stock.length 或 length==stock.length) -> E003
    R5 part.name 长度<=50 -> E002
    """
    issues: list[Issue] = []
    if not parts:
        issues.append(Issue("E001"))
        return issues  # 空清单后续规则无意义
    if stock.length < 1 or stock.kerf < 0:
        issues.append(Issue("E002", detail=f"stock.length={stock.length}, kerf={stock.kerf}"))
    for i, p in enumerate(parts):
        if p.length < 1 or p.qty < 1 or len(p.name) > MAX_NAME_LEN:
            issues.append(
                Issue(
                    "E002",
                    row=i,
                    detail=f"length={p.length}, qty={p.qty}, name_len={len(p.name)}",
                )
            )
            continue  # 非法长度不再判 R4
        if stock.length >= 1 and not (
            p.length <= stock.length
            and (p.length + stock.kerf <= stock.length or p.length == stock.length)
        ):
            issues.append(Issue("E003", row=i, detail=f"length={p.length}, stock={stock.length}"))
    return issues


def check_solution(sol: Solution, parts: list[Part], stock: StockSpec) -> list[Issue]:
    """结果合法性自检（F2.4）。返回空列表=合法。

    C1 每 pattern 消耗长度+锯缝 <= stock.length（切口数按 §2 约定）-> E005
    C2 每种零件实切总数 >= 需求 qty -> E005
    C3 每 pattern counts 非空、bars>=1、下标合法 -> E005
    """
    issues: list[Issue] = []
    produced = [0] * len(parts)
    for pi, pat in enumerate(sol.patterns):
        if (
            not pat.counts
            or pat.bars < 1
            or any(i < 0 or i >= len(parts) or n < 1 for i, n in pat.counts.items())
        ):
            issues.append(Issue("E005", row=pi, detail="C3: counts/bars/下标非法"))
            continue
        used = sum(parts[i].length * n for i, n in pat.counts.items())
        cuts = _cuts_per_bar(pat.counts, pat.remainder)
        if used + cuts * stock.kerf > stock.length:
            issues.append(Issue("E005", row=pi, detail=f"C1: used={used}+kerf>{stock.length}"))
        for i, n in pat.counts.items():
            produced[i] += n * pat.bars
    for i, p in enumerate(parts):
        if produced[i] < p.qty:
            issues.append(Issue("E005", row=i, detail=f"C2: 实切{produced[i]}<需求{p.qty}"))
    return issues
