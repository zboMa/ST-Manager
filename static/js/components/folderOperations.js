/**
 * static/js/components/folderOperations.js
 * 文件夹操作模态框控制器
 */

import { renameFolder, createFolder } from '../api/system.js'; // createSubFolder 实际上也是调用 createFolder
import { buildFolderTree } from '../utils/folderTree.js';

export default function folderOperations() {
    return {
        resourceFolderInput: '',

        // === 1. 代理全局状态 (Getters/Setters) ===
        // 这样 HTML 中的 x-model="folderRenameModal.name" 依然有效，无需修改 HTML 结构
        
        get folderRenameModal() { return this.$store.global.folderModals.rename; },
        get folderCreateSubModal() { return this.$store.global.folderModals.createSub; },
        
        // 兼容 Sidebar 的新建文件夹逻辑
        get showCreateFolder() { return this.$store.global.folderModals.createRoot.visible; },
        set showCreateFolder(val) { this.$store.global.folderModals.createRoot.visible = val; },
        
        get newFolderName() { return this.$store.global.folderModals.createRoot.name; },
        set newFolderName(val) { this.$store.global.folderModals.createRoot.name = val; },
        
        get newFolderParent() { return this.$store.global.folderModals.createRoot.parent; },
        set newFolderParent(val) { this.$store.global.folderModals.createRoot.parent = val; },

        // 获取文件夹列表供下拉框使用
        get allFoldersList() { return this.$store.global.allFoldersList || []; },

        // 复用与侧边栏一致的树形构建逻辑（不依赖展开状态，始终展示完整树）
        get folderTree() {
            return buildFolderTree(this.allFoldersList);
        },

        // === 2. 业务逻辑 ===

        // --- 重命名 ---
        renameFolder() {
            const oldPath = this.folderRenameModal.path;
            const newName = this.folderRenameModal.name.trim();
            
            if (!newName) return alert("名称不能为空");
            if (newName === oldPath.split('/').pop()) {
                this.folderRenameModal.visible = false;
                return;
            }
            
            renameFolder({ old_path: oldPath, new_name: newName })
                .then(res => {
                    if (res.success) {
                        // 刷新文件夹树和卡片列表 (因为路径变了)
                        window.dispatchEvent(new CustomEvent('refresh-folder-list'));
                        window.dispatchEvent(new CustomEvent('refresh-card-list'));
                        this.folderRenameModal.visible = false;
                    } else {
                        alert("重命名失败: " + res.msg);
                    }
                });
        },

        // --- 新建子文件夹 ---
        createSubFolder() {
            const parent = this.folderCreateSubModal.parentPath;
            const name = this.folderCreateSubModal.name.trim();
            
            if (!name) return alert("名称不能为空");
            
            createFolder({ name: name, parent: parent })
                .then(res => {
                    if (res.success) {
                        window.dispatchEvent(new CustomEvent('refresh-folder-list'));
                        this.folderCreateSubModal.visible = false;
                    } else {
                        alert("创建失败: " + res.msg);
                    }
                });
        },

        // --- 新建根文件夹 (Sidebar 使用) ---
        createFolder() {
            const name = this.newFolderName.trim();
            const parent = this.newFolderParent;
            
            if (!name) return alert("名称不能为空");

            createFolder({ name: name, parent: parent })
                .then(res => {
                    if (res.success) {
                        window.dispatchEvent(new CustomEvent('refresh-folder-list'));
                        this.showCreateFolder = false;
                        this.newFolderName = '';
                    } else {
                        alert("创建失败: " + res.msg);
                    }
                });
        }
    }
}