/**
 * static/js/components/wiDetailPopup.js
 * 世界书详情弹窗组件 (对应 detail_wi_popup.html)
 */

import { wiHelpers } from '../utils/wiHelpers.js';
import { deleteWorldInfo } from '../api/wi.js';

export default function wiDetailPopup() {
    return {
        // === 本地状态 ===
        showWiDetailModal: false,
        activeWiDetail: null, // 当前查看的 WI 对象 (包含 id, name, type, path 等)

        ...wiHelpers,

        init() {
            // 监听打开事件 (通常由 wiGrid 触发)
            window.addEventListener('open-wi-detail-modal', (e) => {
                this.activeWiDetail = e.detail;
                this.showWiDetailModal = true;
            });
            
            // 监听关闭事件 (如果其他组件需要强制关闭它)
            window.addEventListener('close-wi-detail-modal', () => {
                this.showWiDetailModal = false;
            });
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
                        // 可选：显示 Toast
                        // this.$store.global.showToast("🗑️ 已删除"); 
                    } else {
                        alert("删除失败: " + res.msg);
                    }
                })
                .catch(err => alert("请求错误: " + err));
        },

        // 进入编辑器
        enterWiEditorFromDetail() {
            this.showWiDetailModal = false;
            // 触发打开全屏编辑器的事件，将当前对象传过去
            window.dispatchEvent(new CustomEvent('open-wi-editor', { 
                detail: this.activeWiDetail 
            }));
        },

        // 打开时光机 (Rollback)
        openRollback(type) {
            this.showWiDetailModal = false; // 关闭当前小弹窗
            
            // 触发全局时光机事件
            window.dispatchEvent(new CustomEvent('open-rollback', {
                detail: {
                    type: 'lorebook',
                    id: this.activeWiDetail.id,
                    path: this.activeWiDetail.path,
                    // 不传 editingData，因为此时不在编辑器里，让 rollback 组件自己去读文件
                    editingData: null, 
                    editingWiFile: null 
                }
            }));
        }
    }
}