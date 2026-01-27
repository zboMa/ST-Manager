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

        // 获取文件夹列表（从全局 Store）
        get allFoldersList() {
            try {
                return Alpine.store('global').allFoldersList || [];
            } catch (e) {
                return [];
            }
        },

        // 获取当前选中的路径（从父组件读取）
        get selectedPath() {
            try {
                if (this.$parent && this.$parent[this.selectedPathVar] !== undefined) {
                    return this.$parent[this.selectedPathVar];
                }
                return '';
            } catch (e) {
                return '';
            }
        },

        // 计算属性：构建文件夹树
        get folderTree() {
            return buildFolderTree(this.allFoldersList || []);
        },

        // 选择文件夹
        selectFolder(path) {
            // 更新父组件中的变量
            try {
                if (this.$parent && this.$parent[this.selectedPathVar] !== undefined) {
                    this.$parent[this.selectedPathVar] = path;
                }
            } catch (e) {
                console.warn('Failed to update parent variable:', e);
            }
            // 触发自定义事件，父组件通过 @folder-selected 监听
            this.$dispatch('folder-selected', { path });
        }
    }
}
