"""
PDF 解析服务
负责 PDF 文件上传、信息提取、元素解析等功能
"""

import hashlib
import uuid
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Generator
from datetime import datetime

import numpy as np
from PyPDF2 import PdfReader
from pdf2image import convert_from_path

from app.config import Config, BASE_DIR, get_element_color
from app.models.schemas import (
    ElementInfo, PageElements, PDFInfo, ParseResult
)


# =======================
# 网络配置（解决 HuggingFace 下载问题）
# =======================
def configure_huggingface_proxy():
    """配置 HuggingFace 代理（解决国内网络问题）"""
    import os

    # 检查是否设置了代理
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")

    if proxy:
        print(f"[HF] 检测到代理设置: {proxy}")
    else:
        # 常见代理端口
        common_proxies = [
            "http://127.0.0.1:7890",
            "http://127.0.0.1:7891",
            "http://127.0.0.1:1080",
            "http://127.0.0.1:10809",
        ]

        # 检查常用端口是否可用
        import socket
        for p in common_proxies:
            host = p.split(":")[1].replace("//", "")
            port = int(p.split(":")[2])
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                sock.close()
                if result == 0:
                    print(f"[HF] 发现可用代理: {p}")
                    os.environ["HTTPS_PROXY"] = p
                    os.environ["https_proxy"] = p
                    os.environ["HTTP_PROXY"] = p
                    os.environ["http_proxy"] = p
                    break
            except:
                continue

    # 设置 HuggingFace 镜像
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    # 设置 HF_HOME 到本地目录（避免下载到默认缓存）
    hf_home = str(BASE_DIR / "models" / "huggingface")
    os.environ["HF_HOME"] = hf_home
    os.environ["XDG_CACHE_HOME"] = hf_home

    # 确保目录存在
    Path(hf_home).mkdir(parents=True, exist_ok=True)
    Path(hf_home, "hub").mkdir(parents=True, exist_ok=True)

    print(f"[HF] HuggingFace 缓存目录: {hf_home}")


# 在模块加载时配置代理
configure_huggingface_proxy()


class PDFService:
    """
    PDF 解析服务类

    提供 PDF 文件的：
    - 上传保存
    - 基本信息获取
    - 元素解析（使用 unstructured）
    - 页面图片转换
    """

    def __init__(self):
        self.upload_dir = Path(Config.UPLOAD_FOLDER)
        self.processed_dir = BASE_DIR / "uploads" / "processed"

    def allowed_file(self, filename: str) -> bool:
        """
        检查文件扩展名是否允许

        Args:
            filename: 文件名

        Returns:
            bool: 是否为允许的文件类型
        """
        return "." in filename and filename.rsplit(".", 1)[1].lower() == "pdf"

    def generate_safe_filename(self, original_filename: str) -> str:
        """
        生成安全的文件名（防止文件名冲突）

        Args:
            original_filename: 原始文件名

        Returns:
            str: 安全的文件名
        """
        ext = Path(original_filename).suffix.lower()
        # 使用 UUID 生成唯一标识
        unique_id = uuid.uuid4().hex[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{timestamp}_{unique_id}{ext}"

    def save_upload(self, file_storage) -> Dict[str, Any]:
        """
        保存上传的 PDF 文件

        Args:
            file_storage: Flask 文件对象

        Returns:
            Dict: 包含 file_path, filename, file_size
        """
        if not self.allowed_file(file_storage.filename):
            raise ValueError("不支持的文件类型，仅允许 PDF 文件")

        # 生成安全文件名
        safe_filename = self.generate_safe_filename(file_storage.filename)
        file_path = self.upload_dir / safe_filename

        # 保存文件（确保使用正确的流）
        file_storage.save(str(file_path))

        # 确保文件完全写入
        file_storage.stream.close()

        # 验证文件保存成功
        if not file_path.exists():
            raise ValueError("文件保存失败")

        file_size = file_path.stat().st_size
        if file_size == 0:
            raise ValueError("保存的文件为空")

        return {
            "file_path": str(file_path),
            "filename": safe_filename,
            "original_filename": file_storage.filename,
            "file_size": file_size
        }

    def get_pdf_info(self, file_path: str) -> Dict[str, Any]:
        """
        获取 PDF 基本信息

        Args:
            file_path: PDF 文件路径

        Returns:
            Dict: 包含页数、文件大小、元数据等信息
        """
        from pathlib import Path as FilePath

        # 检查文件是否存在
        if not FilePath(file_path).exists():
            raise ValueError(f"文件不存在: {file_path}")

        file_stat = FilePath(file_path).stat()
        if file_stat.st_size == 0:
            raise ValueError(f"文件为空: {file_path}")

        try:
            reader = PdfReader(file_path)
        except Exception as e:
            raise ValueError(f"PDF 文件读取失败: {str(e)}")

        # 提取元数据
        metadata = {}
        if reader.metadata:
            metadata = {
                "title": reader.metadata.get("/Title", ""),
                "author": reader.metadata.get("/Author", ""),
                "subject": reader.metadata.get("/Subject", ""),
                "creator": reader.metadata.get("/Creator", ""),
                "producer": reader.metadata.get("/Producer", ""),
                "creation_date": str(reader.metadata.get("/CreationDate", "")),
                "modification_date": str(reader.metadata.get("/ModDate", "")),
            }

        return {
            "num_pages": len(reader.pages),
            "file_size": Path(file_path).stat().st_size,
            "metadata": metadata
        }

    def parse_pdf_elements(
        self,
        file_path: str,
        page: Optional[int] = None,
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        解析 PDF 元素（使用 PaddleOCR + 简单布局分析）
        无需 Tesseract，使用 PaddleOCR 进行 OCR

        Args:
            file_path: PDF 文件路径
            page: 指定页码（从 1 开始），None 表示解析所有页
            progress_callback: 进度回调函数

        Returns:
            List: 元素列表，每项包含 type, content, page, coordinates
        """
        from paddleocr import PaddleOCR
        from PIL import Image
        import io

        print(f"[PARSE] 使用 PaddleOCR 解析 PDF...")

        # 初始化 PaddleOCR（支持中英文）
        try:
            ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False)
            print(f"[PARSE] PaddleOCR 初始化成功")
        except Exception as e:
            print(f"[PARSE] PaddleOCR 初始化失败: {e}")
            raise RuntimeError(f"PaddleOCR 初始化失败: {e}")

        # 转换 PDF 页面为图片
        images = convert_from_path(file_path)
        total_pages = len(images)

        if page is not None:
            images = [images[page - 1]] if 1 <= page <= total_pages else []
            if not images:
                raise ValueError(f"页码 {page} 超出范围")

        # 解析所有请求的页面
        parsed_elements = []
        element_id = 1
        processed_pages = 0

        for img_idx, image in enumerate(images):
            current_page = page if page else img_idx + 1
            processed_pages += 1

            if progress_callback:
                progress_callback(processed_pages, len(images), f"正在解析第 {current_page} 页")

            # 使用 PaddleOCR 识别文字
            result = ocr.ocr(np.array(image), cls=True)

            # 处理识别结果
            if result and result[0]:
                for line in result[0]:
                    if len(line) >= 2:
                        coords = line[0]  # 坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                        text = line[1][0]  # 识别文字
                        confidence = line[1][1]  # 置信度

                        if confidence > 0.5 and text.strip():  # 过滤低置信度结果
                            # 计算边界框
                            points = [[int(c[0]), int(c[1])] for c in coords]

                            parsed_elements.append({
                                "id": element_id,
                                "type": "NarrativeText",  # PaddleOCR 只返回文字
                                "content": text.strip(),
                                "page": current_page,
                                "coordinates": {
                                    "points": points,
                                    "system": "pixel"
                                },
                                "metadata": {
                                    "confidence": confidence
                                },
                                "color": get_element_color("NarrativeText")
                            })
                            element_id += 1

            # 同时提取简单布局信息（标题检测）
            # 检测大字体区域作为标题
            width, height = image.size

            parsed_elements.append({
                "id": element_id,
                "type": "Title",
                "content": f"[页面 {current_page}]",
                "page": current_page,
                "coordinates": None,
                "metadata": {},
                "color": get_element_color("Title")
            })
            element_id += 1

        print(f"[PARSE] PaddleOCR 解析完成，共 {len(parsed_elements)} 个元素")

        # 过滤指定页面
        if page is not None:
            parsed_elements = [e for e in parsed_elements if e["page"] == page]

        return parsed_elements

    def convert_page_to_image(
        self,
        file_path: str,
        page: int,
        dpi: int = 150
    ) -> Optional[str]:
        """
        将 PDF 指定页面转换为图片

        Args:
            file_path: PDF 文件路径
            page: 页码（从 1 开始）
            dpi: 图片分辨率

        Returns:
            str: 图片保存路径，失败返回 None
        """
        try:
            # 转换为图片
            images = convert_from_path(file_path, dpi=dpi)

            if page < 1 or page > len(images):
                return None

            # 获取对应页面图片（注意：images 是从 0 开始索引）
            image = images[page - 1]

            # 保存图片
            task_id = Path(file_path).stem.split('_')[0] + "_" + Path(file_path).stem.split('_')[-1] if '_' in Path(file_path).stem else Path(file_path).stem
            image_filename = f"{task_id}_page_{page}.png"
            image_dir = BASE_DIR / "static" / "images"
            image_dir.mkdir(parents=True, exist_ok=True)
            image_path = image_dir / image_filename

            image.save(str(image_path), "PNG")

            return f"/static/images/{image_filename}"

        except Exception as e:
            print(f"转换页面图片失败: {e}")
            return None

    def parse_pdf(
        self,
        file_path: str,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        完整解析 PDF（所有页面）

        Args:
            file_path: PDF 文件路径
            progress_callback: 进度回调函数

        Returns:
            Dict: 包含 pdf_info, pages 等信息
        """
        # 获取 PDF 基本信息
        pdf_info = self.get_pdf_info(file_path)
        total_pages = pdf_info["num_pages"]

        # 解析所有页面元素
        all_elements = self.parse_pdf_elements(file_path, progress_callback=progress_callback)

        # 按页分组
        pages = []
        for page_num in range(1, total_pages + 1):
            page_elements = [e for e in all_elements if e["page"] == page_num]

            # 转换页面为图片
            image_path = self.convert_page_to_image(file_path, page_num)

            pages.append({
                "page": page_num,
                "total_pages": total_pages,
                "elements": page_elements,
                "image_path": image_path
            })

            # 回调进度
            if progress_callback:
                progress_callback(page_num, total_pages, f"正在解析第 {page_num} 页")

        return {
            "pdf_info": pdf_info,
            "pages": pages
        }

    def parse_pdf_by_page(
        self,
        file_path: str,
        page: int,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        解析 PDF 指定页面

        Args:
            file_path: PDF 文件路径
            page: 页码
            progress_callback: 进度回调函数

        Returns:
            Dict: 包含 page, elements, image_path
        """
        # 获取 PDF 信息
        pdf_info = self.get_pdf_info(file_path)

        if page < 1 or page > pdf_info["num_pages"]:
            raise ValueError(f"页码 {page} 超出范围，有效范围 1-{pdf_info['num_pages']}")

        # 解析指定页面元素
        elements = self.parse_pdf_elements(file_path, page=page)

        # 转换页面为图片
        image_path = self.convert_page_to_image(file_path, page)

        if progress_callback:
            progress_callback(page, pdf_info["num_pages"], f"第 {page} 页解析完成")

        return {
            "page": page,
            "total_pages": pdf_info["num_pages"],
            "elements": elements,
            "image_path": image_path
        }


# 创建全局服务实例
pdf_service = PDFService()
