"""
PDF API 路由
提供 PDF 文件上传、解析、进度查询等接口
"""

from flask import Blueprint, request, jsonify, Response, current_app
from concurrent.futures import ThreadPoolExecutor
import uuid
import threading
import time
import json

from app.services.pdf_service import pdf_service
from app.models.schemas import (
    UploadResponse, PDFInfoResponse, ParseResponse,
    ProgressInfo, ErrorResponse
)


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

        if file.filename == "":
            return jsonify(ErrorResponse(error="未选择文件").model_dump()), 400

        # 检查文件类型
        if not file.filename.lower().endswith('.pdf'):
            return jsonify(ErrorResponse(error="仅支持 PDF 文件").model_dump()), 400

        print(f"[UPLOAD] 收到文件: {file.filename}, 大小: {file.content_length}")

        # 保存文件
        upload_result = pdf_service.save_upload(file)
        print(f"[UPLOAD] 文件保存到: {upload_result['file_path']}")

        # 获取 PDF 信息
        pdf_info = pdf_service.get_pdf_info(upload_result["file_path"])
        print(f"[UPLOAD] PDF 页数: {pdf_info['num_pages']}")

        # 生成任务 ID
        task_id = str(uuid.uuid4())

        # 初始化任务状态
        update_task_status(
            task_id=task_id,
            status="pending",
            message="文件上传成功，等待解析"
        )

        return jsonify({
            "success": True,
            "task_id": task_id,
            "file_path": upload_result["file_path"],
            "filename": upload_result["filename"],
            "file_size": upload_result["file_size"],
            "pdf_info": pdf_info
        })

    except Exception as e:
        print(f"[UPLOAD ERROR] {str(e)}")
        traceback.print_exc()
        return jsonify(ErrorResponse(error=f"上传失败: {str(e)}").model_dump()), 500


# =======================
# PDF 信息接口
# =======================

@pdf_bp.route("/info/<task_id>", methods=["GET"])
def get_pdf_info(task_id: str):
    """
    获取 PDF 基本信息

    Args:
        task_id: 任务 ID

    Query Params:
        - file_path: 文件路径（必需）

    Response:
        - success: 是否成功
        - task_id: 任务 ID
        - pdf_info: PDF 信息
    """
    try:
        file_path = request.args.get("file_path")
        if not file_path:
            return jsonify(ErrorResponse(error="缺少 file_path 参数", code="MISSING_PARAM").model_dump()), 400

        pdf_info = pdf_service.get_pdf_info(file_path)

        return jsonify({
            "success": True,
            "task_id": task_id,
            "pdf_info": pdf_info
        })

    except Exception as e:
        return jsonify(ErrorResponse(error=str(e)).model_dump()), 500


# =======================
# PDF 解析接口
# =======================

@pdf_bp.route("/parse/<task_id>", methods=["POST"])
def parse_pdf(task_id: str):
    """
    开始解析 PDF（异步）

    Request Body (JSON):
        - file_path: 文件路径（必需）
        - page: 指定页码，可选（不传则解析全部）
        - async: 是否异步执行，默认 true

    Response:
        - success: 是否成功
        - task_id: 任务 ID
        - status: 任务状态
    """
    try:
        data = request.json or {}
        file_path = data.get("file_path")
        page = data.get("page")  # 可选，指定页码
        async_mode = data.get("async", True)

        if not file_path:
            return jsonify(ErrorResponse(error="缺少 file_path 参数", code="MISSING_PARAM").model_dump()), 400

        # 如果指定页码，转换为整数
        if page is not None:
            page = int(page)
            if page < 1:
                return jsonify(ErrorResponse(error="页码必须大于 0", code="INVALID_PAGE").model_dump()), 400

        if async_mode:
            # 异步执行
            update_task_status(task_id, "processing", message="开始解析")

            def parse_task():
                """后台解析任务"""
                try:
                    callback = progress_callback_factory(task_id, 0)
                    result = pdf_service.parse_pdf_by_page(file_path, page, callback)

                    # 更新任务状态
                    with task_lock:
                        task_status[task_id]["status"] = "completed"
                        task_status[task_id]["progress"] = 100
                        task_status[task_id]["message"] = "解析完成"
                        task_status[task_id]["result"] = result

                except Exception as e:
                    with task_lock:
                        task_status[task_id]["status"] = "failed"
                        task_status[task_id]["error"] = str(e)
                        task_status[task_id]["message"] = f"解析失败: {str(e)}"

            executor.submit(parse_task)

            return jsonify({
                "success": True,
                "task_id": task_id,
                "status": "processing",
                "message": "解析任务已提交"
            })
        else:
            # 同步执行
            callback = progress_callback_factory(task_id, 0)
            result = pdf_service.parse_pdf_by_page(file_path, page, callback)

            update_task_status(
                task_id,
                "completed",
                progress=100,
                message="解析完成",
                result=result
            )

            return jsonify({
                "success": True,
                "task_id": task_id,
                "status": "completed",
                "result": result
            })

    except ValueError as e:
        return jsonify(ErrorResponse(error=str(e), code="INVALID_PARAM").model_dump()), 400
    except Exception as e:
        return jsonify(ErrorResponse(error=str(e)).model_dump()), 500


@pdf_bp.route("/parse/all/<task_id>", methods=["POST"])
def parse_pdf_all(task_id: str):
    """
    解析整个 PDF（所有页面）

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

        # 异步执行
        update_task_status(task_id, "processing", message="开始解析全部页面")

        def parse_task():
            """后台解析任务"""
            try:
                pdf_info = pdf_service.get_pdf_info(file_path)
                total_pages = pdf_info["num_pages"]
                callback = progress_callback_factory(task_id, total_pages)

                result = pdf_service.parse_pdf(file_path, callback)

                # 更新任务状态
                with task_lock:
                    task_status[task_id]["status"] = "completed"
                    task_status[task_id]["progress"] = 100
                    task_status[task_id]["total_pages"] = total_pages
                    task_status[task_id]["message"] = "全部页面解析完成"
                    task_status[task_id]["result"] = result

            except Exception as e:
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
# 进度查询接口（SSE）
# =======================

@pdf_bp.route("/progress/<task_id>", methods=["GET"])
def get_progress(task_id: str):
    """
    获取解析进度（SSE 流）

    Args:
        task_id: 任务 ID

    Response:
        - text/event-stream: SSE 格式的进度数据
    """
    def generate():
        """SSE 生成器"""
        last_status = None

        while True:
            status = get_task_status(task_id)

            if status is None:
                yield f"event: error\ndata: {json.dumps({'error': '任务不存在'})}\n\n"
                break

            # 检测状态变化
            if status["status"] != last_status:
                last_status = status["status"]

            # 发送进度数据
            data = {
                "task_id": task_id,
                "status": status["status"],
                "current_page": status["current_page"],
                "total_pages": status["total_pages"],
                "progress": round(status["progress"], 2),
                "message": status["message"]
            }

            yield f"event: progress\ndata: {json.dumps(data)}\n\n"

            # 如果完成或失败，关闭连接
            if status["status"] in ["completed", "failed"]:
                if status.get("result"):
                    yield f"event: result\ndata: {json.dumps(status['result'])}\n\n"
                elif status.get("error"):
                    yield f"event: error\ndata: {json.dumps({'error': status['error']})}\n\n"
                break

            # 等待一段时间
            time.sleep(0.5)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@pdf_bp.route("/progress/poll/<task_id>", methods=["GET"])
def poll_progress(task_id: str):
    """
    轮询获取进度（非 SSE）

    Args:
        task_id: 任务 ID

    Response:
        - JSON 格式的进度数据
    """
    status = get_task_status(task_id)

    if status is None:
        return jsonify(ErrorResponse(error="任务不存在", code="TASK_NOT_FOUND").model_dump()), 404

    return jsonify({
        "task_id": task_id,
        "status": status["status"],
        "current_page": status["current_page"],
        "total_pages": status["total_pages"],
        "progress": round(status["progress"], 2),
        "message": status["message"],
        "result": status.get("result"),
        "error": status.get("error")
    })


# =======================
# 页面图片接口
# =======================

@pdf_bp.route("/image/<task_id>", methods=["GET"])
def get_page_image(task_id: str):
    """
    获取指定页面图片

    Args:
        task_id: 任务 ID

    Query Params:
        - page: 页码
        - file_path: 文件路径

    Response:
        - 图片文件
    """
    try:
        page = request.args.get("page", type=int, default=1)
        file_path = request.args.get("file_path")

        if not file_path:
            return jsonify(ErrorResponse(error="缺少 file_path 参数").model_dump()), 400

        image_path = pdf_service.convert_page_to_image(file_path, page)

        if image_path is None:
            return jsonify(ErrorResponse(error="页面图片生成失败").model_dump()), 500

        from flask import send_from_file
        from pathlib import Path

        full_path = Path(__file__).resolve().parent.parent.parent / image_path.lstrip("/")

        return send_from_file(
            str(full_path),
            mimetype="image/png",
            as_attachment=False
        )

    except Exception as e:
        return jsonify(ErrorResponse(error=str(e)).model_dump()), 500
