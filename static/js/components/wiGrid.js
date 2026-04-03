/**
 * static/js/components/wiGrid.js
 * 世界书网格组件
 */

import { listWorldInfo, uploadWorldInfo, createWorldInfo, deleteWorldInfo } from '../api/wi.js';

export default function wiGrid() {
    return {
        flippedWorldInfoIds: {},
        worldInfoBulkBackMode: false,
        worldInfoAutoFlipBackDelayMs: 1800,
        _worldInfoAutoFlipBackTimers: {},

        // === Store 代理 ===
        get wiList() { return this.$store.global.wiList; },
        set wiList(val) { this.$store.global.wiList = val; },
        get wiCurrentPage() { return this.$store.global.wiCurrentPage; },
        set wiCurrentPage(val) { this.$store.global.wiCurrentPage = val; },
        get wiTotalItems() { return this.$store.global.wiTotalItems; },
        set wiTotalItems(val) { this.$store.global.wiTotalItems = val; },
        get wiTotalPages() { return this.$store.global.wiTotalPages; },
        set wiTotalPages(val) { this.$store.global.wiTotalPages = val; },
        get wiSearchQuery() { return this.$store.global.wiSearchQuery; },
        set wiSearchQuery(val) { this.$store.global.wiSearchQuery = val; },
        get wiFilterType() { return this.$store.global.wiFilterType; },
        set wiFilterType(val) { this.$store.global.wiFilterType = val; },
        get wiFilterCategory() { return this.$store.global.wiFilterCategory || ''; },
        get selectedIds() { return this.$store.global.viewState.selectedIds; },
        set selectedIds(val) { this.$store.global.viewState.selectedIds = val; return true; },
        get lastSelectedId() { return this.$store.global.viewState.lastSelectedId; },
        set lastSelectedId(val) { this.$store.global.viewState.lastSelectedId = val; return true; },
        get draggedCards() { return this.$store.global.viewState.draggedCards; },
        set draggedCards(val) { this.$store.global.viewState.draggedCards = val; return true; },

        get wiUploadHintText() {
            if (this.isGlobalCategoryContext()) {
                return `将添加到全局分类 ${this.wiFilterCategory}`;
            }
            if (this.wiFilterType !== 'all' && this.wiFilterType !== 'global') {
                return '当前不在全局分类上下文，上传到全局目录需要明确确认';
            }
            return '将添加到全局目录 (Global)';
        },

        isGlobalCategoryContext() {
            if (!this.wiFilterCategory) return false;
            const capabilities = this.$store.global.wiFolderCapabilities || {};
            const selected = capabilities[this.wiFilterCategory] || {};
            return (this.wiFilterType === 'global' || this.wiFilterType === 'all') && selected.has_physical_folder;
        },

        // 拖拽状态
        dragOverWi: false,

        buildWorldInfoUploadFormData(files, { allowGlobalFallback = false } = {}) {
            const formData = new FormData();
            let hasJson = false;

            for (let i = 0; i < files.length; i++) {
                if (files[i].name.toLowerCase().endsWith('.json')) {
                    formData.append('files', files[i]);
                    hasJson = true;
                }
            }

            if (!hasJson) {
                return null;
            }

            const source_context = this.wiFilterType;
            const target_category = this.isGlobalCategoryContext() ? this.wiFilterCategory : '';
            formData.append('source_context', source_context);
            formData.append('target_category', target_category);
            if (allowGlobalFallback) {
                formData.append('allow_global_fallback', 'true');
            }
            return formData;
        },

        getWorldInfoSourceBadge(item) {
            const source_type = item?.source_type || item?.type;
            if (source_type === 'global') return 'GLOBAL';
            if (source_type === 'resource') return 'RESOURCE';
            return 'EMBEDDED';
        },

        getWorldInfoOwnerName(item) {
            return item?.owner_card_name || item?.card_name || '';
        },

        getWorldInfoOwnerId(item) {
            return item?.owner_card_id || item?.card_id || '';
        },

        getWorldInfoDisplayCategory(item) {
            return item?.display_category || item?.physical_category || '';
        },

        getWorldInfoOwnerFallback(item) {
            const sourceType = item?.source_type || item?.type;
            if (sourceType === 'resource') return 'Resource Lorebook';
            if (sourceType === 'embedded') return 'Embedded Lorebook';
            return 'Global Lorebook';
        },

        getWorldInfoTagPlaceholder(_item) {
            return '标签待接入';
        },

        getWorldInfoNoteState(item) {
            return this.worldInfoHasLocalNote(item) ? '有备注' : '无备注';
        },

        formatCategoryLabel(category) {
            const raw = String(category || '').trim();
            if (!raw) return '根目录';

            const normalized = raw
                .replace(/\\+/g, '/')
                .replace(/\/+/g, '/')
                .replace(/^\/+|\/+$/g, '');
            if (!normalized) return '根目录';
            return normalized;
        },

        getWorldInfoItemById(id) {
            return (this.wiList || []).find(item => item.id === id) || null;
        },

        getWorldInfoRenderKey(item) {
            const id = String(item?.id || '');
            const summary = String(item?.ui_summary || '');
            return `${id}::${summary}`;
        },

        openMarkdownView(content) {
            if (!content) return;
            window.dispatchEvent(new CustomEvent('open-markdown-view', {
                detail: content
            }));
        },

        worldInfoHasLocalNote(item) {
            const summary = item && typeof item.ui_summary === 'string' ? item.ui_summary.trim() : '';
            return summary.length > 0;
        },

        openWorldInfoLocalNote(item) {
            if (!this.worldInfoHasLocalNote(item)) return;
            this.openMarkdownView(item.ui_summary);
        },

        isWorldInfoFlipped(itemId) {
            return !!this.flippedWorldInfoIds[String(itemId)];
        },

        toggleWorldInfoFace(itemId) {
            const key = String(itemId);
            const next = { ...this.flippedWorldInfoIds };
            next[key] = !next[key];
            if (!next[key]) delete next[key];
            this.flippedWorldInfoIds = next;
            this.clearWorldInfoAutoFlipBackTimer(key);
        },

        handleWorldInfoMouseEnter(itemId) {
            this.clearWorldInfoAutoFlipBackTimer(String(itemId));
        },

        handleWorldInfoMouseLeave(itemId) {
            this.scheduleWorldInfoAutoFlipBack(itemId);
        },

        scheduleWorldInfoAutoFlipBack(itemId) {
            if (this.$store.global.deviceType === 'mobile') return;
            if (this.worldInfoBulkBackMode) return;
            if (!this.isWorldInfoFlipped(itemId)) return;

            const key = String(itemId);
            this.clearWorldInfoAutoFlipBackTimer(key);
            this._worldInfoAutoFlipBackTimers[key] = setTimeout(() => {
                if (this.worldInfoBulkBackMode || !this.isWorldInfoFlipped(itemId)) {
                    this.clearWorldInfoAutoFlipBackTimer(key);
                    return;
                }

                const next = { ...this.flippedWorldInfoIds };
                delete next[key];
                this.flippedWorldInfoIds = next;
                this.clearWorldInfoAutoFlipBackTimer(key);
            }, this.worldInfoAutoFlipBackDelayMs);
        },

        clearWorldInfoAutoFlipBackTimer(itemKey) {
            const timer = this._worldInfoAutoFlipBackTimers[itemKey];
            if (!timer) return;

            clearTimeout(timer);
            delete this._worldInfoAutoFlipBackTimers[itemKey];
        },

        clearAllWorldInfoAutoFlipBackTimers() {
            Object.keys(this._worldInfoAutoFlipBackTimers).forEach(key => this.clearWorldInfoAutoFlipBackTimer(key));
        },

        syncWorldInfoUiState() {
            const activeIds = new Set((this.wiList || []).map(item => String(item.id)));

            const nextFlipped = {};
            if (this.worldInfoBulkBackMode) {
                activeIds.forEach(key => {
                    nextFlipped[key] = true;
                });
            } else {
                Object.keys(this.flippedWorldInfoIds).forEach(key => {
                    if (activeIds.has(key) && this.flippedWorldInfoIds[key]) {
                        nextFlipped[key] = true;
                    }
                });
            }
            this.flippedWorldInfoIds = nextFlipped;

            Object.keys(this._worldInfoAutoFlipBackTimers).forEach(key => {
                if (this.worldInfoBulkBackMode || !activeIds.has(String(key)) || !nextFlipped[key]) {
                    this.clearWorldInfoAutoFlipBackTimer(key);
                }
            });
        },

        toggleWorldInfoBulkFlipMode() {
            if (this.worldInfoBulkBackMode) {
                this.clearAllWorldInfoAutoFlipBackTimers();
                this.flippedWorldInfoIds = {};
                this.worldInfoBulkBackMode = false;
                return;
            }

            const next = {};
            (this.wiList || []).forEach(item => {
                next[String(item.id)] = true;
            });
            this.clearAllWorldInfoAutoFlipBackTimers();
            this.flippedWorldInfoIds = next;
            this.worldInfoBulkBackMode = true;
        },

        get visibleWorldInfoFlippedCount() {
            return (this.wiList || []).reduce((count, item) => count + (this.isWorldInfoFlipped(item.id) ? 1 : 0), 0);
        },

        selectedWorldInfoItems() {
            return this.selectedIds
                .map(id => this.getWorldInfoItemById(id))
                .filter(Boolean);
        },

        canSelectWorldInfoItem(item) {
            return (item?.source_type || item?.type) !== 'embedded';
        },

        canDeleteWorldInfoItem(item) {
            return !!item && this.canSelectWorldInfoItem(item);
        },

        canMoveWorldInfoItem(item) {
            return !!item && (item.source_type || item.type) === 'global';
        },

        canDeleteWorldInfoSelection() {
            const items = this.selectedWorldInfoItems();
            return items.length > 0 && items.every(item => this.canDeleteWorldInfoItem(item));
        },

        canMoveWorldInfoSelection() {
            const items = this.selectedWorldInfoItems();
            return items.length > 0 && items.every(item => this.canMoveWorldInfoItem(item));
        },

        toggleSelection(item) {
            if (!this.canSelectWorldInfoItem(item)) return;

            let ids = [...this.selectedIds];
            if (ids.includes(item.id)) {
                ids = ids.filter(id => id !== item.id);
            } else {
                ids.push(item.id);
                this.lastSelectedId = item.id;
            }
            this.selectedIds = ids;
        },

        handleWorldInfoClick(e, item) {
            if (e.ctrlKey || e.metaKey) {
                this.toggleSelection(item);
                return;
            }

            if (e.shiftKey && this.lastSelectedId) {
                const selectableItems = (this.wiList || []).filter(currentItem => this.canSelectWorldInfoItem(currentItem));
                const startIdx = selectableItems.findIndex(currentItem => currentItem.id === this.lastSelectedId);
                const endIdx = selectableItems.findIndex(currentItem => currentItem.id === item.id);

                if (startIdx !== -1 && endIdx !== -1) {
                    const min = Math.min(startIdx, endIdx);
                    const max = Math.max(startIdx, endIdx);
                    const rangeIds = selectableItems.slice(min, max + 1).map(currentItem => currentItem.id);
                    const currentSet = new Set(this.selectedIds);
                    rangeIds.forEach(id => currentSet.add(id));
                    this.selectedIds = Array.from(currentSet);
                }
                return;
            }

            this.openWiDetail(item);
        },

        dragStart(e, item) {
            if (!this.canSelectWorldInfoItem(item)) {
                e.preventDefault();
                return;
            }

            let ids = [...this.selectedIds];
            if (!ids.includes(item.id)) {
                ids = Array.of(item.id);
                this.selectedIds = ids;
            }

            const selectedItems = ids.map(id => this.getWorldInfoItemById(id)).filter(Boolean);
            if (!this.canMoveWorldInfoSelection()) {
                e.preventDefault();
                return;
            }

            this.draggedCards = ids;
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('application/x-st-worldinfo', JSON.stringify(ids));
            e.dataTransfer.setData('text/plain', item.id);

            const cardElement = e.target.closest('.wi-grid-card');
            if (cardElement) {
                requestAnimationFrame(() => {
                    cardElement.classList.add('drag-source');
                });

                const cleanup = () => {
                    cardElement.classList.remove('drag-source');
                    window.dispatchEvent(new CustomEvent('global-drag-end'));
                };

                e.target.addEventListener('dragend', cleanup, { once: true });
            }
        },

        async moveSelectedWorldInfo(target_category = '') {
            if (!this.canMoveWorldInfoSelection()) return;

            const items = this.selectedWorldInfoItems();
            const count = items.length;
            const label = target_category || '根目录';
            if (!confirm(`移动 ${count} 本世界书到 "${label}"?`)) return;

            for (const item of items) {
                const resp = await fetch('/api/world_info/category/move', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        source_type: item.source_type || item.type,
                        file_path: item.path,
                        target_category,
                    })
                });
                const res = await resp.json();
                if (!res?.success) {
                    alert(res?.msg || '移动失败');
                    return;
                }
            }

            this.$store.global.showToast(`✅ 已移动 ${count} 本世界书`);
            this.selectedIds = [];
            this.fetchWorldInfoList();
        },

        async deleteSelectedWorldInfo() {
            if (!this.canDeleteWorldInfoSelection()) return;

            const items = this.selectedWorldInfoItems();
            const count = items.length;
            if (!confirm(`确定将选中的 ${count} 本世界书移至回收站吗？`)) return;

            for (const item of items) {
                const res = await deleteWorldInfo({
                    file_path: item.path,
                    source_type: item.source_type || item.type,
                });
                if (!res?.success) {
                    alert(`删除失败: ${res?.msg || '未知错误'}`);
                    return;
                }
            }

            this.$store.global.showToast(`🗑️ 已删除 ${count} 本世界书`);
            this.selectedIds = [];
            this.fetchWorldInfoList();
        },

        init() {
            // === 监听 Store 变化自动刷新 ===
            this.$watch('$store.global.wiSearchQuery', () => {
                this.wiCurrentPage = 1;
                this.fetchWorldInfoList();
            });

            this.$watch('$store.global.wiFilterType', () => {
                this.wiCurrentPage = 1;
                this.fetchWorldInfoList();
            });

            this.$watch('$store.global.wiFilterCategory', () => {
                this.wiCurrentPage = 1;
                this.fetchWorldInfoList();
            });

            this.$watch('$store.global.wiList', () => {
                this.syncWorldInfoUiState();
            });

            // 监听刷新事件
            window.addEventListener('refresh-wi-list', (e) => {
                if (e.detail && e.detail.resetPage) this.wiCurrentPage = 1;
                this.fetchWorldInfoList();
            });

            window.addEventListener('wi-note-updated', (e) => {
                const detail = e.detail || {};
                if (!detail?.id) return;
                const currentItems = Array.isArray(this.wiList) ? [...this.wiList] : [];
                let changed = false;
                currentItems.forEach((item, index) => {
                    if (!item || item.id !== detail.id) return;
                    item.ui_summary = detail.ui_summary || '';
                    currentItems[index] = { ...item };
                    changed = true;
                });
                if (changed) {
                    this.wiList = currentItems;
                }
                this.syncWorldInfoUiState();
            });

            // 监听搜索框输入
            window.addEventListener('wi-search-changed', (e) => {
                this.wiSearchQuery = e.detail;
                this.wiCurrentPage = 1;
                this.fetchWorldInfoList();
            });

            // 提供给外部（例如侧边栏导入按钮）复用的全局上传入口
            window.stUploadWorldInfoFiles = (files) => {
                // 使用当前 wiGrid 实例来处理上传，保证行为与拖拽一致
                this._uploadWorldInfoInternal(files);
            };

            // 新建世界书（由 Header / Sidebar 触发）
            window.addEventListener('create-worldinfo', () => {
                this.createNewWorldInfo();
            });

            window.addEventListener('delete-selected-worldinfo', () => {
                this.deleteSelectedWorldInfo();
            });

            window.addEventListener('move-selected-worldinfo', (e) => {
                this.moveSelectedWorldInfo(e.detail?.target_category || '');
            });
        },

        // === 数据加载 ===
        fetchWorldInfoList() {
            if (Alpine.store('global').serverStatus.status !== 'ready') return;

            Alpine.store('global').isLoading = true;

            const pageSize = Alpine.store('global').settingsForm.items_per_page_wi || 20;

            const params = {
                search: this.wiSearchQuery,
                type: this.wiFilterType,
                category: this.wiFilterCategory,
                page: this.wiCurrentPage,
                page_size: pageSize
            };

            listWorldInfo(params)
                .then(res => {
                    Alpine.store('global').isLoading = false;
                    if (res.success) {
                        // 更新 Store 中的列表
                        this.wiList = res.items;
                        this.$store.global.wiAllFolders = res.all_folders || [];
                        this.$store.global.wiCategoryCounts = res.category_counts || {};
                        this.$store.global.wiFolderCapabilities = res.folder_capabilities || {};
                        this.syncWorldInfoUiState();

                        this.wiTotalItems = res.total || 0;
                        this.wiTotalPages = Math.ceil(this.wiTotalItems / pageSize) || 1;
                    }
                })
                .catch(() => Alpine.store('global').isLoading = false);
        },

        changeWiPage(p) {
            if (p >= 1 && p <= this.wiTotalPages) {
                this.wiCurrentPage = p;
                const el = document.getElementById('wi-scroll-area');
                if (el) el.scrollTop = 0;
                this.fetchWorldInfoList();
            }
        },

        // === 交互逻辑 ===

        // 打开详情 (Popup 弹窗)
        openWiDetail(item) {
            // 派发事件，由 detail_wi_popup 组件监听并显示
            window.dispatchEvent(new CustomEvent('open-wi-detail-modal', { detail: item }));
        },

        // 打开编辑器 (全屏)
        openWorldInfoEditor(item) {
            window.dispatchEvent(new CustomEvent('open-wi-editor', { detail: item }));
        },

        // 新建全局世界书（使用 ST 兼容格式）
        async createNewWorldInfo() {
            const name = prompt('请输入新世界书名称:', 'New World Info');
            if (name === null) return;

            const finalName = String(name || '').trim();
            if (!finalName) {
                alert('世界书名称不能为空');
                return;
            }

            this.$store.global.isLoading = true;
            try {
                const target_category = this.isGlobalCategoryContext() ? this.wiFilterCategory : '';
                const res = await createWorldInfo({ name: finalName, target_category });
                this.$store.global.isLoading = false;
                if (!res || !res.success) {
                    alert(`创建失败: ${(res && res.msg) ? res.msg : '未知错误'}`);
                    return;
                }

                if (this.$store?.global?.showToast) {
                    this.$store.global.showToast('✅ 已创建世界书（ST 兼容格式）', 1800);
                }

                // 刷新列表并定位到新建条目
                window.dispatchEvent(new CustomEvent('refresh-wi-list', { detail: { resetPage: true } }));
                if (res.item) {
                    // 稍作延迟，避免和列表刷新动画冲突
                    setTimeout(() => {
                        this.openWorldInfoEditor(res.item);
                    }, 60);
                }
            } catch (err) {
                this.$store.global.isLoading = false;
                alert(`创建失败: ${err}`);
            }
        },

        // 从详情页进入编辑器
        // 注意：此函数通常在详情页模态框内调用，传递 item 参数
        enterWiEditorFromDetail(item) {
            // 1. 关闭详情弹窗
            window.dispatchEvent(new CustomEvent('close-wi-detail-modal'));

            // 2. 打开全屏编辑器
            // 使用 setTimeout 确保弹窗关闭动画不冲突（可选）
            setTimeout(() => {
                this.openWorldInfoEditor(item);
            }, 50);
        },

        // 跳转到关联角色卡
        jumpToCardFromWi(cardId) {
            window.dispatchEvent(new CustomEvent('jump-to-card-wi', { detail: cardId }));
        },

        // === 文件上传 ===

        // 核心世界书上传逻辑封装，供拖拽和按钮导入复用
        _uploadWorldInfoInternal(files) {
            if (!files || files.length === 0) return;

            const formData = this.buildWorldInfoUploadFormData(files);

            if (!formData) {
                alert("请选择 .json 格式的世界书文件");
                return;
            }

            this.$store.global.isLoading = true;
            uploadWorldInfo(formData)
                .then(res => {
                    if (res?.requires_global_fallback_confirmation) {
                        if (confirm('当前不在全局分类上下文。确认继续上传到全局根目录吗？')) {
                            const fallbackFormData = this.buildWorldInfoUploadFormData(files, { allowGlobalFallback: true });
                            return uploadWorldInfo(fallbackFormData);
                        }
                        return res;
                    }
                    return res;
                })
                .then(res => {
                    this.$store.global.isLoading = false;
                    if (!res) return;
                    if (res.success) {
                        this.$store.global.showToast(res.msg);
                        // 如果当前不在 global 视图，提示切换
                        const currentType = this.$store.global.wiFilterType;
                        if (currentType !== 'all' && currentType !== 'global') {
                            if (confirm("上传成功（已存入全局目录）。是否切换到全局视图查看？")) {
                                this.$store.global.wiFilterType = 'global';
                                window.dispatchEvent(new CustomEvent('refresh-wi-list', { detail: { resetPage: true } }));
                            } else {
                                this.fetchWorldInfoList();
                            }
                        } else {
                            this.fetchWorldInfoList();
                        }
                    } else {
                        alert("上传失败: " + res.msg);
                    }
                })
                .catch(err => {
                    this.$store.global.isLoading = false;
                    alert("网络错误: " + err);
                });
        },

        handleWiFilesDrop(e) {
            this.dragOverWi = false;
            const files = e.dataTransfer.files;
            this._uploadWorldInfoInternal(files);
        }
    }
}
