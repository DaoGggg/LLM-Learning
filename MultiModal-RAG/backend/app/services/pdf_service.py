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

# 添加 Tesseract 到 PATH（Windows）
if os.name == 'nt':
    tesseract_path = r"D:\Program Files\Tesseract-OCR"
    if tesseract_path not in os.environ.get('PATH', ''):
        os.environ['PATH'] = tesseract_path + ';' + os.environ.get('PATH', '')

# 导入 PyMuPDF（用于图片检测）
try:
    import fitz
    FITZ_AVAILABLE = True
    print(f"[INIT] PyMuPDF 可用，版本: {fitz.__doc__.split()[1] if fitz.__doc__ else 'unknown'}")
except ImportError:
    FITZ_AVAILABLE = False
    print("[INIT] PyMuPDF 不可见，无法检测图片")

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
        progress_callback: Optional[callable] = None,
        total_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        解析 PDF 元素（使用 PaddleOCR + 简单布局分析）
        无需 Tesseract，使用 PaddleOCR 进行 OCR

        Args:
            file_path: PDF 文件路径
            page: 指定页码（从 1 开始），None 表示解析所有页
            progress_callback: 进度回调函数(current, total, message)
            total_pages: 总页数（如果已知，优先使用此值）

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
        # 使用传入的 total_pages 或从 images 获取
        actual_total = total_pages if total_pages is not None else len(images)

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
                progress_callback(processed_pages, actual_total, f"正在解析第 {current_page} 页")

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
            progress_callback: 进度回调函数(current, total, message)

        Returns:
            Dict: 包含 pdf_info, pages 等信息
        """
        # 获取 PDF 基本信息
        pdf_info = self.get_pdf_info(file_path)
        total_pages = pdf_info["num_pages"]

        # 从文件路径生成 task_id（如果未提供）
        task_id = Path(file_path).stem

        print(f"[PARSE] 开始解析 PDF，共 {total_pages} 页")

        # 一次性将所有页面转换为图片（用于前端展示）
        print(f"[PARSE] 转换 PDF 页面为图片...")
        all_images = convert_from_path(file_path, dpi=150)
        print(f"[PARSE] 图片转换完成，共 {len(all_images)} 张")

        # 使用 unstructured 解析 PDF（获取结构化元素）
        print(f"[PARSE] 使用 unstructured 解析结构...")
        all_elements = self._parse_pdf_elements(
            file_path,
            all_images,
            task_id,
            progress_callback=progress_callback,
            total_pages=total_pages
        )
        print(f"[PARSE] 结构解析完成，共 {len(all_elements)} 个元素")

        # 按页分组
        print(f"[PARSE] 整理页面数据...")
        pages = []
        for page_num in range(1, total_pages + 1):
            page_elements = [e for e in all_elements if e["page"] == page_num]

            # 保存页面图片
            image = all_images[page_num - 1]
            task_id = Path(file_path).stem.split('_')[0] + "_" + Path(file_path).stem.split('_')[-1] if '_' in Path(file_path).stem else Path(file_path).stem
            image_filename = f"{task_id}_page_{page_num}.png"
            image_dir = BASE_DIR / "static" / "images"
            image_dir.mkdir(parents=True, exist_ok=True)
            image_path = image_dir / image_filename
            image.save(str(image_path), "PNG")
            image_url = f"/static/images/{image_filename}"

            pages.append({
                "page": page_num,
                "total_pages": total_pages,
                "elements": page_elements,
                "image_path": image_url
            })

            # 回调进度
            if progress_callback:
                progress_callback(page_num, total_pages, f"第 {page_num}/{total_pages} 页处理完成")

        print(f"[PARSE] 全部完成，共 {len(pages)} 页")

        return {
            "pdf_info": pdf_info,
            "pages": pages
        }

    def _parse_pdf_elements(
        self,
        file_path: str,
        images: list,
        task_id: str,
        progress_callback: Optional[callable] = None,
        total_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        使用 unstructured + PaddleOCR 解析 PDF 元素结构
        - unstructured: 识别元素类型（标题、段落、列表等）
        - PaddleOCR: 检测文字位置坐标
        """
        from unstructured.partition.pdf import partition_pdf
        from paddleocr import PaddleOCR
        import re

        print(f"[OCR] 调用 unstructured 进行结构解析...")

        # 1. 使用 unstructured 获取元素类型和文本
        # 尝试多种策略
        elements = []
        strategy_tried = []

        # 策略1: ocr_only + paddleocr（纯 OCR 模式，应该能返回坐标）
        try:
            elements = partition_pdf(
                filename=file_path,
                strategy="ocr_only",
                ocr_engine="paddleocr",
                languages=["chi_sim", "eng"],
                include_metadata=True,
                extract_images_in_pdf=True  # 提取图片元素
            )
            strategy_tried.append("ocr_only+paddleocr")
            print(f"[OCR] ocr_only + paddleocr 策略成功，解析到 {len(elements)} 个元素")
        except Exception as e:
            print(f"[OCR] ocr_only 策略失败: {e}")

        # 策略2: hi_res + paddleocr（如果 ocr_only 失败）
        if not elements:
            try:
                elements = partition_pdf(
                    filename=file_path,
                    strategy="hi_res",
                    ocr_engine="paddleocr",
                    languages=["chi_sim", "eng"],
                    include_metadata=True,
                    extract_images_in_pdf=True,  # 提取图片元素
                    skip_infer_table_types=[]  # 不跳过任何类型
                )
                strategy_tried.append("hi_res+paddleocr")
                print(f"[OCR] hi_res + paddleocr 策略成功，解析到 {len(elements)} 个元素")
            except Exception as e:
                print(f"[OCR] hi_res 策略失败: {e}")

        # 策略3: auto（最后手段，不返回坐标）
        if not elements:
            try:
                elements = partition_pdf(
                    filename=file_path,
                    strategy="auto",
                    include_metadata=True
                )
                strategy_tried.append("auto")
                print(f"[OCR] auto 策略解析到 {len(elements)} 个元素（可能无坐标）")
            except Exception as e:
                print(f"[OCR] 所有策略都失败: {e}")
                raise RuntimeError(f"PDF 解析失败: {e}")

        # 2. 使用 PyMuPDF 检测图片区域（作为补充）
        image_areas = []
        if FITZ_AVAILABLE:
            try:
                pdf_doc = fitz.open(file_path)
                image_areas = []  # 存储图片区域坐标

                for page_num_fitz, page in enumerate(pdf_doc, start=1):
                    page_images = page.get_images(full=True)
                    for img_index, img in enumerate(page_images):
                        xref = img[0]
                        # 获取图片在页面上的位置
                        img_list = page.get_image_rects(xref)
                        if img_list:
                            rect = img_list[0]
                            image_areas.append({
                                "page": page_num_fitz,
                                "x0": rect.x0,
                                "y0": rect.y0,
                                "x1": rect.x1,
                                "y1": rect.y1,
                                "width": rect.width,
                                "height": rect.height
                            })

                if image_areas:
                    print(f"[OCR] 检测到 {len(image_areas)} 个图片区域")

                pdf_doc.close()
            except Exception as e:
                print(f"[OCR] 图片检测失败: {e}")
                image_areas = []
        else:
            print("[OCR] PyMuPDF 不可用，无法检测图片")

        # 2. 初始化 PaddleOCR 获取坐标（作为后备）
        print(f"[OCR] 初始化 PaddleOCR 获取坐标...")
        ocr = None
        try:
            ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False)
        except Exception as e:
            print(f"[OCR] PaddleOCR 初始化失败: {e}，将使用 unstructured 坐标")

        # 3. 按页处理
        parsed_elements = []
        element_id = 1

        def clean_text(text: str) -> str:
            """清理OCR识别的文本，移除乱码但保留标点符号"""
            if not text:
                return ""
            # 尝试解码为 UTF-8，处理常见编码问题
            try:
                # 处理 PaddleOCR 可能返回的编码问题
                text = text.encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
            except:
                pass
            # 只移除非打印控制字符，保留所有标点符号
            import re
            # 保留：中文、英文、数字、空格、换行、以及常用标点符号
            cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
            # 清理多余的空白字符（但保留换行）
            cleaned = re.sub(r'[ \t]+', ' ', cleaned)  # 空格和制表符合并
            cleaned = re.sub(r'\n\s*', '\n', cleaned)  # 清理行尾空格
            cleaned = cleaned.strip()
            return cleaned

        for page_num in range(1, (total_pages or 1) + 1):
            if progress_callback:
                progress_callback(page_num, total_pages or 1, f"正在解析第 {page_num} 页")

            page_image = images[page_num - 1]
            page_img_width, page_img_height = page_image.size

            # 获取当前页的 unstructured 元素
            page_elements = [
                e for e in elements
                if e.metadata and e.metadata.page_number == page_num
            ]

            # 如果没有 page_number，全部放到第一页
            if not page_elements:
                page_elements = elements

            # 使用 PaddleOCR 检测当前页文字坐标（用于后备匹配）
            ocr_results = []
            if ocr:
                try:
                    ocr_result = ocr.ocr(np.array(page_image), cls=True)
                    if ocr_result and ocr_result[0]:
                        for line in ocr_result[0]:
                            if len(line) >= 2:
                                text = clean_text(line[1][0].strip())
                                if text:
                                    coords = line[0]
                                    points = [[int(c[0]), int(c[1])] for c in coords]
                                    min_y = min(p[1] for p in points)
                                    max_y = max(p[1] for p in points)
                                    ocr_results.append({
                                        "text": text,
                                        "points": points,
                                        "min_y": min_y,
                                        "max_y": max_y,
                                        "confidence": line[1][1]
                                    })
                except Exception as e:
                    print(f"[OCR] PaddleOCR 检测失败: {e}")

            # 处理每个 unstructured 元素
            for element_idx, element in enumerate(page_elements):
                # 获取元素类型
                elem_type = type(element).__name__
                elem_type = self._map_element_type(elem_type)

                # 获取文本内容
                content = clean_text(str(element.text).strip()) if element.text else ""

                # 图片元素（Figure/Image）即使没有文本也需要处理
                is_image_element = elem_type == "Image" and type(element).__name__ == "Figure"
                if not content and not is_image_element:
                    continue

                # 如果是图片元素，设置默认内容
                if is_image_element and not content:
                    content = "[图片]"

                # 尝试获取坐标
                bbox = None
                confidence = 1.0

                # 检查 unstructured 是否有坐标信息
                if hasattr(element.metadata, 'coordinates') and element.metadata.coordinates:
                    coords = element.metadata.coordinates
                    if hasattr(coords, 'points') and coords.points:
                        raw_points = coords.points

                        # 获取 layout 尺寸
                        layout_width = None
                        layout_height = None
                        if hasattr(coords, 'layout_width') and coords.layout_width:
                            layout_width = coords.layout_width
                            layout_height = coords.layout_height
                        elif hasattr(element.metadata, 'layout_width') and element.metadata.layout_width:
                            layout_width = element.metadata.layout_width
                            layout_height = element.metadata.layout_height

                        if layout_width and layout_height:
                            # 计算缩放比例
                            scale_x = page_img_width / layout_width
                            scale_y = page_img_height / layout_height

                            # 缩放坐标
                            scaled_points = [
                                [int(p[0] * scale_x),
                                 int(p[1] * scale_y)]
                                for p in raw_points
                            ]
                            bbox = {"points": scaled_points, "system": "pixel"}
                            confidence = 0.9

                # 如果没有 unstructured 坐标，直接使用对应索引的 PaddleOCR 结果
                # PaddleOCR 检测结果已按 Y 坐标排序
                if not bbox and ocr and ocr_results and element_idx < len(ocr_results):
                    ocr_item = ocr_results[element_idx]
                    bbox = {"points": ocr_item["points"], "system": "pixel"}
                    confidence = ocr_item["confidence"]

                parsed_elements.append({
                    "id": element_id,
                    "type": elem_type,
                    "content": content,
                    "page": page_num,
                    "coordinates": bbox,
                    "metadata": {"confidence": confidence},
                    "color": get_element_color(elem_type)
                })
                element_id += 1

            # 额外添加 PaddleOCR 检测到但未被匹配的元素
            if ocr and ocr_results:
                used_indices = set()
                for elem in page_elements:
                    elem_text = str(elem.text).strip() if elem.text else ""
                    if elem_text:
                        for ocr_idx, ocr_item in enumerate(ocr_results):
                            if ocr_idx in used_indices:
                                continue
                            ocr_clean = ocr_item["text"].replace(" ", "").replace("\n", "")
                            elem_clean = elem_text.replace(" ", "").replace("\n", "")
                            if ocr_clean == elem_clean or ocr_clean in elem_clean or elem_clean in ocr_clean:
                                used_indices.add(ocr_idx)
                                break

                # 合并相邻的 OCR 结果（垂直方向上相邻的行合并为一个框）
                def merge_adjacent_boxes(ocr_items):
                    """合并垂直方向相邻的文本框"""
                    if not ocr_items:
                        return []

                    merged = []
                    current_group = [ocr_items[0]]

                    for i in range(1, len(ocr_items)):
                        current = ocr_items[i]
                        prev = current_group[-1]

                        # 检查是否与上一行相邻（Y坐标接近）
                        prev_max_y = prev["max_y"]
                        current_min_y = current["min_y"]

                        # 如果行间距小于阈值，合并
                        if current_min_y - prev_max_y < 25:  # 25像素内的行视为同一段落
                            current_group.append(current)
                        else:
                            # 保存当前组，开始新组
                            merged.append(current_group)
                            current_group = [current]

                    # 保存最后一个组
                    if current_group:
                        merged.append(current_group)

                    return merged

                # 合并相邻框
                merged_groups = merge_adjacent_boxes(ocr_results)

                # 将合并后的组转换为元素
                for group in merged_groups:
                    if len(group) == 1:
                        # 单行，直接使用
                        ocr_item = group[0]
                        if ocr_item["text"] and ocr_item["text"].strip():
                            parsed_elements.append({
                                "id": element_id,
                                "type": "NarrativeText",
                                "content": ocr_item["text"],
                                "page": page_num,
                                "coordinates": {"points": ocr_item["points"], "system": "pixel"},
                                "metadata": {"confidence": ocr_item["confidence"]},
                                "color": get_element_color("NarrativeText")
                            })
                            element_id += 1
                    else:
                        # 多行，合并
                        all_text = " ".join([item["text"] for item in group])

                        # 计算合并后的边界框
                        all_points = []
                        for item in group:
                            all_points.extend(item["points"])

                        min_x = min(p[0] for p in all_points)
                        max_x = max(p[0] for p in all_points)
                        min_y = min(p[1] for p in all_points)
                        max_y = max(p[1] for p in all_points)

                        # 创建合并后的多边形框
                        merged_points = [
                            [min_x, min_y],
                            [max_x, min_y],
                            [max_x, max_y],
                            [min_x, max_y]
                        ]

                        # 计算平均置信度
                        avg_confidence = sum(item["confidence"] for item in group) / len(group)

                        parsed_elements.append({
                            "id": element_id,
                            "type": "NarrativeText",
                            "content": all_text,
                            "page": page_num,
                            "coordinates": {"points": merged_points, "system": "pixel"},
                            "metadata": {"confidence": avg_confidence, "merged": True, "line_count": len(group)},
                            "color": get_element_color("NarrativeText")
                        })
                        element_id += 1

            # 添加图片元素（将 PDF 坐标转换为图片像素坐标）
            # 只有当 unstructured 没有检测到图片元素时，才使用 PyMuPDF 补充
            existing_image_types = set(elem["type"] for elem in parsed_elements)
            has_unstructured_image = "Image" in existing_image_types

            if image_areas and not has_unstructured_image:
                # 计算坐标转换比例（pdf2image 的 DPI 可能与 PDF 默认 72 DPI 不同）
                pdf_dpi = 72  # PDF 默认 DPI
                img_dpi = 150  # pdf2image 使用的 DPI
                scale = img_dpi / pdf_dpi

                page_images_areas = [img for img in image_areas if img["page"] == page_num]
                for img_area in page_images_areas:
                    # 转换坐标
                    x0 = img_area["x0"] * scale
                    y0 = img_area["y0"] * scale
                    x1 = img_area["x1"] * scale
                    y1 = img_area["y1"] * scale

                    # 只有足够大的区域才视为图片
                    if (x1 - x0) > 30 and (y1 - y0) > 30:
                        image_points = [
                            [int(x0), int(y0)],
                            [int(x1), int(y0)],
                            [int(x1), int(y1)],
                            [int(x0), int(y1)]
                        ]

                        # 生成图片文件名
                        img_filename = f"{task_id}_p{page_num}_img{element_id}.png"
                        img_output_dir = Path(BASE_DIR) / "outputs" / "images"
                        img_output_dir.mkdir(parents=True, exist_ok=True)
                        img_filepath = img_output_dir / img_filename

                        # 裁剪并保存图片
                        try:
                            from PIL import Image as PILImage
                            left, top, right, bottom = int(x0), int(y0), int(x1), int(y1)
                            # 确保坐标在范围内
                            left = max(0, left)
                            top = max(0, top)
                            right = min(page_img_width, right)
                            bottom = min(page_img_height, bottom)
                            if right > left and bottom > top:
                                cropped = page_image.crop((left, top, right, bottom))
                                cropped.save(img_filepath, "PNG")
                                image_content = f"![Image](outputs/images/{img_filename})"
                                print(f"[OCR] 保存图片: {img_filename}")
                            else:
                                image_content = f"[图片区域 {img_area['width']:.0f}x{img_area['height']:.0f}]"
                        except Exception as e:
                            print(f"[OCR] 保存图片失败: {e}")
                            image_content = f"[图片区域 {img_area['width']:.0f}x{img_area['height']:.0f}]"

                        parsed_elements.append({
                            "id": element_id,
                            "type": "Image",
                            "content": image_content,
                            "page": page_num,
                            "coordinates": {"points": image_points, "system": "pixel"},
                            "metadata": {},
                            "color": get_element_color("Image")
                        })
                        element_id += 1

            # 添加页面分隔标记
            parsed_elements.append({
                "id": element_id,
                "type": "Title",
                "content": f"[页面 {page_num}]",
                "page": page_num,
                "coordinates": None,
                "metadata": {},
                "color": get_element_color("Title")
            })
            element_id += 1

        return parsed_elements

    def _map_element_type(self, elem_type: str) -> str:
        """
        映射 unstructured 元素类型到标准类型

        Args:
            elem_type: unstructured 元素类型

        Returns:
            str: 标准元素类型
        """
        type_mapping = {
            "Title": "Title",
            "NarrativeText": "NarrativeText",
            "BulletedText": "BulletedText",
            "ListItem": "ListItem",
            "Table": "Table",
            "Figure": "Image",
            "Formula": "Formula",
            "Header": "Header",
            "Footer": "Footer",
            "PageBreak": "PageBreak",
            "SectionHeader": "SectionHeader",
            "CompositeElement": "NarrativeText",
            "Text": "NarrativeText",
            "UnstructuredText": "NarrativeText",
        }
        return type_mapping.get(elem_type, "NarrativeText")

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
