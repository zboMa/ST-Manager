/**
 * static/js/components/wiDetailPopup.js
 * 世界书详情弹窗组件 (对应 detail_wi_popup.html)
 */

import { wiHelpers } from '../utils/wiHelpers.js';
import { deleteWorldInfo, getWorldInfoDetail } from '../api/wi.js';
import { getCardDetail } from '../api/card.js';
import { normalizeWiBook } from '../utils/data.js';
import { formatWiKeys, estimateTokens, getTotalWiTokens, getWiTokenClass } from '../utils/format.js';

export default function wiDetailPopup() {
    return {
        // === 本地状态 ===
        showMobileSidebar: false,
        showWiDetailModal: false,
        activeWiDetail: null, // 当前查看的 WI 对象 (包含 id, name, type, path 等)

        // 阅览室数据
        isLoading: false,
        wiData: null,         // 完整的 WI 对象
        wiEntries: [],        // 归一化后的条目数组
        description: "",      // 世界书描述
        isTruncated: false,
        totalEntries: 0,
        previewLimit: 0,
        isContentTruncated: false,
        previewContentLimit: 0,

        // 搜索过滤
        searchTerm: "",
        activeEntry: null,

        highlightEntryKey: null,   // 用于滚动定位后的短暂高亮
        highlightTimer: null,

        uiFilter: null,    // 'enabled' | 'disabled' | null
        uiStrategy: null,  // 'constant' | 'vector' | 'normal' | null

        // 引入工具函数
        formatWiKeys,
        estimateTokens,
        getWiTokenClass,
        ...wiHelpers,

        init() {
            // 监听关闭状态，彻底清理残留数据
            this.$watch('showWiDetailModal', (val) => {
                if (!val) {
                    this.highlightEntryKey = null;
                    if (this.highlightTimer) clearTimeout(this.highlightTimer);
                    this.activeEntry = null;
                }
            });

            // 监听打开事件 (通常由 wiGrid 触发)
            window.addEventListener('open-wi-detail-modal', async (e) => {
                const nextDetail = e.detail;

                // 1. 设置元数据
                this.activeWiDetail = nextDetail;
                
                // 2. 重置 UI 状态 (但不清空列表)
                this.description = "";
                this.activeEntry = null;
                this.uiFilter = null;
                this.uiStrategy = null;
                this.searchTerm = "";
                this.isTruncated = false;
                this.totalEntries = 0;
                this.previewLimit = 0;
                this.isContentTruncated = false;
                this.previewContentLimit = 0;
                
                // 3. 立即开启 Loading 遮罩
                // 这会让用户看到加载动画，而不是旧数据
                this.isLoading = true;
                
                // 4. 显示弹窗
                this.showWiDetailModal = true;
                
                // 5. 加载数据
                this.loadContent(nextDetail.id);
            });

            // 监听关闭事件 (如果其他组件需要强制关闭它)
            window.addEventListener('close-wi-detail-modal', () => {
                this.showWiDetailModal = false;
            });
        },

        // === 计算属性 ===

        get filteredEntries() {
            if (!this.searchTerm) return this.wiEntries;
            const lower = this.searchTerm.toLowerCase();
            return this.wiEntries.filter(e => {
                const keys = Array.isArray(e.keys) ? e.keys.join(' ') : (e.keys || '');
                const content = e.content || '';
                const comment = e.comment || '';
                return keys.toLowerCase().includes(lower) ||
                    content.toLowerCase().includes(lower) ||
                    comment.toLowerCase().includes(lower);
            });
        },

        get uiFilteredEntries() {
            let arr = this.filteredEntries || [];

            // 1) Enabled / Disabled
            if (this.uiFilter === 'enabled') arr = arr.filter(e => !!e.enabled);
            if (this.uiFilter === 'disabled') arr = arr.filter(e => !e.enabled);

            // 2) Strategy
            if (this.uiStrategy === 'constant') arr = arr.filter(e => !!e.constant);
            if (this.uiStrategy === 'vector') arr = arr.filter(e => !e.constant && !!e.vectorized);
            if (this.uiStrategy === 'normal') arr = arr.filter(e => !e.constant && !e.vectorized);

            return arr;
        },

        // 格式化时间戳
        formatDate(timestamp) {
            if (!timestamp) return '';
            return new Date(timestamp * 1000).toLocaleString();
        },

        get totalTokens() {
            return getTotalWiTokens(this.wiEntries);
        },

        // 选中某个条目查看详情
        selectEntry(entry, shouldScroll = false) {
            this.activeEntry = entry;
            if (shouldScroll) {
                this.$nextTick(() => this.scrollToEntry(entry));
            }
        },

        scrollToEntry(entry) {
            if (!entry) return;

            // 使用唯一 ID 查找
            const domId = `wi-reader-entry-${entry.id}`; 
            const el = document.getElementById(domId);

            if (!el) return;

            try {
                el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
            } catch {
                el.scrollIntoView();
            }

            this.highlightEntryKey = entry.id; // 直接使用 ID
            if (this.highlightTimer) clearTimeout(this.highlightTimer);
            this.highlightTimer = setTimeout(() => {
                this.highlightEntryKey = null;
            }, 900);
        },

        async loadContent(targetId) {
            // 防抖检查
            if (targetId && (!this.activeWiDetail || this.activeWiDetail.id !== targetId)) return;
            
            this.isLoading = true; // 确保加载状态
            
            try {
                let rawData = null;
                let embeddedPreviewApplied = false;
                const previewLimit = 300;
                const entryContentLimit = 2000;

                if (this.activeWiDetail.type === 'embedded') {
                    const res = await getCardDetail(this.activeWiDetail.card_id, {
                        preview_wi: true,
                        wi_preview_limit: previewLimit,
                        wi_preview_entry_max_chars: entryContentLimit
                    });
                    if (res.success && res.card) {
                        rawData = res.card.character_book;
                        this.description = res.card.description || "";
                        if (res.card.wi_preview) {
                            embeddedPreviewApplied = true;
                            const preview = res.card.wi_preview;
                            if (preview.truncated) {
                                this.isTruncated = true;
                                this.totalEntries = preview.total_entries || 0;
                                this.previewLimit = preview.preview_limit || 0;
                            } else {
                                this.isTruncated = false;
                                this.totalEntries = 0;
                                this.previewLimit = 0;
                            }
                            if (preview.truncated_content) {
                                this.isContentTruncated = true;
                                this.previewContentLimit = preview.preview_entry_max_chars || 0;
                            } else {
                                this.isContentTruncated = false;
                                this.previewContentLimit = 0;
                            }
                        }
                    }
                } else {
                    const res = await getWorldInfoDetail({
                        id: this.activeWiDetail.id,
                        source_type: this.activeWiDetail.type,
                        file_path: this.activeWiDetail.path,
                        preview_limit: previewLimit
                    });
                    if (res.success) {
                        rawData = res.data;
                        if (res.truncated) {
                            this.isTruncated = true;
                            this.totalEntries = res.total_entries || 0;
                            this.previewLimit = res.preview_limit || 0;
                        } else {
                            this.isTruncated = false;
                            this.totalEntries = 0;
                            this.previewLimit = 0;
                        }
                        if (res.truncated_content) {
                            this.isContentTruncated = true;
                            this.previewContentLimit = res.preview_entry_max_chars || 0;
                        } else {
                            this.isContentTruncated = false;
                            this.previewContentLimit = 0;
                        }
                    }
                }

                // 二次检查，防止异步请求回来时已经切换了页面
                if (targetId && this.activeWiDetail.id !== targetId) return;

                if (rawData) {
                    // 对内嵌世界书做轻量预览截断，防止渲染卡死
                    if (this.activeWiDetail.type === 'embedded' && !embeddedPreviewApplied) {
                        const previewResult = this._applyPreviewLimits(rawData, previewLimit, entryContentLimit);
                        rawData = previewResult.data;
                        if (previewResult.truncated) {
                            this.isTruncated = true;
                            this.totalEntries = previewResult.totalEntries;
                            this.previewLimit = previewResult.previewLimit;
                        }
                        if (previewResult.truncatedContent) {
                            this.isContentTruncated = true;
                            this.previewContentLimit = previewResult.previewContentLimit;
                        }
                    }
                    const book = normalizeWiBook(rawData, this.activeWiDetail.name);
                    this.wiData = book;
                    let rawEntries = Array.isArray(book.entries) ? book.entries : Object.values(book.entries || {});
                    
                    // 使用 "会话前缀" + 索引，确保每次打开时 ID 都是全新的字符串
                    const sessionPrefix = 's' + Date.now() + '-'; 
                    
                    const processedEntries = rawEntries.map((e, idx) => {
                        // 浅拷贝对象，避免修改原始引用
                        const newEntry = { ...e };
                        // 使用索引号作为 id，确保 Alpine.js key 追踪稳定
                        newEntry.id = idx;
                        return newEntry;
                    });

                    // 一次性赋值，触发更新
                    this.wiEntries = processedEntries;

                    if (book.description) this.description = book.description;
                } else {
                    this.wiEntries = [];
                }

            } catch (err) {
                console.error("Failed to load WI detail:", err);
                this.wiEntries = [];
            } finally {
                // 稍微延迟关闭 loading，让 DOM 有时间渲染
                setTimeout(() => {
                    this.isLoading = false;
                }, 50);
            }
        },

        _applyPreviewLimits(rawData, previewLimit, entryContentLimit) {
            let data = rawData;
            let truncated = false;
            let truncatedContent = false;
            let totalEntries = 0;

            const countEntries = (d) => {
                if (Array.isArray(d)) return d.length;
                if (d && typeof d === 'object') {
                    const entries = d.entries;
                    if (Array.isArray(entries)) return entries.length;
                    if (entries && typeof entries === 'object') return Object.keys(entries).length;
                }
                return 0;
            };

            const truncateEntry = (entry) => {
                if (!entry || typeof entry !== 'object') return entry;
                const newEntry = { ...entry };
                if (typeof newEntry.content === 'string' && newEntry.content.length > entryContentLimit) {
                    newEntry.content = newEntry.content.slice(0, entryContentLimit) + ' ...';
                    truncatedContent = true;
                }
                if (typeof newEntry.comment === 'string' && newEntry.comment.length > entryContentLimit) {
                    newEntry.comment = newEntry.comment.slice(0, entryContentLimit) + ' ...';
                    truncatedContent = true;
                }
                return newEntry;
            };

            totalEntries = countEntries(data);
            if (previewLimit > 0 && totalEntries > previewLimit) {
                if (Array.isArray(data)) {
                    data = data.slice(0, previewLimit);
                } else if (data && typeof data === 'object') {
                    const entries = data.entries;
                    if (Array.isArray(entries)) {
                        data = { ...data, entries: entries.slice(0, previewLimit) };
                    } else if (entries && typeof entries === 'object') {
                        const keys = Object.keys(entries);
                        const trimmed = {};
                        keys.slice(0, previewLimit).forEach((k) => { trimmed[k] = entries[k]; });
                        data = { ...data, entries: trimmed };
                    }
                }
                truncated = true;
            }

            if (entryContentLimit > 0) {
                if (Array.isArray(data)) {
                    data = data.map((e) => truncateEntry(e));
                } else if (data && typeof data === 'object') {
                    const entries = data.entries;
                    if (Array.isArray(entries)) {
                        data = { ...data, entries: entries.map((e) => truncateEntry(e)) };
                    } else if (entries && typeof entries === 'object') {
                        const newEntries = {};
                        Object.keys(entries).forEach((k) => {
                            newEntries[k] = truncateEntry(entries[k]);
                        });
                        data = { ...data, entries: newEntries };
                    }
                }
            }

            return {
                data,
                truncated,
                truncatedContent,
                totalEntries,
                previewLimit,
                previewContentLimit: entryContentLimit
            };
        },

        async loadFullContent() {
            if (!this.activeWiDetail) return;

            this.isLoading = true;
            try {
                let res = null;
                if (this.activeWiDetail.type === 'embedded') {
                    res = await getCardDetail(this.activeWiDetail.card_id, { force_full_wi: true });
                } else {
                    res = await getWorldInfoDetail({
                        id: this.activeWiDetail.id,
                        source_type: this.activeWiDetail.type,
                        file_path: this.activeWiDetail.path,
                        force_full: true
                    });
                }
                if (res.success) {
                    const rawData = this.activeWiDetail.type === 'embedded'
                        ? (res.card ? res.card.character_book : null)
                        : res.data;
                    const book = normalizeWiBook(rawData, this.activeWiDetail.name);
                    this.wiData = book;
                    let rawEntries = Array.isArray(book.entries) ? book.entries : Object.values(book.entries || {});
                    const processedEntries = rawEntries.map((e, idx) => {
                        const newEntry = { ...e };
                        // 使用索引号作为 id，确保 Alpine.js key 追踪稳定
                        newEntry.id = idx;
                        return newEntry;
                    });
                    this.wiEntries = processedEntries;
                    this.isTruncated = false;
                    this.totalEntries = 0;
                    this.previewLimit = 0;
                    this.isContentTruncated = false;
                    this.previewContentLimit = 0;
                    if (book.description) this.description = book.description;
                }
            } catch (err) {
                console.error("Failed to load full WI detail:", err);
            } finally {
                setTimeout(() => {
                    this.isLoading = false;
                }, 50);
            }
        },

        // === 交互逻辑 ===

        // 删除当前世界书
        deleteCurrentWi() {
            if (!this.activeWiDetail) return;

            // 双重保险：如果是嵌入式，直接返回
            if (this.activeWiDetail.type === 'embedded') {
                alert("无法直接删除内嵌世界书，请去角色卡编辑界面操作。");
                return;
            }

            const name = this.activeWiDetail.name || "该世界书";
            if (!confirm(`⚠️ 确定要删除 "${name}" 吗？\n文件将被移至回收站。`)) return;

            deleteWorldInfo(this.activeWiDetail.path)
                .then(res => {
                    if (res.success) {
                        this.showWiDetailModal = false;
                        // 刷新列表
                        window.dispatchEvent(new CustomEvent('refresh-wi-list'));
                        this.$store.global.showToast("🗑️ 已删除"); 
                    } else {
                        alert("删除失败: " + res.msg);
                    }
                })
                .catch(err => alert("请求错误: " + err));
        },

        // 联动跳转编辑器
        enterWiEditorFromDetail(specificEntry = null) {
            const targetEntry = specificEntry || this.activeEntry;

            let jumpToIndex = 0;
            if (targetEntry && this.wiEntries.length > 0) {
                let idx = this.wiEntries.indexOf(targetEntry);
                if (idx !== -1) jumpToIndex = idx;
            }

            this.showWiDetailModal = false;

            // 构造事件数据
            const detailData = {
                ...this.activeWiDetail,
                jumpToIndex: jumpToIndex
            };

            window.dispatchEvent(new CustomEvent('open-wi-editor', {
                detail: detailData
            }));
        },

        // 打开时光机 (Rollback)
        openRollback() {
            this.showWiDetailModal = false; // 关闭当前小弹窗
            this.handleOpenRollback(this.activeWiDetail, null);
        }
    }
}
