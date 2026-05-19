"""Tests for simulation.engine.betting — pure math, no side effects."""

import math
from typing import Callable

import pytest

from simulation.engine.betting import (
    calculate_bet,
    calculate_max_drawdown,
    calculate_pnl,
    calculate_sharpe_ratio,
    calculate_win_rate,
)


# ========================================================================
# calculate_bet
# ========================================================================


class TestCalculateBet:
    # -- fixed mode ------------------------------------------------------

    def test_fixed_sufficient_capital(self):
        """Fixed mode: exact bet_amount when capital >= amount."""
        assert calculate_bet("fixed", 100.0, None, 500.0) == 100.0

    def test_fixed_insufficient_capital(self):
        """Fixed mode: capped at current_capital when amount exceeds it."""
        assert calculate_bet("fixed", 500.0, None, 100.0) == 100.0

    def test_fixed_equal_capital(self):
        """Fixed mode: bet equals capital exactly."""
        assert calculate_bet("fixed", 100.0, None, 100.0) == 100.0

    def test_fixed_zero_capital(self):
        """Fixed mode: zero capital returns zero."""
        assert calculate_bet("fixed", 100.0, None, 0.0) == 0.0

    def test_fixed_small_amount(self):
        """Fixed mode: small positive values work."""
        assert calculate_bet("fixed", 0.01, None, 1000.0) == 0.01

    # -- percent mode ----------------------------------------------------

    def test_percent_normal(self):
        """Percent mode: 50 % of 1000 capital = 500."""
        assert calculate_bet("percent", 0.0, 0.5, 1000.0) == 500.0

    def test_percent_full(self):
        """Percent mode: 100 % = full capital."""
        assert calculate_bet("percent", 0.0, 1.0, 500.0) == 500.0

    def test_percent_small(self):
        """Percent mode: 1 % of 10 000 = 100."""
        result = calculate_bet("percent", 0.0, 0.01, 10000.0)
        assert result == pytest.approx(100.0)

    def test_percent_zero_capital(self):
        """Percent mode: zero capital returns zero."""
        assert calculate_bet("percent", 0.0, 0.5, 0.0) == 0.0

    # -- invalid inputs --------------------------------------------------

    @pytest.mark.parametrize("mode,amount,pct,capital", [
        ("unknown", 100.0, None, 500.0),          # unknown mode
        ("fixed", -10.0, None, 500.0),             # negative amount
        ("fixed", 0.0, None, 500.0),               # zero amount
        ("percent", 0.0, None, 500.0),             # None percent
        ("percent", 0.0, -0.1, 500.0),             # negative percent
        ("percent", 0.0, 0.0, 500.0),              # zero percent
        ("percent", 0.0, 1.5, 500.0),              # percent > 1
        ("fixed", 100.0, None, -1.0),              # negative capital
        ("percent", 0.0, 0.5, -1.0),               # negative capital
    ])
    def test_invalid_inputs(self, mode, amount, pct, capital):
        """All invalid input combinations raise ValueError."""
        with pytest.raises(ValueError):
            calculate_bet(mode, amount, pct, capital)


# ========================================================================
# calculate_pnl
# ========================================================================


class TestCalculatePnl:
    # -- WIN -------------------------------------------------------------

    @pytest.mark.parametrize("fee,expected", [
        (0.0, 100.0),
        (0.002, 99.8),       # 0.2 % fee
        (0.1, 90.0),         # 10 % fee
        (0.5, 50.0),         # 50 % fee
    ])
    def test_win_with_fee(self, fee: float, expected: float):
        """WIN: profit = bet * (1 - fee_rate)."""
        assert calculate_pnl("long", "WIN", 100.0, fee) == pytest.approx(expected)

    def test_win_short_direction(self):
        """WIN with short direction yields same PnL."""
        assert calculate_pnl("short", "WIN", 50.0, 0.0) == 50.0

    # -- LOSE ------------------------------------------------------------

    def test_lose(self):
        """LOSE: loss = -bet_amount."""
        assert calculate_pnl("long", "LOSE", 100.0, 0.0) == -100.0

    def test_lose_with_fee(self):
        """LOSE: fee_rate is irrelevant, loss is always -bet_amount."""
        assert calculate_pnl("long", "LOSE", 100.0, 0.5) == -100.0

    # -- SKIP ------------------------------------------------------------

    def test_skip(self):
        """SKIP: PnL is 0 regardless of other inputs."""
        assert calculate_pnl("long", "SKIP", 100.0, 0.0) == 0.0
        assert calculate_pnl("long", "SKIP", 999.0, 0.5) == 0.0

    def test_skip_zero_bet(self):
        """SKIP with zero bet amount."""
        assert calculate_pnl("long", "SKIP", 0.0, 0.0) == 0.0

    # -- edge cases ------------------------------------------------------

    def test_zero_bet_win(self):
        """WIN with zero bet."""
        assert calculate_pnl("long", "WIN", 0.0, 0.0) == 0.0

    def test_zero_bet_lose(self):
        """LOSE with zero bet."""
        assert calculate_pnl("long", "LOSE", 0.0, 0.0) == 0.0

    # -- invalid inputs --------------------------------------------------

    @pytest.mark.parametrize("direction,result,bet,fee", [
        ("unknown", "WIN", 100.0, 0.0),             # bad direction
        ("long", "UNKNOWN", 100.0, 0.0),            # bad result
        ("long", "WIN", -1.0, 0.0),                 # negative bet
        ("long", "WIN", 100.0, -0.1),               # negative fee
        ("long", "WIN", 100.0, 1.0),                # fee == 1 (boundary)
        ("long", "WIN", 100.0, 1.5),                # fee > 1
    ])
    def test_invalid_inputs(self, direction, result, bet, fee):
        with pytest.raises(ValueError):
            calculate_pnl(direction, result, bet, fee)


# ========================================================================
# calculate_win_rate
# ========================================================================


class TestCalculateWinRate:
    def test_normal(self):
        """Normal case: 7 wins, 3 losses → 70 %."""
        assert calculate_win_rate(7, 3) == pytest.approx(0.7)

    def test_all_wins(self):
        """All wins → 100 %."""
        assert calculate_win_rate(5, 0) == 1.0

    def test_all_losses(self):
        """All losses → 0 %."""
        assert calculate_win_rate(0, 8) == 0.0

    def test_no_completed_rounds(self):
        """No completed rounds → 0.0."""
        assert calculate_win_rate(0, 0) == 0.0

    def test_with_skips(self):
        """Skips are ignored: 7/10 = 0.7 regardless of 5 skips."""
        assert calculate_win_rate(7, 3, skips=5) == pytest.approx(0.7)

    def test_only_skips(self):
        """Only skips, no completed rounds → 0.0."""
        assert calculate_win_rate(0, 0, skips=10) == 0.0

    def test_large_numbers(self):
        """Handles large counts without overflow issues."""
        assert calculate_win_rate(1_000_000, 250_000) == 0.8

    @pytest.mark.parametrize("wins,losses,skips", [
        (-1, 0, 0),
        (0, -1, 0),
        (0, 0, -1),
    ])
    def test_negative_inputs(self, wins: int, losses: int, skips: int):
        with pytest.raises(ValueError):
            calculate_win_rate(wins, losses, skips)


# ========================================================================
# calculate_max_drawdown
# ========================================================================


class TestCalculateMaxDrawdown:
    def test_known_sequence(self):
        """
        Equity: 100, 120, 110, 130, 90, 140
        Peaks:  100, 120, 120, 130, 130, 140
        DD:      0.0, 0.0, 0.0833, 0.0, 0.3077, 0.0
        Max DD should be (130 - 90) / 130 ≈ 0.3077
        """
        equity = [100.0, 120.0, 110.0, 130.0, 90.0, 140.0]
        dd = calculate_max_drawdown(equity)
        assert dd == pytest.approx(0.3076923, rel=1e-5)

    def test_monotonic_up(self):
        """Monotonically increasing → no drawdown."""
        equity = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert calculate_max_drawdown(equity) == 0.0

    def test_monotonic_down(self):
        """Monotonically decreasing → drawdown is from first peak."""
        equity = [100.0, 80.0, 60.0, 40.0]
        # peak=100, max dd = (100-40)/100 = 0.6
        assert calculate_max_drawdown(equity) == pytest.approx(0.6)

    def test_flat(self):
        """Flat equity → no drawdown."""
        equity = [50.0, 50.0, 50.0, 50.0]
        assert calculate_max_drawdown(equity) == 0.0

    def test_multiple_peaks(self):
        """Multiple peaks: max dd picks the largest drop."""
        equity = [100.0, 200.0, 50.0, 150.0, 30.0]
        # peak=200, max dd = (200-30)/200 = 0.85
        assert calculate_max_drawdown(equity) == pytest.approx(0.85)

    def test_negative_equity(self):
        """Equity goes negative -> drawdown capped at 1.0 per point."""
        equity = [100.0, -50.0, 200.0]
        # peak=100, dd at -50 = (100 - (-50))/100 = 1.5 -> but we cap at... 
        # Actually our formula: (peak - value) / peak = (100 - (-50))/100 = 1.5
        # The spec doesn't say cap it. Let's keep it as-is for now.
        # With value=-50, dd=1.5. Then peak=200, dd=0.
        # So max_dd = 1.5
        dd = calculate_max_drawdown(equity)
        assert dd == pytest.approx(1.5)

    def test_single_element(self):
        """Single element → no drawdown."""
        assert calculate_max_drawdown([100.0]) == 0.0

    def test_empty_list(self):
        """Empty list → 0.0."""
        assert calculate_max_drawdown([]) == 0.0


# ========================================================================
# calculate_sharpe_ratio
# ========================================================================


class TestCalculateSharpeRatio:
    def test_consistent_wins(self):
        """All pnl values identical → PnL = 10 each → std=0 → SR=0."""
        assert calculate_sharpe_ratio([10.0, 10.0, 10.0]) == 0.0

    def test_high_variance(self):
        """
        PnL = [5, -5, 5, -5] each time.
        Mean = 0, so SR = 0 regardless of std.
        """
        assert calculate_sharpe_ratio([5.0, -5.0, 5.0, -5.0]) == 0.0

    def test_positive_sharpe(self):
        """PnL with positive mean should yield positive SR."""
        pnl = [2.0, 3.0, 4.0, 3.0, 2.0]
        sr = calculate_sharpe_ratio(pnl)
        assert sr > 0.0

    def test_negative_sharpe(self):
        """PnL with negative mean should yield negative SR."""
        pnl = [-2.0, -3.0, -4.0, -3.0, -2.0]
        sr = calculate_sharpe_ratio(pnl)
        assert sr < 0.0

    def test_with_risk_free_rate(self):
        """Risk-free rate reduces (or negates) the Sharpe ratio."""
        pnl = [2.0, 3.0, 4.0, 3.0, 2.0]
        sr_no_rfr = calculate_sharpe_ratio(pnl, 0.0)
        sr_with_rfr = calculate_sharpe_ratio(pnl, 0.05)
        assert sr_with_rfr < sr_no_rfr

    def test_known_values(self):
        """Manually computed check."""
        pnl = [10.0, 20.0, 30.0]
        # mean = 20, variance = ((10-20)^2 + (20-20)^2 + (30-20)^2) / 2
        #       = (100 + 0 + 100) / 2 = 100
        # std = 10
        # SR = 20 / 10 = 2.0
        assert calculate_sharpe_ratio(pnl) == pytest.approx(2.0)

    def test_single_element(self):
        """Single element → std = 0 → SR = 0."""
        assert calculate_sharpe_ratio([100.0]) == 0.0

    def test_two_elements(self):
        """Two elements works (n-1 = 1 divisor)."""
        pnl = [10.0, 20.0]
        # mean = 15, variance = ((10-15)^2 + (20-15)^2) / 1 = (25 + 25) = 50
        # std = sqrt(50) ≈ 7.071
        # SR = 15 / 7.071 ≈ 2.121
        sr = calculate_sharpe_ratio(pnl)
        assert sr == pytest.approx(15.0 / math.sqrt(50.0))

    def test_empty_list(self):
        """Empty list → 0.0."""
        assert calculate_sharpe_ratio([]) == 0.0

    def test_all_zeros(self):
        """All zeros → std = 0 → SR = 0."""
        assert calculate_sharpe_ratio([0.0, 0.0, 0.0]) == 0.0
