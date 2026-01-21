"""
配置文件
包含 Flask 应用配置、路径配置、PDF 解析参数等
"""

import os
from pathlib import Path

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# =======================
# Flask 应用配置
# =======================
class Config:
    """Flask 应用默认配置"""
    # 密钥配置
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

    # 调试模式
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"

    # CORS 配置
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
    CORS_SUPPORTS_CREDENTIALS = True

    # 文件上传配置
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "52428800"))  # 50MB
    UPLOAD_FOLDER = str(BASE_DIR / "uploads" / "temp")
    ALLOWED_EXTENSIONS = {"pdf"}

    # PDF 解析配置
    PDF_STRATEGY = os.getenv("PDF_STRATEGY", "hi_res")  # auto / fast / hi_res / ocr_only
    OCR_LANGUAGES = os.getenv("OCR_LANGUAGES", "chi_sim,eng").split(",")

    # HuggingFace 镜像（国内用户使用）
    HF_ENDPOINT = os.getenv("HF_ENDPOINT", "https://huggingface.co")  # 可改为国内镜像

    # SSE 配置
    SSE_RETRY = int(os.getenv("SSE_RETRY", "3000"))
    SSE_HEADER_NAME = "text/event-stream"


# =======================
# 路径配置
# =======================
def ensure_dirs():
    """确保所有必要目录存在"""
    dirs = [
        BASE_DIR / "uploads" / "temp",
        BASE_DIR / "uploads" / "processed",
        BASE_DIR / "outputs" / "markdown",
        BASE_DIR / "static",
    ]
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)


# =======================
# PDF 元素类型与颜色映射
# =======================
ELEMENT_TYPE_COLORS = {
    "Title": "#FF6B6B",        # 红色 - 标题
    "NarrativeText": "#4ECDC4",  # 青色 - 段落
    "BulletedText": "#FFEAA7",   # 黄色 - 列表项
    "ListItem": "#FFEAA7",       # 黄色 - 编号列表（与 BulletedText 同色）
    "Table": "#45B7D1",         # 蓝色 - 表格
    "Image": "#96CEB4",         # 绿色 - 图片
    "Formula": "#DDA0DD",       # 紫色 - 公式
    "Header": "#A0A0A0",        # 灰色 - 页眉
    "Footer": "#A0A0A0",        # 灰色 - 页脚
    "PageBreak": "#000000",     # 黑色 - 分页符
    "SectionHeader": "#FF9F43", # 橙色 - 章节标题
    "Other": "#CCCCCC",         # 灰色 - 其他
}


def get_element_color(element_type: str) -> str:
    """获取元素类型对应的边框颜色"""
    return ELEMENT_TYPE_COLORS.get(element_type, ELEMENT_TYPE_COLORS.get("Other"))


# 确保目录存在
ensure_dirs()
