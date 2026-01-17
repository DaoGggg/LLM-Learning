/**
 * Project and Graph management functionality
 */

class ProjectManager {
    constructor() {
        this.projects = [];
        this.currentProject = null;
        this.init();
    }

    async init() {
        console.log('[ProjectManager] Initializing...');
        await this.loadProjects();
    }

    async loadProjects() {
        try {
            this.projects = await api.listProjects();
            console.log('[ProjectManager] Loaded projects:', this.projects.length);
            // If there's a current project ID, find and set it
            const currentId = (await api.getCurrentProject())?.id;
            if (currentId) {
                this.currentProject = this.projects.find(p => p.id === currentId);
                console.log('[ProjectManager] Set current project:', this.currentProject?.name);
            }
            this.renderProjectList();
        } catch (error) {
            console.error('Failed to load projects:', error);
        }
    }

    async createProject(name, description = '') {
        try {
            console.log('[ProjectManager] Creating project:', name);
            const project = await api.createProject(name, description);
            console.log('[ProjectManager] Project created:', project);
            await this.loadProjects();
            await this.selectProject(project.id);
            return project;
        } catch (error) {
            console.error('[ProjectManager] Failed to create project:', error);
            throw error;
        }
    }

    async deleteProject(projectId) {
        if (!confirm('确定要删除这个项目吗？图谱数据将无法恢复。')) {
            return false;
        }
        try {
            await api.deleteProject(projectId);

            // 如果删除的是当前项目，先清空前端状态
            if (this.currentProject && this.currentProject.id === projectId) {
                this.currentProject = null;
                this.clearGraph();
                // 更新左上角状态
                const currentIndicator = document.getElementById('currentProjectIndicator');
                if (currentIndicator) {
                    currentIndicator.textContent = '未选择项目';
                    currentIndicator.style.color = '';
                    currentIndicator.style.background = '';
                }
            }

            await this.loadProjects();
            return true;
        } catch (error) {
            throw error;
        }
    }

    async selectProject(projectId) {
        try {
            console.log('[ProjectManager] Selecting project:', projectId);
            await api.setCurrentProject(projectId);
            // Reload projects to ensure we have the latest data
            await this.loadProjects();
            // After reloading, currentProject should be set correctly from renderProjectList
            if (window.graphManager) {
                await window.graphManager.loadGraph();
            }
            if (window.uploadManager) {
                await window.uploadManager.updateProjectInfo();
            }
        } catch (error) {
            console.error('Failed to select project:', error);
        }
    }

    renderProjectList() {
        const container = document.getElementById('projectList');
        const currentIndicator = document.getElementById('currentProjectIndicator');

        if (!container) return;

        let html = '';
        this.projects.forEach(project => {
            const isActive = this.currentProject && this.currentProject.id === project.id;
            const stats = project.stats || { node_count: 0, edge_count: 0 };
            html += `
                <div class="project-item ${isActive ? 'active' : ''}" data-id="${project.id}">
                    <div class="project-info" onclick="window.projectManager.selectProject('${project.id}')">
                        <div class="project-name">${project.name}</div>
                        <div class="project-stats">${stats.node_count} 节点, ${stats.edge_count} 关系</div>
                    </div>
                    <button class="project-delete" onclick="window.projectManager.deleteProject('${project.id}')" title="删除项目">×</button>
                </div>
            `;
        });

        if (html === '') {
            html = '<div class="no-projects">暂无项目，点击上方按钮创建</div>';
        }

        container.innerHTML = html;

        if (currentIndicator && this.currentProject) {
            currentIndicator.textContent = this.currentProject.name;
        }
    }

    clearGraph() {
        if (window.graphManager) {
            window.graphManager.clearGraph();
        }
    }
}

class GraphManager {
    constructor() {
        this.chartDom = document.getElementById('graphChart');
        this.chart = null;
        this.nodeDetail = document.getElementById('nodeDetail');
        this.nodeContent = document.getElementById('nodeContent');
        this.edgeDetail = document.getElementById('edgeDetail');
        this.edgeContent = document.getElementById('edgeContent');
        this.editMode = false;
        this.selectedNodes = [];
        this.currentEdgeData = null;  // Store current edge data for editing

        this.init();
    }

    init() {
        // Initialize ECharts
        if (this.chartDom) {
            this.chart = echarts.init(this.chartDom);

            // Handle resize
            window.addEventListener('resize', () => {
                this.chart.resize();
            });

            // Refresh button
            const refreshBtn = document.getElementById('refreshGraph');
            if (refreshBtn) {
                refreshBtn.addEventListener('click', () => {
                    this.loadGraph();
                });
            }

            // Toggle edit mode
            const editToggle = document.getElementById('toggleEditMode');
            if (editToggle) {
                editToggle.addEventListener('click', () => {
                    this.toggleEditMode();
                });
            }

            // Add node button
            const addNodeBtn = document.getElementById('addNodeBtn');
            if (addNodeBtn) {
                addNodeBtn.addEventListener('click', () => {
                    this.showAddNodeForm();
                });
            }

            // Close node detail
            const closeNodeDetail = document.getElementById('closeNodeDetail');
            if (closeNodeDetail) {
                closeNodeDetail.addEventListener('click', () => {
                    this.hideNodeDetail();
                });
            }

            // Close edit form
            const closeEditForm = document.getElementById('closeEditForm');
            if (closeEditForm) {
                closeEditForm.addEventListener('click', () => {
                    this.hideEditForm();
                });
            }

            // Save entity
            const saveEntityBtn = document.getElementById('saveEntityBtn');
            if (saveEntityBtn) {
                saveEntityBtn.addEventListener('click', () => {
                    this.saveEntity();
                });
            }

            // Edge detail buttons
            const editEdgeBtn = document.getElementById('editEdgeBtn');
            if (editEdgeBtn) {
                editEdgeBtn.addEventListener('click', () => {
                    this.showEditEdgeForm();
                });
            }

            const deleteEdgeBtn = document.getElementById('deleteEdgeBtn');
            if (deleteEdgeBtn) {
                deleteEdgeBtn.addEventListener('click', () => {
                    this.deleteEdge();
                });
            }

            const closeEdgeDetail = document.getElementById('closeEdgeDetail');
            if (closeEdgeDetail) {
                closeEdgeDetail.addEventListener('click', () => {
                    this.hideEdgeDetail();
                });
            }

            // Edge edit form buttons
            const saveEdgeBtn = document.getElementById('saveEdgeBtn');
            if (saveEdgeBtn) {
                saveEdgeBtn.addEventListener('click', () => {
                    this.saveEdge();
                });
            }

            const closeEdgeEditForm = document.getElementById('closeEdgeEditForm');
            if (closeEdgeEditForm) {
                closeEdgeEditForm.addEventListener('click', () => {
                    this.hideEdgeEditForm();
                });
            }

            // Load initial graph
            this.loadGraph();
        }
    }

    async loadGraph() {
        try {
            console.log('[GraphManager] Loading graph...');
            const data = await api.getGraphData();
            const stats = await api.getGraphStats();

            console.log('[GraphManager] Graph data:', data);
            console.log('[GraphManager] Graph stats:', stats);

            // Update stats display
            this.updateStatsDisplay(stats);

            // Render graph
            this.renderGraph(data);
        } catch (error) {
            console.error('Failed to load graph:', error);
            this.renderGraph({ nodes: [], edges: [] });
        }
    }

    updateStatsDisplay(stats) {
        const entityCount = document.getElementById('entityCount');
        const relationCount = document.getElementById('relationCount');
        if (entityCount) entityCount.textContent = stats.node_count || 0;
        if (relationCount) relationCount.textContent = stats.edge_count || 0;
    }

    renderGraph(data) {
        const { nodes, edges } = data;
        console.log('[GraphManager] Rendering graph with', nodes.length, 'nodes,', edges.length, 'edges');

        if (!this.chart) {
            console.log('[GraphManager] Chart not initialized yet');
            return;
        }

        if (nodes.length === 0) {
            this.chart.setOption({
                title: {
                    text: '暂无知识图谱',
                    left: 'center',
                    top: 'center',
                    textStyle: {
                        color: '#64748b',
                        fontSize: 14,
                        fontWeight: 'normal'
                    }
                },
                series: []
            }, true);  // true = 不合并，完全替换
            return;
        }

        // Prepare ECharts data
        const categories = this.getCategories(nodes);
        const graphData = nodes.map(node => ({
            id: node.id,
            name: node.name,
            category: categories.indexOf(node.category),
            description: node.description,
            chunkId: node.chunkId
        }));

        const links = edges.map(edge => ({
            source: edge.source,
            target: edge.target,
            label: {
                show: true,
                formatter: edge.relation,
                fontSize: 10
            }
        }));

        const option = {
            title: {
                text: '',  // 清除之前的title
                show: false
            },
            tooltip: {
                trigger: 'item',
                formatter: (params) => {
                    if (params.dataType === 'node') {
                        return `<strong>${params.name}</strong><br/>类型: ${categories[params.category] || '未知'}`;
                    }
                    return params.data.label?.formatter || '';
                }
            },
            series: [{
                type: 'graph',
                layout: 'force',
                data: graphData,
                links: links,
                categories: categories.map(cat => ({ name: cat })),
                roam: true,
                draggable: true,
                force: {
                    repulsion: 200,
                    edgeLength: 100,
                    gravity: 0.1
                },
                label: {
                    show: true,
                    position: 'right',
                    formatter: '{b}',
                    fontSize: 11,
                    overflow: 'truncate',
                    width: 80
                },
                lineStyle: {
                    color: '#94a3b8',
                    curveness: 0.1,
                    width: 1.5
                },
                nodeStyle: {
                    borderWidth: 2,
                    borderColor: '#3b82f6',
                    color: '#dbeafe'
                },
                emphasis: {
                    focus: 'adjacency',
                    lineStyle: {
                        width: 3
                    }
                }
            }]
        };

        this.chart.setOption(option, true);  // true = 不合并，完全替换

        // Click handler
        this.chart.off('click');
        this.chart.on('click', (params) => {
            if (params.dataType === 'node') {
                if (this.editMode) {
                    this.showEditNodeForm(params.data);
                } else {
                    this.showNodeDetail(params.data);
                }
            } else if (params.dataType === 'edge') {
                this.showEdgeDetail(params.data);
            }
        });
    }

    getCategories(nodes) {
        const categories = new Set();
        nodes.forEach(node => {
            if (node.category) {
                categories.add(node.category);
            }
        });
        return Array.from(categories);
    }

    async showNodeDetail(nodeData) {
        try {
            const data = await api.getEntity(nodeData.id);

            this.nodeContent.innerHTML = `
                <p><strong>名称:</strong> ${nodeData.name}</p>
                <p><strong>类型:</strong> ${nodeData.category || '未知'}</p>
                <p><strong>描述:</strong> ${nodeData.description || '无'}</p>
                ${data.neighbors && data.neighbors.length > 0 ? `
                    <p><strong>相关实体:</strong></p>
                    <ul>
                        ${data.neighbors.map(n => `
                            <li>${n.name || '未知'} [${n.relation || '相关'}]</li>
                        `).join('')}
                    </ul>
                ` : ''}
                ${this.editMode ? `
                    <div class="node-actions" style="margin-top: 12px;">
                        <button class="btn-primary" onclick="window.graphManager.showEditNodeForm(${JSON.stringify(nodeData).replace(/"/g, '&quot;')})">编辑</button>
                        <button class="btn-danger" onclick="window.graphManager.deleteNode('${nodeData.id}')" style="margin-left: 8px;">删除</button>
                    </div>
                ` : ''}
            `;

            this.nodeDetail.classList.remove('hidden');
        } catch (error) {
            console.error('Failed to get entity details:', error);
        }
    }

    hideNodeDetail() {
        this.nodeDetail.classList.add('hidden');
    }

    toggleEditMode() {
        this.editMode = !this.editMode;
        const toggleBtn = document.getElementById('toggleEditMode');
        const addNodeBtn = document.getElementById('addNodeBtn');

        if (toggleBtn) {
            toggleBtn.textContent = this.editMode ? '退出编辑' : '编辑模式';
            toggleBtn.classList.toggle('active', this.editMode);
        }
        if (addNodeBtn) {
            addNodeBtn.style.display = this.editMode ? 'block' : 'none';
        }
    }

    showAddNodeForm() {
        this.hideNodeDetail();
        const form = document.getElementById('editForm');
        const title = document.getElementById('editFormTitle');
        const nodeId = document.getElementById('editNodeId');

        if (form && title && nodeId) {
            title.textContent = '添加节点';
            nodeId.value = '';
            document.getElementById('editNodeName').value = '';
            document.getElementById('editNodeType').value = '';
            document.getElementById('editNodeDescription').value = '';
            form.classList.remove('hidden');
        }
    }

    showEditNodeForm(nodeData) {
        const form = document.getElementById('editForm');
        const title = document.getElementById('editFormTitle');
        const nodeId = document.getElementById('editNodeId');

        if (form && title && nodeId) {
            title.textContent = '编辑节点';
            nodeId.value = nodeData.id;
            document.getElementById('editNodeName').value = nodeData.name || '';
            document.getElementById('editNodeType').value = nodeData.category || '';
            document.getElementById('editNodeDescription').value = nodeData.description || '';
            form.classList.remove('hidden');
            this.hideNodeDetail();
        }
    }

    hideEditForm() {
        const form = document.getElementById('editForm');
        if (form) {
            form.classList.add('hidden');
        }
    }

    async saveEntity() {
        const nodeId = document.getElementById('editNodeId').value;
        const name = document.getElementById('editNodeName').value.trim();
        const type = document.getElementById('editNodeType').value.trim();
        const description = document.getElementById('editNodeDescription').value.trim();

        if (!name || !type) {
            alert('请填写节点名称和类型');
            return;
        }

        try {
            if (nodeId) {
                // Update existing entity
                await api.updateEntity(nodeId, name, type, description);
            } else {
                // Add new entity
                await api.addEntity(name, type, description);
            }
            this.hideEditForm();
            await this.loadGraph();
        } catch (error) {
            alert('保存失败: ' + error.message);
        }
    }

    async deleteNode(nodeId) {
        if (!confirm('确定要删除这个节点吗？相关关系也会被删除。')) {
            return;
        }

        try {
            await api.deleteEntity(nodeId);
            this.hideNodeDetail();
            await this.loadGraph();
        } catch (error) {
            alert('删除失败: ' + error.message);
        }
    }

    // Edge detail methods
    async showEdgeDetail(edgeData) {
        this.hideNodeDetail();
        this.hideEdgeEditForm();

        try {
            const data = await api.getRelation(edgeData.source, edgeData.target);

            // Store for editing
            this.currentEdgeData = {
                source: edgeData.source,
                target: edgeData.target,
                sourceName: data.source_name,
                targetName: data.target_name,
                relation: data.relation_type,
                description: data.description,
                sourceText: data.source_text
            };

            // Build source text display
            let sourceTextHtml = '';
            if (data.source_text) {
                sourceTextHtml = `<div class="edge-source-text">"${data.source_text}"</div>`;
            } else {
                sourceTextHtml = '<span class="no-source-text">无原始原文</span>';
            }

            this.edgeContent.innerHTML = `
                <div class="edge-info">
                    <p><strong>源节点:</strong> ${data.source_name || '未知'}</p>
                    <p><strong>目标节点:</strong> ${data.target_name || '未知'}</p>
                    <p><strong>关系类型:</strong> ${data.relation_type || '未知'}</p>
                    <p><strong>描述:</strong> ${data.description || '无'}</p>
                </div>
                <div class="edge-source-section">
                    <p><strong>原始原文:</strong></p>
                    ${sourceTextHtml}
                </div>
            `;

            this.edgeDetail.classList.remove('hidden');
        } catch (error) {
            console.error('Failed to get edge details:', error);
            this.edgeContent.innerHTML = '<p>获取边详情失败</p>';
            this.edgeDetail.classList.remove('hidden');
        }
    }

    hideEdgeDetail() {
        this.edgeDetail.classList.add('hidden');
        this.currentEdgeData = null;
    }

    showEditEdgeForm() {
        if (!this.currentEdgeData) return;

        const form = document.getElementById('edgeEditForm');
        if (!form) return;

        document.getElementById('editEdgeSource').value = this.currentEdgeData.source;
        document.getElementById('editEdgeTarget').value = this.currentEdgeData.target;
        document.getElementById('editEdgeSourceName').value = this.currentEdgeData.sourceName || '';
        document.getElementById('editEdgeTargetName').value = this.currentEdgeData.targetName || '';
        document.getElementById('editEdgeRelation').value = this.currentEdgeData.relation || '';
        document.getElementById('editEdgeDescription').value = this.currentEdgeData.description || '';

        // Show source text
        const sourceTextEl = document.getElementById('edgeSourceText');
        if (this.currentEdgeData.sourceText) {
            sourceTextEl.innerHTML = `"${this.currentEdgeData.sourceText}"`;
            sourceTextEl.style.display = 'block';
        } else {
            sourceTextEl.innerHTML = '<span class="no-source-text">无原始原文</span>';
            sourceTextEl.style.display = 'block';
        }

        this.hideEdgeDetail();
        form.classList.remove('hidden');
    }

    hideEdgeEditForm() {
        const form = document.getElementById('edgeEditForm');
        if (form) {
            form.classList.add('hidden');
        }
    }

    async saveEdge() {
        const sourceId = document.getElementById('editEdgeSource').value;
        const targetId = document.getElementById('editEdgeTarget').value;
        const relation = document.getElementById('editEdgeRelation').value.trim();
        const description = document.getElementById('editEdgeDescription').value.trim();

        if (!relation) {
            alert('请填写关系类型');
            return;
        }

        try {
            await api.updateRelation(sourceId, targetId, relation, description);
            this.hideEdgeEditForm();
            await this.loadGraph();

            // Refresh edge detail if still visible
            if (this.currentEdgeData && this.currentEdgeData.source === sourceId && this.currentEdgeData.target === targetId) {
                this.currentEdgeData.relation = relation;
                this.currentEdgeData.description = description;
            }
        } catch (error) {
            alert('保存失败: ' + error.message);
        }
    }

    async deleteEdge() {
        if (!this.currentEdgeData) return;

        if (!confirm('确定要删除这条关系吗？')) {
            return;
        }

        try {
            await api.deleteRelation(this.currentEdgeData.source, this.currentEdgeData.target);
            this.hideEdgeDetail();
            await this.loadGraph();
        } catch (error) {
            alert('删除失败: ' + error.message);
        }
    }

    clearGraph() {
        if (this.chart) {
            this.chart.setOption({
                title: {
                    text: '请先选择或创建项目',
                    left: 'center',
                    top: 'center',
                    textStyle: {
                        color: '#64748b',
                        fontSize: 14,
                        fontWeight: 'normal'
                    }
                },
                series: []
            });
        }
        this.updateStatsDisplay({ node_count: 0, edge_count: 0 });
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.projectManager = new ProjectManager();
    window.graphManager = new GraphManager();
    window.uploadManager = new UploadManager();
});


/**
 * Upload handling functionality
 */
class UploadManager {
    constructor() {
        this.dropZone = document.getElementById('dropZone');
        this.fileInput = document.getElementById('fileInput');
        this.uploadProgress = document.getElementById('uploadProgress');
        this.progressFill = document.getElementById('progressFill');
        this.progressText = document.getElementById('progressText');
        this.fileList = document.getElementById('fileList');

        this.files = [];

        this.init();
    }

    init() {
        if (!this.dropZone) return;

        // Click to select file
        this.dropZone.addEventListener('click', () => {
            this.fileInput.click();
        });

        // File input change
        this.fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFiles(e.target.files);
            }
        });

        // Drag and drop
        this.dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.dropZone.classList.add('drag-over');
        });

        this.dropZone.addEventListener('dragleave', () => {
            this.dropZone.classList.remove('drag-over');
        });

        this.dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            this.dropZone.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                this.handleFiles(e.dataTransfer.files);
            }
        });
    }

    async updateProjectInfo() {
        // Update project info display (currently empty, reserved for future use)
        console.log('[UploadManager] Project info updated');
    }

    async handleFiles(fileList) {
        console.log('[UploadManager] handleFiles called, currentProject:', window.projectManager.currentProject);

        // Check if project is selected - both locally and verify with server
        if (!window.projectManager.currentProject) {
            alert('请先选择或创建一个项目');
            return;
        }

        // Double-check with server
        try {
            const current = await api.getCurrentProject();
            console.log('[UploadManager] Server current project:', current);
            if (!current || !current.id) {
                alert('请先选择或创建一个项目');
                return;
            }
        } catch (e) {
            console.error('[UploadManager] Error checking current project:', e);
            alert('请先选择或创建一个项目');
            return;
        }

        for (const file of fileList) {
            if (!this.isValidFile(file)) {
                alert(`不支持的文件格式: ${file.name}`);
                continue;
            }

            this.showProgress();
            this.updateProgress(5, '正在解析文档...');

            try {
                const result = await api.uploadFile(file);

                this.updateProgress(30, '正在提取实体...');

                // 轮询检查图谱数据更新
                let attempts = 0;
                const maxAttempts = 30; // 最多等待30次（约15秒）

                const pollInterval = setInterval(async () => {
                    attempts++;
                    try {
                        const stats = await api.getGraphStats();
                        const nodeCount = stats.node_count || 0;
                        console.log('[UploadManager] Poll attempt', attempts, ': nodeCount =', nodeCount);

                        // 计算进度（假设处理完成时至少有几个节点）
                        const estimatedTotal = 50; // 预估总节点数
                        const progress = Math.min(30 + (nodeCount / estimatedTotal) * 70, 95);

                        this.updateProgress(progress, `正在构建图谱... 已提取 ${nodeCount} 个实体`);

                        // 如果节点数稳定增长，视为处理中
                        if (nodeCount > 0 && attempts < maxAttempts) {
                            // 继续轮询
                        } else {
                            // 处理完成
                            clearInterval(pollInterval);
                            console.log('[UploadManager] Polling complete, calling loadGraph()...');
                            this.updateProgress(100, '处理完成');
                            this.addFileToList(file.name, true);
                            this.updateGraphStats();

                            // 刷新图谱显示
                            if (window.graphManager) {
                                window.graphManager.loadGraph();
                            } else {
                                console.error('[UploadManager] graphManager not found!');
                            }

                            // 3秒后隐藏进度条
                            setTimeout(() => {
                                this.hideProgress();
                            }, 3000);
                        }
                    } catch (e) {
                        console.error('[UploadManager] Polling error:', e);
                        // 忽略轮询错误
                    }
                }, 500); // 每500ms检查一次

            } catch (error) {
                this.updateProgress(0, `失败: ${error.message}`);
                this.addFileToList(file.name, false);

                // 错误信息不自动消失
                return;
            }
        }
    }

    isValidFile(file) {
        const validExtensions = ['.pdf', '.doc', '.docx', '.txt'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        return validExtensions.includes(ext);
    }

    showProgress() {
        this.uploadProgress.classList.remove('hidden');
    }

    hideProgress() {
        this.uploadProgress.classList.add('hidden');
        this.progressFill.style.width = '0%';
    }

    updateProgress(percent, text) {
        this.progressFill.style.width = `${percent}%`;
        this.progressText.textContent = text;
    }

    addFileToList(fileName, success) {
        const item = document.createElement('div');
        item.className = 'file-item';
        item.innerHTML = `
            <span class="file-icon">${success ? '✓' : '✗'}</span>
            <span>${fileName}</span>
        `;
        this.fileList.appendChild(item);
    }

    async updateGraphStats() {
        try {
            const stats = await api.getGraphStats();
            const entityCount = document.getElementById('entityCount');
            const relationCount = document.getElementById('relationCount');
            if (entityCount) entityCount.textContent = stats.node_count || 0;
            if (relationCount) relationCount.textContent = stats.edge_count || 0;
        } catch (error) {
            console.error('Failed to update graph stats:', error);
        }
    }
}
