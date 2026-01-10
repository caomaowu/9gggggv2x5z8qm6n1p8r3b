from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.models.schemas.analyze import AnalyzeRequest
from app.services.market_data import MarketDataService
from app.services.trading_engine import TradingEngine
from app.services.history_service import history_service
from app.core.progress import update_analysis_progress
from app.utils.id_manager import get_result_id_manager
from app.utils.analysis_log import get_analysis_logger
import logging
import pandas as pd

router = APIRouter()
logger = logging.getLogger(__name__)

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
            
        # 哈雷酱添加：如果是在做回测（to_end 或 date_range），且请求了未来K线，则获取“未来”数据用于验证
        future_kline_list = []
        future_kline_chart_base64 = None
        
        if request.data_method in ["to_end", "date_range"] and request.future_kline_count > 0:
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
                            title=f"未来{len(future_df)}根K线走势 (回测验证)"
                        )
                        
                        # 2. 准备数据列表
                        future_df_reset = future_df.reset_index()
                        # 处理索引列名
                        date_col = 'Date' if 'Date' in future_df_reset.columns else 'index'
                        if date_col in future_df_reset.columns:
                            future_df_reset[date_col] = future_df_reset[date_col].dt.strftime('%Y-%m-%d %H:%M:%S')
                            future_df_reset.rename(columns={date_col: 'datetime'}, inplace=True)
                        
                        # 转换为全小写列名
                        future_df_reset.columns = [str(c).lower() for c in future_df_reset.columns]
                        future_kline_list = future_df_reset.to_dict(orient='records')
                        
                        logger.info(f"Successfully fetched {len(future_kline_list)} future klines for verification")
            except Exception as e:
                logger.warning(f"Failed to fetch future verification data: {e}")
                # 不阻断主流程，只是没有未来数据而已

        # 2. Configure Engine
        engine_config = {
            "decision_agent_version": request.ai_version,
            # Add other config overrides if needed
        }
            
        trading_engine = TradingEngine(config=engine_config)
        
        # 3. Run Analysis
        logger.info(f"[{result_id}] Starting AI analysis with engine config: {engine_config}")
        update_analysis_progress("analyzing", 30, "Running AI analysis...")
        result = await trading_engine.run_analysis(
            df, 
            request.asset, 
            timeframe_for_result
        )
        
        # Inject Result ID and Request Metadata
        result['result_id'] = result_id
        result['asset'] = request.asset
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
        
        # 4. Generate Charts for Frontend (Optional but good for UX)
        # 既然用户不想要综合图表，且 pattern_chart 和 trend_chart 已经在 TradingEngine 中处理，
        # 这里就不再生成 summary_chart 了，避免生成用户不想要的“奇怪图表”。
        result['summary_chart_base64'] = None

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

        logger.info("Analysis completed successfully")
        update_analysis_progress("completed", 100, "Analysis completed")
        
        # Format response to match expected frontend structure if needed
        # For now return raw result
        return result
        
    except Exception as e:
        logger.error(f"[{result_id}] Analysis error: {e}")
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
