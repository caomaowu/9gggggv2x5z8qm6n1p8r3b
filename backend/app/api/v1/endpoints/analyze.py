from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.models.schemas.analyze import AnalyzeRequest
from app.services.market_data import MarketDataService
from app.services.trading_engine import TradingEngine
from app.services.history_service import history_service
from app.core.progress import update_analysis_progress
from app.utils.id_manager import get_result_id_manager
from app.utils.analysis_log import get_analysis_logger
from app.core.config import settings
from app.core.events import check_env_changes
import logging
import pandas as pd
from typing import Any

router = APIRouter()
logger = logging.getLogger(__name__)

# ======================================================================
# 衍生品数据周期映射（方案A+D）
# rubik 端点不支持任意 bar，需将分析周期映射到 OKX 支持的最小可用周期。
# 当分析周期 > 拉取周期时，通过增大 limit 补偿时间跨度。
# ======================================================================

DERIVATIVE_PERIOD_MAP: dict[str, str] = {
    "1m": "5m",      # rubik OI历史最小支持 5m
    "3m": "5m",
    "5m": "5m",
    "15m": "1H",     # 降级到 1H
    "30m": "1H",     # 降级到 1H
    "1h": "1H",
    "4h": "1H",      # 拉 1H，用 limit ×4 补偿
    "1d": "1D",
    "1w": "1D",      # 拉 1D，用 limit ×7 补偿
}

# 周期→分钟数（用于计算 adjusted_limit）
_TIMEFRAME_MINUTES: dict[str, int] = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "4h": 240, "1d": 1440, "1w": 10080,
}

def get_market_service():
    return MarketDataService()

def get_trading_engine():
    # In a real app, this might be a singleton or cached
    return TradingEngine()

@router.post("/")
async def analyze_market(
    request: AnalyzeRequest,
    market_service: MarketDataService = Depends(get_market_service),
    # trading_engine: TradingEngine = Depends(get_trading_engine) # Instantiating per request for config flexibility
):
    import time
    start_time = time.time()
    result_id = "UNKNOWN" # Default safe value for error handling
    try:
        # 1. Generate Result ID
        id_manager = get_result_id_manager()
        
        # 处理时间框架：如果是多时间框架模式，使用逗号连接或者特殊格式
        timeframe_for_id = request.timeframe
        if request.multi_timeframe_mode and request.timeframes:
             # 为了避免文件名/ID过长，可以使用 "+" 连接，或者简写
             # 这里选择用 "+" 连接，如 4h+1d
             timeframe_for_id = "+".join(request.timeframes)
        elif isinstance(request.timeframe, list):
             timeframe_for_id = "+".join(request.timeframe)
             
        result_id = id_manager.get_next_id(asset=request.asset, timeframe=timeframe_for_id)
        
        # 2. Log Analysis Start
        analysis_logger = get_analysis_logger()
        analysis_logger.append_start_log(result_id, request.asset, request.timeframe)

        update_analysis_progress("start", 0, f"[{result_id}] Starting analysis for {request.asset}")
        
        logger.info(f"[{result_id}] Fetching market data for {request.asset} ({request.timeframe})...")
        update_analysis_progress("fetching_data", 10, f"[{result_id}] Fetching market data...")
        
        # Determine start/end time based on request
        # (Simplified logic compared to original for brevity, but should be robust)
        start_dt_str = None
        end_dt_str = None
        
        if request.data_method == "date_range":
             if request.start_date:
                 start_dt_str = f"{request.start_date} {request.start_time}:00"
             if request.end_date:
                 end_dt_str = f"{request.end_date} {request.end_time}:00"
        elif request.data_method == "to_end" and request.end_date:
             end_dt_str = f"{request.end_date} {request.end_time}:00"

        # Multi-Timeframe Support
        if request.multi_timeframe_mode and request.timeframes:
            logger.info(f"[{result_id}] Multi-timeframe mode enabled with timeframes: {request.timeframes}")
            
            # 获取多个时间框架的数据
            multi_df = {}
            for tf in request.timeframes:
                logger.info(f"[{result_id}] Fetching {tf} timeframe data...")
                df_single = market_service.get_ohlcv_data_enhanced(
                    symbol=request.asset,
                    timeframe=tf,
                    limit=request.kline_count,
                    method=request.data_method,
                    start_date=start_dt_str,
                    end_date=end_dt_str
                )
                
                if df_single is None or df_single.empty:
                    logger.warning(f"[{result_id}] No data found for timeframe {tf}")
                    continue
                    
                multi_df[tf] = df_single
                
            if not multi_df:
                raise HTTPException(status_code=404, detail="No market data found for any timeframe")
                
            df = multi_df
            timeframe_for_result = ",".join(request.timeframes)
        else:
            # Single Timeframe Mode (original logic)
            timeframe = request.timeframe if isinstance(request.timeframe, str) else request.timeframe[0]
            df = market_service.get_ohlcv_data_enhanced(
                symbol=request.asset,
                timeframe=timeframe,
                limit=request.kline_count,
                method=request.data_method,
                start_date=start_dt_str,
                end_date=end_dt_str
            )
            
            if df is None or df.empty:
                raise HTTPException(status_code=404, detail="No market data found")
            
            timeframe_for_result = timeframe
            
        # 哈雷酱修复：在回测模式(to_end)下，修正最后一根K线的收盘价，消除未来函数
        # 获取该时刻的真实价格（通过 1m K线），并覆盖主数据的 Close
        if request.data_method == "to_end" and end_dt_str:
            try:
                # 获取截止到 end_dt_str 的最新 1m 价格
                real_price_df = market_service.get_ohlcv_data(
                    symbol=request.asset,
                    timeframe="1m",
                    limit=1,
                    end_date=end_dt_str
                )
                
                if real_price_df is not None and not real_price_df.empty:
                    real_close = float(real_price_df.iloc[-1]['Close'])
                    logger.info(f"[{result_id}] Correcting latest price to {real_close} (from 1m data at {end_dt_str})")
                    
                    def fix_last_candle(dataframe):
                        if dataframe is None or dataframe.empty:
                            return dataframe
                        # 使用副本以避免警告，虽然这里可能已经是副本
                        df_copy = dataframe.copy()
                        last_idx = df_copy.index[-1]
                        
                        # 修正 Close
                        df_copy.loc[last_idx, 'Close'] = real_close
                        
                        # 修正 High/Low 以保持一致性 (如果 Close 超出了范围)
                        if real_close > df_copy.loc[last_idx, 'High']:
                            df_copy.loc[last_idx, 'High'] = real_close
                        if real_close < df_copy.loc[last_idx, 'Low']:
                            df_copy.loc[last_idx, 'Low'] = real_close
                            
                        return df_copy

                    # 应用修正
                    if isinstance(df, dict):
                        new_multi_df = {}
                        for tf, sub_df in df.items():
                            new_multi_df[tf] = fix_last_candle(sub_df)
                        df = new_multi_df
                    else:
                        df = fix_last_candle(df)
                else:
                    logger.warning(f"[{result_id}] Failed to fetch real price for correction at {end_dt_str}")
            except Exception as e:
                logger.error(f"[{result_id}] Error correcting latest price: {e}")
                # 出错不阻断，继续使用原始数据

        # 哈雷酱添加：如果是在做回测（to_end 或 date_range），且请求了未来K线，则获取“未来”数据用于验证
        future_kline_list = []
        future_kline_chart_base64 = None
        
        # User requirement: Force fetch 15m future data for backtesting validation (36 candles)
        future_15m_kline_list = []
        future_15m_chart_base64 = None
        
        if request.data_method in ["to_end", "date_range"]:
            # 1. Fetch User Requested Future Data (Main Timeframe)
            if request.future_kline_count > 0:
                try:
                    # 关键修复：直接使用用户指定的结束时间作为未来数据的起始时间
                    # 避免从 df.index[-1] 转换带来的格式或时区问题
                    # end_dt_str 已经在前面构造好，格式为 "YYYY-MM-DD HH:MM:00"，这是 API 验证通过的格式
                    future_start_str = end_dt_str
                    
                    # 如果因为某种原因 end_dt_str 为空（防御性编程），则回退到 last_dt
                    if not future_start_str:
                        # 多时间框架模式下，使用第一个时间框架的数据
                        reference_df = df[list(df.keys())[0]] if isinstance(df, dict) else df
                        last_dt = reference_df.index[-1]
                        future_start_str = last_dt.strftime("%Y-%m-%d %H:%M:%S")

                    logger.info(f"Fetching future verification data starting from {future_start_str}...")
                    
                    # 计算未来的结束时间，以确保 API 能返回我们需要的数据范围
                    # 假设 API 忽略 start_time，只看 end_time，且返回 end_time 之前的 limit 条
                    future_end_str = None
                    try:
                        # 多时间框架模式下，使用第一个时间框架
                        tf = timeframe_for_result.split(",")[0] if "," in timeframe_for_result else timeframe_for_result
                        delta = None
                        if tf == '1mo':
                            delta = pd.Timedelta(days=31)
                        elif tf == '1w':
                            delta = pd.Timedelta(weeks=1)
                        else:
                            # 尝试将 m 替换为 min (pandas 使用 min 表示分钟，避免歧义)
                            # 注意：要避免把 1mo 替换成 1mino
                            if tf.endswith('m') and not tf.endswith('mo'):
                                tf_pd = tf.replace('m', 'min') 
                            else:
                                tf_pd = tf
                            delta = pd.Timedelta(tf_pd)
                        
                        if delta:
                            # 加上缓冲，确保覆盖所需范围
                            # 比如需要 13 条，我们计算 13+20 条的时间跨度
                            total_delta = delta * (request.future_kline_count + 20)
                            start_dt = pd.to_datetime(future_start_str)
                            future_end_dt = start_dt + total_delta
                            future_end_str = future_end_dt.strftime("%Y-%m-%d %H:%M:%S")
                            logger.info(f"Calculated future end date: {future_end_str}")
                    except Exception as e:
                        logger.warning(f"Failed to calculate future end date: {e}")

                    # 获取比请求多一点的数据，以便过滤
                    # 如果 future_end_str 有值，就用它。否则用 None (默认到 Now)
                    future_df = market_service.get_ohlcv_data(
                        symbol=request.asset,
                        timeframe=tf,
                        limit=request.future_kline_count + 50, # 大幅增加 limit 以防止不足
                        start_date=future_start_str,
                        end_date=future_end_str 
                    )
                    
                    if future_df is not None and not future_df.empty:
                        # 过滤掉已经包含在主分析数据中的时间点
                        # 这里的 last_dt 是主数据的最后一条时间
                        reference_df = df[tf] if isinstance(df, dict) else df
                        last_dt = reference_df.index[-1]
                        future_df = future_df[future_df.index > last_dt]
                        
                        # 截取用户请求的数量
                        future_df = future_df.head(request.future_kline_count)
                        
                        if not future_df.empty:
                            # 1. 生成图表
                            from app.utils.chart_generator import chart_generator
                            future_kline_chart_base64 = chart_generator.generate_kline_chart(
                                future_df, 
                                title=f"未来{len(future_df)}根K线走势 ({tf}周期 回测验证)"
                            )
                            
                            # 2. 准备数据列表
                            future_df_reset = future_df.reset_index()
                            # 处理索引列名
                            date_col = 'Date' if 'Date' in future_df_reset.columns else 'index'
                            if date_col in future_df_reset.columns:
                                # API 返回 UTC 时间，+8h 转为北京时间后格式化
                                future_df_reset[date_col] = (future_df_reset[date_col] + pd.Timedelta(hours=8)).dt.strftime('%Y-%m-%d %H:%M:%S')
                                future_df_reset.rename(columns={date_col: 'datetime'}, inplace=True)
                            
                            # 转换为全小写列名
                            future_df_reset.columns = [str(c).lower() for c in future_df_reset.columns]
                            future_kline_list = future_df_reset.to_dict(orient='records')
                            
                            logger.info(f"Successfully fetched {len(future_kline_list)} future klines for verification")
                except Exception as e:
                    logger.warning(f"Failed to fetch future verification data: {e}")
                    # 不阻断主流程，只是没有未来数据而已

            # 2. Fetch 15m Future Data (Forced, 36 candles)
            # --------------------------------------------------------------------------------
            # User Requirement (2025-01-20): 
            # Regardless of the analysis timeframe, always fetch and display the 
            # 15-minute timeframe data for the 36 periods immediately following the analysis time.
            # This provides a consistent "short-term verification" view for backtesting.
            # --------------------------------------------------------------------------------
            try:
                # Use same start time
                future_start_str = end_dt_str
                if not future_start_str:
                     reference_df = df[list(df.keys())[0]] if isinstance(df, dict) else df
                     last_dt = reference_df.index[-1]
                     future_start_str = last_dt.strftime("%Y-%m-%d %H:%M:%S")

                # Calculate end time for 15m * 36 candles + buffer
                # 36 candles * 15 min = 540 min = 9 hours
                # Add buffer of 4 hours
                start_dt = pd.to_datetime(future_start_str)
                # future_start_str 为用户输入的北京时间（如 "2026-05-01 15:59:00"），
                # 而 API 返回的 df_future_15m.index 是 UTC naive datetime。
                # 将 start_dt 转为 UTC naive，确保过滤比较时区一致。
                start_dt = start_dt.tz_localize('Asia/Shanghai').tz_convert('UTC').tz_localize(None)
                future_end_15m = start_dt + pd.Timedelta(hours=13) 
                future_end_str_15m = future_end_15m.strftime("%Y-%m-%d %H:%M:%S")

                logger.info(f"Fetching 15m future verification data (36 candles) from {future_start_str} to {future_end_str_15m}...")
                
                df_future_15m = market_service.get_ohlcv_data(
                    symbol=request.asset,
                    timeframe="15m",
                    limit=100, # Request more to filter
                    start_date=future_start_str,
                    end_date=future_end_str_15m 
                )
                
                if df_future_15m is not None and not df_future_15m.empty:
                     # Filter: strictly after analysis time
                     # Make sure indices are comparable (timezone-aware vs naive)
                     if df_future_15m.index.tz is None and start_dt.tz is not None:
                         start_dt = start_dt.tz_localize(None)
                     elif df_future_15m.index.tz is not None and start_dt.tz is None:
                         start_dt = start_dt.tz_localize('UTC') # Assume UTC if one is aware

                     df_future_15m = df_future_15m[df_future_15m.index > start_dt]
                     
                     # Take exactly 36 candles (or less if not enough)
                     target_count_15m = 36
                     df_future_15m = df_future_15m.head(target_count_15m)
                     
                     if not df_future_15m.empty:
                        # Generate chart
                        from app.utils.chart_generator import chart_generator
                        future_15m_chart_base64 = chart_generator.generate_kline_chart(
                            df_future_15m, 
                            title=f"未来36根15分钟K线走势 (短线验证)"
                        )
                        
                        # Prepare list
                        future_15m_reset = df_future_15m.reset_index()
                        date_col = 'Date' if 'Date' in future_15m_reset.columns else 'index'
                        if date_col in future_15m_reset.columns:
                            # API 返回 UTC 时间，+8h 转为北京时间后格式化
                            future_15m_reset[date_col] = (future_15m_reset[date_col] + pd.Timedelta(hours=8)).dt.strftime('%Y-%m-%d %H:%M:%S')
                            future_15m_reset.rename(columns={date_col: 'datetime'}, inplace=True)
                        
                        future_15m_reset.columns = [str(c).lower() for c in future_15m_reset.columns]
                        future_15m_kline_list = future_15m_reset.to_dict(orient='records')
                        
                        logger.info(f"Successfully fetched {len(future_15m_kline_list)} 15m future klines")

            except Exception as e:
                logger.error(f"Failed to fetch 15m future data: {e}")

        check_env_changes()

        # --- Fetch derivative data for brale mechanics agent ---
        # 方案A+D：根据分析周期映射 rubik period，用 adjusted_limit 补偿时间跨度
        derivative_data: dict[str, Any] = {}
        try:
            logger.info(f"[{result_id}] Fetching derivative data for mechanics agent...")

            # 确定衍生品拉取周期：取主时间框架，映射到 rubik 可用周期
            deriv_tf = timeframe_for_result
            if "," in deriv_tf:
                deriv_tf = deriv_tf.split(",")[0]  # 多时间框架取第一个
            # 规范化大小写
            deriv_tf_lower = deriv_tf.lower()
            rubik_period = DERIVATIVE_PERIOD_MAP.get(deriv_tf_lower, "1H")

            # 计算 adjusted_limit：保持与 K 线相同的时间跨度
            analysis_minutes = _TIMEFRAME_MINUTES.get(deriv_tf_lower, 60)
            period_minutes = _TIMEFRAME_MINUTES.get(rubik_period.lower(), 60)
            limit_multiplier = max(1, analysis_minutes // period_minutes)
            adjusted_limit = request.kline_count * limit_multiplier
            logger.info(
                f"[{result_id}] Derivative period mapping: {deriv_tf}→{rubik_period} "
                f"(analysis={analysis_minutes}m, rubik={period_minutes}m, "
                f"multiplier={limit_multiplier}, limit={request.kline_count}→{adjusted_limit})"
            )

            # 回测模式下计算 after 时间戳（仅资金费率支持翻页，rubik 端点忽略 after）
            # 使用 _date_str_to_unix_ms 确保 Asia/Shanghai → UTC 时区转换正确，
            # 与其他 API 调用（K线、OI 等）的时区处理保持一致。
            funding_after: int | None = None
            if request.data_method in ("to_end", "date_range") and end_dt_str:
                try:
                    funding_after = market_service._date_str_to_unix_ms(end_dt_str)
                    logger.info(
                        f"[{result_id}] Backtest mode: funding_after={funding_after} (end={end_dt_str})"
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(f"[{result_id}] Failed to parse end_dt_str for after timestamp: {e}")

            # --- 拉取各衍生品数据 ---
            # rubik 端点不支持 after，永远拉最新全量，由 _filter_rubik_to_kline_window 切片
            derivative_data["oi"] = market_service.fetch_open_interest(request.asset)

            derivative_data["oi_history"] = market_service.fetch_open_interest_history(
                request.asset, period=rubik_period, limit=adjusted_limit
            )
            derivative_data["funding_history"] = market_service.fetch_funding_rate_history(
                request.asset, limit=max(24, min(adjusted_limit, 50)), after=funding_after
            )
            derivative_data["long_short_history"] = market_service.fetch_long_short_ratio(
                request.asset, period=rubik_period, limit=adjusted_limit
            )
            derivative_data["taker_volume_history"] = market_service.fetch_taker_volume_ratio(
                request.asset, period=rubik_period, limit=adjusted_limit
            )
            derivative_data["liquidation_orders"] = market_service.fetch_liquidation_orders(
                request.asset
            )

            present = [k for k, v in derivative_data.items() if v is not None]
            logger.info(f"[{result_id}] Derivative data fetched: {len(present)}/{len(derivative_data)} available ({present})")
        except Exception as e:
            logger.warning(f"[{result_id}] Failed to fetch derivative data: {e}")

        engine_config = {
            "decision_agent_version": request.ai_version,
        }
            
        trading_engine = TradingEngine(config=engine_config)

        agent_cfg_dict = settings.get_agent_config()
        graph_cfg_dict = settings.get_graph_config()
        agent_provider = agent_cfg_dict.get("provider")
        graph_provider = graph_cfg_dict.get("provider")

        logger.info(f"[{result_id}] Starting AI analysis with engine config: {engine_config}")
        update_analysis_progress("analyzing", 30, "Running AI analysis...")
        result = await trading_engine.run_analysis(
            df, 
            request.asset, 
            timeframe_for_result,
            derivative_data=derivative_data,
        )
        
        # Inject Result ID and Request Metadata
        result['result_id'] = result_id
        
        # Normalize asset name for consistent display (e.g. "BTC" -> "BTC/USDT")
        try:
            # Use internal method to get standard format (e.g. BTC-USDT)
            normalized_symbol = market_service._convert_symbol(request.asset)
            # Convert to display format (BTC/USDT)
            display_asset_name = normalized_symbol.replace("-", "/")
        except Exception:
            # Fallback to original input
            display_asset_name = request.asset

        result['asset'] = display_asset_name
        result['asset_name'] = display_asset_name
        
        result['timeframe'] = timeframe_for_result
        result['multi_timeframe_mode'] = request.multi_timeframe_mode
        if request.multi_timeframe_mode:
            result['timeframes'] = request.timeframes
            # 多周期模式下，data_length 使用主周期（第一个）的数据长度
            if isinstance(df, dict) and request.timeframes:
                 first_tf = request.timeframes[0]
                 if first_tf in df:
                     result['data_length'] = len(df[first_tf])
                 else:
                     result['data_length'] = 0
            else:
                 result['data_length'] = 0
        else:
            # 单周期模式
            result['data_length'] = len(df) if hasattr(df, '__len__') else 0
        
        # 哈雷酱添加：注入未来验证数据
        if future_kline_list:
            result['future_kline_data'] = future_kline_list
            result['future_kline_chart_base64'] = future_kline_chart_base64
            
        # 注入强制获取的 15m 验证数据
        if future_15m_kline_list:
            result['future_15m_kline_data'] = future_15m_kline_list
            result['future_15m_chart_base64'] = future_15m_chart_base64
        
        # Determine analysis time display
        analysis_time_display = None
        if request.data_method == "to_end" and end_dt_str:
            analysis_time_display = end_dt_str
        elif request.data_method == "date_range" and end_dt_str:
            analysis_time_display = f"{start_dt_str} to {end_dt_str}"
        else:
             # For latest, use current time
             analysis_time_display = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        result['analysis_time_display'] = analysis_time_display
        result['data_method_short'] = request.data_method

        # 4. Generate Charts for Frontend (Optional but good for UX)
        # 既然用户不想要综合图表，且 pattern_chart 和 trend_chart 已经在 TradingEngine 中处理，
        # 这里就不再生成 summary_chart 了，避免生成用户不想要的“奇怪图表”。
        result['summary_chart_base64'] = None

        result['llm_config'] = {
            "agent": {
                "provider": agent_provider,
                "name": agent_provider,
                "model": agent_cfg_dict.get("model"),
                "temperature": agent_cfg_dict.get("temperature"),
            },
            "graph": {
                "provider": graph_provider,
                "name": graph_provider,
                "model": graph_cfg_dict.get("model"),
                "temperature": graph_cfg_dict.get("temperature"),
            },
        }

        # 5. Auto-save HTML Report (User Requirement: Automation, No Browser Dependency)
        try:
            from app.services.html_export_service import html_export_service
            saved_path = html_export_service.save_html(result)
            logger.info(f"[{result_id}] HTML report automatically saved to: {saved_path}")
            result['html_report_path'] = saved_path
            update_analysis_progress("completed", 99, f"Report saved: {saved_path}")
        except Exception as e:
            logger.error(f"[{result_id}] Failed to auto-save HTML report: {e}")
            # Do not block response, but log error

        # 6. Save JSON History (For History Recall)
        try:
            history_service.save_result(result_id, result)
        except Exception as e:
             logger.error(f"[{result_id}] Failed to save JSON history: {e}")

        elapsed_time = time.time() - start_time
        logger.info(f"分析任务执行成功 - 总耗时: {elapsed_time:.2f}秒")
        update_analysis_progress("completed", 100, f"分析完成 (耗时: {elapsed_time:.2f}秒)")
        
        # Format response to match expected frontend structure if needed
        # For now return raw result
        result['total_analysis_time'] = f"{elapsed_time:.2f}秒"
        return result
        
    except HTTPException as e:
        detail = getattr(e, "detail", "") or ""
        logger.error(f"[{result_id}] Analysis HTTP error: {detail}")
        update_analysis_progress("error", 0, f"Error: {detail}")
        raise
    except Exception as e:
        logger.exception(f"[{result_id}] Analysis error")
        update_analysis_progress("error", 0, f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{result_id}")
async def get_analysis_history(result_id: str):
    """
    Get historical analysis result by ID.
    """
    result = history_service.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis result not found")
    return result

@router.get("/history")
async def list_analysis_history(limit: int = 20):
    """
    List recent analysis history.
    """
    return history_service.get_history_list(limit)
