/**
 * static/js/components/wiEditor.js
 * 全屏世界书编辑器组件
 */

import {
    getWorldInfoDetail,
    saveWorldInfo,
    listWiEntryHistory,
    clipboardList,
    clipboardAdd,
    clipboardDelete,
    clipboardClear,
    clipboardReorder
} from '../api/wi.js';
import { getCardDetail, updateCard } from '../api/card.js';
import { createSnapshot as apiCreateSnapshot, cleanupInitBackups as apiCleanupInitBackups } from '../api/system.js';
import { normalizeWiBook, toStV3Worldbook, getCleanedV3Data, updateWiKeys } from '../utils/data.js';
import { createAutoSaver } from '../utils/autoSave.js';
import { wiHelpers } from '../utils/wiHelpers.js';
import { formatWiKeys, estimateTokens, getTotalWiTokens } from '../utils/format.js';

export default function wiEditor() {
    const autoSaver = createAutoSaver();
    return {
        // === 本地状态 ===
        showFullScreenWI: false,
        showWiList: true,
        showWiSettings: true,
        isLoading: false,
        isSaving: false,

        // 编辑器核心数据
        editingData: {
            id: null,
            char_name: "",
            character_book: { name: "", entries: [] },
            extensions: { regex_scripts: [], tavern_helper: [] }
        },

        // 当前编辑的文件元数据 (用于保存路径)
        editingWiFile: null,

        // 索引与视图控制
        currentWiIndex: 0,
        entryUidField: 'st_manager_uid',
        initialSnapshotChecked: false,
        initialSnapshotInitPromise: null,

        // 条目历史回滚
        showEntryHistoryModal: false,
        isEntryHistoryLoading: false,
        entryHistoryItems: [],
        entryHistoryTargetUid: '',
        entryHistoryVersions: [],
        entryHistorySelection: { left: null, right: null },
        entryHistoryDiff: { left: '', right: '' },

        // === 剪切板状态 ===
        showWiClipboard: false,
        wiClipboardItems: [],
        wiClipboardOverwriteMode: false,
        clipboardPendingEntry: null, // 等待覆写的条目
        isEditingClipboard: false,   // 是否正在编辑剪切板内容
        currentClipboardIndex: -1,

        // 拖拽状态
        wiDraggingIndex: null,

        formatWiKeys,
        estimateTokens,
        updateWiKeys,
        ...wiHelpers,

        get activeCard() {
            return this.editingData;
        },

        // === 初始化 ===
        init() {
            // 监听打开编辑器事件
            window.addEventListener('open-wi-editor', (e) => {
                this.openWorldInfoEditor(e.detail);
            });

            // 监听打开文件事件 (通常用于独立文件)
            window.addEventListener('open-wi-file', (e) => {
                this.openWorldInfoFile(e.detail);
            });

            // 监听时光机恢复，确保编辑器内存与磁盘恢复结果同步
            window.addEventListener('wi-restore-applied', (e) => {
                this._handleRestoreApplied(e?.detail || {});
            });

            // 监听关闭
            this.$watch('showFullScreenWI', (val) => {
                if (!val) {
                    this._cleanupInitBackupsOnExit();
                    autoSaver.stop();
                    this.isEditingClipboard = false;
                    this.currentWiIndex = 0;
                    this.initialSnapshotChecked = false;
                    this.initialSnapshotInitPromise = null;
                }
            });

            window.addEventListener('keydown', (e) => {
                if (this.showFullScreenWI && e.key === 'Escape') {
                    this.showFullScreenWI = false;
                }
            });
        },

        openRollback() {
            this.handleOpenRollback(this.editingWiFile, this.editingData);
        },

        _normalizePathForCompare(path) {
            return String(path || '').replace(/\\/g, '/').toLowerCase();
        },

        _isRestoreForCurrentEditor(detail) {
            if (!this.showFullScreenWI || !this.editingWiFile) return false;

            const targetType = String(detail.targetType || '');
            const targetId = String(detail.targetId || '');
            const targetFilePath = this._normalizePathForCompare(detail.targetFilePath || '');
            const currentFile = this.editingWiFile || {};

            if (targetType === 'card') {
                // 仅内嵌模式会直接编辑角色卡
                const currentCardId = String(this.editingData?.id || currentFile.card_id || '');
                const normalizedTargetCardId = targetId.startsWith('embedded::')
                    ? targetId.replace('embedded::', '')
                    : targetId;
                return !!currentCardId && currentCardId === normalizedTargetCardId;
            }

            if (targetType === 'lorebook') {
                // 内嵌世界书回滚会落到宿主卡片
                if (targetId.startsWith('embedded::')) {
                    const currentCardId = String(this.editingData?.id || currentFile.card_id || '');
                    return !!currentCardId && currentCardId === targetId.replace('embedded::', '');
                }

                // 独立世界书按 file_path 精确匹配
                const currentPath = this._normalizePathForCompare(currentFile.file_path || currentFile.path || '');
                return !!currentPath && !!targetFilePath && currentPath === targetFilePath;
            }

            return false;
        },

        async _syncEditorStateAfterRestore() {
            if (!this.editingWiFile) return false;

            const keepIndex = this.currentWiIndex;
            const currentFile = this.editingWiFile;

            if (currentFile.type === 'embedded' || this.editingData?.id) {
                const cardId = this.editingData?.id || currentFile.card_id;
                const res = await getCardDetail(cardId);
                if (!res || !res.success || !res.card) {
                    return false;
                }

                const card = res.card;
                if (card.character_book) {
                    card.character_book = normalizeWiBook(card.character_book, card.char_name || "WI");
                }

                if (Array.isArray(card.character_book?.entries)) {
                    const sessionTs = Date.now();
                    card.character_book.entries.forEach((entry, idx) => {
                        entry.id = `edit-${sessionTs}-${idx}`;
                    });
                }

                this.editingData = card;
                this._ensureEntryUids();
            } else {
                const res = await getWorldInfoDetail({
                    id: currentFile.id,
                    source_type: currentFile.source_type,
                    file_path: currentFile.file_path || currentFile.path,
                    force_full: true
                });

                if (!res || !res.success) {
                    return false;
                }

                const book = normalizeWiBook(res.data, currentFile.name || "World Info");
                if (Array.isArray(book.entries)) {
                    const sessionTs = Date.now();
                    book.entries.forEach((entry, idx) => {
                        entry.id = `edit-${sessionTs}-${idx}`;
                    });
                }

                this.editingData.character_book = book;
                this._ensureEntryUids();
            }

            const entries = this.getWIArrayRef();
            if (!entries.length) {
                this.currentWiIndex = 0;
            } else {
                this.currentWiIndex = Math.max(0, Math.min(keepIndex, entries.length - 1));
            }

            if (autoSaver && typeof autoSaver.initBaseline === 'function') {
                autoSaver.initBaseline(this.editingData);
            }
            return true;
        },

        async _handleRestoreApplied(detail) {
            if (!this._isRestoreForCurrentEditor(detail)) return;

            try {
                const synced = await this._syncEditorStateAfterRestore();
                if (synced) {
                    this.$store.global.showToast('⏪ 已同步恢复版本到当前编辑器', 2200);
                }
            } catch (e) {
                console.warn('Sync editor after restore failed:', e);
            }
        },

        _generateEntryUid() {
            return `wi-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
        },

        _ensureEntryUids() {
            const arr = this.getWIArrayRef();
            const used = new Set();
            arr.forEach((entry) => {
                if (!entry || typeof entry !== 'object') return;
                let uid = String(entry[this.entryUidField] || '').trim();
                if (!uid || used.has(uid)) {
                    uid = this._generateEntryUid();
                    entry[this.entryUidField] = uid;
                }
                used.add(uid);
            });
        },

        _getEntryHistoryContext() {
            const file = this.editingWiFile || {};
            if (file.type === 'embedded' || (!file.type && this.editingData?.id)) {
                return {
                    source_type: 'embedded',
                    source_id: (this.editingData && this.editingData.id) ? this.editingData.id : (file.card_id || ''),
                    file_path: ''
                };
            }
            return {
                source_type: 'lorebook',
                source_id: file.id || '',
                file_path: file.file_path || file.path || ''
            };
        },

        formatEntryHistoryTime(ts) {
            if (!ts) return '';
            const d = new Date(ts * 1000);
            if (Number.isNaN(d.getTime())) return '';
            return d.toLocaleString();
        },

        _escapeEntryHistoryHtml(text) {
            return String(text ?? '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
        },

        _toEntryHistoryArray(val) {
            if (Array.isArray(val)) return val.map(v => String(v ?? '').trim()).filter(Boolean);
            if (typeof val === 'string') return val.split(',').map(s => s.trim()).filter(Boolean);
            return [];
        },

        _normalizeEntryHistorySnapshot(raw) {
            if (!raw || typeof raw !== 'object') return null;
            return {
                comment: String(raw.comment ?? ''),
                content: String(raw.content ?? ''),
                keys: this._toEntryHistoryArray(raw.keys ?? raw.key),
                secondary_keys: this._toEntryHistoryArray(raw.secondary_keys ?? raw.keysecondary)
            };
        },

        _getEntryHistoryMeta(left, right) {
            if (left && right) {
                const changed = {
                    comment: left.comment !== right.comment,
                    keys: left.keys.join('|') !== right.keys.join('|') ||
                        left.secondary_keys.join('|') !== right.secondary_keys.join('|'),
                    content: left.content !== right.content
                };
                const status = (changed.comment || changed.keys || changed.content) ? 'changed' : 'same';
                return { status, changed };
            }
            if (left && !right) {
                return { status: 'removed', changed: { comment: true, keys: true, content: true } };
            }
            return { status: 'added', changed: { comment: true, keys: true, content: true } };
        },

        _entryHistoryFieldDiffClass(meta, side, fieldChanged) {
            if (meta.status === 'added' && side === 'right') {
                return 'bg-green-500/20 border border-green-500/40';
            }
            if (meta.status === 'removed' && side === 'left') {
                return 'bg-red-500/20 border border-red-500/40';
            }
            if (meta.status === 'changed' && fieldChanged) {
                return 'bg-yellow-500/20 border border-yellow-500/40';
            }
            return 'bg-black/10 border border-transparent';
        },

        _splitEntryHistoryLinesWithLimit(text, maxLines = 240, maxChars = 16000) {
            const raw = String(text ?? '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
            let limited = raw;
            let truncatedByChars = false;
            if (limited.length > maxChars) {
                limited = limited.slice(0, maxChars);
                truncatedByChars = true;
            }
            let lines = limited.split('\n');
            let truncatedByLines = false;
            if (lines.length > maxLines) {
                lines = lines.slice(0, maxLines);
                truncatedByLines = true;
            }
            if (truncatedByChars || truncatedByLines) {
                lines.push('...(内容过长，已截断显示)');
            }
            return lines;
        },

        _buildEntryHistoryLineOps(leftLines, rightLines, maxCells = 70000) {
            const n = leftLines.length;
            const m = rightLines.length;

            if (n * m > maxCells) {
                const approx = [];
                const len = Math.max(n, m);
                for (let i = 0; i < len; i++) {
                    const l = i < n ? leftLines[i] : null;
                    const r = i < m ? rightLines[i] : null;
                    if (l !== null && r !== null) {
                        approx.push({ t: l === r ? 'same' : 'changed', left: l, right: r });
                    } else if (l !== null) {
                        approx.push({ t: 'removed', left: l, right: null });
                    } else {
                        approx.push({ t: 'added', left: null, right: r });
                    }
                }
                return approx;
            }

            const dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
            for (let i = n - 1; i >= 0; i--) {
                for (let j = m - 1; j >= 0; j--) {
                    if (leftLines[i] === rightLines[j]) {
                        dp[i][j] = dp[i + 1][j + 1] + 1;
                    } else {
                        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
                    }
                }
            }

            const rawOps = [];
            let i = 0;
            let j = 0;
            while (i < n && j < m) {
                if (leftLines[i] === rightLines[j]) {
                    rawOps.push({ t: 'same', text: leftLines[i] });
                    i += 1;
                    j += 1;
                } else if (dp[i + 1][j] >= dp[i][j + 1]) {
                    rawOps.push({ t: 'remove', text: leftLines[i] });
                    i += 1;
                } else {
                    rawOps.push({ t: 'add', text: rightLines[j] });
                    j += 1;
                }
            }
            while (i < n) {
                rawOps.push({ t: 'remove', text: leftLines[i] });
                i += 1;
            }
            while (j < m) {
                rawOps.push({ t: 'add', text: rightLines[j] });
                j += 1;
            }

            const aligned = [];
            let k = 0;
            while (k < rawOps.length) {
                const op = rawOps[k];
                if (op.t === 'same') {
                    aligned.push({ t: 'same', left: op.text, right: op.text });
                    k += 1;
                    continue;
                }

                const removes = [];
                const adds = [];
                while (k < rawOps.length && rawOps[k].t !== 'same') {
                    if (rawOps[k].t === 'remove') removes.push(rawOps[k].text);
                    if (rawOps[k].t === 'add') adds.push(rawOps[k].text);
                    k += 1;
                }

                const pairCount = Math.min(removes.length, adds.length);
                for (let x = 0; x < pairCount; x++) {
                    aligned.push({ t: 'changed', left: removes[x], right: adds[x] });
                }
                for (let x = pairCount; x < removes.length; x++) {
                    aligned.push({ t: 'removed', left: removes[x], right: null });
                }
                for (let x = pairCount; x < adds.length; x++) {
                    aligned.push({ t: 'added', left: null, right: adds[x] });
                }
            }
            return aligned;
        },

        _entryHistoryLineClass(type, side) {
            if (type === 'changed') return 'bg-yellow-500/20 border border-yellow-500/40';
            if (type === 'added' && side === 'right') return 'bg-green-500/20 border border-green-500/40';
            if (type === 'removed' && side === 'left') return 'bg-red-500/20 border border-red-500/40';
            if (type === 'added' && side === 'left') return 'bg-green-500/10 border border-green-500/30';
            if (type === 'removed' && side === 'right') return 'bg-red-500/10 border border-red-500/30';
            return 'bg-black/10 border border-transparent';
        },

        _renderEntryHistoryLineDiffHtml(leftText, rightText, side) {
            const leftLines = this._splitEntryHistoryLinesWithLimit(leftText);
            const rightLines = this._splitEntryHistoryLinesWithLimit(rightText);
            const rows = this._buildEntryHistoryLineOps(leftLines, rightLines);

            let leftNo = 0;
            let rightNo = 0;
            let html = '';
            rows.forEach((row) => {
                const isLeft = side === 'left';
                const text = isLeft ? row.left : row.right;
                const cls = this._entryHistoryLineClass(row.t, side);

                if (row.left !== null) leftNo += 1;
                if (row.right !== null) rightNo += 1;
                const lineNo = isLeft ? (row.left !== null ? leftNo : '') : (row.right !== null ? rightNo : '');
                const lineText = text === null ? '∅' : this._escapeEntryHistoryHtml(text);
                const lineTextClass = text === null ? 'text-[var(--text-dim)] italic' : 'text-[var(--text-main)]';

                html += `
                    <div class="px-2 py-0.5 rounded ${cls}">
                        <span class="inline-block w-8 mr-2 text-[10px] text-[var(--text-dim)] text-right select-none">${lineNo || ' '}</span>
                        <span class="text-[11px] whitespace-pre-wrap break-words ${lineTextClass}">${lineText || ' '}</span>
                    </div>
                `;
            });
            return html;
        },

        _renderEntryHistoryPane(entry, oppositeEntry, meta, side) {
            if (!entry) {
                return `
                    <div class="m-2 p-3 rounded border border-dashed border-[var(--border-light)] text-[11px] text-[var(--text-dim)] opacity-70">
                        <div>（此侧无对应条目）</div>
                    </div>
                `;
            }

            const isLeft = side === 'left';
            const markClass = (isLeft && (meta.status === 'removed' || meta.status === 'changed'))
                ? 'text-red-300'
                : ((!isLeft && (meta.status === 'added' || meta.status === 'changed')) ? 'text-green-300' : 'text-[var(--text-main)]');

            const comment = this._escapeEntryHistoryHtml(entry.comment || '(无备注)');
            const keys = this._escapeEntryHistoryHtml(entry.keys.join(', ') || '(空)');
            const sec = this._escapeEntryHistoryHtml(entry.secondary_keys.join(', ') || '(空)');

            const commentCls = meta.changed.comment ? markClass : 'text-[var(--text-main)]';
            const keyCls = meta.changed.keys ? markClass : 'text-[var(--text-main)]';
            const contentCls = meta.changed.content ? markClass : 'text-[var(--text-main)]';

            const commentBgCls = this._entryHistoryFieldDiffClass(meta, side, meta.changed.comment);
            const keysBgCls = this._entryHistoryFieldDiffClass(meta, side, meta.changed.keys);
            const leftContent = side === 'left' ? (entry.content || '') : (oppositeEntry?.content || '');
            const rightContent = side === 'right' ? (entry.content || '') : (oppositeEntry?.content || '');
            const lineDiffHtml = this._renderEntryHistoryLineDiffHtml(leftContent, rightContent, side);

            return `
                <div class="m-2 p-3 rounded border bg-[var(--bg-sub)] border-[var(--border-light)]">
                    <div class="mt-1 p-1.5 rounded ${commentBgCls}">
                        <div class="text-sm font-bold ${commentCls}">${comment}</div>
                    </div>
                    <div class="mt-2 p-1.5 rounded ${keysBgCls}">
                        <div class="text-[11px] ${keyCls}">关键词: ${keys}</div>
                        <div class="mt-1 text-[11px] ${keyCls}">次级词: ${sec}</div>
                    </div>
                    <div class="mt-2 p-1.5 rounded bg-black/5 border border-[var(--border-light)]">
                        <div class="text-[11px] text-[var(--text-dim)]">内容预览</div>
                        <div class="mt-1 p-2 rounded bg-black/10 max-h-72 overflow-auto">${lineDiffHtml}</div>
                        <div class="mt-1 text-[10px] ${contentCls}">行级高亮：绿=新增，黄=修改，红=删除</div>
                    </div>
                </div>
            `;
        },

        updateEntryHistoryDiff() {
            const leftVer = this.entryHistorySelection.left;
            const rightVer = this.entryHistorySelection.right;
            if (!leftVer || !rightVer) {
                this.entryHistoryDiff = {
                    left: '<div class="p-6 text-center text-[var(--text-dim)] text-xs">请选择版本进行对比</div>',
                    right: '<div class="p-6 text-center text-[var(--text-dim)] text-xs">请选择版本进行对比</div>'
                };
                return;
            }

            const left = this._normalizeEntryHistorySnapshot(leftVer.snapshot);
            const right = this._normalizeEntryHistorySnapshot(rightVer.snapshot);
            const meta = this._getEntryHistoryMeta(left, right);

            this.entryHistoryDiff = {
                left: this._renderEntryHistoryPane(left, right, meta, 'left'),
                right: this._renderEntryHistoryPane(right, left, meta, 'right')
            };
        },

        setEntryHistorySide(side, version) {
            if (!version) return;
            this.entryHistorySelection[side] = version;
            this.updateEntryHistoryDiff();
        },

        openEntryHistoryModal() {
            if (this.isEditingClipboard) {
                alert('剪切板条目不支持历史版本。');
                return;
            }
            if (!this.activeEditorEntry) return;

            this._ensureEntryUids();
            const uid = this.activeEditorEntry[this.entryUidField];
            if (!uid) {
                alert('当前条目缺少唯一标识，无法读取历史版本。');
                return;
            }

            const context = this._getEntryHistoryContext();
            this.entryHistoryTargetUid = uid;
            this.entryHistoryItems = [];
            this.entryHistoryVersions = [];
            this.entryHistorySelection = { left: null, right: null };
            this.entryHistoryDiff = { left: '', right: '' };
            this.showEntryHistoryModal = true;
            this.isEntryHistoryLoading = true;

            listWiEntryHistory({
                ...context,
                entry_uid: uid
            }).then(res => {
                if (res.success) {
                    const rawItems = Array.isArray(res.items) ? res.items : [];
                    this.entryHistoryItems = rawItems.map((item, idx) => ({
                        ...item,
                        // 历史记录一律标记为非 current，避免类型混淆导致按钮误禁用
                        is_current: false,
                        id: item && item.id !== undefined ? item.id : (`h-${item?.created_at || Date.now()}-${idx}`)
                    }));
                    const currentVersion = {
                        id: '__current__',
                        is_current: true,
                        created_at: Math.floor(Date.now() / 1000),
                        snapshot: JSON.parse(JSON.stringify(this.activeEditorEntry || {}))
                    };
                    this.entryHistoryVersions = [currentVersion, ...this.entryHistoryItems];
                    this.entryHistorySelection = {
                        left: this.entryHistoryItems[0] || null,
                        right: currentVersion
                    };
                    this.updateEntryHistoryDiff();
                } else {
                    alert('读取历史失败: ' + (res.msg || '未知错误'));
                }
            }).catch(e => {
                alert('读取历史失败: ' + e);
            }).finally(() => {
                this.isEntryHistoryLoading = false;
            });
        },

        canRestoreEntryFromSelection() {
            const left = this.entryHistorySelection.left;
            if (!left) return false;
            if (left.is_current === true) return false;
            return !!left.snapshot;
        },

        restoreEntryFromSelectedHistory() {
            const target = this.entryHistorySelection.left;
            if (!this.canRestoreEntryFromSelection()) {
                alert('请在左侧选择一个历史版本再恢复。');
                return;
            }
            this.restoreEntryFromHistory(target);
        },

        _resolveEntryRestoreTarget(uid) {
            const targetUid = String(uid || this.entryHistoryTargetUid || '').trim();
            const current = this.activeEditorEntry;
            if (current && targetUid) {
                const currentUid = String(current[this.entryUidField] || '').trim();
                if (currentUid && currentUid === targetUid) {
                    return { entry: current, index: this.currentWiIndex };
                }
            }

            const arr = this.getWIArrayRef();
            if (!Array.isArray(arr) || !arr.length || !targetUid) return { entry: current, index: this.currentWiIndex };
            const idx = arr.findIndex((it) => String(it?.[this.entryUidField] || '').trim() === targetUid);
            if (idx >= 0) return { entry: arr[idx], index: idx };
            return { entry: current, index: this.currentWiIndex };
        },

        restoreEntryFromHistory(item) {
            if (!item || !item.snapshot) return;
            const keepUid = String(this.entryHistoryTargetUid || item.snapshot?.[this.entryUidField] || '').trim();
            const resolved = this._resolveEntryRestoreTarget(keepUid);
            const target = resolved.entry;
            if (!target) {
                alert('未找到可恢复的目标条目，请重新打开条目时光机后再试。');
                return;
            }
            if (!confirm('确定回滚当前条目到该历史版本吗？')) return;
            const keepId = target.id;
            const keepRestoreUid = target[this.entryUidField] || keepUid;
            const restored = JSON.parse(JSON.stringify(item.snapshot));

            Object.keys(target).forEach((k) => delete target[k]);
            Object.assign(target, restored);

            if (keepId !== undefined) target.id = keepId;
            if (keepRestoreUid) target[this.entryUidField] = keepRestoreUid;
            if (typeof resolved.index === 'number' && resolved.index >= 0) {
                this.currentWiIndex = resolved.index;
            }

            this.showEntryHistoryModal = false;
            this.$store.global.showToast('⏪ 条目已回滚，请记得保存世界书', 2200);
        },

        getTotalWiTokens() {
            // 必须传入当前的条目数组
            return getTotalWiTokens(this.getWIArrayRef());
        },

        async _createWholeWorldbookSnapshot() {
            const payload = this._getAutoSavePayload();
            const isLorebook = payload.type === 'lorebook';
            const res = await apiCreateSnapshot({
                id: payload.id,
                type: isLorebook ? 'lorebook' : 'card',
                file_path: payload.file_path || '',
                label: '',
                // 整本保存前快照：备份磁盘上的“旧文件状态”，避免首版被覆盖
                content: null,
                compact: isLorebook
            });
            return res;
        },

        async _ensureInitialBaselineSnapshot() {
            const payload = this._getAutoSavePayload();
            const isLorebook = payload.type === 'lorebook';
            const snapshotType = isLorebook ? 'lorebook' : 'card';

            const snapshotRes = await apiCreateSnapshot({
                id: payload.id,
                type: snapshotType,
                file_path: payload.file_path || '',
                label: 'INIT',
                content: null,
                compact: isLorebook
            });

            if (!snapshotRes || !snapshotRes.success) {
                throw new Error((snapshotRes && snapshotRes.msg) ? snapshotRes.msg : '创建初始快照失败');
            }
            return { created: true };
        },

        async _ensureInitialBaselineOnEnter() {
            if (this.initialSnapshotChecked) return;
            if (!this.initialSnapshotInitPromise) {
                this.initialSnapshotInitPromise = this._ensureInitialBaselineSnapshot()
                    .then((res) => {
                        this.initialSnapshotChecked = true;
                        if (res && res.created) this.$store.global.showToast('🧷 已记录本次编辑初始版本', 1800);
                        return res;
                    })
                    .catch((e) => {
                        this.initialSnapshotChecked = false;
                        throw e;
                    })
                    .finally(() => {
                        this.initialSnapshotInitPromise = null;
                    });
            }
            return this.initialSnapshotInitPromise;
        },

        _nextTickPromise() {
            return new Promise((resolve) => {
                this.$nextTick(() => resolve());
            });
        },

        async _flushPendingEditorInput() {
            const active = document.activeElement;
            if (!active || !this.$root || !this.$root.contains(active)) return;

            const tag = active.tagName;
            const isField = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
            if (!isField) return;

            try {
                active.dispatchEvent(new Event('input', { bubbles: true }));
                active.dispatchEvent(new Event('change', { bubbles: true }));
                if (typeof active.blur === 'function') active.blur();
            } catch (e) {
                console.warn('Flush editor input failed:', e);
            }

            await this._nextTickPromise();
        },

        _getSnapshotContext() {
            const file = this.editingWiFile || {};

            if (file.type === 'embedded' || (!file.type && this.editingData?.id)) {
                return {
                    id: (this.editingData && this.editingData.id) ? this.editingData.id : (file.card_id || ''),
                    type: 'card',
                    file_path: ''
                };
            }

            return {
                id: file.id || file.path || file.file_path || '',
                type: 'lorebook',
                file_path: file.file_path || file.path || ''
            };
        },

        async _cleanupInitBackupsOnExit() {
            const pendingInit = this.initialSnapshotInitPromise;
            if (pendingInit) {
                try {
                    await pendingInit;
                } catch (e) {
                    console.warn('Init snapshot promise rejected before cleanup:', e);
                }
            }

            const ctx = this._getSnapshotContext();
            if (!ctx.id) return;
            try {
                const res = await apiCleanupInitBackups({
                    id: ctx.id,
                    type: ctx.type,
                    file_path: ctx.file_path,
                    // 保留最近一个 INIT，避免“仅保存条目”后时光机无历史
                    keep_latest: 1
                });
                if (!res || !res.success) {
                    console.warn('Cleanup INIT backups failed:', res && res.msg ? res.msg : res);
                }
            } catch (e) {
                console.warn('Cleanup INIT backups error:', e);
            }
        },

        async _ensureInitSnapshotReadyForSave() {
            if (this.initialSnapshotInitPromise) {
                try {
                    await this.initialSnapshotInitPromise;
                } catch (e) {
                    console.warn('Init snapshot on enter failed:', e);
                }
                return;
            }

            if (!this.initialSnapshotChecked) {
                try {
                    await this._ensureInitialBaselineOnEnter();
                } catch (e) {
                    console.warn('Init snapshot retry before save failed:', e);
                }
            }
        },

        saveWholeWorldbook() {
            if (this.editingWiFile && this.editingWiFile.type === 'embedded') {
                return this.saveChanges(true);
            }
            return this.saveWiFileChanges(true);
        },

        async saveChanges(withSnapshot = false) {
            // 如果不是内嵌模式，但误调了此方法，转给文件保存逻辑
            if (!this.editingWiFile || this.editingWiFile.type !== 'embedded') {
                return this.saveWiFileChanges(withSnapshot);
            }

            await this._flushPendingEditorInput();
            this._ensureEntryUids();
            this.isSaving = true;
            await this._ensureInitSnapshotReadyForSave();

            if (withSnapshot) {
                try {
                    const snapshotRes = await this._createWholeWorldbookSnapshot();
                    if (!snapshotRes || !snapshotRes.success) {
                        this.isSaving = false;
                        alert("整本保存失败：无法创建版本快照" + (snapshotRes && snapshotRes.msg ? ` (${snapshotRes.msg})` : ""));
                        return;
                    }
                } catch (e) {
                    this.isSaving = false;
                    alert("整本保存失败：创建版本快照异常 - " + e);
                    return;
                }
            }

            // 1. 深拷贝当前编辑数据
            const cardData = JSON.parse(JSON.stringify(this.editingData));

            // 2. 使用工具函数清洗 V3 数据结构 (构建标准角色卡 Payload)
            const cleanData = getCleanedV3Data(cardData);

            // 3. 构造发送给 update_card 的完整数据
            const payload = {
                id: this.editingData.id, // 角色卡 ID
                ...cleanData,
                // 1. 映射后端专用字段名
                char_name: cleanData.name || this.editingData.char_name,
                
                // 2. 传递文件名 (防止意外重命名或丢失扩展名)
                new_filename: this.editingData.filename,

                // 3. 补全 UI 专属字段 (如果不传，后端会将其清空)
                ui_summary: this.editingData.ui_summary || "",
                source_link: this.editingData.source_link || "",
                resource_folder: this.editingData.resource_folder || "",
                
                // 4. Bundle 状态透传 (保持包模式状态不丢失)
                save_ui_to_bundle: this.editingData.is_bundle,
                bundle_dir: this.editingData.is_bundle ? this.editingData.bundle_dir : undefined,
                // 显式确保 character_book 被包含（虽然 getCleanedV3Data 也会包含，但双重保险）
                character_book: this.editingData.character_book
            };

            updateCard(payload).then(res => {
                this.isSaving = false;
                if (res.success) {
                    if (withSnapshot) {
                        this.$store.global.showToast("💾 已保存整本并生成回滚版本", 2200);
                    } else {
                        this.$store.global.showToast("💾 条目修改已保存", 1800);
                    }

                    // 通知外部 (如卡片列表或详情页) 刷新数据
                    window.dispatchEvent(new CustomEvent('card-updated', { detail: res.updated_card }));

                    // 更新自动保存的基准
                    if (autoSaver && typeof autoSaver.initBaseline === 'function') {
                        autoSaver.initBaseline(this.editingData);
                    }
                } else {
                    alert("保存失败: " + res.msg);
                }
            }).catch(e => {
                this.isSaving = false;
                alert("请求错误: " + e);
            });
        },

        // === 辅助：生成自动保存的 Payload ===
        _getAutoSavePayload() {
            // 场景 A: 角色卡内嵌模式
            if (this.editingWiFile && this.editingWiFile.type === 'embedded') {
                // 如果是内嵌，我们需要保存整个 Card 数据 (以此确保一致性)
                const contentToSave = getCleanedV3Data(this.editingData);
                return {
                    id: this.editingData.id, // 角色卡 ID
                    type: 'card',
                    content: contentToSave,
                    file_path: ""
                };
            }

            // 场景 B: 独立世界书文件
            const name = this.editingData.character_book?.name || "World Info";
            const contentToSave = toStV3Worldbook(this.editingData.character_book, name);

            return {
                id: this.editingWiFile ? this.editingWiFile.id : 'unknown',
                type: 'lorebook',
                content: contentToSave,
                file_path: this.editingWiFile ? (this.editingWiFile.path || this.editingWiFile.file_path) : ""
            };
        },

        // === 核心打开逻辑 ===

        // 打开编辑器 (适配三种来源: global, resource, embedded)
        openWorldInfoEditor(item) {
            this.isLoading = true;
            this.initialSnapshotChecked = false;
            this.initialSnapshotInitPromise = null;

            const handleSuccess = (dataObj, source) => {
                // === 强制执行归一化 ===
                // 不管是 embedded 还是 global，统统过一遍清洗
                if (dataObj.character_book) {
                    dataObj.character_book = normalizeWiBook(dataObj.character_book, dataObj.char_name || "WI");
                }

                if (dataObj.character_book && Array.isArray(dataObj.character_book.entries)) {
                    const sessionTs = Date.now();
                    dataObj.character_book.entries.forEach((entry, idx) => {
                        entry.id = `edit-${sessionTs}-${idx}`;
                    });
                }

                // 赋值给响应式对象
                this.editingData = dataObj;
                this.editingWiFile = item;
                this._ensureEntryUids();
                let targetIndex = 0;
                if (typeof item.jumpToIndex === 'number' && item.jumpToIndex >= 0) {
                    targetIndex = item.jumpToIndex;
                }
                this.currentWiIndex = targetIndex;
                this.isLoading = false;

                this.openFullScreenWI();

                // 滚动到选中项
                if (targetIndex >= 0) {
                    this.$nextTick(() => {
                        // 稍微延迟以等待列表渲染
                        setTimeout(() => {
                            // 再次强制设置一次 index
                            this.currentWiIndex = targetIndex;

                            const elId = `wi-item-${targetIndex}`;
                            const el = document.getElementById(elId);
                            if (el) {
                                el.scrollIntoView({ behavior: 'auto', block: 'center' }); // 使用 auto 瞬间定位，避免 smooth 还没滚到就停止
                                el.classList.add('bg-accent-main', 'text-white'); // 临时高亮
                                setTimeout(() => el.classList.remove('bg-accent-main', 'text-white'), 800);
                            }
                        }, 100);
                    });
                }
            };

            // 1. 内嵌类型 (Embedded): 获取角色卡数据
            if (item.type === 'embedded') {
                getCardDetail(item.card_id).then(res => {
                    if (res.success && res.card) {
                        // 这是一个角色卡对象，character_book 在其中
                        this.editingData = res.card;

                        // 确保 character_book 存在
                        if (!this.editingData.character_book) {
                            this.editingData.character_book = { name: item.name || "World Info", entries: [] };
                        } else if (Array.isArray(this.editingData.character_book)) {
                            // 兼容 V2 数组
                            this.editingData.character_book = {
                                name: item.name || "World Info",
                                entries: this.editingData.character_book
                            };
                        }

                        this.editingWiFile = item;
                        this.currentWiIndex = 0;
                        this.isEditingClipboard = false;
                        this.currentClipboardIndex = -1;

                        handleSuccess(res.card, "Embedded");
                    } else {
                        alert("无法加载关联的角色卡数据");
                    }
                }).catch(e => {
                    this.isLoading = false;
                    alert("加载失败: " + e);
                });
                return;
            } else {
                // 独立文件 (Global / Resource)
                getWorldInfoDetail({
                    id: item.id,
                    source_type: item.type, // list 返回的是 type
                    file_path: item.path,
                    force_full: true
                }).then(res => {
                    if (res.success) {
                        // 归一化数据
                        const bookData = normalizeWiBook(res.data, "");
                        this.editingData.character_book = bookData;

                        this.editingWiFile = item;
                        this.currentWiIndex = 0;
                        this.isEditingClipboard = false;
                        this.currentClipboardIndex = -1;
                        const dummyObj = {
                            id: null,
                            character_book: res.data // 这里是原始数据
                        };
                        handleSuccess(dummyObj, "Global/Resource");
                    } else {
                        alert(res.msg);
                    }
                }).catch(e => {
                    this.isLoading = false;
                    alert("加载失败: " + e);
                });
            }
        },

        // 打开独立文件 (兼容接口)
        openWorldInfoFile(item) {
            this.isLoading = true;
            this.initialSnapshotChecked = false;
            this.initialSnapshotInitPromise = null;
            getWorldInfoDetail({
                id: item.id,
                source_type: item.source_type,
                file_path: item.file_path,
                force_full: true
            }).then(res => {
                this.isLoading = false;
                if (res.success) {
                    const book = normalizeWiBook(res.data, item.name || "World Info");
                    
                    if (Array.isArray(book.entries)) {
                        const sessionTs = Date.now();
                        book.entries.forEach((entry, idx) => {
                            entry.id = `edit-${sessionTs}-${idx}`;
                        });
                    }
                    
                    this.editingData.character_book = book;
                    this.editingWiFile = item;
                    this._ensureEntryUids();
                    this.openFullScreenWI();
                    this.$nextTick(async () => {
                        if (this.initialSnapshotInitPromise) {
                            try {
                                await this.initialSnapshotInitPromise;
                            } catch (e) {
                                console.warn('Init snapshot on enter failed before auto-save start:', e);
                            }
                        }
                        autoSaver.initBaseline(this.editingData);
                        autoSaver.start(() => this.editingData, () => this._getAutoSavePayload());
                    });
                } else {
                    this.isLoading = false; alert(res.msg);
                }
            });
        },

        openFullScreenWI() {
            this.showFullScreenWI = true;
            // 确保选中第一项
            const entries = this.getWIArrayRef();
            if (entries.length > 0) {
                this.currentWiIndex = 0;
            }
            // 加载剪切板
            this.loadWiClipboard();

            // 进入编辑器时自动生成“本次编辑起点”的 INIT 快照
            this._ensureInitialBaselineOnEnter().catch((e) => {
                console.warn('Auto init snapshot failed:', e);
            });
        },

        // === 数据存取 ===

        getWIEntries() {
            return this.getWIArrayRef();
        },

        // 获取当前编辑器应该显示的数据 (Computed)
        get activeEditorEntry() {
            if (this.isEditingClipboard) {
                if (this.currentClipboardIndex >= 0 && this.currentClipboardIndex < this.wiClipboardItems.length) {
                    return this.wiClipboardItems[this.currentClipboardIndex].content;
                }
                return null;
            } else {
                const arr = this.getWIArrayRef();
                if (this.currentWiIndex >= 0 && this.currentWiIndex < arr.length) {
                    return arr[this.currentWiIndex];
                }
                return null;
            }
        },

        // === 保存逻辑 ===

        async saveWiFileChanges(withSnapshot = false) {
            if (!this.editingWiFile) return;

            // 如果是内嵌模式，实际上应该调用 UpdateCard
            if (this.editingWiFile.type === 'embedded') {
                alert("内嵌世界书将随角色卡自动保存 (Auto-save) 或请关闭后点击角色保存。");
                return;
            }

            await this._flushPendingEditorInput();
            this._ensureEntryUids();
            this.isSaving = true;
            await this._ensureInitSnapshotReadyForSave();

            if (withSnapshot) {
                try {
                    const snapshotRes = await this._createWholeWorldbookSnapshot();
                    if (!snapshotRes || !snapshotRes.success) {
                        this.isSaving = false;
                        alert("整本保存失败：无法创建版本快照" + (snapshotRes && snapshotRes.msg ? ` (${snapshotRes.msg})` : ""));
                        return;
                    }
                } catch (e) {
                    this.isSaving = false;
                    alert("整本保存失败：创建版本快照异常 - " + e);
                    return;
                }
            }

            // 独立文件保存
            const contentToSave = toStV3Worldbook(
                this.editingData.character_book,
                this.editingData.character_book?.name || this.editingWiFile?.name || "World Info"
            );

            saveWorldInfo({
                save_mode: 'overwrite',
                file_path: this.editingWiFile.file_path || this.editingWiFile.path,
                content: contentToSave,
                compact: true
            }).then(res => {
                this.isSaving = false;
                if (res.success) {
                    if (withSnapshot) {
                        this.$store.global.showToast("💾 已保存整本并生成回滚版本", 2200);
                    } else {
                        this.$store.global.showToast("💾 条目修改已保存", 1800);
                    }
                    autoSaver.initBaseline(this.editingData);
                } else {
                    alert("保存失败: " + res.msg);
                }
            }).catch(e => {
                this.isSaving = false;
                alert("请求错误: " + e);
            });
        },

        saveAsGlobalWi() {
            const name = prompt("请输入新世界书名称:", this.editingData.character_book.name || "New World Book");
            if (!name) return;

            this._ensureEntryUids();
            const contentToSave = toStV3Worldbook(this.editingData.character_book, name);
            contentToSave.name = name; // 确保内部名一致

            saveWorldInfo({
                save_mode: 'new_global',
                name: name,
                content: contentToSave,
                compact: true
            }).then(res => {
                if (res.success) {
                    alert("已另存为全局世界书！");
                    window.dispatchEvent(new CustomEvent('refresh-wi-list'));
                } else {
                    alert(res.msg);
                }
            });
        },

        exportWorldBookSingle() {
            const book = this.editingData.character_book || { entries: [], name: "World Info" };
            this.downloadWorldInfoJson(book, book.name);
        },

        // === 剪切板逻辑 ===

        loadWiClipboard() {
            clipboardList().then(res => {
                if (res.success) {
                    // 1. 先清空，给 Alpine 一个明确的信号
                    this.wiClipboardItems = [];

                    // 2. 在 nextTick 中赋值，确保 DOM 准备好重绘
                    this.$nextTick(() => {
                        this.wiClipboardItems = res.items;

                        // 3. 强制确保侧边栏是展开的，否则用户看不到
                        if (this.wiClipboardItems.length > 0) {
                            this.showWiClipboard = true;
                        }
                    });
                }
            });
        },

        saveClipboardItem() {
            if (!this.isEditingClipboard || this.currentClipboardIndex === -1) return;
            const item = this.wiClipboardItems[this.currentClipboardIndex];
            if (!item) return;

            // 更新 (Overwrite)
            this._addWiClipboardRequest(item.content, item.db_id);
            alert("剪切板条目已更新");
        },

        copyWiToClipboard(entry) {
            // 1. 确定目标数据：优先使用传入参数，否则使用当前编辑器内容
            let targetData = entry;

            // 如果传入的是 Event 对象（点击事件），或者为空，则使用当前编辑器数据
            if (!targetData || targetData instanceof Event || (targetData.target && targetData.type)) {
                targetData = this.activeEditorEntry;
            }

            if (!targetData) {
                alert("无法获取要复制的条目内容");
                return;
            }

            // 2. 深度拷贝并清洗 (移除 Proxy，转为纯 JSON 对象)
            let copy;
            try {
                // 使用 JSON 序列化再反序列化，彻底斩断引用和 Proxy
                copy = JSON.parse(JSON.stringify(targetData));
            } catch (e) {
                console.error("Copy failed:", e);
                return;
            }

            // 3. 清理 ID 和 UID，确保被视为新条目
            // 注意：必须显式设置为 undefined 或 delete，防止后端复用 ID
            delete copy.id;
            delete copy.uid;
            delete copy[this.entryUidField];

            // 4. 确保 content 字段存在
            if (copy.content === undefined || copy.content === null) copy.content = "";

            // 5. 发送请求
            this._addWiClipboardRequest(copy);
        },

        _addWiClipboardRequest(entry, overwriteId = null) {
            // 获取当前焦点元素
            const activeEl = document.activeElement;
            const isSafeButton = activeEl &&
                activeEl.tagName === 'BUTTON' &&
                !activeEl.classList.contains('wi-list-item');
            const originalHtml = isSafeButton ? activeEl.innerHTML : '';
            if (isSafeButton && !overwriteId) activeEl.innerHTML = '⏳...';

            clipboardAdd(entry, overwriteId).then(res => {
                if (res.success) {
                    this.wiClipboardItems = [];
                    setTimeout(() => {
                        this.loadWiClipboard();
                    }, 50);
                    this.wiClipboardOverwriteMode = false;
                    this.clipboardPendingEntry = null;
                    if (!this.showWiClipboard) this.showWiClipboard = true;

                    this.$store.global.showToast("📋 已复制到全局剪切板");
                } else if (res.code === 'FULL') {
                    this.wiClipboardOverwriteMode = true;
                    this.clipboardPendingEntry = entry;
                    if (!this.showWiClipboard) this.showWiClipboard = true;
                } else {
                    alert("保存失败: " + res.msg);
                }
            }).finally(() => {
                if (isSafeButton && !overwriteId) activeEl.innerHTML = originalHtml;
            });
        },

        addWiEntryFromClipboard(content) {
            const arr = this.getWIArrayRef();
            const newEntry = JSON.parse(JSON.stringify(content));
            newEntry.id = Math.floor(Math.random() * 1000000);
            newEntry[this.entryUidField] = this._generateEntryUid();

            let insertPos = this.currentWiIndex + 1;
            if (insertPos > arr.length) insertPos = arr.length;

            arr.splice(insertPos, 0, newEntry);
            this.currentWiIndex = insertPos;
            this.isEditingClipboard = false;

            this.$nextTick(() => {
                const item = document.querySelectorAll('.wi-list-item')[insertPos];
                if (item) item.scrollIntoView({ behavior: 'smooth', block: 'center' });
            });
        },

        deleteWiClipboardItem(dbId) {
            if (!confirm("删除此剪切板条目？")) return;
            clipboardDelete(dbId).then(() => this.loadWiClipboard());
        },

        clearWiClipboard() {
            if (!confirm("清空所有剪切板内容？")) return;
            clipboardClear().then(() => this.loadWiClipboard());
        },

        selectMainWiItem(index) {
            this.isEditingClipboard = false;
            this.currentClipboardIndex = -1;
            this.currentWiIndex = index;
        },

        selectClipboardItem(index) {
            // 覆写模式检查
            if (this.wiClipboardOverwriteMode) {
                const item = this.wiClipboardItems[index];
                if (confirm(`确定要覆盖 "${item.content.comment || '未命名'}" 吗？`)) {
                    this._addWiClipboardRequest(this.clipboardPendingEntry, item.db_id);
                }
                return;
            }
            this.isEditingClipboard = true;
            this.currentClipboardIndex = index;
            this.currentWiIndex = -1;
        },

        exitClipboardEdit() {
            this.isEditingClipboard = false;
            this.currentClipboardIndex = -1;
            // 恢复之前选中的主条目 (如果有)
            const arr = this.getWIArrayRef();
            if (arr.length > 0 && this.currentWiIndex === -1) {
                this.currentWiIndex = 0;
            }
        },

        // === 拖拽排序逻辑 ===

        // 1. 主列表拖拽
        wiDragStart(e, index) {
            this.wiDraggingIndex = index;
            e.dataTransfer.effectAllowed = 'copyMove';
            e.dataTransfer.setData('application/x-wi-index', index.toString());

            const arr = this.getWIArrayRef();
            const item = arr[index];

            if (item) {
                const exportItem = JSON.parse(JSON.stringify(item));
                e.dataTransfer.setData('text/plain', JSON.stringify(exportItem, null, 2));
            }
            const target = e.target;
            target.classList.add('dragging');
            const cleanup = () => {
                target.classList.remove('dragging');
                this.wiDraggingIndex = null;
            };
            target.addEventListener('dragend', cleanup, { once: true });
        },

        wiDragOver(e, index) {
            e.preventDefault();
            const target = e.currentTarget;
            const rect = target.getBoundingClientRect();
            const midY = rect.top + rect.height / 2;

            target.classList.remove('drag-over-top', 'drag-over-bottom');
            if (e.clientY < midY) target.classList.add('drag-over-top');
            else target.classList.add('drag-over-bottom');
        },

        wiDragLeave(e) {
            e.currentTarget.classList.remove('drag-over-top', 'drag-over-bottom');
        },

        wiDrop(e, targetIndex) {
            e.preventDefault();
            e.stopPropagation();
            const el = e.currentTarget;
            el.classList.remove('drag-over-top', 'drag-over-bottom', 'dragging');

            // A. 从剪切板拖入
            const clipData = e.dataTransfer.getData('application/x-wi-clipboard');
            if (clipData) {
                try {
                    const content = JSON.parse(clipData);
                    const arr = this.getWIArrayRef();
                    const newEntry = JSON.parse(JSON.stringify(content));
                    newEntry.id = Math.floor(Math.random() * 1000000);
                    newEntry[this.entryUidField] = this._generateEntryUid();

                    arr.splice(targetIndex, 0, newEntry);
                    this.currentWiIndex = targetIndex;
                    this.isEditingClipboard = false;
                } catch (err) { console.error(err); }
                return;
            }

            // B: 内部列表排序
            let sourceIndexStr = e.dataTransfer.getData('application/x-wi-index');

            if (!sourceIndexStr && this.wiDraggingIndex !== null) {
                sourceIndexStr = this.wiDraggingIndex.toString();
            }

            if (!sourceIndexStr) return;

            const sourceIndex = parseInt(sourceIndexStr);

            if (isNaN(sourceIndex) || sourceIndex === targetIndex) return;

            const arr = this.getWIArrayRef();
            if (sourceIndex >= arr.length || targetIndex > arr.length) return;

            const itemToMove = arr[sourceIndex];

            let oldSelectedIndex = this.currentWiIndex;
            let newSelectedIndex = oldSelectedIndex;

            // 根据拖拽方向执行不同的 splice 操作
            if (sourceIndex < targetIndex) {
                arr.splice(sourceIndex, 1);
                arr.splice(targetIndex - 1, 0, itemToMove);

                if (oldSelectedIndex === sourceIndex) {
                    newSelectedIndex = targetIndex - 1;
                } else if (oldSelectedIndex > sourceIndex && oldSelectedIndex < targetIndex) {
                    newSelectedIndex = oldSelectedIndex - 1;
                }
            } else {
                arr.splice(sourceIndex, 1);
                arr.splice(targetIndex, 0, itemToMove);
                if (oldSelectedIndex === sourceIndex) {
                    newSelectedIndex = targetIndex;
                } else if (oldSelectedIndex >= targetIndex && oldSelectedIndex < sourceIndex) {
                    newSelectedIndex = oldSelectedIndex + 1;
                }
            }

            this.currentWiIndex = newSelectedIndex;
        },

        // 2. 剪切板拖拽
        clipboardDragStart(e, item, idx) {
            e.dataTransfer.setData('application/x-wi-clipboard', JSON.stringify(item.content));
            e.dataTransfer.setData('text/plain', JSON.stringify(item.content));
            e.dataTransfer.effectAllowed = 'copyMove';
            // 内部排序用
            e.dataTransfer.setData('application/x-wi-clipboard-index', idx);

            const target = e.target;
            target.classList.add('dragging');
            target.addEventListener('dragend', () => {
                target.classList.remove('dragging');
            }, { once: true });
        },

        clipboardDropInside(e, targetIdx) {
            e.preventDefault();
            e.stopPropagation();
            const sourceIdxStr = e.dataTransfer.getData('application/x-wi-clipboard-index');
            if (sourceIdxStr) {
                const sourceIdx = parseInt(sourceIdxStr);
                if (sourceIdx === targetIdx) return;
                const items = [...this.wiClipboardItems];
                const [moved] = items.splice(sourceIdx, 1);
                items.splice(targetIdx, 0, moved);
                this.wiClipboardItems = items;
                const orderMap = items.map(i => i.db_id);
                clipboardReorder(orderMap);
                return;
            }

            if (this.wiDraggingIndex !== null && this.wiDraggingIndex !== undefined) {
                const arr = this.getWIArrayRef();
                const rawEntry = arr[this.wiDraggingIndex];
                if (rawEntry) {
                    this.copyWiToClipboard(rawEntry);
                }
            }
        },

        // === 处理剪切板容器的 Drop ===
        handleClipboardDropReorder(e) {
            e.preventDefault();
            e.stopPropagation();

            // 剪切板内部排序
            const isClipboardInternal = e.dataTransfer.types.includes('application/x-wi-clipboard-index');

            if (isClipboardInternal) {
                const sourceIdxStr = e.dataTransfer.getData('application/x-wi-clipboard-index');
                if (sourceIdxStr) {
                    const sourceIdx = parseInt(sourceIdxStr);
                    if (sourceIdx === this.wiClipboardItems.length - 1) return;

                    const items = [...this.wiClipboardItems];
                    const [moved] = items.splice(sourceIdx, 1);
                    items.push(moved);

                    this.wiClipboardItems = items;
                    const orderMap = items.map(i => i.db_id);
                    clipboardReorder(orderMap);
                }
            } else {
                // 从左侧主列表拖入 (复制)
                if (this.wiDraggingIndex !== null && this.wiDraggingIndex !== undefined) {
                    const arr = this.getWIArrayRef();
                    const rawEntry = arr[this.wiDraggingIndex];

                    if (rawEntry) {
                        // 深拷贝
                        let entryCopy = null;
                        try {
                            entryCopy = JSON.parse(JSON.stringify(rawEntry));
                        } catch (err) { return; }
                        this.copyWiToClipboard(entryCopy);
                    }
                }
            }
        }
    }
}
