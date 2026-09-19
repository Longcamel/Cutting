"""全系统唯一数据结构定义（详细设计 §2，字段定义冻结）。

约定：长度单位统一为毫米(int)，数量 int；禁止 float 参与长度计算。
切口数（不变式，§2）：余料>0 时切口数=段数；余料=0 时切口数=段数−1。
零件在 parts 列表中的下标即其全局标识（CuttingPattern.counts 的键）。
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Part:
    """一种零件需求。"""

    length: int  # mm，>=1
    qty: int  # >=1
    name: str = ""  # 可空，Excel"名称"列，仅展示用


@dataclass(frozen=True)
class StockSpec:
    """原料与全局参数。"""

    length: int  # mm，>=1
    kerf: int  # mm，>=0，锯缝损耗
    material: str = ""  # 材料名，报表标注
    company: str = ""  # 可空，PDF抬头
    project: str = ""  # 可空，PDF抬头


@dataclass
class CuttingPattern:
    """一种切法：一根原料上的切割组合 + 该切法使用根数。"""

    counts: dict[int, int]  # {零件在parts列表中的下标: 每根切出的件数}
    bars: int = 1  # 此切法消耗的原料根数
    remainder: int = 0  # 每根余料 mm（由求解器填入）


@dataclass
class Statistics:
    bars_used: int  # 原料总根数
    total_stock_len: int  # 原料总长 = bars_used * stock.length
    total_part_len: int  # 零件总长（不含锯缝）
    kerf_loss: int  # 锯缝损耗总长
    waste_len: int  # 余料总长 = total_stock_len - total_part_len - kerf_loss
    utilization: float  # 利用率% = total_part_len / total_stock_len * 100


@dataclass
class Solution:
    patterns: list[CuttingPattern] = field(default_factory=list)
    stats: Statistics | None = None
    exact: bool = False  # 是否数学最优（精确模式且未超时）
    elapsed_s: float = 0.0


__all__ = [
    "Part",
    "StockSpec",
    "CuttingPattern",
    "Statistics",
    "Solution",
]
