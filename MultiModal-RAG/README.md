# MultiModal-RAG Demo 1 - PDF 结构解析器

## 项目简介

本项目是多模态 RAG（Retrieval Augmented Generation）的第一步实现，专注于 PDF 结构解析功能。

使用 `unstructured` 库 + PaddleOCR 解析 PDF 文件，识别并标注文档中的各类元素（标题、段落、表格、图片等），并支持在页面上可视化展示解析结果。

## 功能特性

- [x] PDF 文件上传（拖拽 + 点击）
- [x] PDF 结构解析（使用 unstructured + PaddleOCR）
- [x] 元素类型识别（标题、段落、列表、表格、图片、公式等）
- [x] 页面可视化标注（不同颜色边框标注不同元素）
- [x] 鼠标悬停查看元素详情
- [x] SSE 实时进度推送
- [x] Markdown 文件生成与下载

## 技术栈

**后端**
- Python 3.10+
- Flask + Flask-CORS + Flask-SSE
- Unstructured（PDF 解析）
- PaddleOCR（OCR 识别）
- PyPDF2 + pdf2image

**前端**
- HTML5 + CSS3 + JavaScript (ES6+)
- Bootstrap 5
- jQuery
- Server-Sent Events (SSE)

## 目录结构

```
MultiModal-RAG/
├── backend/                          # 后端项目
│   ├── app/
│   │   ├── __init__.py               # Flask 应用工厂
│   │   ├── config.py                 # 配置文件
│   │   ├── api/
│   │   │   ├── pdf_routes.py         # PDF 上传/解析接口
│   │   │   └── download_routes.py    # Markdown 下载接口
│   │   ├── services/
│   │   │   └── pdf_service.py        # PDF 解析核心服务
│   │   └── models/
│   │       └── schemas.py            # Pydantic 数据模型
│   ├── uploads/                      # 上传文件目录
│   ├── outputs/                      # 输出文件目录
│   │   └── markdown/                 # Markdown 文件
│   ├── static/                       # 静态资源
│   ├── requirements.txt              # Python 依赖
│   └── run.py                        # 启动入口
│
├── frontend/                         # 前端项目
│   ├── index.html                    # 主页面
│   ├── css/
│   │   └── style.css                 # 样式文件
│   └── js/
│       └── app.js                    # 前端逻辑
│
└── MultiModal-demo1.md               # 设计文档
```

## 安装步骤

### 1. 创建 conda 环境（推荐）

```bash
# 创建新环境
conda create -n pdf-parser python=3.10

# 激活环境
conda activate pdf-parser
```

### 2. 安装依赖

```bash
# 进入后端目录
cd backend

# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Poppler（pdf2image 需要）
# Windows: 下载安装 poppler for Windows
# https://github.com/oschwartz10612/poppler-windows/releases/

# 将 poppler 添加到系统 PATH
```

### 3. 安装 PaddleOCR

```bash
# 安装 PaddlePaddle
pip install paddlepaddle==3.0.0

# 安装 PaddleOCR
pip install paddleocr==2.8.0
```

### 4. 安装 Graphviz（可选，用于流程图）

```bash
# Windows: 下载安装 graphviz
# https://graphviz.org/download/

# 添加到系统 PATH
```

## 运行项目

### 1. 启动后端服务

```bash
cd backend
python run.py
```

后端服务将在 `http://localhost:5000` 启动。

### 2. 访问前端

直接在浏览器中打开 `frontend/index.html`，或通过后端访问：
```
http://localhost:5000/
```

## API 接口

| 方法 | 路由 | 功能 |
|------|------|------|
| POST | `/api/pdf/upload` | 上传 PDF 文件 |
| GET | `/api/pdf/info/<task_id>` | 获取 PDF 基本信息 |
| POST | `/api/pdf/parse/all/<task_id>` | 解析全部页面 |
| GET | `/api/pdf/progress/<task_id>` | SSE 进度流 |
| POST | `/api/download/markdown/<task_id>` | 生成 Markdown |
| GET | `/api/download/markdown/<task_id>` | 下载 Markdown |
| GET | `/health` | 健康检查 |

## 使用流程

1. **上传文件**: 拖拽或点击选择 PDF 文件
2. **开始解析**: 点击"开始上传并解析"按钮
3. **查看进度**: 实时查看解析进度（SSE 推送）
4. **查看结果**: 点击"查看结果"按钮
5. **交互查看**:
   - 页面上的彩色边框标注不同元素类型
   - 鼠标悬停显示元素详情
   - 点击可复制内容
6. **下载 Markdown**: 点击下载按钮获取转换后的 Markdown

## 元素类型与颜色

| 元素类型 | 颜色 | 说明 |
|----------|------|------|
| Title | 红色 (#FF6B6B) | 标题 |
| NarrativeText | 青色 (#4ECDC4) | 段落文本 |
| BulletedText | 黄色 (#FFEAA7) | 列表项 |
| Table | 蓝色 (#45B7D1) | 表格 |
| Image | 绿色 (#96CEB4) | 图片 |
| Formula | 紫色 (#DDA0DD) | 公式 |

## 注意事项

1. **首次运行**: 首次解析 PDF 时会下载 PaddleOCR 模型，可能需要一些时间
2. **内存占用**: 解析大型 PDF 文件时内存占用较高
3. **中文支持**: 确保系统已安装中文字体，否则中文可能显示为方块
4. **Poppler**: pdf2image 需要安装 Poppler 库

## 常见问题

### Q: 解析失败怎么办？
A: 检查日志输出，确保：
- PDF 文件未损坏
- Poppler 已正确安装
- 内存充足

### Q: 中文显示为方块？
A: 安装中文字体（如 SimHei 或 Noto Sans CJK）

### Q: SSE 进度不更新？
A: 检查浏览器控制台，确保后端服务正常运行

## 后续计划

- [ ] 支持批量上传
- [ ] 添加表格识别优化
- [ ] 图片内容提取（VLM）
- [ ] 公式识别优化
- [ ] 性能优化（大文件分批处理）

## License

MIT License
