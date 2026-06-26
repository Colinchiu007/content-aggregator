"""
Content-Aggregator Celery 集成

复用 trendscope 的统一 Celery 实例，不创建独立 worker。
所有任务以 ca_ 前缀命名，与 trendscope 的 ts_ 任务区分。

使用方式:
    celery -A trendscope.crawler.celery_app worker -l info -c 4

此模块被 trendscope.crawler.tasks 自动导入（通过 sys.path），
无需单独启动 worker 进程。
"""
import warnings

try:
    from trendscope.crawler.celery_app import app as celery_app
except ImportError:
    warnings.warn(
        "trendscope 未安装，Celery 任务注册跳过。"
        "请先安装 trendscope: pip install -e /path/to/trendscope"
    )
    raise

# 注册 content-aggregator 的任务（通过模块导入）
from . import tasks  # noqa: F401
