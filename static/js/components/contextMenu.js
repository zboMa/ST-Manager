/**
 * static/js/components/contextMenu.js
 * 上下文菜单组件 (右键菜单)
 */

import { deleteFolder } from '../api/system.js';

import { toggleBundleMode } from '../api/card.js';

import { executeRules } from '../api/automation.js';

export default function contextMenu() {
    return {
        visible: false,
        x: 0,
        y: 0,
        target: null, // path
        type: null,   // 'folder' | 'card'
        targetFolder: null, // 文件夹对象引用
        // 删除文件夹确认弹窗状态（包含“是否删除子文件”可选项）
        deleteFolderConfirm: {
            visible: false,
            path: '',
            cardCount: 0,
            hasSubfolders: false,
            deleteChildren: false
        },

        // 设备类型辅助：用于区分移动端样式
        get isMobile() {
            try {
                return this.$store && this.$store.global && this.$store.global.deviceType === 'mobile';
            } catch (e) {
                return false;
            }
        },

        init() {
            // 监听显示事件 (由 Sidebar 触发)
            window.addEventListener('show-context-menu', (e) => {
                const { x, y, type, target, targetFolder } = e.detail;

                // 边界检测 (防止菜单溢出屏幕)
                const menuWidth = 160;
                const menuHeight = 200;

                this.x = (x + menuWidth > window.innerWidth) ? x - menuWidth : x;
                this.y = (y + menuHeight > window.innerHeight) ? y - menuHeight : y;

                this.type = type;
                this.target = target;
                this.targetFolder = targetFolder;
                this.visible = true;

                window.dispatchEvent(new CustomEvent('load-rulesets-for-menu'));
            });

            // 监听隐藏事件
            window.addEventListener('hide-context-menu', () => {
                this.visible = false;
            });

            // 点击外部自动关闭
            window.addEventListener('click', () => {
                // 弹窗打开时不要被全局 click 立刻关闭，确保可切换复选框并点确认
                if (this.deleteFolderConfirm && this.deleteFolderConfirm.visible) return;
                this.visible = false;
            });
        },

        hideContextMenu() {
            this.visible = false;
        },

        // === 菜单动作 ===

        // 切换目录排除状态
        handleExclude() {
            if (this.type === 'folder' && this.target !== '') {
                const store = this.$store.global;
                let list = [...store.viewState.excludedCategories];

                if (list.includes(this.target)) {
                    // 取消排除
                    list = list.filter(t => t !== this.target);
                } else {
                    // 添加排除
                    list.push(this.target);
                }

                store.viewState.excludedCategories = list;
                this.visible = false;
            }
        },

        // 运行自动化（桌面端）
        handleRunAuto(rulesetId) {
            if (this.target === null || this.target === undefined) return;

            const folderName = this.target === '' ? '根目录' : this.target;
            const msg = `确定对 "${folderName}" 下的所有卡片 (包括子文件夹) 执行此自动化规则吗？\n\n注意：这可能会移动大量文件。`;

            if (!confirm(msg)) return;

            // 关闭菜单
            this.visible = false;
            this.$store.global.isLoading = true;

            executeRules({
                category: this.target, // 传路径给后端，后端解析所有 ID
                recursive: true,
                ruleset_id: rulesetId
            }).then(res => {
                this.$store.global.isLoading = false;
                if (res.success) {
                    alert(`✅ 执行完成！\n已处理: ${res.processed} 张卡片\n移动: ${res.summary.moves}\n变更: ${res.summary.tag_changes}`);
                    // 刷新全部
                    window.dispatchEvent(new CustomEvent('refresh-card-list'));
                    window.dispatchEvent(new CustomEvent('refresh-folder-list'));
                } else {
                    alert("执行失败: " + res.msg);
                }
            }).catch(e => {
                this.$store.global.isLoading = false;
                alert("Error: " + e);
            });
        },

        // 打开移动端执行规则弹窗（文件夹模式）
        handleOpenExecuteRulesMobile() {
            if (this.type !== 'folder' || this.target === null || this.target === undefined) return;
            
            // 关闭菜单
            this.visible = false;
            
            // 触发打开移动端执行规则弹窗事件，传递文件夹信息
            window.dispatchEvent(new CustomEvent('open-execute-rules-mobile-modal', {
                detail: {
                    mode: 'folder',
                    category: this.target,
                    recursive: true
                }
            }));
        },

        // 重命名
        handleRename() {
            if (this.type === 'folder' && this.target) {
                const currentName = this.target.split('/').pop();

                // 直接操作全局 Store
                this.$store.global.folderModals.rename = {
                    visible: true,
                    path: this.target,
                    name: currentName
                };

                this.visible = false;
            }
        },

        // 新建子文件夹
        handleCreateSub() {
            if (this.type === 'folder') {
                // 直接操作全局 Store
                this.$store.global.folderModals.createSub = {
                    visible: true,
                    parentPath: this.target,
                    name: ''
                };

                this.visible = false;
            }
        },

        // 删除
        handleDelete() {
            if (this.type === 'folder') {
                const store = Alpine.store('global');
                const path = this.target;

                // 1. 获取卡片计数 (防止 undefined 默认为 0)
                const cardCount = (store.categoryCounts && store.categoryCounts[path]) || 0;

                // 2. 检查是否有子文件夹
                // 遍历 allFoldersList，看是否有路径以 "path/" 开头的
                const hasSubfolders = store.allFoldersList.some(f =>
                    f.path.startsWith(path + '/') && f.path !== path
                );

                // 3. 判断是否需要确认
                // 如果既有卡片又有子文件夹，或者其中之一存在，则需要确认 (因为涉及移动文件)
                // 默认不勾选递归删除子内容（保持原“文件夹解散”行为）
                // 打开自定义确认弹窗：默认不勾选递归删除子内容（保持原“文件夹解散”行为）
                this.deleteFolderConfirm = {
                    visible: true,
                    path: path,
                    cardCount: cardCount,
                    hasSubfolders: hasSubfolders,
                    deleteChildren: false
                };
            }
        },
        
        cancelDeleteFolder() {
            this.deleteFolderConfirm.visible = false;
            this.visible = false;
        },

        confirmDeleteFolder() {
            const path = this.deleteFolderConfirm.path;
            const deleteChildren = !!this.deleteFolderConfirm.deleteChildren;

            // 关闭弹窗
            this.deleteFolderConfirm.visible = false;
            this.visible = false;

            // 执行删除
            deleteFolder({ folder_path: path, delete_children: deleteChildren }).then(res => {
                if (res.success) {
                    // 刷新文件夹树和卡片列表
                    window.dispatchEvent(new CustomEvent('refresh-folder-list'));
                    // 即使是空文件夹，删除后也建议刷新列表，确保同步
                    window.dispatchEvent(new CustomEvent('refresh-card-list'));
                } else {
                    alert(res.msg);
                }
            });
        },

        // 聚合模式
        handleBundle() {
            if (this.type === 'folder') {
                // Toggle Bundle Mode
                // 1. Check
                toggleBundleMode({ folder_path: this.target, action: 'check' }).then(res => {
                    if (!res.success) return alert(res.msg);

                    if (confirm(`将 "${this.target}" 设为聚合角色包？\n包含 ${res.count} 张图片。`)) {
                        toggleBundleMode({ folder_path: this.target, action: 'enable' }).then(r2 => {
                            if (r2.success) {
                                alert(r2.msg);
                                window.dispatchEvent(new CustomEvent('refresh-folder-list'));
                                window.dispatchEvent(new CustomEvent('refresh-card-list'));
                            } else alert(r2.msg);
                        });
                    }
                });
            }
        }
    }
}