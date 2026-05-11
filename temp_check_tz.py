import pandas as pd

user_cutoff_str = '2026-05-01 15:59:00'

naive_ts = pd.Timestamp(user_cutoff_str).value // 1_000_000
print(f'Naive -> UTC epoch ms: {naive_ts}')

shanghai_ts = pd.Timestamp(user_cutoff_str, tz='Asia/Shanghai').value // 1_000_000
print(f'Shanghai -> UTC epoch ms: {shanghai_ts}')

diff_hours = (naive_ts - shanghai_ts) / 3600000
print(f'Difference: {diff_hours} hours')

print()
print('4h candle open times (UTC):')
for h in [0, 4, 8, 12, 16, 20]:
    candle_ts = pd.Timestamp(f'2026-05-01 {h:02d}:00:00').value // 1_000_000
    naive_included = 'INCLUDED (WRONG)' if candle_ts < naive_ts else 'EXCLUDED'
    shanghai_included = 'INCLUDED (CORRECT)' if candle_ts < shanghai_ts else 'EXCLUDED'
    print(f'  {h:02d}:00 open -> {candle_ts}: {naive_included:s} | {shanghai_included:s}')

naive_count = sum(1 for h in [0,4,8,12,16,20] if pd.Timestamp(f'2026-05-01 {h:02d}:00:00').value // 1_000_000 < naive_ts)
sha_count = sum(1 for h in [0,4,8,12,16,20] if pd.Timestamp(f'2026-05-01 {h:02d}:00:00').value // 1_000_000 < shanghai_ts)
print()
print(f'Candles before naive cutoff (15:59 UTC): {naive_count}')
print(f'Candles before Shanghai cutoff (07:59 UTC): {sha_count}')
print(f'Extra candles with naive interpretation: {naive_count - sha_count}')
