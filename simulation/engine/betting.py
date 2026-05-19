"""Betting calculation module for crypto simulation trading.

Pure math functions with no side effects — no I/O, no database access,
no external dependencies beyond the standard library.
"""

import math


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_bet(
    bet_mode: str,
    bet_amount: float,
    bet_percent: float | None,
    current_capital: float,
) -> float:
    """Calculate the actual bet amount for a single round.

    Parameters
    ----------
    bet_mode : str
        ``"fixed"`` or ``"percent"``.
    bet_amount : float
        Fixed amount in USDT (used when *bet_mode* is ``"fixed"``).
        Must be strictly positive.
    bet_percent : float | None
        Percentage of current capital as a value in (0, 1].
        Used when *bet_mode* is ``"percent"``.  ``None`` is rejected.
    current_capital : float
        Current available capital.  Must be >= 0.

    Returns
    -------
    float
        The actual bet amount for this round:
        - ``"fixed"`` mode → ``min(bet_amount, current_capital)``
        - ``"percent"`` mode → ``current_capital * bet_percent``
        Always non-negative and never exceeds *current_capital*.

    Raises
    ------
    ValueError
        - *bet_mode* is not ``"fixed"`` or ``"percent"``.
        - *bet_amount* <= 0 in ``"fixed"`` mode.
        - *bet_percent* is ``None``, <= 0, or > 1 in ``"percent"`` mode.
        - *current_capital* is negative.
    """
    _validate_bet_mode(bet_mode)

    if current_capital < 0.0:
        raise ValueError("current_capital must be non-negative")

    if current_capital == 0.0:
        return 0.0

    if bet_mode == "fixed":
        if bet_amount <= 0.0:
            raise ValueError("bet_amount must be positive in fixed mode")
        return min(bet_amount, current_capital)

    # percent mode
    if bet_percent is None:
        raise ValueError("bet_percent is required in percent mode")
    if bet_percent <= 0.0 or bet_percent > 1.0:
        raise ValueError("bet_percent must be in (0, 1]")
    return current_capital * bet_percent


def calculate_pnl(
    direction: str,
    result: str,
    bet_amount: float,
    fee_rate: float = 0.0,
) -> float:
    """Calculate profit / loss for a single round.

    Parameters
    ----------
    direction : str
        ``"long"`` or ``"short"``.  Recorded for audit trail but does **not**
        affect the numeric result (the outcome is already determined by the
        caller).
    result : str
        ``"WIN"``, ``"LOSE"``, or ``"SKIP"``.
    bet_amount : float
        Amount that was wagered.  Must be >= 0.
    fee_rate : float, optional
        Fee rate as a decimal (e.g. 0.002 for 0.2 %).  Applied on top of
        winnings.  Default 0.0.  Must be in [0, 1).

    Returns
    -------
    float
        - ``"WIN"``:  ``+bet_amount * (1 - fee_rate)``
        - ``"LOSE"``: ``-bet_amount``
        - ``"SKIP"``: ``0.0``

    Raises
    ------
    ValueError
        - *result* is not a recognised value.
        - *direction* is not ``"long"`` or ``"short"``.
        - *bet_amount* is negative.
        - *fee_rate* is outside [0, 1).
    """
    if direction not in ("long", "short"):
        raise ValueError("direction must be 'long' or 'short'")

    if result not in ("WIN", "LOSE", "SKIP"):
        raise ValueError("result must be 'WIN', 'LOSE', or 'SKIP'")

    if bet_amount < 0.0:
        raise ValueError("bet_amount must be non-negative")

    if fee_rate < 0.0 or fee_rate >= 1.0:
        raise ValueError("fee_rate must be in [0, 1)")

    if result == "WIN":
        return bet_amount * (1.0 - fee_rate)
    if result == "LOSE":
        return -bet_amount
    return 0.0  # SKIP


def calculate_win_rate(wins: int, losses: int, skips: int = 0) -> float:
    """Calculate the win rate, excluding skipped rounds.

    Parameters
    ----------
    wins : int
        Number of winning rounds.  Must be >= 0.
    losses : int
        Number of losing rounds.  Must be >= 0.
    skips : int, optional
        Number of skipped rounds (ignored in calculation).  Must be >= 0.

    Returns
    -------
    float
        ``wins / (wins + losses)``, or ``0.0`` when there are no completed
        rounds.

    Raises
    ------
    ValueError
        Any argument is negative.
    """
    _validate_nonnegative("wins", wins)
    _validate_nonnegative("losses", losses)
    _validate_nonnegative("skips", skips)

    total = wins + losses
    if total == 0:
        return 0.0
    return wins / total


def calculate_max_drawdown(equity_points: list[float]) -> float:
    """Calculate the maximum drawdown from a list of cumulative equity values.

    Drawdown is measured as the largest percentage decline from a peak to a
    subsequent trough.

    Parameters
    ----------
    equity_points : list[float]
        Time-ordered cumulative equity / capital values.

    Returns
    -------
    float
        Maximum drawdown as a fraction in [0, 1] (e.g. 0.25 = 25 % loss).
        Returns ``0.0`` for an empty list.
    """
    if not equity_points:
        return 0.0

    peak = equity_points[0]
    max_dd = 0.0

    for value in equity_points:
        if value > peak:
            peak = value
        dd = (peak - value) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    return max_dd


def calculate_sharpe_ratio(pnl_list: list[float], risk_free_rate: float = 0.0) -> float:
    """Calculate the (non-annualised) Sharpe ratio from per-round PnL values.

    .. math::

        SR = \\frac{\\mu(\\text{pnl}) - r_f}{\\sigma(\\text{pnl})}

    where :math:`\\mu` is the mean, :math:`\\sigma` is the sample standard
    deviation, and :math:`r_f` is the risk-free rate.

    Parameters
    ----------
    pnl_list : list[float]
        Per-round profit / loss values.
    risk_free_rate : float, optional
        Risk-free rate per round (default ``0.0``).

    Returns
    -------
    float
        Sharpe ratio.  ``0.0`` when std dev is zero or the list is empty.
    """
    n = len(pnl_list)
    if n == 0:
        return 0.0

    mean = sum(pnl_list) / n

    if n == 1:
        return 0.0

    variance = sum((x - mean) ** 2 for x in pnl_list) / (n - 1)
    std_dev = math.sqrt(variance)

    if std_dev == 0.0:
        return 0.0

    return (mean - risk_free_rate) / std_dev


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_bet_mode(bet_mode: str) -> None:
    """Raise ``ValueError`` if *bet_mode* is not recognised."""
    if bet_mode not in ("fixed", "percent"):
        raise ValueError("bet_mode must be 'fixed' or 'percent'")


def _validate_nonnegative(name: str, value: int) -> None:
    """Raise ``ValueError`` if *value* is negative."""
    if value < 0:
        raise ValueError(f"{name} must be non-negative, got {value}")
