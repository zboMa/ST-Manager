/**
 * static/js/state.js
 * 全局状态管理 (Alpine.store)
 */

import { 
    getServerStatus, 
    getSettings, 
    saveSettings, 
    performSystemAction, 
    triggerScan 
} from './api/system.js';

import { 
    updateCssVariable, 
    applyFont 
} from './utils/dom.js';

// 主题预设常量
const THEME_PRESETS = {
    blue:   { main: '#2563eb', hover: '#1d4ed8', light: '#60a5fa', faint: 'rgba(37, 99, 235, 0.3)' },
    purple: { main: '#7c3aed', hover: '#6d28d9', light: '#a78bfa', faint: 'rgba(124, 58, 237, 0.3)' },
    green:  { main: '#059669', hover: '#047857', light: '#34d399', faint: 'rgba(5, 150, 105, 0.3)' },
    red:    { main: '#dc2626', hover: '#b91c1c', light: '#f87171', faint: 'rgba(220, 38, 38, 0.3)' },
    orange: { main: '#ea580c', hover: '#c2410c', light: '#fb923c', faint: 'rgba(234, 88, 12, 0.3)' },
    pink:   { main: '#db2777', hover: '#be185d', light: '#f472b6', faint: 'rgba(219, 39, 119, 0.3)' },
};

const DEFAULT_TAG_CATEGORY = '未分类';
const DEFAULT_TAG_CATEGORY_COLOR = '#64748b';
const DEFAULT_TAG_CATEGORY_OPACITY = 16;

function buildDefaultTagTaxonomy() {
    return {
        default_category: DEFAULT_TAG_CATEGORY,
        category_order: [DEFAULT_TAG_CATEGORY],
        categories: {
            [DEFAULT_TAG_CATEGORY]: {
                color: DEFAULT_TAG_CATEGORY_COLOR,
                opacity: DEFAULT_TAG_CATEGORY_OPACITY,
            },
        },
        tag_to_category: {},
        updated_at: 0,
    };
}

function normalizeHexColor(value, fallback = DEFAULT_TAG_CATEGORY_COLOR) {
    const fallbackColor = typeof fallback === 'string' && fallback ? fallback : DEFAULT_TAG_CATEGORY_COLOR;
    if (typeof value !== 'string') return fallbackColor;

    let color = value.trim();
    if (!color) return fallbackColor;

    if (!color.startsWith('#')) {
        color = `#${color}`;
    }

    const hex = color.slice(1);
    if (/^[0-9a-fA-F]{3}$/.test(hex)) {
        return `#${hex[0]}${hex[0]}${hex[1]}${hex[1]}${hex[2]}${hex[2]}`.toLowerCase();
    }

    if (/^[0-9a-fA-F]{6}$/.test(hex)) {
        return color.toLowerCase();
    }

    return fallbackColor;
}

function normalizeOpacity(value, fallback = DEFAULT_TAG_CATEGORY_OPACITY) {
    const fallbackNum = Number.isFinite(Number(fallback))
        ? Math.max(0, Math.min(100, Math.round(Number(fallback))))
        : DEFAULT_TAG_CATEGORY_OPACITY;

    const raw = Number(value);
    if (!Number.isFinite(raw)) return fallbackNum;

    return Math.max(0, Math.min(100, Math.round(raw)));
}

export function initState() {
    Alpine.store('global', {
        // === 状态属性 ===
        isLoading: false,
        isSaving: false,
        showSettingsModal: false,

        // 设备类型: 'desktop' | 'mobile'
        deviceType: 'desktop',
        
        // 模式: 'cards' | 'worldinfo' | 'chats'
        currentMode: 'cards',
        
        // 侧边栏显示状态（移动端使用）
        visibleSidebar: true,
        
        // 服务器状态
        serverStatus: { status: 'initializing', message: '', progress: 0, total: 0 },
        _bootstrapped: false,

        // 界面状态
        isDarkMode: true,
        windowWidth: window.innerWidth,
        toastMessage: '',
        showToastState: false,
        toastTimer: null,
        _resizeTimer: null,

        // 数据池 (供 Sidebar 和 Grid 共享)
        allTagsPool: [],
        sidebarTagsPool: [],
        globalTagsPool: [],
        sidebarTagGroups: [],
        globalTagGroups: [],
        tagTaxonomy: buildDefaultTagTaxonomy(),
        categoryCounts: {},
        libraryTotal: 0,
        allFoldersList: [],
        showTagFilterModal: false,

        // 分页配置
        itemsPerPage: 20,

        // 当前会话排序（仅影响当前列表，不写入配置）
        currentSort: 'date_desc',

        // 世界书共享状态
        wiList: [], // 世界书列表数据
        wiSearchQuery: '', // 搜索关键词
        wiFilterType: 'all', // 筛选类型: 'all', 'global', 'resource', 'embedded'
        wiCurrentPage: 1,
        wiTotalItems: 0,
        wiTotalPages: 1,

        // 聊天记录共享状态
        chatList: [],
        chatSearchQuery: '',
        chatFilterType: 'all', // all | bound | unbound | favorites
        chatCurrentPage: 1,
        chatTotalItems: 0,
        chatTotalPages: 1,

        extensionFilterType: 'all', // 'all', 'global', 'resource'

        // 预设筛选状态
        presetFilterType: 'all', // 'all', 'global', 'resource'
        presetSearch: '',
        extensionSearch: '',

        availableRuleSets: [], // 规则集列表
        
        // 设置表单
        settingsForm: { 
            cards_dir: 'data/library/characters',
            chats_dir: 'data/library/chats',
            presets_dir: 'data/library/presets',
            quick_replies_dir: 'data/library/extensions/quick-replies',
            default_sort: 'date_desc', 
            show_header_sort: true,
            st_url: 'http://127.0.0.1:8000',
            st_data_dir: '',
            st_username: '',
            st_password: '',
            st_auth_type: 'basic',
            st_proxy: '', 
            host: '127.0.0.1',
            port: 5000,
            items_per_page: 0,
            items_per_page_wi: 0,
            theme_accent: 'blue',
            auto_save_enabled: false,
            auto_save_interval: 3, 
            dark_mode: true,
            font_style: 'sans', 
            card_width: 220, 
            bg_url: '', 
            bg_opacity: 0.95, 
            bg_blur: 0,
            favorites_first: false,
            png_deterministic_sort: false,
            allowed_abs_resource_roots: [],
            wi_preview_limit: 300,
            wi_preview_entry_max_chars: 2000,
            wi_entry_history_limit: 7,
            auth_username: '',
            auth_password: '',
            auth_trusted_ips: [],
            auth_max_attempts: 5,
            auth_fail_window_seconds: 600,
            auth_lockout_seconds: 900,
            auth_hard_lock_threshold: 50,
            auto_rename_on_import: true,
            
            // Discord 论坛标签抓取配置
            discord_auth_type: 'token',
            discord_bot_token: '',
            discord_user_cookie: '',

            // 自动化标签分隔规则
            automation_slash_is_tag_separator: false,
        },

        // === 集中管理的视图状态 ===
        viewState: {
            searchQuery: '',
            searchType: 'mix',
            searchScope: 'current', // 'current' | 'all_dirs' | 'full'
            filterCategory: '',
            filterTags: [],
            excludedTags: [],
            excludedCategories: [],
            recursiveFilter: true,
            selectedIds: [],
            lastSelectedId: null,
            tagSearchQuery: '',
            draggedCards: [],   // 当前正在拖拽的卡片 ID 列表
            draggedFolder: null, // 当前正在拖拽的文件夹路径
            favFilter: 'none', // 'none' | 'included' | 'excluded'
        },

        // === 文件夹模态框状态 ===
        folderModals: {
            // 重命名模态框
            rename: {
                visible: false,
                path: '',
                name: ''
            },
            // 新建子文件夹模态框
            createSub: {
                visible: false,
                parentPath: '',
                name: ''
            },
            // 新建根/一级文件夹模态框 (兼容 Sidebar 逻辑)
            createRoot: {
                visible: false,
                parent: '',
                name: ''
            }
        },

        // === 初始化逻辑 ===
        init() {
            this.checkServerStatus();
            this.loadUserPreferences();

            // 监听窗口大小变化
            window.addEventListener('resize', () => {
                this.windowWidth = window.innerWidth;
                clearTimeout(this._resizeTimer);
                this._resizeTimer = setTimeout(() => this.updateItemsPerPage(), 200);
            });

            // 全局防止浏览器默认打开图片
            window.addEventListener('dragover', e => e.preventDefault());
            window.addEventListener('drop', e => e.preventDefault());
        },

        // 轮询服务器状态，准备就绪后执行 bootstrap
        checkServerStatus() {
            getServerStatus()
                .then(res => {
                    this.serverStatus = res;
                    if (res.status === 'ready') {
                        if (!this._bootstrapped) {
                            this._bootstrapped = true;
                            this.bootstrapOnce();
                        }
                    } else {
                        setTimeout(() => this.checkServerStatus(), 500);
                    }
                })
                .catch(() => {
                    setTimeout(() => this.checkServerStatus(), 1000);
                });
        },

        // 仅执行一次的启动逻辑 (加载设置)
        bootstrapOnce() {
            getSettings()
                .then(settings => {
                    const localPerPage = localStorage.getItem('st_manager_per_page');
                    const localPerPageWi = localStorage.getItem('st_manager_per_page_wi');
                    
                    const normalizedRoots = Array.isArray(settings.allowed_abs_resource_roots)
                        ? settings.allowed_abs_resource_roots
                        : (typeof settings.allowed_abs_resource_roots === 'string'
                            ? settings.allowed_abs_resource_roots.split(/[\r\n,]+/).map(s => s.trim()).filter(Boolean)
                            : []);

                    this.settingsForm = {
                        ...settings,
                        allowed_abs_resource_roots: normalizedRoots,
                        default_sort: settings.default_sort || 'date_desc',
                        show_header_sort: settings.show_header_sort !== false,
                        st_auth_type: settings.st_auth_type || 'basic',
                        st_proxy: settings.st_proxy || '',
                        items_per_page: localPerPage ? parseInt(localPerPage) : (settings.items_per_page || 0),
                        items_per_page_wi: localPerPageWi ? parseInt(localPerPageWi) : (settings.items_per_page_wi || 0)
                    };

                    this.currentSort = this.settingsForm.default_sort || 'date_desc';

                    // 应用视觉设置
                    if (settings.theme_accent) this.applyTheme(settings.theme_accent);
                    this.isDarkMode = (settings.dark_mode !== undefined) ? settings.dark_mode : true;
                    this.applyDarkMode();
                    applyFont(this.settingsForm.font_style || 'sans');
                    
                    updateCssVariable('--card-min-width', (this.settingsForm.card_width || 220) + 'px');
                    
                    if (this.settingsForm.bg_url) {
                        this.updateBackgroundImage(this.settingsForm.bg_url);
                        updateCssVariable('--bg-blur', (this.settingsForm.bg_blur || 0) + 'px');
                        updateCssVariable('--bg-overlay-opacity', this.settingsForm.bg_opacity || 0.95);
                    } else {
                        this.updateBackgroundImage('');
                    }

                    this.updateItemsPerPage();

                    // 发出事件通知组件设置已加载 (代替原 app.js 直接调用 fetchCards)
                    window.dispatchEvent(new CustomEvent('settings-loaded'));
                })
                .catch(err => {
                    console.error("Bootstrap failed", err);
                    // 即使失败也发出事件，让 UI 尝试加载默认数据
                    window.dispatchEvent(new CustomEvent('settings-loaded'));
                });
        },

        // 加载本地存储的偏好 (UI 优先)
        loadUserPreferences() {
            const savedPerPage = localStorage.getItem('st_manager_per_page');
            
            if (savedPerPage) this.settingsForm.items_per_page = parseInt(savedPerPage);
        },

        // === 全局动作 ===

        // 切换深色模式
        toggleDarkMode() {
            this.isDarkMode = !this.isDarkMode;
            this.settingsForm.dark_mode = this.isDarkMode;
            this.applyDarkMode();
            this.saveSettings(false); // 静默保存
        },

        applyDarkMode() {
            if (this.isDarkMode) {
                document.documentElement.classList.remove('light-mode');
            } else {
                document.documentElement.classList.add('light-mode');
            }
        },

        // 应用主题色
        applyTheme(colorName) {
            const t = THEME_PRESETS[colorName] || THEME_PRESETS.blue;
            updateCssVariable('--accent-main', t.main);
            updateCssVariable('--accent-hover', t.hover);
            updateCssVariable('--accent-light', t.light);
            updateCssVariable('--accent-faint', t.faint);
            this.settingsForm.theme_accent = colorName;
        },

        // 更新背景图
        updateBackgroundImage(url) {
            if (!url) {
                updateCssVariable('--bg-image-url', 'none');
                updateCssVariable('--bg-overlay-opacity', '1'); 
            } else {
                updateCssVariable('--bg-image-url', `url('${url}')`);
                const opacity = this.settingsForm.bg_opacity !== undefined ? this.settingsForm.bg_opacity : 0.95;
                updateCssVariable('--bg-overlay-opacity', opacity);
            }
        },

        // 保存设置
        saveSettings(closeModal = true) {
            this.applyTheme(this.settingsForm.theme_accent);
            
            // 乐观更新 localStorage
            if (this.settingsForm.items_per_page) localStorage.setItem('st_manager_per_page', this.settingsForm.items_per_page);
            if (this.settingsForm.items_per_page_wi) localStorage.setItem('st_manager_per_page_wi', this.settingsForm.items_per_page_wi);

            return saveSettings(this.settingsForm)
                .then(res => {
                    if (res.success) {
                        this.updateItemsPerPage();
                        // 触发事件让组件刷新
                        if (closeModal) {
                            window.dispatchEvent(new CustomEvent('settings-saved', { detail: { closeModal: true } }));
                        }
                    } else {
                        alert("保存失败: " + res.msg);
                    }
                    return res;
                });
        },

        // 计算每页项目数 (响应式)
        updateItemsPerPage() {
            const userSetting = parseInt(this.settingsForm.items_per_page) || 0;

            if (userSetting > 0) {
                this.itemsPerPage = Math.min(Math.max(userSetting, 10), 500);
            } else {
                const availableWidth = window.innerWidth - 300 - 48; // Sidebar + Padding
                const availableHeight = window.innerHeight - 64 - 60; // Header + Footer
                
                // 估算
                const cols = Math.floor(Math.max(1, availableWidth / 224));
                const rows = Math.floor(Math.max(1, availableHeight / 472));
                
                this.itemsPerPage = Math.max(20, Math.floor(cols * rows * 1.5));
            }
        },

        normalizeTagTaxonomy(raw) {
            const fallback = buildDefaultTagTaxonomy();
            if (!raw || typeof raw !== 'object') return fallback;

            const defaultCategory = String(raw.default_category || '').trim() || DEFAULT_TAG_CATEGORY;

            const categories = {};
            const rawCategories = raw.categories;
            if (rawCategories && typeof rawCategories === 'object' && !Array.isArray(rawCategories)) {
                Object.entries(rawCategories).forEach(([rawName, rawCfg]) => {
                    const name = String(rawName || '').trim();
                    if (!name) return;

                    let color = DEFAULT_TAG_CATEGORY_COLOR;
                    let opacity = DEFAULT_TAG_CATEGORY_OPACITY;
                    if (rawCfg && typeof rawCfg === 'object' && !Array.isArray(rawCfg)) {
                        color = normalizeHexColor(rawCfg.color, DEFAULT_TAG_CATEGORY_COLOR);
                        opacity = normalizeOpacity(rawCfg.opacity, DEFAULT_TAG_CATEGORY_OPACITY);
                    } else if (typeof rawCfg === 'string') {
                        color = normalizeHexColor(rawCfg, DEFAULT_TAG_CATEGORY_COLOR);
                    }

                    categories[name] = {
                        color,
                        opacity,
                    };
                });
            }

            if (!categories[defaultCategory]) {
                categories[defaultCategory] = {
                    color: DEFAULT_TAG_CATEGORY_COLOR,
                    opacity: DEFAULT_TAG_CATEGORY_OPACITY,
                };
            }

            const categoryOrder = [];
            const seen = new Set();
            const rawOrder = Array.isArray(raw.category_order) ? raw.category_order : [];
            rawOrder.forEach((item) => {
                const name = String(item || '').trim();
                if (!name || seen.has(name) || !categories[name]) return;
                seen.add(name);
                categoryOrder.push(name);
            });

            if (!seen.has(defaultCategory)) {
                categoryOrder.unshift(defaultCategory);
                seen.add(defaultCategory);
            }

            Object.keys(categories)
                .sort((a, b) => a.localeCompare(b, 'zh-CN', { sensitivity: 'base' }))
                .forEach((name) => {
                    if (seen.has(name)) return;
                    seen.add(name);
                    categoryOrder.push(name);
                });

            const tagToCategory = {};
            const rawMap = raw.tag_to_category;
            if (rawMap && typeof rawMap === 'object' && !Array.isArray(rawMap)) {
                Object.entries(rawMap).forEach(([rawTag, rawCategory]) => {
                    const tag = String(rawTag || '').trim();
                    if (!tag) return;

                    let category = String(rawCategory || '').trim();
                    if (!category || !categories[category]) {
                        category = defaultCategory;
                    }
                    tagToCategory[tag] = category;
                });
            }

            let updatedAt = parseInt(raw.updated_at, 10);
            if (Number.isNaN(updatedAt) || updatedAt < 0) updatedAt = 0;

            return {
                default_category: defaultCategory,
                category_order: categoryOrder,
                categories,
                tag_to_category: tagToCategory,
                updated_at: updatedAt,
            };
        },

        setTagTaxonomy(raw) {
            this.tagTaxonomy = this.normalizeTagTaxonomy(raw);
            this.rebuildTagGroups();
            return this.tagTaxonomy;
        },

        getCategoryColor(category) {
            const taxonomy = this.tagTaxonomy || buildDefaultTagTaxonomy();
            const categories = taxonomy.categories || {};
            const cfg = categories[category] || {};
            return normalizeHexColor(cfg.color, DEFAULT_TAG_CATEGORY_COLOR);
        },

        getCategoryOpacity(category) {
            const taxonomy = this.tagTaxonomy || buildDefaultTagTaxonomy();
            const categories = taxonomy.categories || {};
            const cfg = categories[category] || {};
            return normalizeOpacity(cfg.opacity, DEFAULT_TAG_CATEGORY_OPACITY);
        },

        getTagCategory(tag) {
            const taxonomy = this.tagTaxonomy || buildDefaultTagTaxonomy();
            const defaultCategory = taxonomy.default_category || DEFAULT_TAG_CATEGORY;
            const tagToCategory = taxonomy.tag_to_category || {};

            const key = String(tag || '').trim();
            if (!key) return defaultCategory;

            const category = String(tagToCategory[key] || '').trim();
            if (!category || !taxonomy.categories || !taxonomy.categories[category]) {
                return defaultCategory;
            }
            return category;
        },

        getTagColor(tag) {
            return this.getCategoryColor(this.getTagCategory(tag));
        },

        getTagChipStyle(tag) {
            const color = this.getTagColor(tag);
            const opacity = this.getCategoryOpacity(this.getTagCategory(tag));
            const bgColorWeight = Math.max(8, Math.min(62, Math.round(opacity * 0.62)));
            const borderColorWeight = Math.max(18, Math.min(76, Math.round(opacity * 0.82)));
            const textColorWeight = Math.max(8, Math.min(34, Math.round(opacity * 0.32)));

            const bgBaseWeight = 100 - bgColorWeight;
            const borderBaseWeight = 100 - borderColorWeight;
            const textBaseWeight = 100 - textColorWeight;

            return `--tag-cat-color:${color};--tag-cat-opacity:${opacity};--tag-cat-bg:color-mix(in srgb, var(--bg-tag, var(--bg-sub)) ${bgBaseWeight}%, ${color} ${bgColorWeight}%);--tag-cat-border:color-mix(in srgb, var(--border-light) ${borderBaseWeight}%, ${color} ${borderColorWeight}%);--tag-cat-text:color-mix(in srgb, var(--text-main) ${textBaseWeight}%, ${color} ${textColorWeight}%);`;
        },

        groupTagsByTaxonomy(tags) {
            const tagList = Array.isArray(tags) ? tags : [];
            if (tagList.length === 0) return [];

            const taxonomy = this.tagTaxonomy || buildDefaultTagTaxonomy();
            const order = Array.isArray(taxonomy.category_order) ? taxonomy.category_order : [];
            const grouped = new Map();

            tagList.forEach((rawTag) => {
                const tag = String(rawTag || '').trim();
                if (!tag) return;

                const category = this.getTagCategory(tag);
                if (!grouped.has(category)) {
                    grouped.set(category, []);
                }
                grouped.get(category).push(tag);
            });

            const orderedCategories = [];
            const seen = new Set();
            order.forEach((rawCategory) => {
                const category = String(rawCategory || '').trim();
                if (!category || seen.has(category) || !grouped.has(category)) return;
                seen.add(category);
                orderedCategories.push(category);
            });

            Array.from(grouped.keys())
                .sort((a, b) => a.localeCompare(b, 'zh-CN', { sensitivity: 'base' }))
                .forEach((category) => {
                    if (seen.has(category)) return;
                    seen.add(category);
                    orderedCategories.push(category);
                });

            return orderedCategories.map((category) => ({
                category,
                color: this.getCategoryColor(category),
                opacity: this.getCategoryOpacity(category),
                tags: grouped.get(category) || [],
            }));
        },

        rebuildTagGroups() {
            this.globalTagGroups = this.groupTagsByTaxonomy(this.globalTagsPool || []);
            this.sidebarTagGroups = this.groupTagsByTaxonomy(this.sidebarTagsPool || []);
        },

        // 显示 Toast 通知
        showToast(msg, duration = 3000) {
            this.toastMessage = msg;
            this.showToastState = true;
            if (this.toastTimer) clearTimeout(this.toastTimer);
            this.toastTimer = setTimeout(() => {
                this.showToastState = false;
            }, duration);
        },

        // 执行系统操作 (打开文件夹等)
        systemAction(action) {
            performSystemAction(action)
                .then(res => {
                    if (!res.success && res.msg) alert(res.msg);
                    else if (res.msg) alert(res.msg);
                });
        },

        // 触发立即扫描
        scanNow() {
            if (!confirm("立即触发一次全量扫描同步磁盘与数据库？\n（适用于 watchdog 未安装或你手动改动过文件）")) return;
            this.isLoading = true;
            triggerScan()
                .then(res => {
                    if (!res.success) alert("触发扫描失败: " + (res.msg || 'unknown'));
                    else alert("已触发扫描任务（后台进行中）。稍后可点刷新查看结果。");
                })
                .catch(err => alert("网络错误: " + err))
                .finally(() => { this.isLoading = false; });
        },
        // 全局标签切换逻辑 (三态：包含 -> 排除 -> 无)
        // options.forceExclude=true 时可直接进入“排除”状态（用于 Shift+点击）
        toggleFilterTag(tag, options = {}) {
            const vs = this.viewState;
            let includeTags = [...vs.filterTags];
            let excludeTags = [...vs.excludedTags];
            const forceExclude = !!(options && options.forceExclude);

            const inInclude = includeTags.indexOf(tag);
            const inExclude = excludeTags.indexOf(tag);

            if (forceExclude) {
                // Shift+点击：直接进入排除（若已排除则保持不变）
                if (inInclude > -1) {
                    includeTags.splice(inInclude, 1);
                }
                if (inExclude === -1) {
                    excludeTags.push(tag);
                }
            } else {
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
            }

            // 更新状态
            vs.filterTags = includeTags;
            vs.excludedTags = excludeTags;
            
            // 触发列表刷新
            window.dispatchEvent(new CustomEvent('refresh-card-list'));
        },
        //  切换收藏筛选 (三态循环)
        toggleFavFilter() {
            const vs = this.viewState;
            if (vs.favFilter === 'none') {
                vs.favFilter = 'included';
            } else if (vs.favFilter === 'included') {
                vs.favFilter = 'excluded';
            } else {
                vs.favFilter = 'none';
            }
            // 触发列表刷新
            window.dispatchEvent(new CustomEvent('refresh-card-list'));
        },
    });
}
