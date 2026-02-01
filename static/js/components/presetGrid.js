/**
 * static/js/components/presetGrid.js
 * 预设网格组件 - 对齐 extensionGrid.js 风格
 */
export default function presetGrid() {
    return {
        items: [],
        isLoading: false,
        dragOver: false,
        selectedPreset: null,
        showDetailModal: false,

        get filterType() { return this.$store.global.presetFilterType || 'all'; },

        init() {
            // 监听模式切换
            this.$watch('$store.global.currentMode', (val) => {
                if (val === 'presets') {
                    this.fetchItems();
                }
            });

            // 监听侧边栏筛选变化
            this.$watch('$store.global.presetFilterType', () => {
                if (this.$store.global.currentMode === 'presets') {
                    this.fetchItems();
                }
            });
            
            // 初始加载
            if (this.$store.global.currentMode === 'presets') {
                this.fetchItems();
            }
        },

        fetchItems() {
            this.isLoading = true;
            const filterType = this.$store.global.presetFilterType || 'all';
            const search = this.$store.global.presetSearch || '';
            
            let url = `/api/presets/list?filter_type=${filterType}`;
            if (search) {
                url += `&search=${encodeURIComponent(search)}`;
            }
            
            fetch(url)
                .then(res => res.json())
                .then(res => {
                    this.items = res.items || [];
                    this.isLoading = false;
                })
                .catch((err) => { 
                    console.error('Failed to fetch presets:', err);
                    this.isLoading = false; 
                });
        },

        async handleDrop(e) {
            this.dragOver = false;
            const files = e.dataTransfer.files;
            if (!files.length) return;
            
            const formData = new FormData();
            for (let i = 0; i < files.length; i++) {
                formData.append('files', files[i]);
            }
            
            this.isLoading = true;
            try {
                const resp = await fetch('/api/presets/upload', {
                    method: 'POST',
                    body: formData
                });
                const res = await resp.json();
                if (res.success) {
                    this.$store.global.showToast(res.msg);
                    this.fetchItems();
                } else {
                    this.$store.global.showToast(res.msg, 'error');
                }
            } catch (e) {
                this.$store.global.showToast('上传失败', 'error');
            } finally {
                this.isLoading = false;
            }
        },

        async openPreset(item) {
            // 获取详情并打开编辑器
            this.isLoading = true;
            try {
                const resp = await fetch(`/api/presets/detail/${encodeURIComponent(item.id)}`);
                const res = await resp.json();
                
                if (res.success) {
                    this.selectedPreset = res.preset;
                    this.showDetailModal = true;
                } else {
                    this.$store.global.showToast(res.msg || '获取详情失败', 'error');
                }
            } catch (e) {
                this.$store.global.showToast('获取详情失败', 'error');
            } finally {
                this.isLoading = false;
            }
        },

        closeDetailModal() {
            this.showDetailModal = false;
            this.selectedPreset = null;
        },

        async deletePreset(item, e) {
            e.stopPropagation();
            
            if (!confirm(`确定要删除预设 "${item.name}" 吗？`)) {
                return;
            }
            
            try {
                const resp = await fetch('/api/presets/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: item.id })
                });
                const res = await resp.json();
                
                if (res.success) {
                    this.$store.global.showToast(res.msg);
                    this.fetchItems();
                } else {
                    this.$store.global.showToast(res.msg, 'error');
                }
            } catch (e) {
                this.$store.global.showToast('删除失败', 'error');
            }
        },

        editPresetRaw() {
            if (!this.selectedPreset) return;
            
            // 触发高级编辑器
            window.dispatchEvent(new CustomEvent('open-script-file-editor', {
                detail: {
                    fileData: this.selectedPreset.raw_data,
                    filePath: this.selectedPreset.path,
                    type: 'preset'
                }
            }));
            
            this.closeDetailModal();
        },
        
        formatDate(ts) {
            if (!ts) return '-';
            return new Date(ts * 1000).toLocaleString();
        },

        formatSize(bytes) {
            if (!bytes) return '-';
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / 1024 / 1024).toFixed(1) + ' MB';
        },

        formatParam(val) {
            if (val === null || val === undefined) return '-';
            if (typeof val === 'number') {
                return Number.isInteger(val) ? val : val.toFixed(2);
            }
            return val;
        }
    }
}
