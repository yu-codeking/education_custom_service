"""
启动uvicorn web服务
用法（项目根目录下执行）：uv run python -m edu_service.main
"""
import uvicorn

from edu_service.config.settings import settings

if __name__ == '__main__':

    uvicorn.run(app="edu_service.api.app:app", host=settings.app_host, port=settings.app_port)
