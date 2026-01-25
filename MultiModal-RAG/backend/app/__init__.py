"""
Flask 应用工厂
负责创建和配置 Flask 应用实例
"""

from pathlib import Path

from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_sse import sse

from app.config import Config, BASE_DIR


def create_app(config_name: str = "default") -> Flask:
    """
    创建 Flask 应用实例

    Args:
        config_name: 配置名称（default / production）

    Returns:
        Flask 应用实例
    """
    app = Flask(
        __name__,
        static_folder=str(BASE_DIR / "static"),
        static_url_path="/static",
        template_folder=str(BASE_DIR / "templates") if (BASE_DIR / "templates").exists() else None
    )

    # 加载配置
    app.config.from_object(Config)
    app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

    # 初始化 CORS
    CORS(
        app,
        resources={r"/api/*": {"origins": Config.CORS_ORIGINS}},
        supports_credentials=Config.CORS_SUPPORTS_CREDENTIALS
    )

    # 初始化 SSE
    app.register_blueprint(sse, url_prefix="/stream")

    # 注册蓝图
    from app.api.pdf_routes import pdf_bp
    from app.api.download_routes import download_bp

    app.register_blueprint(pdf_bp, url_prefix="/api/pdf")
    app.register_blueprint(download_bp, url_prefix="/api/download")

    # 健康检查接口
    @app.route("/health")
    def health_check():
        """健康检查接口"""
        return {
            "status": "healthy",
            "service": "PDF Parser API",
            "version": "1.0.0"
        }

    # 根路径返回前端页面
    @app.route("/")
    def index():
        """返回前端首页"""
        frontend_dir = BASE_DIR / "frontend"
        frontend_dir = Path(frontend_dir).resolve()
        if (frontend_dir / "index.html").exists():
            return send_from_directory(str(frontend_dir), "index.html")
        return {"message": "PDF Parser API is running", "endpoints": ["/api/pdf/upload", "/api/pdf/parse"]}

    # 提供前端静态文件 (css, js, lib)
    @app.route("/css/<path:filename>")
    def serve_css(filename):
        return send_from_directory(str(BASE_DIR / "frontend" / "css"), filename)

    @app.route("/js/<path:filename>")
    def serve_js(filename):
        return send_from_directory(str(BASE_DIR / "frontend" / "js"), filename)

    @app.route("/lib/<path:filename>")
    def serve_lib(filename):
        return send_from_directory(str(BASE_DIR / "frontend" / "lib"), filename)

    # 提供解析出的图片文件
    @app.route("/outputs/images/<path:filename>")
    def serve_image(filename):
        return send_from_directory(str(BASE_DIR / "outputs" / "images"), filename)

    return app


def create_app_with_config() -> Flask:
    """创建带有默认配置的应用"""
    return create_app("default")
