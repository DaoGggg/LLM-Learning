"""
PDF API 路由
使用 MinerU 进行 PDF 结构化解析
"""

from flask import Blueprint, request, jsonify, Response, current_app
from concurrent.futures import ThreadPoolExecutor
import uuid
import threading
import time
import json

from app.models.schemas import ErrorResponse


# 创建蓝图
pdf_bp = Blueprint("pdf", __name__)

# 线程池（用于后台解析）
executor = ThreadPoolExecutor(max_workers=4)

# 任务状态存储（内存中，生产环境建议用 Redis）
task_status = {}
task_lock = threading.Lock()


def update_task_status(
    task_id: str,
    status: str,
    current_page: int = 0,
    total_pages: int = 0,
    progress: float = 0.0,
    message: str = "",
    result: dict = None,
    error: str = None
):
    """更新任务状态"""
    with task_lock:
        task_status[task_id] = {
            "status": status,
            "current_page": current_page,
            "total_pages": total_pages,
            "progress": progress,
            "message": message,
            "result": result,
            "error": error
        }


def get_task_status(task_id: str) -> dict:
    """获取任务状态"""
    with task_lock:
        return task_status.get(task_id, None)


def progress_callback_factory(task_id: str, total_pages: int):
    """创建进度回调函数"""
    def callback(current: int, total: int, message: str = ""):
        progress = (current / total * 100) if total > 0 else 0
        update_task_status(
            task_id=task_id,
            status="processing",
            current_page=current,
            total_pages=total,
            progress=progress,
            message=message
        )
    return callback


# =======================
# 文件上传接口
# =======================

@pdf_bp.route("/upload", methods=["POST"])
def upload_pdf():
    """
    上传 PDF 文件

    Request:
        - multipart/form-data: file (PDF 文件)

    Response:
        - success: 是否成功
        - task_id: 任务 ID
        - file_path: 文件保存路径
        - filename: 文件名
        - file_size: 文件大小
        - pdf_info: PDF 基本信息
    """
    import traceback
    try:
        # 检查是否有文件
        if "file" not in request.files:
            return jsonify(ErrorResponse(error="未上传文件").model_dump()), 400

        file = request.files["file"]

        # 检查文件类型
        if not file.filename.lower().endswith('.pdf'):
            return jsonify(ErrorResponse(error="只支持 PDF 文件").model_dump()), 400

        # 生成任务 ID
        task_id = str(uuid.uuid4())

        # 保存文件
        upload_dir = current_app.config['UPLOAD_FOLDER']
        import os
        os.makedirs(upload_dir, exist_ok=True)

        # 使用原始文件名（替换特殊字符）
        filename = file.filename
        file_path = os.path.join(upload_dir, f"{task_id}_{filename}")
        file.save(file_path)

        # 获取 PDF 信息
        from PyPDF2 import PdfReader
        reader = PdfReader(file_path)
        num_pages = len(reader.pages)
        file_size = os.path.getsize(file_path)

        # 初始化任务状态
        update_task_status(task_id, "pending", total_pages=num_pages)

        response_data = {
            "success": True,
            "task_id": task_id,
            "file_path": file_path,
            "filename": filename,
            "file_size": file_size,
            "pdf_info": {
                "num_pages": num_pages,
                "filename": filename
            }
        }

        print(f"[UPLOAD] 文件已保存: {file_path}")
        return jsonify(response_data)

    except Exception as e:
        import traceback as tb
        tb.print_exc()
        return jsonify(ErrorResponse(error=str(e)).model_dump()), 500


# =======================
# 解析接口
# =======================

@pdf_bp.route("/parse/<task_id>", methods=["POST"])
def parse_pdf(task_id: str):
    """
    使用 MinerU 解析 PDF

    Request Body (JSON):
        - file_path: 文件路径（必需）

    Response:
        - success: 是否成功
        - task_id: 任务 ID
        - status: 任务状态
    """
    try:
        data = request.json or {}
        file_path = data.get("file_path")

        if not file_path:
            return jsonify(ErrorResponse(error="缺少 file_path 参数", code="MISSING_PARAM").model_dump()), 400

        # 检查文件是否存在
        import os
        if not os.path.exists(file_path):
            return jsonify(ErrorResponse(error="文件不存在", code="FILE_NOT_FOUND").model_dump()), 404

        # 异步执行
        update_task_status(task_id, "processing", message="开始使用 MinerU 解析")

        def parse_task():
            """后台解析任务"""
            try:
                from app.services.mineru_service import mineru_service

                callback = lambda current, total, msg: update_task_status(
                    task_id, "processing",
                    current_page=current,
                    total_pages=total or 1,
                    progress=(current / total * 100) if total > 0 else 0,
                    message=msg
                )

                result = mineru_service.parse_pdf(file_path, callback)
                total_pages = result['pdf_info']['num_pages']
                print(f"[MinerU] 解析完成，共 {total_pages} 页")

                # 更新任务状态
                with task_lock:
                    task_status[task_id]["status"] = "completed"
                    task_status[task_id]["progress"] = 100
                    task_status[task_id]["total_pages"] = total_pages
                    task_status[task_id]["message"] = "MinerU 解析完成"
                    task_status[task_id]["result"] = result

            except Exception as e:
                import traceback
                print(f"[MinerU ERROR] {str(e)}")
                traceback.print_exc()
                with task_lock:
                    task_status[task_id]["status"] = "failed"
                    task_status[task_id]["error"] = str(e)
                    task_status[task_id]["message"] = f"解析失败: {str(e)}"

        executor.submit(parse_task)

        return jsonify({
            "success": True,
            "task_id": task_id,
            "status": "processing",
            "message": "解析任务已提交，请通过 /progress/<task_id> 查询进度"
        })

    except Exception as e:
        return jsonify(ErrorResponse(error=str(e)).model_dump()), 500


# =======================
# 进度查询接口
# =======================

@pdf_bp.route("/progress/sse/<task_id>", methods=["GET"])
def progress_sse(task_id: str):
    """Server-Sent Events 进度推送"""
    def generate():
        last_status = None
        while True:
            status = get_task_status(task_id)
            if not status:
                break

            if status["status"] == "completed":
                yield f"data: {json.dumps(status)}\n\n"
                break
            elif status["status"] == "failed":
                yield f"data: {json.dumps(status)}\n\n"
                break

            # 只在状态变化时发送
            if status != last_status:
                yield f"data: {json.dumps(status)}\n\n"
                last_status = status

            time.sleep(0.5)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@pdf_bp.route("/progress/poll/<task_id>", methods=["GET"])
def progress_poll(task_id: str):
    """轮询获取进度"""
    status = get_task_status(task_id)
    if not status:
        return jsonify(ErrorResponse(error="任务不存在", code="TASK_NOT_FOUND").model_dump()), 404
    return jsonify(status)


# =======================
# PDF 信息接口
# =======================

@pdf_bp.route("/info/<task_id>", methods=["GET"])
def get_pdf_info(task_id: str):
    """获取 PDF 文件信息"""
    try:
        status = get_task_status(task_id)
        if not status or not status.get("result"):
            return jsonify(ErrorResponse(error="任务不存在或未完成", code="TASK_NOT_FOUND").model_dump()), 404

        result = status["result"]
        pdf_info = result.get("pdf_info", {})

        return jsonify({
            "success": True,
            "pdf_info": pdf_info,
            "pages": len(result.get("pages", []))
        })

    except Exception as e:
        return jsonify(ErrorResponse(error=str(e)).model_dump()), 500


# =======================
# 健康检查
# =======================

@pdf_bp.route("/health", methods=["GET"])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "service": "PDF Parser",
        "parser": "MinerU"
    })
