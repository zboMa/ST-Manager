/**
 * static/js/components/moveToBundleModal.js
 * 移动到包弹窗组件
 */

import { moveCard } from '../api/card.js';

export default function moveToBundleModal() {
    return {
        showMoveToBundleModal: false,
        cardId: '',
        targetBundleDir: '',
        availableBundles: [],

        init() {
            // 监听打开移动到包弹窗事件
            window.addEventListener('open-move-to-bundle-modal', (e) => {
                this.cardId = e.detail && e.detail.cardId ? e.detail.cardId : '';
                
                if (!this.cardId) {
                    alert("卡片ID无效");
                    return;
                }

                // 加载可用包列表
                this.loadAvailableBundles();
                this.targetBundleDir = '';
                this.showMoveToBundleModal = true;
            });

            // 监听获取所有卡片事件（用于获取包列表）
            window.addEventListener('get-all-cards-for-bundles', () => {
                // 这个事件由 cardGrid 响应，返回所有卡片
                // 我们通过请求 cardGrid 来获取
            });
        },

        // 加载可用包列表
        loadAvailableBundles() {
            // 通过 API 获取所有包（获取所有卡片并筛选包）
            // 使用较大的 page_size 来获取所有卡片
            import('../api/card.js').then(({ listCards }) => {
                return listCards({
                    page: 1,
                    page_size: 10000, // 获取所有卡片
                    recursive: true
                });
            }).then(data => {
                const allCards = data.cards || [];
                // 筛选出所有包
                const bundles = allCards.filter(card => card.is_bundle === true);
                
                // 获取当前卡片信息（从详情页传入或从列表中查找）
                const currentCard = allCards.find(c => c.id === this.cardId);
                const currentBundleDir = currentCard?.bundle_dir;
                
                // 过滤掉当前卡片所在的包（如果当前卡片已经在某个包中）
                this.availableBundles = bundles.filter(bundle => {
                    // 排除当前卡片所在的包
                    if (bundle.bundle_dir === currentBundleDir) {
                        return false;
                    }
                    return true;
                });
            }).catch(err => {
                console.error("加载包列表失败:", err);
                this.availableBundles = [];
            });
        },

        // 执行移动操作
        executeMove() {
            if (!this.cardId || !this.targetBundleDir) return;

            const bundleName = this.targetBundleDir.split('/').pop() || this.targetBundleDir;
            if (!confirm(`确定将卡片移动到包 "${bundleName}" 中吗？`)) return;

            this.$store.global.isLoading = true;
            document.body.style.cursor = 'wait';

            // 包的 bundle_dir 就是目标分类
            moveCard({
                card_id: this.cardId,
                target_category: this.targetBundleDir
            })
                .then(res => {
                    document.body.style.cursor = 'default';
                    this.$store.global.isLoading = false;
                    
                    if (res.success) {
                        // 更新计数
                        if (res.category_counts) {
                            this.$store.global.categoryCounts = res.category_counts;
                        }
                        // 关闭弹窗
                        this.showMoveToBundleModal = false;
                        // 刷新列表
                        window.dispatchEvent(new CustomEvent('refresh-card-list'));
                        // 关闭详情页（通过触发 detailModal 的关闭事件）
                        const detailModal = Alpine.$data(document.querySelector('[x-data*="detailModal"]'));
                        if (detailModal) {
                            detailModal.showDetail = false;
                        }
                        // 显示提示
                        this.$store.global.showToast(`✅ 已移动到包 "${bundleName}"`);
                    } else {
                        alert("移动失败: " + res.msg);
                    }
                })
                .catch(err => {
                    document.body.style.cursor = 'default';
                    this.$store.global.isLoading = false;
                    alert("网络请求错误: " + err);
                });
        }
    }
}
