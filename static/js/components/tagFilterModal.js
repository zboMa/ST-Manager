/**
 * static/js/components/tagFilterModal.js
 * 标签管理模态框 (查看全库标签/删除标签)
 */

import { deleteTags } from '../api/system.js';

export default function tagFilterModal() {
    return {
        // === 本地状态 ===
        showTagFilterModal: false,
        tagSearchQuery: '',
        
        // 删除模式状态
        isDeleteMode: false,
        selectedTagsForDeletion: [],

        get sidebarTagsPool() {
            return this.$store.global.sidebarTagsPool || [];
        },

        // 获取过滤后的标签池 (搜索用)
        get filteredTagsPool() {
            const query = this.tagSearchQuery || '';
            const pool = this.sidebarTagsPool || []; // 使用侧边栏专用池
            if (!query) return pool;
            return pool.filter(t => t.toLowerCase().includes(query.toLowerCase()));
        },

        get filterTags() { return this.$store.global.viewState.filterTags; },
        set filterTags(val) { this.$store.global.viewState.filterTags = val; },

        init() {
            this.$watch('$store.global.showTagFilterModal', (val) => {
                this.showTagFilterModal = val;
                if (!val) {
                    this.isDeleteMode = false;
                    this.selectedTagsForDeletion = [];
                }
            });
            
            // 双向绑定：组件关闭时更新 store
            this.$watch('showTagFilterModal', (val) => {
                this.$store.global.showTagFilterModal = val;
            });

            window.addEventListener('open-tag-filter-modal', () => {
                this.showTagFilterModal = true;
            });
        },

        toggleFilterTag(tag) {
            const store = this.$store.global.viewState;
            let includeTags = [...store.filterTags];
            let excludeTags = [...store.excludedTags];

            const inInclude = includeTags.indexOf(tag);
            const inExclude = excludeTags.indexOf(tag);

            if (inInclude > -1) {
                // 当前是包含 -> 转为排除
                includeTags.splice(inInclude, 1);
                excludeTags.push(tag);
            } else if (inExclude > -1) {
                // 当前是排除 -> 转为无
                excludeTags.splice(inExclude, 1);
            } else {
                // 当前是无 -> 转为包含
                includeTags.push(tag);
            }

            // 更新状态
            this.filterTags = includeTags;
            this.$store.global.viewState.excludedTags = excludeTags;
            
            // 触发刷新 (State 中的 watcher 会自动处理，这里可以不再手动调 fetchCards，或者为了保险保留)
            window.dispatchEvent(new CustomEvent('refresh-card-list'));
        },

        // === 删除模式逻辑 ===

        toggleDeleteMode() {
            this.isDeleteMode = !this.isDeleteMode;
            if (!this.isDeleteMode) {
                this.selectedTagsForDeletion = []; // 退出时清空
            }
        },

        toggleTagSelectionForDeletion(tag) {
            const index = this.selectedTagsForDeletion.indexOf(tag);
            if (index > -1) {
                this.selectedTagsForDeletion.splice(index, 1);
            } else {
                this.selectedTagsForDeletion.push(tag);
            }
        },

        // 从当前视图的卡片中移除选中的标签
        deleteFilterTags() {
            // 合并包含和排除的标签
            const includeTags = this.$store.global.viewState.filterTags;
            const excludeTags = this.$store.global.viewState.excludedTags;
            
            // 合并并去重
            const tags = [...new Set([...includeTags, ...excludeTags])];
            
            if (!tags || tags.length === 0) {
                alert("请先选择要删除的标签");
                return;
            }
            
            // 派发事件给 CardGrid 处理（因为只有 CardGrid 知道当前显示了哪些卡片 ID）
            window.dispatchEvent(new CustomEvent('req-batch-remove-current-tags', {
                detail: { tags: [...tags] }
            }));
        },

        deleteSelectedTags() {
            if (this.selectedTagsForDeletion.length === 0) {
                alert("请先选择要删除的标签");
                return;
            }
            
            const tagsToDelete = this.selectedTagsForDeletion.join(', ');
            
            // 获取当前分类 (从全局状态)
            const currentCategory = this.$store.global.viewState.filterCategory;
            const scopeText = currentCategory ? `"${currentCategory}" 分类下` : "所有";
            
            const confirmMsg = `⚠️ 警告：确定要从【${scopeText}】的角色卡中移除以下标签吗？\n\n${tagsToDelete}\n\n此操作不可撤销！`;
            
            if (!confirm(confirmMsg)) return;
            
            deleteTags({ 
                tags: this.selectedTagsForDeletion,
                category: currentCategory 
            })
            .then(res => {
                if (res.success) {
                    alert(`成功删除 ${res.total_tags_deleted} 个标签，更新了 ${res.updated_cards} 张卡片`);
                    
                    // 1. 更新全局标签池
                    const globalPool = this.$store.global.globalTagsPool || [];
                    const sidebarPool = this.$store.global.sidebarTagsPool || [];
                    
                    this.$store.global.globalTagsPool = globalPool.filter(t => !this.selectedTagsForDeletion.includes(t));
                    this.$store.global.sidebarTagsPool = sidebarPool.filter(t => !this.selectedTagsForDeletion.includes(t));
                    this.$store.global.allTagsPool = this.$store.global.sidebarTagsPool;

                    // 2. 更新 Layout 中的筛选标签 (如果正好删除了当前正在筛选的标签)
                    // 需要访问 Layout 状态，这里通过事件通知
                    // 其实 Layout 可以自己监听 refresh-card-list 并重新校验 tags，这里简单触发刷新即可
                    
                    // 3. 清空选择
                    this.selectedTagsForDeletion = [];
                    this.isDeleteMode = false;
                    
                    // 4. 刷新列表
                    window.dispatchEvent(new CustomEvent('refresh-card-list'));
                } else {
                    alert("删除失败: " + res.msg);
                }
            })
            .catch(err => {
                alert("网络错误: " + err);
            });
        }
    }
}