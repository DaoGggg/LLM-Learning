"""
应用启动入口
"""

import os

# 设置环境变量（根据需要调整）
os.environ.setdefault("FLASK_ENV", "development")

from app import create_app

# 创建应用
app = create_app()

if __name__ == "__main__":
    print("=" * 50)
    print("PDF Parser API 启动中...")
    print("=" * 50)
    print(f"访问地址: http://localhost:5000")
    print(f"API 端点:")
    print(f"  - POST /api/pdf/upload          : 上传 PDF")
    print(f"  - GET  /api/pdf/info/<task_id>  : 获取 PDF 信息")
    print(f"  - POST /api/pdf/parse/<task_id> : 解析 PDF")
    print(f"  - GET  /api/pdf/progress/<task_id> : SSE 进度流")
    print(f"  - GET  /health                  : 健康检查")
    print("=" * 50)

    # 启动服务器
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        threaded=True
    )
