/**
 * PDF 结构解析器 - 前端逻辑
 * MultiModal RAG Demo 1
 */

(function() {
    'use strict';

    // API 基础地址
    const API_BASE = '';

    // 全局状态
    let state = {
        taskId: null,
        filePath: null,
        fileName: null,
        fileSize: 0,
        currentFile: null,  // 保存文件对象
        currentPage: 1,
        totalPages: 0,
        elements: [],
        imagePath: null,
        parseResult: null,
        isParsing: false
    };

    // DOM 元素
    const elements = {
        // 文件上传
        dropZone: document.getElementById('dropZone'),
        fileInput: document.getElementById('fileInput'),
        selectFileBtn: document.getElementById('selectFileBtn'),  // 新增
        fileInfo: document.getElementById('fileInfo'),
        fileName: document.getElementById('fileName'),
        fileSize: document.getElementById('fileSize'),
        uploadBtn: document.getElementById('uploadBtn'),

        // 进度
        progressCard: document.getElementById('progressCard'),
        progressBar: document.getElementById('progressBar'),
        progressMessage: document.getElementById('progressMessage'),
        pageInfo: document.getElementById('pageInfo'),
        viewResultBtn: document.getElementById('viewResultBtn'),
        cancelBtn: document.getElementById('cancelBtn'),

        // 图例
        legendCard: document.getElementById('legendCard'),

        // 结果展示
        resultCard: document.getElementById('resultCard'),
        emptyState: document.getElementById('emptyState'),
        pdfImage: document.getElementById('pdfImage'),
        annotationLayer: document.getElementById('annotationLayer'),
        pageIndicator: document.getElementById('pageIndicator'),
        currentPage: document.getElementById('currentPage'),
        totalPages: document.getElementById('totalPages'),
        prevPageBtn: document.getElementById('prevPageBtn'),
        nextPageBtn: document.getElementById('nextPageBtn'),

        // 元素详情
        elementDetail: document.getElementById('elementDetail'),
        detailType: document.getElementById('detailType'),
        detailPage: document.getElementById('detailPage'),
        detailContent: document.getElementById('detailContent'),

        // 下载
        downloadMdBtn: document.getElementById('downloadMdBtn')
    };

    // =======================
    // 初始化
    // =======================
    function init() {
        // 文件输入事件
        elements.fileInput.addEventListener('change', handleFileSelect);

        // 上传按钮
        elements.uploadBtn.addEventListener('click', uploadAndParse);

        // 选择文件按钮（直接触发 input）
        if (elements.selectFileBtn) {
            elements.selectFileBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                elements.fileInput.click();
            });
        }

        // 拖拽上传（只处理拖拽，不处理点击）
        setupDropZone();

        // 页面导航
        elements.prevPageBtn.addEventListener('click', () => changePage(-1));
        elements.nextPageBtn.addEventListener('click', () => changePage(1));

        // 下载按钮
        elements.downloadMdBtn.addEventListener('click', downloadMarkdown);
    }

    // =======================
    // 拖拽上传
    // =======================
    function setupDropZone() {
        // 只处理拖拽事件，不再处理点击事件（点击由 selectFileBtn 处理）

        // 拖拽进入
        elements.dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            elements.dropZone.classList.add('dragover');
        });

        // 拖拽离开
        elements.dropZone.addEventListener('dragleave', () => {
            elements.dropZone.classList.remove('dragover');
        });

        // 放下文件
        elements.dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            elements.dropZone.classList.remove('dragover');

            const files = e.dataTransfer.files;
            if (files.length > 0 && files[0].name.endsWith('.pdf')) {
                handleFile(files[0]);
            } else {
                showToast('error', '错误', '请上传 PDF 文件');
            }
        });
    }

    function handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            handleFile(file);
        }
    }

    function handleFile(file) {
        // 重置状态
        resetUploadState(false);

        // 保存文件名和大小用于显示
        state.fileName = file.name;
        state.fileSize = file.size;

        // 显示文件信息
        elements.fileName.textContent = file.name;
        elements.fileSize.textContent = formatFileSize(file.size);
        elements.fileInfo.style.display = 'block';
        elements.uploadBtn.disabled = false;

        showToast('success', '文件已选择', file.name);
    }

    // =======================
    // 上传和解析
    // =======================
    async function uploadAndParse() {
        // 直接从 input 获取文件
        const file = elements.fileInput.files[0];
        if (!file) {
            showToast('warning', '提示', '请先选择文件');
            return;
        }

        // 防止重复点击
        if (state.isParsing) {
            return;
        }
        state.isParsing = true;
        elements.uploadBtn.disabled = true;
        elements.dropZone.style.pointerEvents = 'none';

        try {
            // 调试：确认文件状态
            console.log('[UPLOAD DEBUG] 文件名:', file.name);
            console.log('[UPLOAD DEBUG] 文件大小:', file.size);
            console.log('[UPLOAD DEBUG] 文件类型:', file.type);

            // 1. 上传文件
            showToast('info', '上传中', '正在上传文件...');

            // 使用 FileReader 读取文件内容
            const fileContent = await readFileAsArrayBuffer(file);

            // 通过 Blob 上传（更可靠）
            const blob = new Blob([fileContent], { type: file.type });
            const formData = new FormData();
            formData.append('file', blob, file.name);

            const uploadResponse = await fetch(API_BASE + '/api/pdf/upload', {
                method: 'POST',
                body: formData
            });

            if (!uploadResponse.ok) {
                const errorData = await uploadResponse.json().catch(() => ({}));
                throw new Error(errorData.error || '上传失败');
            }

            const uploadData = await uploadResponse.json();

            state.taskId = uploadData.task_id;
            state.filePath = uploadData.file_path;
            state.totalPages = uploadData.pdf_info.num_pages;

            // 清空 input
            elements.fileInput.value = '';

            showToast('success', '上传成功', '开始解析...');

            // 2. 开始解析
            startParsing();

        } catch (error) {
            console.error('上传失败:', error);
            state.isParsing = false;
            elements.uploadBtn.disabled = false;
            elements.dropZone.style.pointerEvents = 'auto';
            showToast('error', '错误', error.message);
            resetUploadState();
        }
    }

    // 辅助函数：读取文件为 ArrayBuffer
    function readFileAsArrayBuffer(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsArrayBuffer(file);
        });
    }

    function startParsing() {
        // 显示进度卡片
        elements.progressCard.style.display = 'block';
        elements.legendCard.style.display = 'block';
        elements.uploadBtn.disabled = true;

        // 开始 SSE 监听进度
        startProgressListener();

        // 使用 MinerU 解析
        const apiEndpoint = `/api/pdf/parse/${state.taskId}`;

        showToast('info', '使用 MinerU 解析引擎', '开始解析...');

        // 发送解析请求
        fetch(API_BASE + apiEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                file_path: state.filePath
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast('success', '解析任务已提交', '请查看进度');
            } else {
                throw new Error(data.error || '解析请求失败');
            }
        })
        .catch(error => {
            console.error('解析请求失败:', error);
            showToast('error', '错误', error.message);
        });
    }

    // =======================
    // SSE 进度监听
    // =======================
    let eventSource = null;
    let pollInterval = null;

    function startProgressListener() {
        // 关闭现有的 SSE 或轮询
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }

        // 使用轮询方式（比 SSE 更可靠，避免长连接超时问题）
        pollInterval = setInterval(async () => {
            try {
                const response = await fetch(API_BASE + '/api/pdf/progress/poll/' + state.taskId);
                if (response.ok) {
                    const data = await response.json();
                    updateProgress(data);

                    // 如果完成，处理结果
                    if (data.status === 'completed' && data.result) {
                        clearInterval(pollInterval);
                        pollInterval = null;
                        handleParseComplete(data);
                    } else if (data.status === 'failed') {
                        clearInterval(pollInterval);
                        pollInterval = null;
                        showToast('error', '错误', data.message || '解析失败');
                    }
                }
            } catch (error) {
                console.error('轮询进度失败:', error);
            }
        }, 500); // 每 500ms 轮询一次
    }

    function updateProgress(data) {
        const progress = Math.round(data.progress);

        elements.progressBar.style.width = progress + '%';
        elements.progressBar.textContent = progress + '%';
        elements.progressMessage.textContent = data.message || '';
        elements.pageInfo.textContent = `${data.current_page} / ${data.total_pages} 页`;

        state.currentPage = data.current_page;
        state.totalPages = data.total_pages;

        // 解析完成后启用查看结果按钮
        if (data.status === 'completed') {
            elements.viewResultBtn.disabled = false;
            showToast('success', '解析完成', '可以查看结果了');
        }
    }

    function handleParseComplete(result) {
        state.parseResult = result.result;
        state.elements = result.result.pages;
        state.totalPages = result.result.pages.length;

        // 停止轮询
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }

        showToast('success', '解析完成', '共 ' + state.totalPages + ' 页');

        // 启用查看结果按钮
        elements.viewResultBtn.disabled = false;

        // 重置为第一页（避免显示最后一页）
        state.currentPage = 1;

        // 自动显示结果
        elements.viewResultBtn.click();
    }

    // =======================
    // 查看结果
    // =======================
    elements.viewResultBtn.addEventListener('click', () => {
        showResult();
    });

    function showResult() {
        elements.emptyState.style.display = 'none';
        elements.resultCard.style.display = 'block';

        // 更新页面信息
        updatePageInfo();

        // 加载第一页
        loadPage(state.currentPage);
    }

    function updatePageInfo() {
        elements.currentPage.textContent = state.currentPage;
        elements.totalPages.textContent = state.totalPages;

        // 更新按钮状态
        elements.prevPageBtn.disabled = state.currentPage <= 1;
        elements.nextPageBtn.disabled = state.currentPage >= state.totalPages;
    }

    function loadPage(pageNum) {
        const pageData = state.parseResult.pages.find(p => p.page === pageNum);
        if (!pageData) {
            showToast('error', '错误', '页面数据不存在');
            return;
        }

        state.currentPage = pageNum;
        state.imagePath = pageData.image_path;
        state.currentElements = pageData.elements;

        // 更新页面信息
        updatePageInfo();

        // 加载页面图片
        if (pageData.image_path) {
            elements.pdfImage.src = pageData.image_path;
            elements.pdfImage.onload = () => {
                // 图片加载完成后绘制标注框
                drawAnnotations(pageData.elements);
            };

            // 点击图片显示坐标（调试用）
            elements.pdfImage.onclick = (e) => {
                const rect = e.target.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const naturalWidth = elements.pdfImage.naturalWidth;
                const naturalHeight = elements.pdfImage.naturalHeight;
                const naturalX = Math.round(x * (naturalWidth / rect.width));
                const naturalY = Math.round(y * (naturalHeight / rect.height));
                console.log(`[CLICK] 像素: (${Math.round(x)}, ${Math.round(y)}) / 自然: (${naturalX}, ${naturalY})`);
                console.log(`  百分比: X=${(naturalX/naturalWidth*100).toFixed(1)}%, Y=${(naturalY/naturalHeight*100).toFixed(1)}%`);
                console.log(`  图片尺寸: ${Math.round(rect.width)}x${Math.round(rect.height)}`);
                console.log(`  自然尺寸: ${naturalWidth}x${naturalHeight}`);
            };
        } else {
            showToast('warning', '警告', '页面图片生成失败');
        }
    }

    function changePage(delta) {
        const newPage = state.currentPage + delta;
        if (newPage >= 1 && newPage <= state.totalPages) {
            loadPage(newPage);
        }
    }

    // =======================
    // 绘制标注框（使用 SVG 原生元素）
    // =======================
    function drawAnnotations(pageElements) {
        const svg = elements.annotationLayer;
        const img = elements.pdfImage;
        const imageContainer = document.getElementById('imageContainer');

        // 清空现有标注
        svg.innerHTML = '';

        // 获取图片的自然尺寸和显示尺寸
        const naturalWidth = img.naturalWidth;
        const naturalHeight = img.naturalHeight;

        // 使用 offsetWidth/offsetHeight 获取显示尺寸
        const displayWidth = img.offsetWidth;
        const displayHeight = img.offsetHeight;

        // 计算缩放比例
        const scaleX = displayWidth / naturalWidth;
        const scaleY = displayHeight / naturalHeight;

        // 设置 SVG viewBox 以匹配显示尺寸
        svg.setAttribute('viewBox', `0 0 ${displayWidth} ${displayHeight}`);
        svg.style.width = displayWidth + 'px';
        svg.style.height = displayHeight + 'px';

        console.log('\n========== 绘制标注框调试 ==========');
        console.log(`[IMG] natural: ${naturalWidth}x${naturalHeight}`);
        console.log(`[IMG] display: ${displayWidth}x${displayHeight}`);
        console.log(`[SCALE] X=${scaleX.toFixed(4)}, Y=${scaleY.toFixed(4)}`);
        console.log(`[SVG] viewBox: 0 0 ${displayWidth} ${displayHeight}`);
        console.log('===================================\n');

        // 绘制每个元素的边框
        pageElements.forEach((element, index) => {
            if (!element.coordinates || !element.coordinates.points) return;
            if (element.content && element.content.startsWith('[页面')) return;

            const points = element.coordinates.points;
            if (!points || points.length < 4) return;

            // 计算边界框
            let minX = Infinity, minY = Infinity;
            let maxX = -Infinity, maxY = -Infinity;
            points.forEach(point => {
                minX = Math.min(minX, point[0]);
                minY = Math.min(minY, point[1]);
                maxX = Math.max(maxX, point[0]);
                maxY = Math.max(maxY, point[1]);
            });

            // 计算 SVG 坐标（直接使用缩放后的值）
            const x = Math.round(minX * scaleX);
            const y = Math.round(minY * scaleY);
            const width = Math.max(Math.round((maxX - minX) * scaleX), 20);
            const height = Math.max(Math.round((maxY - minY) * scaleY), 15);

            // 获取元素类型的颜色
            const typeColor = element.color || getElementColor(element.type);

            // 创建 SVG group 元素
            const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            group.setAttribute('class', 'element-group');
            group.style.cursor = 'pointer';
            group.style.pointerEvents = 'all';
            group.style.opacity = '0.6';
            group.style.transition = 'opacity 0.2s ease';
            group.dataset.rawX = minX;
            group.dataset.rawY = minY;
            group.dataset.content = element.content;

            // 悬停效果
            group.addEventListener('mouseenter', () => {
                group.style.opacity = '1';
                showElementDetail(element, group);
            });
            group.addEventListener('mouseleave', () => {
                group.style.opacity = '0.6';
                hideElementDetail();
            });
            group.addEventListener('click', () => {
                showElementDetail(element, group);
            });

            // 创建矩形框
            const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.setAttribute('x', x);
            rect.setAttribute('y', y);
            rect.setAttribute('width', width);
            rect.setAttribute('height', height);
            rect.setAttribute('fill', typeColor + '20');  // 添加透明度
            rect.setAttribute('stroke', typeColor);
            rect.setAttribute('stroke-width', '2');
            rect.setAttribute('rx', '3');

            group.appendChild(rect);
            svg.appendChild(group);

            // 打印前3个元素的调试信息
            if (index < 3) {
                console.log(`[ELEMENT ${index}] ${element.type}: "${element.content.substring(0, 30)}..."`);
                console.log(`  原始坐标: X=[${minX},${maxX}], Y=[${minY},${maxY}]`);
                console.log(`  百分比: X=${(minX/naturalWidth*100).toFixed(1)}%, Y=${(minY/naturalHeight*100).toFixed(1)}%`);
                console.log(`  SVG 坐标: x=${x}, y=${y}, w=${width}, h=${height}`);
            }
        });

        // 延迟验证 SVG rect 的实际渲染位置
        setTimeout(() => {
            const svgRects = svg.querySelectorAll('rect');
            const imgRect = img.getBoundingClientRect();
            console.log('\n========== 实际渲染验证 ==========');
            console.log(`[IMG] 视口: left=${imgRect.left.toFixed(1)}, top=${imgRect.top.toFixed(1)}, w=${imgRect.width.toFixed(1)}, h=${imgRect.height.toFixed(1)}`);
            svgRects.forEach((rect, i) => {
                if (i >= 3) return;
                const box = rect.getBoundingClientRect();
                console.log(`[RECT ${i}] 视口: left=${box.left.toFixed(1)}, top=${box.top.toFixed(1)}, w=${box.width.toFixed(1)}, h=${box.height.toFixed(1)}`);
            });
            console.log('==================================\n');
        }, 200);
    }

    // 获取元素类型的颜色
    function getElementColor(type) {
        const colors = {
            'Title': '#FF6B6B',
            'NarrativeText': '#4ECDC4',
            'BulletedText': '#FFEAA7',
            'ListItem': '#FFEAA7',
            'Table': '#45B7D1',
            'Image': '#96CEB4',
            'Formula': '#DDA0DD'
        };
        return colors[type] || '#888888';
    }

    // =======================
    // 元素详情
    // =======================
    let currentElementContent = '';
    let activeGroup = null;

    function showElementDetail(element, group) {
        // 高亮边框（SVG group）
        hideElementDetail();
        activeGroup = group;
        group.style.opacity = '1';
        group.style.filter = 'drop-shadow(0 0 5px rgba(0,0,0,0.5))';

        // 更新详情面板
        elements.detailType.textContent = element.type;
        elements.detailType.dataset.type = element.type;
        elements.detailPage.textContent = '第 ' + element.page + ' 页';
        elements.detailContent.textContent = element.content;
        currentElementContent = element.content;

        // 显示面板
        elements.elementDetail.style.display = 'block';
    }

    function hideElementDetail() {
        // 移除所有 group 的高亮
        document.querySelectorAll('.element-group').forEach(g => {
            g.style.opacity = '0.6';
            g.style.filter = '';
        });
    }

    // 暴露为全局函数（供 HTML onclick 调用）
    window.closeElementDetail = function() {
        elements.elementDetail.style.display = 'none';
        hideElementDetail();
    };

    function copyElementContent() {
        navigator.clipboard.writeText(currentElementContent)
            .then(() => {
                showToast('success', '已复制', '内容已复制到剪贴板');
            })
            .catch(() => {
                showToast('error', '复制失败', '请手动复制内容');
            });
    }

    // =======================
    // Markdown 下载
    // =======================
    async function downloadMarkdown() {
        if (!state.taskId) {
            showToast('error', '错误', '没有可下载的内容');
            return;
        }

        try {
            showToast('info', '生成中', '正在生成 Markdown...');

            // 先创建 Markdown
            const createResponse = await fetch(API_BASE + '/api/download/markdown/' + state.taskId, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    file_path: state.filePath,
                    result: state.parseResult
                })
            });

            if (!createResponse.ok) {
                throw new Error('生成失败');
            }

            // 下载文件
            window.location.href = API_BASE + '/api/download/markdown/' + state.taskId;

            showToast('success', '下载成功', 'Markdown 文件已开始下载');

        } catch (error) {
            console.error('下载失败:', error);
            showToast('error', '错误', error.message);
        }
    }

    // =======================
    // 工具函数
    // =======================
    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    }

    function showToast(type, title, message) {
        const toastEl = document.getElementById('toast');
        const toastTitle = document.getElementById('toastTitle');
        const toastBody = document.getElementById('toastBody');

        // 设置类型样式
        toastEl.className = 'toast';
        if (type === 'success') {
            toastEl.classList.add('bg-success', 'text-white');
        } else if (type === 'error') {
            toastEl.classList.add('bg-danger', 'text-white');
        } else if (type === 'warning') {
            toastEl.classList.add('bg-warning', 'text-dark');
        } else {
            toastEl.classList.add('bg-info', 'text-white');
        }

        toastTitle.textContent = title;
        toastBody.textContent = message;

        const toast = new bootstrap.Toast(toastEl);
        toast.show();
    }

    function resetUploadState(clearFileInfo = true) {
        state.taskId = null;
        state.filePath = null;
        state.fileName = null;
        state.fileSize = 0;
        state.currentFile = null;
        state.isParsing = false;

        if (clearFileInfo) {
            elements.fileInfo.style.display = 'none';
        }
        elements.uploadBtn.disabled = true;
        elements.dropZone.style.pointerEvents = 'auto';
        elements.progressCard.style.display = 'none';
        elements.resultCard.style.display = 'none';
        elements.emptyState.style.display = 'block';
    }

    // =======================
    // 启动
    // =======================
    document.addEventListener('DOMContentLoaded', init);

})();
