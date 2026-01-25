"""
下载 API 路由
提供 Markdown 文件下载、预览等接口
"""

from flask import Blueprint, request, jsonify, Response, send_file
from pathlib import Path
import uuid
from datetime import datetime

from app.services.pdf_service import pdf_service
from app.models.schemas import ErrorResponse


# 创建蓝图
download_bp = Blueprint("download", __name__)


def generate_markdown(pages_data: list, pdf_info: dict, task_id: str) -> str:
    """
    生成 Markdown 内容

    Args:
        pages_data: 页面解析数据
        pdf_info: PDF 信息
        task_id: 任务 ID

    Returns:
        str: Markdown 内容
    """
    lines = []

    # 标题
    title = pdf_info.get("metadata", {}).get("title", "") or f"PDF Document - {task_id[:8]}"
    lines.append(f"# {title}\n")

    # 元信息
    lines.append("## Document Information\n")
    lines.append(f"- **Generated At**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **Total Pages**: {pdf_info['num_pages']}")
    lines.append(f"- **File Size**: {pdf_info['file_size'] / 1024:.2f} KB\n")

    lines.append("---\n")

    # 按页展示元素
    for page_data in pages_data:
        page_num = page_data["page"]
        elements = page_data["elements"]

        lines.append(f"## Page {page_num}\n")

        for element in elements:
            elem_type = element.get("type", "Text")
            content = element.get("content", "")

            if elem_type == "Title":
                lines.append(f"### {content}\n")
            elif elem_type == "NarrativeText":
                lines.append(f"{content}\n")
            elif elem_type == "BulletedText":
                lines.append(f"- {content}\n")
            elif elem_type == "ListItem":
                lines.append(f"1. {content}\n")
            elif elem_type == "Table":
                # 表格处理：表格内容已经是 Markdown 格式
                if content.startswith('|'):
                    # Markdown 表格格式
                    lines.append(f"**表格 (Page {page_num})**\n")
                    lines.append(f"{content}\n")
                elif content.startswith('images/') or content.startswith('[表格图片:'):
                    # 图片路径格式（向后兼容）
                    if content.startswith('[表格图片:'):
                        img_path = content.replace('[表格图片: ', '').rstrip(']')
                    else:
                        img_path = content
                    img_filename = img_path.split('/')[-1] if '/' in img_path else img_path
                    lines.append(f"**表格 (Page {page_num})**\n")
                    lines.append(f"![表格图片](/static/images/pdf_pages/{img_filename})\n")
                else:
                    # 纯文本内容
                    lines.append(f"**Table:** {content}\n")
            elif elem_type == "Image":
                # 图片内容已经是 markdown 图片语法，直接输出
                if content.startswith('images/'):
                    img_filename = content.split('/')[-1] if '/' in content else content
                    lines.append(f"![图片](/static/images/pdf_pages/{img_filename})\n")
                else:
                    lines.append(f"{content}\n")
            elif elem_type == "Formula":
                lines.append(f"`{content}`\n")
            else:
                lines.append(f"{content}\n")

        lines.append("\n---\n")

    return "\n".join(lines)


def save_markdown(task_id: str, content: str) -> str:
    """
    保存 Markdown 文件

    Args:
        task_id: 任务 ID
        content: Markdown 内容

    Returns:
        str: 文件保存路径
    """
    output_dir = Path(__file__).resolve().parent.parent.parent / "outputs" / "markdown"
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{task_id}.md"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return str(filepath)


# =======================
# Markdown 下载接口
# =======================

@download_bp.route("/markdown/<task_id>", methods=["POST"])
def create_markdown(task_id: str):
    """
    创建 Markdown 文件

    Request Body (JSON):
        - file_path: PDF 文件路径
        - result: 解析结果（可选，如果不传则重新解析）

    Response:
        - success: 是否成功
        - task_id: 任务 ID
        - markdown_path: Markdown 文件路径
    """
    try:
        data = request.json or {}
        file_path = data.get("file_path")
        result_data = data.get("result")

        if not result_data:
            if not file_path:
                return jsonify(ErrorResponse(error="缺少 file_path 或 result 参数").model_dump()), 400

            # 重新解析
            result = pdf_service.parse_pdf(file_path)
        else:
            result = result_data

        # 提取必要信息
        pdf_info = result.get("pdf_info", {})
        pages = result.get("pages", [])

        # 生成 Markdown
        content = generate_markdown(pages, pdf_info, task_id)

        # 保存文件
        markdown_path = save_markdown(task_id, content)

        return jsonify({
            "success": True,
            "task_id": task_id,
            "markdown_path": markdown_path,
            "message": "Markdown 文件生成成功"
        })

    except Exception as e:
        return jsonify(ErrorResponse(error=str(e)).model_dump()), 500


@download_bp.route("/markdown/<task_id>", methods=["GET"])
def download_markdown(task_id: str):
    """
    下载 Markdown 文件

    Args:
        task_id: 任务 ID

    Response:
        - 附件形式的 Markdown 文件
    """
    try:
        filepath = Path(__file__).resolve().parent.parent.parent / "outputs" / "markdown" / f"{task_id}.md"

        if not filepath.exists():
            return jsonify(ErrorResponse(error="Markdown 文件不存在，请先创建").model_dump()), 404

        return send_file(
            str(filepath),
            mimetype="text/markdown",
            as_attachment=True,
            download_name=f"document_{task_id[:8]}.md"
        )

    except Exception as e:
        return jsonify(ErrorResponse(error=str(e)).model_dump()), 500


@download_bp.route("/markdown/<task_id>/preview", methods=["GET"])
def preview_markdown(task_id: str):
    """
    预览 Markdown 文件内容

    Args:
        task_id: 任务 ID

    Response:
        - Markdown 文件内容
    """
    try:
        filepath = Path(__file__).resolve().parent.parent.parent / "outputs" / "markdown" / f"{task_id}.md"

        if not filepath.exists():
            return jsonify(ErrorResponse(error="Markdown 文件不存在").model_dump()), 404

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        return Response(
            content,
            mimetype="text/markdown"
        )

    except Exception as e:
        return jsonify(ErrorResponse(error=str(e)).model_dump()), 500


@download_bp.route("/markdown/<task_id>", methods=["DELETE"])
def delete_markdown(task_id: str):
    """
    删除 Markdown 文件

    Args:
        task_id: 任务 ID

    Response:
        - success: 是否成功
    """
    try:
        filepath = Path(__file__).resolve().parent.parent.parent / "outputs" / "markdown" / f"{task_id}.md"

        if filepath.exists():
            filepath.unlink()
            return jsonify({
                "success": True,
                "message": "Markdown 文件已删除"
            })
        else:
            return jsonify(ErrorResponse(error="文件不存在").model_dump()), 404

    except Exception as e:
        return jsonify(ErrorResponse(error=str(e)).model_dump()), 500
