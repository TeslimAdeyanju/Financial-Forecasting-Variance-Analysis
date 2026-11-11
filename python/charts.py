"""Shared matplotlib styling: one validated categorical order, thin marks, recessive axes."""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# Categorical slots in fixed order (CVD-validated reference palette). Never cycle past these.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
# Diverging pair for polarity (favourable / adverse) with a neutral grey midpoint.
FAVOURABLE, ADVERSE, NEUTRAL = "#2a78d6", "#e34948", "#bdbcb6"
SURFACE, TEXT, TEXT_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def apply_style() -> None:
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "figure.dpi": 110,
            "figure.figsize": (11, 4.5),
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.labelcolor": TEXT_2,
            "axes.edgecolor": GRID,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "axes.axisbelow": True,
            "axes.prop_cycle": mpl.cycler(color=SERIES),
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "lines.linewidth": 2,
            "lines.markersize": 5,
            "xtick.color": TEXT_2,
            "ytick.color": TEXT_2,
            "text.color": TEXT,
            "legend.frameon": False,
            "patch.linewidth": 0,
        }
    )


def money_axis(ax, which: str = "y") -> None:
    """Currency ticks scaled to the axis range ($k / $m), with enough decimals to keep ticks distinct."""
    axis = ax.yaxis if which == "y" else ax.xaxis
    lo, hi = ax.get_ylim() if which == "y" else ax.get_xlim()
    span = max(abs(lo), abs(hi))
    scale, div = ("m", 1e6) if span >= 1e6 else ("k", 1e3) if span >= 1e4 else ("", 1)
    step = (hi - lo) / div / 6
    decimals = 0 if step >= 1 or not scale else 1 if step >= 0.1 else 2
    axis.set_major_formatter(FuncFormatter(lambda v, _: f"{'-' if v < 0 else ''}${abs(v) / div:,.{decimals}f}{scale}"))


def pct(decimals: int = 0) -> FuncFormatter:
    return FuncFormatter(lambda v, _: f"{v:.{decimals}f}%")


def finish(ax, title: str, subtitle: str | None = None, xlabel: str = "", ylabel: str = ""):
    ax.set_title(title, pad=22 if subtitle else 8)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, color=TEXT_2, fontsize=9, va="bottom")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    return ax


def show():
    plt.tight_layout()
    plt.show()
