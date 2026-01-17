/**
 * API Service for backend communication
 */

const API_BASE = '/api';

const api = {
    // ============ Project APIs ============

    /**
     * List all projects
     */
    async listProjects() {
        const response = await fetch(`${API_BASE}/projects`);
        if (!response.ok) {
            throw new Error('Failed to list projects');
        }
        return response.json();
    },

    /**
     * Create a new project
     */
    async createProject(name, description = '') {
        const response = await fetch(`${API_BASE}/projects`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description })
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create project');
        }
        return response.json();
    },

    /**
     * Delete a project
     */
    async deleteProject(projectId) {
        const response = await fetch(`${API_BASE}/projects/${projectId}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            throw new Error('Failed to delete project');
        }
        return response.json();
    },

    /**
     * Set current project
     */
    async setCurrentProject(projectId) {
        const response = await fetch(`${API_BASE}/projects/current`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_id: projectId })
        });
        if (!response.ok) {
            throw new Error('Failed to set current project');
        }
        return response.json();
    },

    /**
     * Get current project
     */
    async getCurrentProject() {
        const response = await fetch(`${API_BASE}/projects/current`);
        if (!response.ok) {
            throw new Error('Failed to get current project');
        }
        return response.json();
    },

    // ============ Graph APIs ============

    /**
     * Get graph data
     */
    async getGraphData() {
        const response = await fetch(`${API_BASE}/graph`);
        if (!response.ok) {
            throw new Error('Failed to get graph data');
        }
        return response.json();
    },

    /**
     * Get graph statistics
     */
    async getGraphStats() {
        const response = await fetch(`${API_BASE}/graph/stats`);
        if (!response.ok) {
            throw new Error('Failed to get graph stats');
        }
        return response.json();
    },

    // ============ Entity APIs ============

    /**
     * Search entities
     */
    async searchEntities(query) {
        const response = await fetch(`${API_BASE}/graph/entities/search?query=${encodeURIComponent(query)}`);
        if (!response.ok) {
            throw new Error('Search failed');
        }
        return response.json();
    },

    /**
     * Get entity details
     */
    async getEntity(entityId) {
        const response = await fetch(`${API_BASE}/graph/entity/${entityId}`);
        if (!response.ok) {
            throw new Error('Entity not found');
        }
        return response.json();
    },

    /**
     * Add entity
     */
    async addEntity(name, entityType, description = '', chunkId = '') {
        const response = await fetch(`${API_BASE}/graph/entity`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, entity_type: entityType, description, chunk_id: chunkId })
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to add entity');
        }
        return response.json();
    },

    /**
     * Update entity
     */
    async updateEntity(entityId, name, entityType, description = '') {
        const response = await fetch(`${API_BASE}/graph/entity/${entityId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, entity_type: entityType, description })
        });
        if (!response.ok) {
            throw new Error('Failed to update entity');
        }
        return response.json();
    },

    /**
     * Delete entity
     */
    async deleteEntity(entityId) {
        const response = await fetch(`${API_BASE}/graph/entity/${entityId}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            throw new Error('Failed to delete entity');
        }
        return response.json();
    },

    // ============ Relation APIs ============

    /**
     * Add relation
     */
    async addRelation(sourceId, targetId, relationType, description = '') {
        const response = await fetch(`${API_BASE}/graph/relation`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source_id: sourceId,
                target_id: targetId,
                relation_type: relationType,
                description
            })
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to add relation');
        }
        return response.json();
    },

    /**
     * Delete relation
     */
    async deleteRelation(sourceId, targetId) {
        const response = await fetch(`${API_BASE}/graph/relation?source_id=${sourceId}&target_id=${targetId}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            throw new Error('Failed to delete relation');
        }
        return response.json();
    },

    /**
     * Get relation details
     */
    async getRelation(sourceId, targetId) {
        const response = await fetch(`${API_BASE}/graph/relation?source_id=${sourceId}&target_id=${targetId}`);
        if (!response.ok) {
            throw new Error('Failed to get relation');
        }
        return response.json();
    },

    /**
     * Update relation
     */
    async updateRelation(sourceId, targetId, relationType, description = '') {
        const response = await fetch(`${API_BASE}/graph/relation?source_id=${sourceId}&target_id=${targetId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ relation_type: relationType, description })
        });
        if (!response.ok) {
            throw new Error('Failed to update relation');
        }
        return response.json();
    },

    // ============ Document APIs ============

    /**
     * Upload a file
     */
    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }

        return response.json();
    },

    /**
     * Send chat message
     */
    async sendMessage(message, history = []) {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, history })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Chat failed');
        }

        return response.json();
    }
};

// Export for use in other modules
window.api = api;
