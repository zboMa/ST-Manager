/**
 * static/js/components/batchTagModal.js
 * 批量标签操作组件
 */

import { batchUpdateTags } from '../api/system.js';

export default function batchTagModal() {
    return {
        // === 本地状态 ===
        showBatchTagModal: false,
        batchTagPickerSearch: "",
        
        // 输入框状态
        batchTagInputAdd: "",
        batchTagInputRemove: "",
        
        // 批量选择器状态 (从池中选)
        batchSelectedTags: [],
        
        // 目标卡片 IDs
        targetIds: [],

        init() {
            // 监听打开事件
            window.addEventListener('open-batch-tag-modal', (e) => {
                // e.detail.ids 来自 Header 发出的事件
                this.targetIds = e.detail && e.detail.ids ? e.detail.ids : [];
                
                if (this.targetIds.length === 0) {
                    // 如果事件没传，尝试直接读 Store (容错)
                    this.targetIds = this.$store.global.viewState.selectedIds || [];
                }

                if (this.targetIds.length === 0) {
                    alert("未选择任何卡片");
                    return;
                }

                // 重置表单
                this.batchTagInputAdd = "";
                this.batchTagInputRemove = "";
                this.batchSelectedTags = [];
                this.showBatchTagModal = true;
            });
        },

        // === 计算属性：过滤标签池 ===
        get filteredBatchTagPool() {
            const pool = this.$store.global.globalTagsPool || [];
            if (!this.batchTagPickerSearch) return pool;
            return pool.filter(t => t.toLowerCase().includes(this.batchTagPickerSearch.toLowerCase()));
        },

        // === 选择器操作 ===

        toggleBatchSelectTag(tag) {
            const i = this.batchSelectedTags.indexOf(tag);
            if (i > -1) this.batchSelectedTags.splice(i, 1);
            else this.batchSelectedTags.push(tag);
        },

        // === 执行批量操作 ===

        // 1. 添加 (从输入框或选择器)
        // 注意：HTML 中通常有两个入口，一个是输入框回车调用 batchAddTag，一个是“应用选择”调用 applyBatchAddTags
        
        batchAddTag(tag) {
            const val = (tag || this.batchTagInputAdd || "").trim();
            if (!val) return;
            
            this._performBatchUpdate([val], [], "add", { triggerMerge: true });
        },

        applyBatchAddTags() {
            if (this.batchSelectedTags.length === 0) return alert("未选择任何标签");
            this._performBatchUpdate(this.batchSelectedTags, [], "add-select");
        },

        // 2. 移除
        batchRemoveTag(tag) {
            const val = (tag || this.batchTagInputRemove || "").trim();
            if (!val) return;
            
            this._performBatchUpdate([], [val], "remove");
        },

        applyBatchRemoveTags() {
            if (this.batchSelectedTags.length === 0) return alert("未选择任何标签");
            this._performBatchUpdate([], this.batchSelectedTags, "remove-select");
        },

        // 内部统一执行函数
        _performBatchUpdate(addList, removeList, mode, options = {}) {
            if (this.targetIds.length === 0) {
                alert("未选择任何卡片");
                return;
            }

            batchUpdateTags({
                card_ids: this.targetIds,
                add: addList,
                remove: removeList,
                trigger_merge: !!options.triggerMerge
            })
            .then(res => {
                if (res.success) {
                    let message = "成功更新 " + res.updated + " 张卡片";
                    const merge = res.tag_merge || {};
                    if (merge.cards) {
                        message += `\n全局标签合并已应用到 ${merge.cards} 张卡片`;
                    }
                    alert(message);
                    
                    // 清理状态
                    if (mode === "add") this.batchTagInputAdd = "";
                    if (mode === "remove") this.batchTagInputRemove = "";
                    if (mode.includes("select")) this.batchSelectedTags = [];
                    
                    // 刷新列表
                    window.dispatchEvent(new CustomEvent('refresh-card-list'));
                    this.showBatchTagModal = false;
                } else {
                    alert(res.msg);
                }
            });
        }
    }
}
