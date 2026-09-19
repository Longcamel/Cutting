"""利用率统计（详细设计 §3.5，纯函数）。

切口数按 §2 不变式：某切法余料>0 时切口数=段数；余料=0 时切口数=段数−1。
"""

from .models import Part, Solution, Statistics, StockSpec


def _cuts_per_bar(pattern_counts: dict[int, int], remainder: int) -> int:
    """一根原料按此切法的切口数。"""
    n = sum(pattern_counts.values())
    return n if remainder > 0 else max(n - 1, 0)


def compute(sol: Solution, parts: list[Part], stock: StockSpec) -> Statistics:
    """遍历 patterns 汇总统计量。utilization 为百分比（保留小数，由调用方格式化）。"""
    bars_used = 0
    total_part_len = 0
    kerf_loss = 0
    for pat in sol.patterns:
        bars_used += pat.bars
        part_len_per_bar = sum(parts[i].length * n for i, n in pat.counts.items())
        total_part_len += part_len_per_bar * pat.bars
        kerf_loss += _cuts_per_bar(pat.counts, pat.remainder) * stock.kerf * pat.bars
    total_stock_len = bars_used * stock.length
    waste_len = total_stock_len - total_part_len - kerf_loss
    utilization = (total_part_len / total_stock_len * 100.0) if total_stock_len > 0 else 0.0
    return Statistics(
        bars_used=bars_used,
        total_stock_len=total_stock_len,
        total_part_len=total_part_len,
        kerf_loss=kerf_loss,
        waste_len=waste_len,
        utilization=utilization,
    )
