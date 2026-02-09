/**
 * static/js/components/folderTreeSelector.js
 * 可复用的文件夹树选择器组件
 * 
 * 使用方式：
 * <div x-data="folderTreeSelector({ 
 *   selectedPathVar: 'targetCategory',  // 父组件中要绑定的变量名（字符串）
 *   showQuickButtons: true,
 *   maxHeight: '220px'
 * })" 
 * @folder-selected="targetCategory = $event.detail.path">
 *   <!-- 组件会自动读取 $store.global.allFoldersList -->
 * </div>
 * 
 * 组件会通过 $parent 访问父组件的变量，实现双向绑定。
 */

import { buildFolderTree } from '../utils/folderTree.js';

export default function folderTreeSelector(config = {}) {
    return {
        // 配置参数
        selectedPathVar: config.selectedPathVar || 'targetCategory', // 父组件变量名
        showQuickButtons: config.showQuickButtons !== false,
        maxHeight: config.maxHeight || '220px',

        // 本地展开状态
        expandedFolders: {},

        // 获取文件夹列表（从全局 Store）
        get allFoldersList() {
            try {
                return Alpine.store('global').allFoldersList || [];
            } catch (e) {
                return [];
            }
        },

        // 获取当前选中的路径（从父组件读取，Alpine.js 会自动追踪响应式变化）
        get selectedPath() {
            try {
                if (this.$parent && this.$parent[this.selectedPathVar] !== undefined) {
                    const value = this.$parent[this.selectedPathVar];
                    // 确保返回字符串，处理 null/undefined
                    return value != null ? String(value) : '';
                }
                return '';
            } catch (e) {
                return '';
            }
        },

        // 计算属性：构建文件夹树
        // 注意：这里不直接用 expandedFolders 去控制可见性，
        // 子级是否显示由 expanded 状态在前端计算，visible 仅表示“这个节点本身是否应该存在”
        get folderTree() {
            const baseTree = buildFolderTree(this.allFoldersList || [], null);
            const expandedMap = this.expandedFolders || {};
            return baseTree.map(folder => ({
                ...folder,
                expanded: !!expandedMap[folder.path]
            }));
        },

        // 切换文件夹展开/收起
        toggleFolder(path, event) {
            if (event) {
                event.stopPropagation();
            }
            this.expandedFolders[path] = !this.expandedFolders[path];
            // 强制更新 (Alpine sometimes needs help with deep object mutation reactivity)
            this.expandedFolders = { ...this.expandedFolders };
        },

        // 选择文件夹
        selectFolder(path) {
            // 更新父组件中的变量
            try {
                if (this.$parent && this.$parent[this.selectedPathVar] !== undefined) {
                    this.$parent[this.selectedPathVar] = path;
                    // 强制触发响应式更新
                    this.$nextTick(() => {
                        // 确保 Alpine.js 检测到变化
                    });
                }
            } catch (e) {
                console.warn('Failed to update parent variable:', e);
            }
            // 触发自定义事件，父组件通过 @folder-selected 监听
            this.$dispatch('folder-selected', { path });
        },
        
        // 检查是否选中（用于快捷按钮）
        isSelected(value) {
            const current = this.selectedPath;
            // 处理 "根目录" 和空字符串的等价关系
            if (value === '根目录' && (current === '' || current === '根目录')) {
                return true;
            }
            if (value === '' && (current === '' || current === '根目录')) {
                return true;
            }
            return current === value;
        },

        // 判断某个节点在当前展开状态下是否应该显示
        // - folder.visible: 控制节点本身是否参与渲染（例如后端过滤结果）
        // - expandedFolders: 控制其父级是否展开，从而决定“子级是否可见”
        isFolderVisible(folder) {
            // 如果节点本身不可见，直接隐藏
            if (folder.visible === false) return false;

            // 根级节点始终可见（前提是自身 visible）
            if (!folder.level || folder.level === 0) {
                return true;
            }

            const parts = String(folder.path || '').split('/');
            if (parts.length <= 1) {
                // 保险起见，按根级处理
                return true;
            }

            // 从父级开始，逐级检查是否都已展开
            let currentPath = '';
            for (let i = 0; i < parts.length - 1; i++) {
                currentPath = i === 0 ? parts[i] : `${currentPath}/${parts[i]}`;
                if (!this.expandedFolders[currentPath]) {
                    return false;
                }
            }

            return true;
        }
    }
}
