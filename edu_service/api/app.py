"""
定义FastAPI实例
"""
from fastapi import FastAPI

from edu_service.api.chat_router import router
from edu_service.infrastructure.db_client import init_db_engine, dispose_engine
from edu_service.infrastructure.http_client import init_http_client, disposed_http_client


async def lifespan(_: FastAPI):
    """
    fastapi生命周期的回调函数
    """

    # 1. 初始化各种资源
    print("应用启动：初始化数据库引擎与HTTP客户端")
    init_db_engine()
    init_http_client()

    # 2. 真正执行路由请求（/api/）
    yield

    # 3. 释放各种资源
    print("应用关闭：释放数据库引擎与HTTP客户端")
    await dispose_engine()
    await disposed_http_client()


app = FastAPI(
    title="教育智能客服系统",
    description="面向在线教育行业的智能客服：课程咨询 / 订单查询 / 学习进度 / 退费申请 / 工单提交",
    lifespan=lifespan,
)

# 注册路由
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
