/**
 * static/js/components/wiEditor.js
 * 全屏世界书编辑器组件
 */

import {
    getWorldInfoDetail,
    saveWorldInfo,
    clipboardList,
    clipboardAdd,
    clipboardDelete,
    clipboardClear,
    clipboardReorder
} from '../api/wi.js';
import { getCardDetail, updateCard } from '../api/card.js';
import { normalizeWiBook, toStV3Worldbook, getCleanedV3Data, updateWiKeys } from '../utils/data.js';
import { createAutoSaver } from '../utils/autoSave.js';
import { wiHelpers } from '../utils/wiHelpers.js';
import { formatWiKeys, estimateTokens, getTotalWiTokens } from '../utils/format.js';

export default function wiEditor() {
    const autoSaver = createAutoSaver();
    return {
        // === 本地状态 ===
        showFullScreenWI: false,
        showWiList: true,
        showWiSettings: true,
        isLoading: false,
        isSaving: false,

        // 编辑器核心数据
        editingData: {
            id: null,
            char_name: "",
            character_book: { name: "", entries: [] },
            extensions: { regex_scripts: [], tavern_helper: [] }
        },

        // 当前编辑的文件元数据 (用于保存路径)
        editingWiFile: null,

        // 索引与视图控制
        currentWiIndex: 0,

        // === 剪切板状态 ===
        showWiClipboard: false,
        wiClipboardItems: [],
        wiClipboardOverwriteMode: false,
        clipboardPendingEntry: null, // 等待覆写的条目
        isEditingClipboard: false,   // 是否正在编辑剪切板内容
        currentClipboardIndex: -1,

        // 拖拽状态
        wiDraggingIndex: null,

        formatWiKeys,
        estimateTokens,
        updateWiKeys,
        ...wiHelpers,

        get activeCard() {
            return this.editingData;
        },

        // === 初始化 ===
        init() {
            // 监听打开编辑器事件
            window.addEventListener('open-wi-editor', (e) => {
                this.openWorldInfoEditor(e.detail);
            });

            // 监听打开文件事件 (通常用于独立文件)
            window.addEventListener('open-wi-file', (e) => {
                this.openWorldInfoFile(e.detail);
            });

            // 监听关闭
            this.$watch('showFullScreenWI', (val) => {
                if (!val) {
                    autoSaver.stop();
                    this.isEditingClipboard = false;
                    this.currentWiIndex = 0;
                }
            });

            window.addEventListener('keydown', (e) => {
                if (this.showFullScreenWI && e.key === 'Escape') {
                    this.showFullScreenWI = false;
                }
            });
        },

        openRollback() {
            this.handleOpenRollback(this.editingWiFile, this.editingData);
        },

        getTotalWiTokens() {
            // 必须传入当前的条目数组
            return getTotalWiTokens(this.getWIArrayRef());
        },

        saveChanges() {
            // 如果不是内嵌模式，但误调了此方法，转给文件保存逻辑
            if (!this.editingWiFile || this.editingWiFile.type !== 'embedded') {
                return this.saveWiFileChanges();
            }

            this.isSaving = true;

            // 1. 深拷贝当前编辑数据
            const cardData = JSON.parse(JSON.stringify(this.editingData));

            // 2. 使用工具函数清洗 V3 数据结构 (构建标准角色卡 Payload)
            const cleanData = getCleanedV3Data(cardData);

            // 3. 构造发送给 update_card 的完整数据
            const payload = {
                id: this.editingData.id, // 角色卡 ID
                ...cleanData,
                // 1. 映射后端专用字段名
                char_name: cleanData.name || this.editingData.char_name,
                
                // 2. 传递文件名 (防止意外重命名或丢失扩展名)
                new_filename: this.editingData.filename,

                // 3. 补全 UI 专属字段 (如果不传，后端会将其清空)
                ui_summary: this.editingData.ui_summary || "",
                source_link: this.editingData.source_link || "",
                resource_folder: this.editingData.resource_folder || "",
                
                // 4. Bundle 状态透传 (保持包模式状态不丢失)
                save_ui_to_bundle: this.editingData.is_bundle,
                bundle_dir: this.editingData.is_bundle ? this.editingData.bundle_dir : undefined,
                // 显式确保 character_book 被包含（虽然 getCleanedV3Data 也会包含，但双重保险）
                character_book: this.editingData.character_book
            };

            updateCard(payload).then(res => {
                this.isSaving = false;
                if (res.success) {
                    this.$store.global.showToast("💾 角色内嵌世界书已保存", 2000);

                    // 通知外部 (如卡片列表或详情页) 刷新数据
                    window.dispatchEvent(new CustomEvent('card-updated', { detail: res.updated_card }));

                    // 更新自动保存的基准
                    if (autoSaver && typeof autoSaver.initBaseline === 'function') {
                        autoSaver.initBaseline(this.editingData);
                    }
                } else {
                    alert("保存失败: " + res.msg);
                }
            }).catch(e => {
                this.isSaving = false;
                alert("请求错误: " + e);
            });
        },

        // === 辅助：生成自动保存的 Payload ===
        _getAutoSavePayload() {
            // 场景 A: 角色卡内嵌模式
            if (this.editingWiFile && this.editingWiFile.type === 'embedded') {
                // 如果是内嵌，我们需要保存整个 Card 数据 (以此确保一致性)
                const contentToSave = getCleanedV3Data(this.editingData);
                return {
                    id: this.editingData.id, // 角色卡 ID
                    type: 'card',
                    content: contentToSave,
                    file_path: ""
                };
            }

            // 场景 B: 独立世界书文件
            const name = this.editingData.character_book?.name || "World Info";
            const contentToSave = toStV3Worldbook(this.editingData.character_book, name);

            return {
                id: this.editingWiFile ? this.editingWiFile.id : 'unknown',
                type: 'lorebook',
                content: contentToSave,
                file_path: this.editingWiFile ? (this.editingWiFile.path || this.editingWiFile.file_path) : ""
            };
        },

        // === 核心打开逻辑 ===

        // 打开编辑器 (适配三种来源: global, resource, embedded)
        openWorldInfoEditor(item) {
            this.isLoading = true;

            const handleSuccess = (dataObj, source) => {
                // === 强制执行归一化 ===
                // 不管是 embedded 还是 global，统统过一遍清洗
                if (dataObj.character_book) {
                    dataObj.character_book = normalizeWiBook(dataObj.character_book, dataObj.char_name || "WI");
                }

                if (dataObj.character_book && Array.isArray(dataObj.character_book.entries)) {
                    const sessionTs = Date.now();
                    dataObj.character_book.entries.forEach((entry, idx) => {
                        entry.id = `edit-${sessionTs}-${idx}`;
                    });
                }

                // 赋值给响应式对象
                this.editingData = dataObj;
                this.editingWiFile = item;
                let targetIndex = 0;
                if (typeof item.jumpToIndex === 'number' && item.jumpToIndex >= 0) {
                    targetIndex = item.jumpToIndex;
                }
                this.currentWiIndex = targetIndex;
                this.isLoading = false;

                this.openFullScreenWI();

                // 滚动到选中项
                if (targetIndex >= 0) {
                    this.$nextTick(() => {
                        // 稍微延迟以等待列表渲染
                        setTimeout(() => {
                            // 再次强制设置一次 index
                            this.currentWiIndex = targetIndex;

                            const elId = `wi-item-${targetIndex}`;
                            const el = document.getElementById(elId);
                            if (el) {
                                el.scrollIntoView({ behavior: 'auto', block: 'center' }); // 使用 auto 瞬间定位，避免 smooth 还没滚到就停止
                                el.classList.add('bg-accent-main', 'text-white'); // 临时高亮
                                setTimeout(() => el.classList.remove('bg-accent-main', 'text-white'), 800);
                            }
                        }, 100);
                    });
                }
            };

            // 1. 内嵌类型 (Embedded): 获取角色卡数据
            if (item.type === 'embedded') {
                getCardDetail(item.card_id).then(res => {
                    if (res.success && res.card) {
                        // 这是一个角色卡对象，character_book 在其中
                        this.editingData = res.card;

                        // 确保 character_book 存在
                        if (!this.editingData.character_book) {
                            this.editingData.character_book = { name: item.name || "World Info", entries: [] };
                        } else if (Array.isArray(this.editingData.character_book)) {
                            // 兼容 V2 数组
                            this.editingData.character_book = {
                                name: item.name || "World Info",
                                entries: this.editingData.character_book
                            };
                        }

                        this.editingWiFile = item;
                        this.currentWiIndex = 0;
                        this.isEditingClipboard = false;
                        this.currentClipboardIndex = -1;

                        handleSuccess(res.card, "Embedded");
                    } else {
                        alert("无法加载关联的角色卡数据");
                    }
                }).catch(e => {
                    this.isLoading = false;
                    alert("加载失败: " + e);
                });
                return;
            } else {
                // 独立文件 (Global / Resource)
                getWorldInfoDetail({
                    id: item.id,
                    source_type: item.type, // list 返回的是 type
                    file_path: item.path,
                    force_full: true
                }).then(res => {
                    if (res.success) {
                        // 归一化数据
                        const bookData = normalizeWiBook(res.data, "");
                        this.editingData.character_book = bookData;

                        this.editingWiFile = item;
                        this.currentWiIndex = 0;
                        this.isEditingClipboard = false;
                        this.currentClipboardIndex = -1;
                        const dummyObj = {
                            id: null,
                            character_book: res.data // 这里是原始数据
                        };
                        handleSuccess(dummyObj, "Global/Resource");
                    } else {
                        alert(res.msg);
                    }
                }).catch(e => {
                    this.isLoading = false;
                    alert("加载失败: " + e);
                });
            }
        },

        // 打开独立文件 (兼容接口)
        openWorldInfoFile(item) {
            this.isLoading = true;
            getWorldInfoDetail({
                id: item.id,
                source_type: item.source_type,
                file_path: item.file_path,
                force_full: true
            }).then(res => {
                this.isLoading = false;
                if (res.success) {
                    const book = normalizeWiBook(res.data, item.name || "World Info");
                    
                    if (Array.isArray(book.entries)) {
                        const sessionTs = Date.now();
                        book.entries.forEach((entry, idx) => {
                            entry.id = `edit-${sessionTs}-${idx}`;
                        });
                    }
                    
                    this.editingData.character_book = book;
                    this.editingWiFile = item;
                    this.openFullScreenWI();
                    this.$nextTick(() => {
                        autoSaver.initBaseline(this.editingData);
                        autoSaver.start(() => this.editingData, () => this._getAutoSavePayload());
                    });
                } else {
                    this.isLoading = false; alert(res.msg);
                }
            });
        },

        openFullScreenWI() {
            this.showFullScreenWI = true;
            // 确保选中第一项
            const entries = this.getWIArrayRef();
            if (entries.length > 0) {
                this.currentWiIndex = 0;
            }
            // 加载剪切板
            this.loadWiClipboard();
        },

        // === 数据存取 ===

        getWIEntries() {
            return this.getWIArrayRef();
        },

        // 获取当前编辑器应该显示的数据 (Computed)
        get activeEditorEntry() {
            if (this.isEditingClipboard) {
                if (this.currentClipboardIndex >= 0 && this.currentClipboardIndex < this.wiClipboardItems.length) {
                    return this.wiClipboardItems[this.currentClipboardIndex].content;
                }
                return null;
            } else {
                const arr = this.getWIArrayRef();
                if (this.currentWiIndex >= 0 && this.currentWiIndex < arr.length) {
                    return arr[this.currentWiIndex];
                }
                return null;
            }
        },

        // === 保存逻辑 ===

        saveWiFileChanges() {
            if (!this.editingWiFile) return;

            // 如果是内嵌模式，实际上应该调用 UpdateCard
            if (this.editingWiFile.type === 'embedded') {
                alert("内嵌世界书将随角色卡自动保存 (Auto-save) 或请关闭后点击角色保存。");
                return;
            }

            // 独立文件保存
            const contentToSave = toStV3Worldbook(
                this.editingData.character_book,
                this.editingData.character_book?.name || this.editingWiFile?.name || "World Info"
            );

            saveWorldInfo({
                save_mode: 'overwrite',
                file_path: this.editingWiFile.file_path || this.editingWiFile.path,
                content: contentToSave,
                compact: true
            }).then(res => {
                if (res.success) {
                    this.$store.global.showToast("💾 世界书已保存", 2000);
                    autoSaver.initBaseline(this.editingData);
                } else {
                    alert("保存失败: " + res.msg);
                }
            });
        },

        saveAsGlobalWi() {
            const name = prompt("请输入新世界书名称:", this.editingData.character_book.name || "New World Book");
            if (!name) return;

            const contentToSave = toStV3Worldbook(this.editingData.character_book, name);
            contentToSave.name = name; // 确保内部名一致

            saveWorldInfo({
                save_mode: 'new_global',
                name: name,
                content: contentToSave,
                compact: true
            }).then(res => {
                if (res.success) {
                    alert("已另存为全局世界书！");
                    window.dispatchEvent(new CustomEvent('refresh-wi-list'));
                } else {
                    alert(res.msg);
                }
            });
        },

        exportWorldBookSingle() {
            const book = this.editingData.character_book || { entries: [], name: "World Info" };
            this.downloadWorldInfoJson(book, book.name);
        },

        // === 剪切板逻辑 ===

        loadWiClipboard() {
            clipboardList().then(res => {
                if (res.success) {
                    // 1. 先清空，给 Alpine 一个明确的信号
                    this.wiClipboardItems = [];

                    // 2. 在 nextTick 中赋值，确保 DOM 准备好重绘
                    this.$nextTick(() => {
                        this.wiClipboardItems = res.items;

                        // 3. 强制确保侧边栏是展开的，否则用户看不到
                        if (this.wiClipboardItems.length > 0) {
                            this.showWiClipboard = true;
                        }
                    });
                }
            });
        },

        saveClipboardItem() {
            if (!this.isEditingClipboard || this.currentClipboardIndex === -1) return;
            const item = this.wiClipboardItems[this.currentClipboardIndex];
            if (!item) return;

            // 更新 (Overwrite)
            this._addWiClipboardRequest(item.content, item.db_id);
            alert("剪切板条目已更新");
        },

        copyWiToClipboard(entry) {
            // 1. 确定目标数据：优先使用传入参数，否则使用当前编辑器内容
            let targetData = entry;

            // 如果传入的是 Event 对象（点击事件），或者为空，则使用当前编辑器数据
            if (!targetData || targetData instanceof Event || (targetData.target && targetData.type)) {
                targetData = this.activeEditorEntry;
            }

            if (!targetData) {
                alert("无法获取要复制的条目内容");
                return;
            }

            // 2. 深度拷贝并清洗 (移除 Proxy，转为纯 JSON 对象)
            let copy;
            try {
                // 使用 JSON 序列化再反序列化，彻底斩断引用和 Proxy
                copy = JSON.parse(JSON.stringify(targetData));
            } catch (e) {
                console.error("Copy failed:", e);
                return;
            }

            // 3. 清理 ID 和 UID，确保被视为新条目
            // 注意：必须显式设置为 undefined 或 delete，防止后端复用 ID
            delete copy.id;
            delete copy.uid;

            // 4. 确保 content 字段存在
            if (copy.content === undefined || copy.content === null) copy.content = "";

            // 5. 发送请求
            this._addWiClipboardRequest(copy);
        },

        _addWiClipboardRequest(entry, overwriteId = null) {
            // 获取当前焦点元素
            const activeEl = document.activeElement;
            const isSafeButton = activeEl &&
                activeEl.tagName === 'BUTTON' &&
                !activeEl.classList.contains('wi-list-item');
            const originalHtml = isSafeButton ? activeEl.innerHTML : '';
            if (isSafeButton && !overwriteId) activeEl.innerHTML = '⏳...';

            clipboardAdd(entry, overwriteId).then(res => {
                if (res.success) {
                    this.wiClipboardItems = [];
                    setTimeout(() => {
                        this.loadWiClipboard();
                    }, 50);
                    this.wiClipboardOverwriteMode = false;
                    this.clipboardPendingEntry = null;
                    if (!this.showWiClipboard) this.showWiClipboard = true;

                    this.$store.global.showToast("📋 已复制到全局剪切板");
                } else if (res.code === 'FULL') {
                    this.wiClipboardOverwriteMode = true;
                    this.clipboardPendingEntry = entry;
                    if (!this.showWiClipboard) this.showWiClipboard = true;
                } else {
                    alert("保存失败: " + res.msg);
                }
            }).finally(() => {
                if (isSafeButton && !overwriteId) activeEl.innerHTML = originalHtml;
            });
        },

        addWiEntryFromClipboard(content) {
            const arr = this.getWIArrayRef();
            const newEntry = JSON.parse(JSON.stringify(content));
            newEntry.id = Math.floor(Math.random() * 1000000);

            let insertPos = this.currentWiIndex + 1;
            if (insertPos > arr.length) insertPos = arr.length;

            arr.splice(insertPos, 0, newEntry);
            this.currentWiIndex = insertPos;
            this.isEditingClipboard = false;

            this.$nextTick(() => {
                const item = document.querySelectorAll('.wi-list-item')[insertPos];
                if (item) item.scrollIntoView({ behavior: 'smooth', block: 'center' });
            });
        },

        deleteWiClipboardItem(dbId) {
            if (!confirm("删除此剪切板条目？")) return;
            clipboardDelete(dbId).then(() => this.loadWiClipboard());
        },

        clearWiClipboard() {
            if (!confirm("清空所有剪切板内容？")) return;
            clipboardClear().then(() => this.loadWiClipboard());
        },

        selectMainWiItem(index) {
            this.isEditingClipboard = false;
            this.currentClipboardIndex = -1;
            this.currentWiIndex = index;
        },

        selectClipboardItem(index) {
            // 覆写模式检查
            if (this.wiClipboardOverwriteMode) {
                const item = this.wiClipboardItems[index];
                if (confirm(`确定要覆盖 "${item.content.comment || '未命名'}" 吗？`)) {
                    this._addWiClipboardRequest(this.clipboardPendingEntry, item.db_id);
                }
                return;
            }
            this.isEditingClipboard = true;
            this.currentClipboardIndex = index;
            this.currentWiIndex = -1;
        },

        exitClipboardEdit() {
            this.isEditingClipboard = false;
            this.currentClipboardIndex = -1;
            // 恢复之前选中的主条目 (如果有)
            const arr = this.getWIArrayRef();
            if (arr.length > 0 && this.currentWiIndex === -1) {
                this.currentWiIndex = 0;
            }
        },

        // === 拖拽排序逻辑 ===

        // 1. 主列表拖拽
        wiDragStart(e, index) {
            this.wiDraggingIndex = index;
            e.dataTransfer.effectAllowed = 'copyMove';
            e.dataTransfer.setData('application/x-wi-index', index.toString());

            const arr = this.getWIArrayRef();
            const item = arr[index];

            if (item) {
                const exportItem = JSON.parse(JSON.stringify(item));
                e.dataTransfer.setData('text/plain', JSON.stringify(exportItem, null, 2));
            }
            const target = e.target;
            target.classList.add('dragging');
            const cleanup = () => {
                target.classList.remove('dragging');
                this.wiDraggingIndex = null;
            };
            target.addEventListener('dragend', cleanup, { once: true });
        },

        wiDragOver(e, index) {
            e.preventDefault();
            const target = e.currentTarget;
            const rect = target.getBoundingClientRect();
            const midY = rect.top + rect.height / 2;

            target.classList.remove('drag-over-top', 'drag-over-bottom');
            if (e.clientY < midY) target.classList.add('drag-over-top');
            else target.classList.add('drag-over-bottom');
        },

        wiDragLeave(e) {
            e.currentTarget.classList.remove('drag-over-top', 'drag-over-bottom');
        },

        wiDrop(e, targetIndex) {
            e.preventDefault();
            e.stopPropagation();
            const el = e.currentTarget;
            el.classList.remove('drag-over-top', 'drag-over-bottom', 'dragging');

            // A. 从剪切板拖入
            const clipData = e.dataTransfer.getData('application/x-wi-clipboard');
            if (clipData) {
                try {
                    const content = JSON.parse(clipData);
                    const arr = this.getWIArrayRef();
                    const newEntry = JSON.parse(JSON.stringify(content));
                    newEntry.id = Math.floor(Math.random() * 1000000);

                    arr.splice(targetIndex, 0, newEntry);
                    this.currentWiIndex = targetIndex;
                    this.isEditingClipboard = false;
                } catch (err) { console.error(err); }
                return;
            }

            // B: 内部列表排序
            let sourceIndexStr = e.dataTransfer.getData('application/x-wi-index');

            if (!sourceIndexStr && this.wiDraggingIndex !== null) {
                sourceIndexStr = this.wiDraggingIndex.toString();
            }

            if (!sourceIndexStr) return;

            const sourceIndex = parseInt(sourceIndexStr);

            if (isNaN(sourceIndex) || sourceIndex === targetIndex) return;

            const arr = this.getWIArrayRef();
            if (sourceIndex >= arr.length || targetIndex > arr.length) return;

            const itemToMove = arr[sourceIndex];

            let oldSelectedIndex = this.currentWiIndex;
            let newSelectedIndex = oldSelectedIndex;

            // 根据拖拽方向执行不同的 splice 操作
            if (sourceIndex < targetIndex) {
                arr.splice(sourceIndex, 1);
                arr.splice(targetIndex - 1, 0, itemToMove);

                if (oldSelectedIndex === sourceIndex) {
                    newSelectedIndex = targetIndex - 1;
                } else if (oldSelectedIndex > sourceIndex && oldSelectedIndex < targetIndex) {
                    newSelectedIndex = oldSelectedIndex - 1;
                }
            } else {
                arr.splice(sourceIndex, 1);
                arr.splice(targetIndex, 0, itemToMove);
                if (oldSelectedIndex === sourceIndex) {
                    newSelectedIndex = targetIndex;
                } else if (oldSelectedIndex >= targetIndex && oldSelectedIndex < sourceIndex) {
                    newSelectedIndex = oldSelectedIndex + 1;
                }
            }

            this.currentWiIndex = newSelectedIndex;
        },

        // 2. 剪切板拖拽
        clipboardDragStart(e, item, idx) {
            e.dataTransfer.setData('application/x-wi-clipboard', JSON.stringify(item.content));
            e.dataTransfer.setData('text/plain', JSON.stringify(item.content));
            e.dataTransfer.effectAllowed = 'copyMove';
            // 内部排序用
            e.dataTransfer.setData('application/x-wi-clipboard-index', idx);

            const target = e.target;
            target.classList.add('dragging');
            target.addEventListener('dragend', () => {
                target.classList.remove('dragging');
            }, { once: true });
        },

        clipboardDropInside(e, targetIdx) {
            e.preventDefault();
            e.stopPropagation();
            const sourceIdxStr = e.dataTransfer.getData('application/x-wi-clipboard-index');
            if (sourceIdxStr) {
                const sourceIdx = parseInt(sourceIdxStr);
                if (sourceIdx === targetIdx) return;
                const items = [...this.wiClipboardItems];
                const [moved] = items.splice(sourceIdx, 1);
                items.splice(targetIdx, 0, moved);
                this.wiClipboardItems = items;
                const orderMap = items.map(i => i.db_id);
                clipboardReorder(orderMap);
                return;
            }

            if (this.wiDraggingIndex !== null && this.wiDraggingIndex !== undefined) {
                const arr = this.getWIArrayRef();
                const rawEntry = arr[this.wiDraggingIndex];
                if (rawEntry) {
                    this.copyWiToClipboard(rawEntry);
                }
            }
        },

        // === 处理剪切板容器的 Drop ===
        handleClipboardDropReorder(e) {
            e.preventDefault();
            e.stopPropagation();

            // 剪切板内部排序
            const isClipboardInternal = e.dataTransfer.types.includes('application/x-wi-clipboard-index');

            if (isClipboardInternal) {
                const sourceIdxStr = e.dataTransfer.getData('application/x-wi-clipboard-index');
                if (sourceIdxStr) {
                    const sourceIdx = parseInt(sourceIdxStr);
                    if (sourceIdx === this.wiClipboardItems.length - 1) return;

                    const items = [...this.wiClipboardItems];
                    const [moved] = items.splice(sourceIdx, 1);
                    items.push(moved);

                    this.wiClipboardItems = items;
                    const orderMap = items.map(i => i.db_id);
                    clipboardReorder(orderMap);
                }
            } else {
                // 从左侧主列表拖入 (复制)
                if (this.wiDraggingIndex !== null && this.wiDraggingIndex !== undefined) {
                    const arr = this.getWIArrayRef();
                    const rawEntry = arr[this.wiDraggingIndex];

                    if (rawEntry) {
                        // 深拷贝
                        let entryCopy = null;
                        try {
                            entryCopy = JSON.parse(JSON.stringify(rawEntry));
                        } catch (err) { return; }
                        this.copyWiToClipboard(entryCopy);
                    }
                }
            }
        }
    }
}
