/**
 * Chat functionality with SSE streaming and retrieval chain display
 */

class ChatManager {
    constructor() {
        this.messagesContainer = document.getElementById('chatMessages');
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.clearBtn = document.getElementById('clearChat');

        this.history = [];
        this.isProcessing = false;
        this.abortController = null;
        this.currentStreamingMessage = null;

        this.init();
    }

    init() {
        // Event listeners
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.clearBtn.addEventListener('click', () => this.clearChat());
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 100) + 'px';
        });
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || this.isProcessing) return;

        // Abort any ongoing request
        if (this.abortController) {
            this.abortController.abort();
        }
        this.abortController = new AbortController();

        // Add user message
        this.addMessage(message, 'user');
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';

        // Show loading
        this.showLoading();

        try {
            // Use SSE for streaming
            await this.streamMessageWithSSE(message);

            // Update history
            this.history.push({ role: 'user', content: message });

        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error('Chat error:', error);
                this.hideLoading();
                this.addMessage(`抱歉，发生错误: ${error.message}`, 'bot');
            }
        } finally {
            this.abortController = null;
        }
    }

    async streamMessageWithSSE(message) {
        const historyParam = encodeURIComponent(JSON.stringify(this.history));
        const url = `/api/chat/stream?question=${encodeURIComponent(message)}&history=${historyParam}`;
        console.log('[ChatManager] SSE URL:', url);

        try {
            const response = await fetch(url, {
                signal: this.abortController.signal
            });

            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let fullResponse = '';
            let responseData = null;
            let isFirstChunk = true;

            this.hideLoading();
            this.startStreamingMessage('');

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (const line of lines) {
                    let trimmedLine = line.trim();
                    if (!trimmedLine) continue;

                    // SSE format: remove "data:" prefix
                    if (trimmedLine.startsWith('data:')) {
                        trimmedLine = trimmedLine.slice(5).trim();
                    }
                    if (!trimmedLine) continue;

                    console.log('[ChatManager] SSE line:', trimmedLine.substring(0, 100));

                    // Check for completion marker
                    if (trimmedLine.startsWith('[COMPLETE]')) {
                        try {
                            const jsonStr = trimmedLine.substring('[COMPLETE]'.length);
                            responseData = JSON.parse(jsonStr);
                            console.log('[ChatManager] Complete response:', responseData.response?.substring(0, 100));
                            console.log('[ChatManager] used_graph:', responseData.used_graph);
                            console.log('[ChatManager] retrieval_chain length:', responseData.retrieval_chain?.length);
                            console.log('[ChatManager] retrieved_entities length:', responseData.retrieved_entities?.length);
                            this.finishStreaming();
                            this.updateStreamingMessage(fullResponse);
                            this.addGraphInfo(responseData);
                            return;
                        } catch (e) {
                            console.warn('[ChatManager] Parse complete error:', e);
                            console.log('[ChatManager] Raw complete line:', trimmedLine.substring(0, 200));
                        }
                    }
                    // Check for error marker
                    else if (trimmedLine.startsWith('[ERROR]')) {
                        const errorMsg = trimmedLine.substring('[ERROR]'.length);
                        throw new Error(errorMsg);
                    }
                    // Regular text chunk
                    else {
                        fullResponse += trimmedLine;

                        if (isFirstChunk) {
                            isFirstChunk = false;
                        }
                        this.updateStreamingMessage(fullResponse);
                    }
                }
            }

            // If we get here without complete, try to use what we have
            if (responseData) {
                this.finishStreaming();
                this.addGraphInfo(responseData);
            }

        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('[ChatManager] Request aborted');
            } else {
                throw error;
            }
        }
    }

    startStreamingMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot streaming';
        messageDiv.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-content">
                <div class="message-text"></div>
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;
        this.messagesContainer.appendChild(messageDiv);
        this.currentStreamingMessage = messageDiv;
        this.scrollToBottom();
    }

    updateStreamingMessage(text) {
        const messageDiv = this.messagesContainer.querySelector('.message.streaming');
        if (messageDiv) {
            const textDiv = messageDiv.querySelector('.message-text');
            if (textDiv) {
                textDiv.innerHTML = this.formatMessage(text);
            }
            this.scrollToBottom();
        }
    }

    finishStreaming() {
        const messageDiv = this.messagesContainer.querySelector('.message.streaming');
        if (messageDiv) {
            const typingIndicator = messageDiv.querySelector('.typing-indicator');
            if (typingIndicator) {
                typingIndicator.remove();
            }
            messageDiv.classList.remove('streaming');
        }
    }

    addGraphInfo(responseData) {
        // Use the saved streaming message reference
        let messageDiv = this.currentStreamingMessage;
        if (!messageDiv) {
            // Fallback to finding the last bot message
            messageDiv = this.messagesContainer.querySelector('.message.bot:last-of-type');
        }
        if (!messageDiv) {
            console.warn('[ChatManager] No message div found for graph info');
            return;
        }

        // Remove any existing graph info
        const existingGraphInfo = messageDiv.querySelector('.graph-info-panel');
        if (existingGraphInfo) {
            existingGraphInfo.remove();
        }

        // Add graph info
        const graphInfoHtml = this.formatGraphInfo(responseData);
        const contentDiv = messageDiv.querySelector('.message-content');
        if (contentDiv && graphInfoHtml) {
            contentDiv.insertAdjacentHTML('beforeend', graphInfoHtml);
        }

        // Update history with assistant message
        const textContent = messageDiv.querySelector('.message-text')?.innerText || '';
        this.history.push({ role: 'assistant', content: textContent });

        // Clear the reference
        this.currentStreamingMessage = null;
    }

    addMessage(content, role) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        const avatar = role === 'bot' ? '🤖' : '👤';
        const htmlContent = this.formatMessage(content);

        messageDiv.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                <div class="message-text">${htmlContent}</div>
            </div>
        `;

        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addMessageWithGraphInfo(content, role, response) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        const avatar = role === 'bot' ? '🤖' : '👤';
        const htmlContent = this.formatMessage(content);

        let graphInfoHtml = '';
        if (role === 'bot' && response) {
            graphInfoHtml = this.formatGraphInfo(response);
        }

        messageDiv.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                <div class="message-text">${htmlContent}</div>
                ${graphInfoHtml}
            </div>
        `;

        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();

        // Update history
        if (role === 'bot') {
            this.history.push({ role: 'assistant', content: content });
        }
    }

    formatGraphInfo(response) {
        // Retrieval chain display
        let chainHtml = '';
        const chain = response.retrieval_chain || [];

        if (chain && chain.length > 0) {
            const chainItems = chain.map(step => {
                const entities = step.entities || [];
                const entityList = entities.map(e => {
                    const neighborHtml = e.neighbors && e.neighbors.length > 0
                        ? `<div class="chain-neighbor-list">
                            ${e.neighbors.map(n => `<span class="chain-neighbor">${n.name}[${n.relation}]</span>`).join(' ')}
                           </div>`
                        : '';

                    return `<div class="chain-entity">
                        <span class="chain-entity-name">${e.name}</span>
                        <span class="chain-entity-type">${e.type}</span>
                        ${neighborHtml}
                    </div>`;
                }).join('');

                return `<div class="chain-step">
                    <div class="chain-step-header">
                        <span class="chain-keyword">${step.step}</span>
                        <span class="chain-count">找到 ${step.found} 个实体</span>
                    </div>
                    <div class="chain-entities">
                        ${entityList || '<span class="chain-empty">无匹配实体</span>'}
                    </div>
                </div>`;
            }).join('');

            chainHtml = `
                <div class="retrieval-chain">
                    <div class="chain-title">
                        <span class="chain-icon">🔍</span>
                        <span>知识图谱检索链路</span>
                    </div>
                    ${chainItems}
                </div>
            `;
        }

        // Entities display (if no chain, show entities)
        let entitiesHtml = '';
        const entities = response.retrieved_entities || [];

        if (chain.length === 0 && entities.length > 0) {
            entitiesHtml = `
                <div class="retrieved-entities">
                    <div class="entities-title">召回实体:</div>
                    <div class="entities-list">
                        ${entities.map(e => `
                            <div class="entity-item">
                                <span class="entity-name">${e.name}</span>
                                <span class="entity-type">${e.type}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        // Summary badge
        let summaryHtml = '';
        if (response.used_graph && entities.length > 0) {
            summaryHtml = `
                <div class="graph-summary">
                    <span class="graph-badge">已使用知识图谱</span>
                    <span class="entity-count">召回 ${entities.length} 个实体</span>
                </div>
            `;
        }

        return `
            <div class="graph-info-panel">
                ${summaryHtml}
                ${chainHtml}
                ${entitiesHtml}
            </div>
        `;
    }

    formatMessage(text) {
        if (!text) return '';
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }

    showLoading() {
        this.isProcessing = true;
        this.sendBtn.disabled = true;
        this.sendBtn.innerHTML = '<span>•••</span>';

        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message bot';
        loadingDiv.id = 'loadingMessage';
        loadingDiv.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-content">
                <div class="loading-dots">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;
        this.messagesContainer.appendChild(loadingDiv);
        this.scrollToBottom();
    }

    hideLoading() {
        this.isProcessing = false;
        this.sendBtn.disabled = false;
        this.sendBtn.innerHTML = '<span>发送</span>';

        const loadingEl = document.getElementById('loadingMessage');
        if (loadingEl) {
            loadingEl.remove();
        }
    }

    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    clearChat() {
        this.messagesContainer.innerHTML = `
            <div class="message bot">
                <div class="message-avatar">🤖</div>
                <div class="message-content">
                    <p>对话已清空</p>
                </div>
            </div>
        `;
        this.history = [];
    }
}

// Initialize chat when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.chatManager = new ChatManager();
});
