/**
 * static/js/components/chatGrid.js
 * 聊天记录网格与全屏阅读器组件
 */

import {
    bindChatToCard,
    deleteChat,
    getChatDetail,
    importChats,
    listChats,
    saveChat,
    updateChatMeta,
} from '../api/chat.js';
import { listCards } from '../api/card.js';
import { openPath } from '../api/system.js';
import { formatDate } from '../utils/format.js';


function escapeRegExp(text) {
    return String(text || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}


function replaceTextValue(source, query, replacement, caseSensitive) {
    const input = String(source || '');
    const needle = String(query || '');
    if (!needle) {
        return { text: input, count: 0 };
    }

    if (caseSensitive) {
        const parts = input.split(needle);
        return {
            text: parts.join(replacement),
            count: Math.max(0, parts.length - 1),
        };
    }

    const regex = new RegExp(escapeRegExp(needle), 'gi');
    let count = 0;
    const text = input.replace(regex, () => {
        count += 1;
        return replacement;
    });
    return { text, count };
}


export default function chatGrid() {
    return {
        dragOverChats: false,
        detailOpen: false,
        detailLoading: false,
        activeChat: null,

        detailSearchQuery: '',
        detailSearchResults: [],
        detailSearchIndex: -1,
        detailBookmarkedOnly: false,

        detailDraftName: '',
        detailDraftNotes: '',
        bookmarkDraft: '',
        jumpFloorInput: '',

        replaceQuery: '',
        replaceReplacement: '',
        replaceCaseSensitive: false,
        replaceStatus: '',

        linkedCardIdFilter: '',
        linkedCardNameFilter: '',
        pendingOpenChatId: '',

        filePickerMode: 'global',
        filePickerPayload: null,

        readerShowLeftPanel: true,
        readerShowRightPanel: true,

        bindPickerOpen: false,
        bindPickerLoading: false,
        bindPickerSearch: '',
        bindPickerResults: [],
        bindPickerTargetChatId: '',

        get chatList() { return this.$store.global.chatList; },
        set chatList(val) { this.$store.global.chatList = val; },
        get chatCurrentPage() { return this.$store.global.chatCurrentPage; },
        set chatCurrentPage(val) { this.$store.global.chatCurrentPage = val; },
        get chatTotalItems() { return this.$store.global.chatTotalItems; },
        set chatTotalItems(val) { this.$store.global.chatTotalItems = val; },
        get chatTotalPages() { return this.$store.global.chatTotalPages; },
        set chatTotalPages(val) { this.$store.global.chatTotalPages = val; },
        get chatSearchQuery() { return this.$store.global.chatSearchQuery; },
        set chatSearchQuery(val) { this.$store.global.chatSearchQuery = val; },
        get chatFilterType() { return this.$store.global.chatFilterType; },
        set chatFilterType(val) { this.$store.global.chatFilterType = val; },

        get visibleDetailMessages() {
            if (!this.activeChat || !Array.isArray(this.activeChat.messages)) return [];

            const bookmarks = Array.isArray(this.activeChat.bookmarks) ? this.activeChat.bookmarks : [];
            const bookmarkSet = new Set(bookmarks.map(item => Number(item.floor || 0)).filter(Boolean));

            let messages = this.activeChat.messages.map((message) => ({
                ...message,
                is_bookmarked: bookmarkSet.has(Number(message.floor || 0)),
            }));

            if (this.detailBookmarkedOnly) {
                messages = messages.filter(item => item.is_bookmarked);
            }

            return messages;
        },

        get readerBodyGridStyle() {
            const isMobile = this.$store.global.deviceType === 'mobile';
            const left = this.readerShowLeftPanel ? (isMobile ? 1 : 320) : 0;
            const right = this.readerShowRightPanel ? (isMobile ? 1 : 300) : 0;

            if (isMobile) {
                if (!this.readerShowLeftPanel && !this.readerShowRightPanel) {
                    return 'grid-template-columns: minmax(0, 1fr);';
                }
                if (this.readerShowLeftPanel && !this.readerShowRightPanel) {
                    return 'grid-template-columns: minmax(0, 1fr);';
                }
                if (!this.readerShowLeftPanel && this.readerShowRightPanel) {
                    return 'grid-template-columns: minmax(0, 1fr);';
                }
                return 'grid-template-columns: minmax(0, 1fr);';
            }

            return `grid-template-columns: ${left}px minmax(0, 1fr) ${right}px;`;
        },

        init() {
            this.$watch('$store.global.chatSearchQuery', () => {
                this.chatCurrentPage = 1;
                this.fetchChats();
            });

            this.$watch('$store.global.chatFilterType', () => {
                this.chatCurrentPage = 1;
                this.fetchChats();
            });

            window.addEventListener('refresh-chat-list', () => {
                this.fetchChats();
            });

            window.addEventListener('settings-loaded', () => {
                if (this.$store.global.currentMode === 'chats') {
                    this.fetchChats();
                }
            });

            window.addEventListener('open-chat-manager', (e) => {
                const detail = e.detail || {};
                this.$store.global.currentMode = 'chats';
                this.linkedCardIdFilter = detail.card_id || '';
                this.linkedCardNameFilter = detail.card_name || '';
                this.pendingOpenChatId = detail.chat_id || '';
                this.chatFilterType = 'all';
                this.chatCurrentPage = 1;
                this.fetchChats();
            });

            window.addEventListener('open-chat-reader', (e) => {
                const detail = e.detail || {};
                if (!detail.chat_id) return;
                this.openChatDetail({ id: detail.chat_id });
            });

            window.addEventListener('open-chat-file-picker', (event) => {
                const detail = event.detail || {};
                this.triggerChatImport(detail);
            });

            window.addEventListener('keydown', (e) => {
                if (e.key !== 'Escape') return;
                if (this.bindPickerOpen) {
                    this.closeBindPicker();
                    return;
                }
                if (this.detailOpen) {
                    this.closeChatDetail();
                }
            });

            window.stUploadChatFiles = (files, payload = {}) => {
                this._uploadChatFiles(files, payload.cardId || '', payload.characterName || '');
            };

            if (this.$store.global.currentMode === 'chats' && this.$store.global.serverStatus.status === 'ready') {
                this.fetchChats();
            }
        },

        fetchChats() {
            if (this.$store.global.serverStatus.status !== 'ready') return;

            this.$store.global.isLoading = true;
            const params = {
                page: this.chatCurrentPage,
                page_size: this.$store.global.settingsForm.items_per_page_wi || 20,
                search: this.chatSearchQuery || '',
                filter: this.chatFilterType || 'all',
            };

            if (this.linkedCardIdFilter) {
                params.card_id = this.linkedCardIdFilter;
            }

            listChats(params)
                .then((res) => {
                    this.$store.global.isLoading = false;
                    if (!res.success) return;

                    this.chatList = res.items || [];
                    this.chatTotalItems = res.total || 0;
                    this.chatTotalPages = Math.max(1, Math.ceil((res.total || 0) / (res.page_size || 1)));

                    if (this.pendingOpenChatId) {
                        const targetId = this.pendingOpenChatId;
                        this.pendingOpenChatId = '';
                        const targetItem = (this.chatList || []).find(item => item.id === targetId);
                        this.openChatDetail(targetItem || { id: targetId, title: targetId });
                    }
                })
                .catch(() => {
                    this.$store.global.isLoading = false;
                });
        },

        changeChatPage(page) {
            if (page < 1 || page > this.chatTotalPages) return;
            this.chatCurrentPage = page;
            const el = document.getElementById('chat-scroll-area');
            if (el) el.scrollTop = 0;
            this.fetchChats();
        },

        async openChatDetail(item) {
            if (!item || !item.id) return;

            this.detailOpen = true;
            this.detailLoading = true;
            this.activeChat = null;
            this.detailSearchQuery = '';
            this.detailSearchResults = [];
            this.detailSearchIndex = -1;
            this.detailBookmarkedOnly = false;
            this.bookmarkDraft = '';
            this.jumpFloorInput = '';
            this.replaceQuery = '';
            this.replaceReplacement = '';
            this.replaceStatus = '';

            const isMobile = this.$store.global.deviceType === 'mobile';
            this.readerShowLeftPanel = !isMobile;
            this.readerShowRightPanel = !isMobile;

            try {
                const res = await getChatDetail(item.id);
                if (!res.success || !res.chat) {
                    alert(res.msg || '读取聊天详情失败');
                    this.detailOpen = false;
                    return;
                }

                this.activeChat = res.chat;
                this.detailDraftName = res.chat.display_name || '';
                this.detailDraftNotes = res.chat.notes || '';
                this.$nextTick(() => {
                    this.scrollToFloor(res.chat.last_view_floor || 1, false);
                });
            } catch (err) {
                alert('读取聊天详情失败: ' + err);
                this.detailOpen = false;
            } finally {
                this.detailLoading = false;
            }
        },

        closeChatDetail() {
            this.detailOpen = false;
            this.detailLoading = false;
            this.activeChat = null;
            this.detailSearchQuery = '';
            this.detailSearchResults = [];
            this.detailSearchIndex = -1;
            this.detailBookmarkedOnly = false;
            this.bookmarkDraft = '';
            this.jumpFloorInput = '';
            this.replaceQuery = '';
            this.replaceReplacement = '';
            this.replaceStatus = '';
        },

        formatChatDate(ts) {
            const output = formatDate(ts);
            return output || '-';
        },

        formatDate(ts) {
            return this.formatChatDate(ts);
        },

        floorToneClass(floor) {
            const num = Number(floor || 0);
            if (num >= 1000) return 'chat-card-floor-extreme';
            if (num >= 500) return 'chat-card-floor-high';
            if (num >= 100) return 'chat-card-floor-mid';
            return 'chat-card-floor-low';
        },

        messageBadgeClass(message) {
            if (message.is_user) return 'is-user';
            if (message.is_system) return 'is-system';
            return 'is-assistant';
        },

        clearLinkedCardFilter() {
            this.linkedCardIdFilter = '';
            this.linkedCardNameFilter = '';
            this.chatCurrentPage = 1;
            this.fetchChats();
        },

        async reloadActiveChat() {
            if (!this.activeChat || !this.activeChat.id) return;
            const res = await getChatDetail(this.activeChat.id);
            if (!res.success || !res.chat) return;
            this.activeChat = res.chat;
            this.detailDraftName = res.chat.display_name || '';
            this.detailDraftNotes = res.chat.notes || '';
        },

        async toggleFavorite(item) {
            if (!item || !item.id) return;

            const next = !item.favorite;
            item.favorite = next;

            try {
                const res = await updateChatMeta({ id: item.id, favorite: next });
                if (!res.success || !res.chat) {
                    item.favorite = !next;
                    alert(res.msg || '收藏状态更新失败');
                    return;
                }

                Object.assign(item, res.chat);
                if (this.activeChat && this.activeChat.id === item.id) {
                    this.activeChat.favorite = res.chat.favorite;
                }
                window.dispatchEvent(new CustomEvent('refresh-detail-chats'));
            } catch (err) {
                item.favorite = !next;
                alert('收藏状态更新失败: ' + err);
            }
        },

        async saveChatMeta() {
            if (!this.activeChat) return;

            const payload = {
                id: this.activeChat.id,
                display_name: this.detailDraftName,
                notes: this.detailDraftNotes,
                last_view_floor: this.activeChat.last_view_floor || 0,
                bookmarks: this.activeChat.bookmarks || [],
                favorite: this.activeChat.favorite || false,
            };

            try {
                const res = await updateChatMeta(payload);
                if (!res.success || !res.chat) {
                    alert(res.msg || '保存失败');
                    return;
                }

                this.activeChat = {
                    ...this.activeChat,
                    ...res.chat,
                    messages: this.activeChat.messages,
                    raw_messages: this.activeChat.raw_messages,
                    metadata: this.activeChat.metadata,
                };

                const index = this.chatList.findIndex(item => item.id === res.chat.id);
                if (index > -1) {
                    this.chatList.splice(index, 1, {
                        ...this.chatList[index],
                        ...res.chat,
                    });
                }

                window.dispatchEvent(new CustomEvent('refresh-detail-chats'));
                this.$store.global.showToast('聊天本地信息已保存', 1500);
            } catch (err) {
                alert('保存聊天信息失败: ' + err);
            }
        },

        async deleteChat(item) {
            if (!item || !item.id) return;
            if (!confirm(`确定将聊天记录 "${item.title || item.chat_name}" 移至回收站吗？`)) return;

            try {
                const res = await deleteChat(item.id);
                if (!res.success) {
                    alert(res.msg || '删除失败');
                    return;
                }

                this.chatList = this.chatList.filter(chat => chat.id !== item.id);
                this.chatTotalItems = Math.max(0, this.chatTotalItems - 1);
                if (this.activeChat && this.activeChat.id === item.id) {
                    this.closeChatDetail();
                }
                window.dispatchEvent(new CustomEvent('refresh-detail-chats'));
                this.$store.global.showToast('聊天记录已移至回收站', 1800);
            } catch (err) {
                alert('删除失败: ' + err);
            }
        },

        openChatFolder(item) {
            if (!item || !item.file_path) return;
            openPath({ path: item.file_path, is_file: true }).then((res) => {
                if (!res.success) {
                    alert(res.msg || '打开失败');
                }
            });
        },

        jumpToBoundCard(item) {
            if (!item || !item.bound_card_id) return;
            window.dispatchEvent(new CustomEvent('jump-to-card-wi', { detail: item.bound_card_id }));
            this.closeChatDetail();
        },

        scrollElementToTop(el, behavior = 'smooth') {
            if (!el) return;

            const container = el.closest('.chat-reader-center');
            if (container) {
                const top = Math.max(0, el.offsetTop - container.offsetTop - 12);
                container.scrollTo({ top, behavior });
                return;
            }

            try {
                el.scrollIntoView({ behavior, block: 'start' });
            } catch {
                el.scrollIntoView();
            }
        },

        async openBindPicker(item) {
            const target = item || this.activeChat;
            if (!target || !target.id) return;

            this.bindPickerOpen = true;
            this.bindPickerTargetChatId = target.id;
            this.bindPickerSearch = target.bound_card_name || target.character_name || '';
            await this.fetchBindPickerResults();
        },

        closeBindPicker() {
            this.bindPickerOpen = false;
            this.bindPickerLoading = false;
            this.bindPickerSearch = '';
            this.bindPickerResults = [];
            this.bindPickerTargetChatId = '';
        },

        async fetchBindPickerResults() {
            this.bindPickerLoading = true;
            try {
                const res = await listCards({
                    page: 1,
                    page_size: 60,
                    category: '',
                    tags: '',
                    excluded_tags: '',
                    excluded_categories: '',
                    search: this.bindPickerSearch || '',
                    search_type: 'name',
                    search_scope: 'all_dirs',
                    sort: 'name_asc',
                    recursive: true,
                });

                this.bindPickerResults = Array.isArray(res.cards) ? res.cards : [];
            } catch (err) {
                this.bindPickerResults = [];
            } finally {
                this.bindPickerLoading = false;
            }
        },

        async applyBinding(chatId, cardId = '', unbind = false) {
            if (!chatId) return;

            try {
                const res = await bindChatToCard({
                    id: chatId,
                    card_id: cardId,
                    unbind,
                });

                if (!res.success) {
                    alert(res.msg || '绑定失败');
                    return;
                }

                this.fetchChats();
                window.dispatchEvent(new CustomEvent('refresh-detail-chats'));
                if (this.activeChat && this.activeChat.id === chatId) {
                    await this.reloadActiveChat();
                }
                this.closeBindPicker();
                this.$store.global.showToast(unbind ? '聊天绑定已解除' : '聊天绑定已更新', 1500);
            } catch (err) {
                alert('绑定失败: ' + err);
            }
        },

        async bindCardPick(card) {
            if (!card || !card.id || !this.bindPickerTargetChatId) return;
            await this.applyBinding(this.bindPickerTargetChatId, card.id, false);
        },

        async unbindCurrentChat() {
            if (!this.bindPickerTargetChatId) return;
            await this.applyBinding(this.bindPickerTargetChatId, '', true);
        },

        _uploadChatFiles(files, cardId = '', characterName = '') {
            const fileList = Array.from(files || []).filter(file => file && file.name && file.name.toLowerCase().endsWith('.jsonl'));
            if (fileList.length === 0) {
                alert('请选择 .jsonl 聊天记录文件');
                return;
            }

            const formData = new FormData();
            fileList.forEach(file => formData.append('files', file));
            if (cardId) formData.append('card_id', cardId);
            if (characterName) formData.append('character_name', characterName);

            this.$store.global.isLoading = true;
            importChats(formData)
                .then((res) => {
                    this.$store.global.isLoading = false;
                    if (!res.success && (!res.items || res.items.length === 0)) {
                        alert(res.msg || '聊天导入失败');
                        return;
                    }

                    if (Array.isArray(res.failed) && res.failed.length > 0) {
                        const message = res.failed.map(item => `${item.name}: ${item.msg}`).join('\n');
                        alert(`部分文件导入失败:\n${message}`);
                    }

                    this.$store.global.showToast(`已导入 ${res.imported || 0} 个聊天记录`, 1800);
                    this.fetchChats();
                    window.dispatchEvent(new CustomEvent('refresh-card-list'));
                    window.dispatchEvent(new CustomEvent('refresh-detail-chats'));
                })
                .catch((err) => {
                    this.$store.global.isLoading = false;
                    alert('聊天导入失败: ' + err);
                });
        },

        handleChatFilesDrop(event, cardId = '', characterName = '') {
            this.dragOverChats = false;
            this._uploadChatFiles(event?.dataTransfer?.files || [], cardId, characterName);
        },

        triggerChatImport(options = {}) {
            this.filePickerMode = options.mode || 'global';
            this.filePickerPayload = options.payload || null;
            if (this.$refs.chatImportInput) {
                this.$refs.chatImportInput.click();
            }
        },

        handleChatInputChange(e) {
            const input = e.target;
            try {
                const payload = this.filePickerPayload || {};
                if (this.filePickerMode === 'card') {
                    this._uploadChatFiles(input.files || [], payload.cardId || '', payload.characterName || '');
                } else {
                    this._uploadChatFiles(input.files || [], '', '');
                }
            } finally {
                this.filePickerMode = 'global';
                this.filePickerPayload = null;
                input.value = '';
            }
        },

        searchInDetail() {
            const query = String(this.detailSearchQuery || '').trim().toLowerCase();
            this.detailSearchResults = [];
            this.detailSearchIndex = -1;
            if (!query || !this.activeChat) return;

            const matches = [];
            this.visibleDetailMessages.forEach((message) => {
                const text = `${message.name || ''}\n${message.content || ''}\n${message.mes || ''}`.toLowerCase();
                if (text.includes(query)) {
                    matches.push(Number(message.floor || 0));
                }
            });

            this.detailSearchResults = matches;
            if (matches.length > 0) {
                this.detailSearchIndex = 0;
                this.scrollToFloor(matches[0]);
            }
        },

        nextSearchResult() {
            if (!this.detailSearchResults.length) return;
            this.detailSearchIndex = (this.detailSearchIndex + 1) % this.detailSearchResults.length;
            this.scrollToFloor(this.detailSearchResults[this.detailSearchIndex]);
        },

        previousSearchResult() {
            if (!this.detailSearchResults.length) return;
            this.detailSearchIndex = (this.detailSearchIndex - 1 + this.detailSearchResults.length) % this.detailSearchResults.length;
            this.scrollToFloor(this.detailSearchResults[this.detailSearchIndex]);
        },

        scrollToFloor(floor, persist = true) {
            const targetFloor = Number(floor || 0);
            if (!targetFloor || !this.activeChat) return;

            this.jumpFloorInput = String(targetFloor);

            this.$nextTick(() => {
                const root = document.querySelector('.chat-reader-overlay');
                const el = root ? root.querySelector(`[data-chat-floor="${targetFloor}"]`) : null;
                if (el) {
                    this.scrollElementToTop(el, 'smooth');
                }
            });

            if (persist) {
                this.activeChat.last_view_floor = targetFloor;
                updateChatMeta({ id: this.activeChat.id, last_view_floor: targetFloor }).then((res) => {
                    if (res.success && res.chat) {
                        const index = this.chatList.findIndex(item => item.id === res.chat.id);
                        if (index > -1) {
                            this.chatList.splice(index, 1, { ...this.chatList[index], ...res.chat });
                        }
                    }
                }).catch(() => {});
            }
        },

        jumpToInputFloor() {
            const value = String(this.jumpFloorInput || '').trim().replace(/^#/, '');
            const floor = parseInt(value, 10);
            if (!floor || floor < 1) {
                alert('请输入有效的楼层编号');
                return;
            }
            this.scrollToFloor(floor);
        },

        jumpToEdge(which) {
            const messages = this.visibleDetailMessages;
            if (!messages.length) return;
            if (which === 'first') {
                this.scrollToFloor(messages[0].floor);
                return;
            }
            this.scrollToFloor(messages[messages.length - 1].floor);
        },

        toggleBookmark(message) {
            if (!this.activeChat || !message) return;

            const floor = Number(message.floor || 0);
            if (!floor) return;

            const current = Array.isArray(this.activeChat.bookmarks) ? [...this.activeChat.bookmarks] : [];
            const index = current.findIndex(item => Number(item.floor || 0) === floor);
            if (index > -1) {
                current.splice(index, 1);
            } else {
                current.push({
                    id: `${floor}_${Date.now()}`,
                    floor,
                    label: String(this.bookmarkDraft || '').trim(),
                    text: String(message.content || message.mes || '').trim().slice(0, 120),
                    created_at: Date.now() / 1000,
                });
                this.bookmarkDraft = '';
            }

            this.activeChat.bookmarks = current;
            this.saveChatMeta();
        },

        isBookmarked(floor) {
            if (!this.activeChat || !Array.isArray(this.activeChat.bookmarks)) return false;
            const target = Number(floor || 0);
            return this.activeChat.bookmarks.some(item => Number(item.floor || 0) === target);
        },

        async persistChatContent(rawMessages, toastText = '聊天内容已保存') {
            if (!this.activeChat) return false;

            const payload = {
                id: this.activeChat.id,
                raw_messages: rawMessages,
                metadata: this.activeChat.metadata || {},
            };

            const res = await saveChat(payload);
            if (!res.success || !res.chat) {
                alert(res.msg || '聊天保存失败');
                return false;
            }

            const preserveName = this.detailDraftName;
            const preserveNotes = this.detailDraftNotes;
            this.activeChat = res.chat;
            this.detailDraftName = preserveName;
            this.detailDraftNotes = preserveNotes;

            const index = this.chatList.findIndex(item => item.id === res.chat.id);
            if (index > -1) {
                this.chatList.splice(index, 1, { ...this.chatList[index], ...res.chat });
            }

            window.dispatchEvent(new CustomEvent('refresh-detail-chats'));
            this.$store.global.showToast(toastText, 1600);
            return true;
        },

        async replaceAllInChat() {
            if (!this.activeChat) return;

            const query = String(this.replaceQuery || '');
            if (!query.trim()) {
                alert('请输入要查找的内容');
                return;
            }

            const replacement = String(this.replaceReplacement || '');
            const rawMessages = JSON.parse(JSON.stringify(this.activeChat.raw_messages || []));

            let changedMessages = 0;
            let totalReplaced = 0;

            rawMessages.forEach((message) => {
                if (!message || typeof message !== 'object') return;
                const original = String(message.mes || '');
                const result = replaceTextValue(original, query, replacement, this.replaceCaseSensitive);
                if (result.count > 0) {
                    message.mes = result.text;
                    changedMessages += 1;
                    totalReplaced += result.count;
                }
            });

            if (totalReplaced === 0) {
                this.replaceStatus = '没有找到可替换内容';
                this.$store.global.showToast(this.replaceStatus, 1400);
                return;
            }

            const ok = await this.persistChatContent(rawMessages, `已替换 ${totalReplaced} 处文本`);
            if (!ok) return;

            this.replaceStatus = `已在 ${changedMessages} 条记录中替换 ${totalReplaced} 处`;
            if (this.detailSearchQuery) {
                this.searchInDetail();
            }
        },

        openImmersive(item) {
            if (!item || !item.id) return;
            this.openChatDetail(item);
        },
    };
}
