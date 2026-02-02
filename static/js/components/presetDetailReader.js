/**
 * static/js/components/presetDetailReader.js
 * 预设详情阅读器组件 - 独立的弹窗组件
 */
export default function presetDetailReader() {
    return {
        // 弹窗状态
        showModal: false,
        isLoading: false,
        
        // 当前预设数据
        activePresetDetail: null,
        
        // 内部标签状态
        sidebarTab: 'samplers',
        
        init() {
            // 监听打开事件
            window.addEventListener('open-preset-reader', (e) => {
                this.openPreset(e.detail);
            });
        },
        
        async openPreset(item) {
            this.isLoading = true;
            this.showModal = true;
            
            try {
                const resp = await fetch(`/api/presets/detail/${encodeURIComponent(item.id)}`);
                const res = await resp.json();
                
                if (res.success) {
                    this.activePresetDetail = res.preset;
                    this.sidebarTab = 'samplers';
                } else {
                    this.$store.global.showToast(res.msg || '获取详情失败', 'error');
                    this.closeModal();
                }
            } catch (e) {
                console.error('Failed to load preset:', e);
                this.$store.global.showToast('获取详情失败', 'error');
                this.closeModal();
            } finally {
                this.isLoading = false;
            }
        },
        
        closeModal() {
            this.showModal = false;
            this.activePresetDetail = null;
        },
        
        editRaw() {
            if (!this.activePresetDetail) return;
            // 触发编辑事件
            window.dispatchEvent(new CustomEvent('edit-preset-raw', {
                detail: this.activePresetDetail
            }));
        },
        
        openAdvancedExtensions() {
            if (!this.activePresetDetail) return;
            
            // 准备extensions数据结构
            const extensions = this.activePresetDetail.extensions || {};
            const regex_scripts = extensions.regex_scripts || [];
            const tavern_helper = extensions.tavern_helper || { scripts: [] };
            
            // 构造editingData，与角色卡详情页保持一致
            const editingData = {
                extensions: {
                    regex_scripts: regex_scripts,
                    tavern_helper: tavern_helper
                }
            };
            
            // 触发高级编辑器事件
            window.dispatchEvent(new CustomEvent('open-advanced-editor', {
                detail: editingData
            }));
            
            // 监听保存事件，将修改后的extensions保存回预设
            const saveHandler = (e) => {
                if (e.detail && e.detail.extensions) {
                    this.savePresetExtensions(e.detail.extensions);
                }
                window.removeEventListener('advanced-editor-save', saveHandler);
            };
            window.addEventListener('advanced-editor-save', saveHandler);
        },
        
        // 保存extensions到预设文件
        async savePresetExtensions(extensions) {
            if (!this.activePresetDetail) return;
            
            try {
                const resp = await fetch('/api/presets/save-extensions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id: this.activePresetDetail.id,
                        extensions: extensions
                    })
                });
                
                const res = await resp.json();
                if (res.success) {
                    this.$store.global.showToast('扩展已保存');
                    // 刷新详情
                    this.openPreset({ id: this.activePresetDetail.id });
                } else {
                    this.$store.global.showToast(res.msg || '保存失败', 'error');
                }
            } catch (e) {
                console.error('Failed to save preset extensions:', e);
                this.$store.global.showToast('保存失败', 'error');
            }
        },
        
        // 格式化参数值
        formatParam(value) {
            if (value === undefined || value === null) return '-';
            if (typeof value === 'number') return value.toString();
            return String(value);
        },
        
        // 标准化 prompts
        normalizePrompts(prompts) {
            if (!prompts || !Array.isArray(prompts)) return [];
            return prompts.map((p, idx) => ({
                ...p,
                key: p.identifier || p.key || `prompt-${idx}`,
                meta: p.meta || [],
                enabled: p.enabled !== false
            }));
        },
        
        // 获取 prompt 图标
        getPromptIcon(key) {
            const map = {
                'worldInfoBefore': '🌍', 'worldInfoAfter': '🌍',
                'charDescription': '👤', 'charPersonality': '🧠', 'personaDescription': '🎭',
                'scenario': '🏰',
                'chatHistory': '🕒', 'dialogueExamples': '💬',
                'main': '📜', 'jailbreak': '🔓'
            };
            return map[key] || '📌';
        },
        
        // 获取 prompt role
        getPromptRole(prompt) {
            const roleMeta = prompt.meta.find(m => m.startsWith('role:'));
            if (roleMeta) return roleMeta.split(':')[1].trim();
            return 'system';
        }
    };
}
