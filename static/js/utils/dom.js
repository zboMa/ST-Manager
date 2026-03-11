/**
 * static/js/utils/dom.js
 * DOM 操作与渲染工具
 */

const htmlComponentRenderCache = new WeakMap();
let renderRuntimeModule = null;
let renderRuntimeModulePromise = null;
let messageSegmentRendererModule = null;
let messageSegmentRendererModulePromise = null;

function loadRenderRuntimeModule() {
    if (renderRuntimeModule) {
        return Promise.resolve(renderRuntimeModule);
    }

    if (!renderRuntimeModulePromise) {
        renderRuntimeModulePromise = import('../runtime/renderRuntime.js')
            .then((module) => {
                renderRuntimeModule = module;
                return module;
            })
            .catch((error) => {
                renderRuntimeModulePromise = null;
                console.warn('Failed to load render runtime module:', error);
                throw error;
            });
    }

    return renderRuntimeModulePromise;
}

function loadMessageSegmentRendererModule() {
    if (messageSegmentRendererModule) {
        return Promise.resolve(messageSegmentRendererModule);
    }

    if (!messageSegmentRendererModulePromise) {
        messageSegmentRendererModulePromise = import('../runtime/messageSegmentRenderer.js')
            .then((module) => {
                messageSegmentRendererModule = module;
                return module;
            })
            .catch((error) => {
                messageSegmentRendererModulePromise = null;
                console.warn('Failed to load message segment renderer module:', error);
                throw error;
            });
    }

    return messageSegmentRendererModulePromise;
}

function scorePreviewAppHtml(htmlPayload) {
    const source = String(htmlPayload || '');
    if (!source.trim()) {
        return 0;
    }

    let score = 0;
    if (/<!DOCTYPE html/i.test(source) || /<html[\s>]/i.test(source)) score += 2;
    if (/id=["']readingContent["']/i.test(source)) score += 8;
    if (/function\s+processTextContent\s*\(/i.test(source)) score += 8;
    if (/window\.setTheme\s*=\s*applyTheme/i.test(source)) score += 5;
    if (/showArgMenu\s*\(/i.test(source)) score += 4;
    if (/triggerSlash\s*\(/i.test(source)) score += 4;
    if (/class=["'][^"']*dialogue-container/i.test(source) || /createDialogueElement\s*\(/i.test(source)) score += 4;

    if (/sakura-collapsible/i.test(source)) score -= 8;
    if (/Sakura\s*-\s*折叠栏/i.test(source)) score -= 10;
    if (/id=["']raw-markdown["']/i.test(source)) score -= 6;

    return score;
}

function classifyPreviewFrontendText(text, options = {}) {
    const source = String(text || '').trim();
    if (!source) {
        return null;
    }

    const normalized = source
        .replace(/^```(?:html|text|xml)?\s*/i, '')
        .replace(/```$/i, '')
        .trim();
    const score = scorePreviewAppHtml(normalized);
    if (score < Number(options.appThreshold || 8)) {
        return null;
    }

    return {
        type: 'app-stage',
        minHeight: Number(options.minHeight || 260),
        maxHeight: Number(options.maxHeight || 3200),
    };
}

function buildMixedPreviewParts(content, options = {}) {
    const rawContent = String(content || '');
    const trimmedContent = rawContent.trim();
    if (!trimmedContent) {
        return [];
    }

    const htmlFragmentRegex = /^\s*<(?:div|style|details|section|article|main|link|table|script|iframe|svg|html|body|head|canvas)/i;
    const codeBlockRegex = /```(?:html|xml|text|js|css|json)?\s*([\s\S]*?)```/gi;
    const looksLikeHtmlPayload = (text) => {
        const block = String(text || '');
        return block.includes('<!DOCTYPE')
            || block.includes('<html')
            || block.includes('<script')
            || block.includes('export default')
            || (block.includes('<div') && block.includes('<style'));
    };

    let htmlPayload = '';
    let markdownCommentary = '';
    let match;
    let foundPayload = false;

    while ((match = codeBlockRegex.exec(rawContent)) !== null) {
        const blockContent = String(match[1] || '');
        if (!looksLikeHtmlPayload(blockContent)) {
            continue;
        }

        htmlPayload = blockContent;
        markdownCommentary = rawContent.replace(match[0], '');
        foundPayload = true;
        break;
    }

    if (!foundPayload) {
        if (htmlFragmentRegex.test(trimmedContent)
            || rawContent.includes('<!DOCTYPE')
            || rawContent.includes('<html')
            || rawContent.includes('<script')) {
            htmlPayload = rawContent;
            markdownCommentary = '';
        } else {
            markdownCommentary = rawContent;
        }
    }

    const cleanedCommentary = markdownCommentary.replace(/<open>|<\/open>/gi, '').trim();
    const cleanedPayload = htmlPayload.replace(/<open>|<\/open>/gi, '').trim();

    const parts = [];
    if (cleanedCommentary) {
        parts.push({
            type: 'markdown',
            text: cleanedCommentary,
        });
    }

    if (cleanedPayload) {
        parts.push({
            type: 'app-stage',
            text: cleanedPayload,
            minHeight: Number(options.minHeight || 260),
            maxHeight: Number(options.maxHeight || 3200),
        });
    }

    if (!parts.length) {
        parts.push({
            type: 'markdown',
            text: trimmedContent,
        });
    }

    return parts;
}

function destroyMixedPreviewHost(el) {
    if (!el) return;

    if (messageSegmentRendererModule?.destroyMessageSegmentHost) {
        if (el.__stmMixedPreviewHost) {
            messageSegmentRendererModule.destroyMessageSegmentHost(el.__stmMixedPreviewHost);
        }
        messageSegmentRendererModule.destroyMessageSegmentHost(el);
    }

    if (el.__stmMixedPreviewHost instanceof HTMLElement) {
        el.__stmMixedPreviewHost.innerHTML = '';
    }
    el.__stmMixedPreviewHost = null;
}

export function clearInlineIsolatedHtml(el, options = {}) {
    if (!el || !renderRuntimeModule?.clearIsolatedHtml) {
        return;
    }
    renderRuntimeModule.clearIsolatedHtml(el, options);
}

function buildHtmlComponentSignature(content, options = {}) {
    return JSON.stringify({
        content: String(content || ''),
        minHeight: Number.parseInt(options.minHeight, 10) || 0,
        maxHeight: Number.parseInt(options.maxHeight, 10) || 0,
        mode: String(options.mode || 'html-component'),
        assetBase: String(options.assetBase || ''),
    });
}

export function updateCssVariable(name, value) {
    document.documentElement.style.setProperty(name, value);
}

export function applyFont(type) {
    let fontVal = 'ui-sans-serif, system-ui, sans-serif';
    if (type === 'serif') fontVal = 'ui-serif, Georgia, Cambria, "Times New Roman", Times, serif';
    if (type === 'mono') fontVal = 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace';
    updateCssVariable('--app-font-family', fontVal);
}

export function insertAtCursor(textarea, myValue) {
    if (textarea.selectionStart || textarea.selectionStart == '0') {
        var startPos = textarea.selectionStart;
        var endPos = textarea.selectionEnd;
        return textarea.value.substring(0, startPos)
            + myValue
            + textarea.value.substring(endPos, textarea.value.length);
    } else {
        return textarea.value + myValue;
    }
}


function escapeHtml(text) {
    return String(text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

export function renderMarkdown(text) {
    if (!text) return '<span class="text-gray-500 italic">空内容</span>';
    let safeText = String(text);
    if (typeof marked !== 'undefined') {
        marked.setOptions({ breaks: true });
        try {
            return marked.parse(safeText);
        } catch (e) {
            console.error("Markdown parse error:", e);
            return safeText;
        }
    }
    return safeText;
}

export function updateInlineRenderContent(el, content, options = {}) {
    if (!el) return;

    const rawContent = String(content || '');
    const trimmed = rawContent.trim();
    const mode = options.mode || 'markdown';
    const isolated = Boolean(options.isolated);
    const emptyHtml = options.emptyHtml || '<span class="text-gray-500 italic">空内容</span>';

    if (!trimmed) {
        htmlComponentRenderCache.delete(el);
        clearInlineIsolatedHtml(el);
        if (el.shadowRoot) {
            el.shadowRoot.innerHTML = `<div>${emptyHtml}</div>`;
        } else {
            el.innerHTML = emptyHtml;
        }
        return;
    }

    if (mode === 'html-component') {
        const signature = buildHtmlComponentSignature(rawContent, options);
        if (htmlComponentRenderCache.get(el) === signature) {
            return;
        }
        htmlComponentRenderCache.set(el, signature);
        if (!el.shadowRoot) {
            el.attachShadow({ mode: 'open' });
        }
        updateShadowContent(el, rawContent, options);
        return;
    }

    htmlComponentRenderCache.delete(el);
    clearInlineIsolatedHtml(el);

    const rendered = mode === 'markdown'
        ? renderMarkdown(rawContent)
        : `<div>${escapeHtml(rawContent).replace(/\n/g, '<br>')}</div>`;

    if (isolated && !el.shadowRoot) {
        el.attachShadow({ mode: 'open' });
    }

    if (el.shadowRoot) {
        el.shadowRoot.innerHTML = `
            <style>
                :host {
                    display: block;
                    color: inherit;
                }
                .inline-render {
                    display: block;
                    color: inherit;
                    min-width: 0;
                    overflow-wrap: anywhere;
                    word-break: break-word;
                }
                .inline-render img {
                    max-width: 100%;
                    height: auto;
                }
                .inline-render pre {
                    white-space: pre-wrap;
                    word-break: break-word;
                }
            </style>
            <div class="inline-render markdown-body">${rendered}</div>
        `;
        return;
    }

    el.innerHTML = rendered;
}

export function updateShadowContent(el, content, options = {}) {
    destroyMixedPreviewHost(el);

    const shadowRenderToken = Number(el.__stmShadowRenderToken || 0) + 1;
    el.__stmShadowRenderToken = shadowRenderToken;

    if (!el.shadowRoot) {
        el.attachShadow({ mode: 'open' });
    }

    const shadow = el.shadowRoot;
    const minHeight = Number.parseInt(options.minHeight, 10);
    const hostMinHeight = Number.isFinite(minHeight) ? `${Math.max(0, minHeight)}px` : '0px';
    const maxHeight = Number.parseInt(options.maxHeight, 10);
    const hostMaxHeight = Number.isFinite(maxHeight) ? `${Math.max(0, maxHeight)}px` : 'none';
    const scrollMode = Boolean(options.scroll);
    const hostOverflow = scrollMode ? 'hidden' : 'visible';
    const wrapperOverflow = scrollMode ? 'auto' : 'visible';
    const hostHeight = scrollMode ? '100%' : 'auto';
    const wrapperHeight = scrollMode ? '100%' : 'auto';

    if (content === null || content === undefined) {
        htmlComponentRenderCache.delete(el);
        clearInlineIsolatedHtml(el);
        shadow.innerHTML = '';
        return;
    }

    let rawContent = content || "";
    const trimmedContent = rawContent.trim();

    const htmlFragmentRegex = /^\s*<(?:div|style|details|section|article|main|link|table|script|iframe|svg|html|body|head|canvas)/i;
    let forceHtmlMode = false;

    if (htmlFragmentRegex.test(trimmedContent)) {
        forceHtmlMode = true;
    }

    let htmlPayload = "";
    let markdownCommentary = "";

    const codeBlockRegex = /```(?:html|xml|text|js|css|json)?\s*([\s\S]*?)```/gi;
    let match;
    let foundPayload = false;

    while ((match = codeBlockRegex.exec(rawContent)) !== null) {
        const blockContent = match[1];
        if (blockContent.includes('<!DOCTYPE') ||
            blockContent.includes('<html') ||
            blockContent.includes('<script') ||
            blockContent.includes('export default') ||
            (blockContent.includes('<div') && blockContent.includes('<style'))) {

            htmlPayload = blockContent;
            markdownCommentary = rawContent.replace(match[0], "");
            foundPayload = true;
            break;
        }
    }

    if (!foundPayload) {
        if (forceHtmlMode || rawContent.includes('<!DOCTYPE') || rawContent.includes('<html') || rawContent.includes('<script')) {
            htmlPayload = rawContent;
            markdownCommentary = "";
        } else {
            markdownCommentary = rawContent;
        }
    }

    markdownCommentary = markdownCommentary.replace(/<open>|<\/open>/gi, "").trim();

    const hasPayload = !!htmlPayload;

    if (hasPayload) {
        let renderedMd = "";
        if (markdownCommentary) {
            const looksLikeTrustedHtml = /^\s*<(?:[a-z][\w:-]*|!doctype|!--)/i.test(markdownCommentary);
            if (looksLikeTrustedHtml) {
                renderedMd = markdownCommentary;
            } else if (typeof marked !== 'undefined') {
                renderedMd = marked.parse(markdownCommentary, { breaks: true });
            } else {
                renderedMd = `<p>${markdownCommentary.replace(/\n/g, "<br>")}</p>`;
            }
        }
        loadRenderRuntimeModule()
            .then((module) => {
                if (el.__stmShadowRenderToken !== shadowRenderToken || !el.isConnected) {
                    return;
                }
                module.renderIsolatedHtml(el, {
                    htmlPayload,
                    noteHtml: renderedMd,
                    minHeight: Number.parseInt(options.minHeight, 10),
                    maxHeight: Number.parseInt(options.maxHeight, 10),
                    assetBase: options.assetBase || '',
                });
            })
            .catch(() => {
                if (el.__stmShadowRenderToken !== shadowRenderToken || !el.isConnected) {
                    return;
                }
                shadow.innerHTML = `<div class="scroll-wrapper markdown-body">运行时模块加载失败，无法渲染 HTML 预览。</div>`;
            });
        return;
    }

    clearInlineIsolatedHtml(el);

    const style = `
                <style>
                    :host {
                        display: block;
                        min-height: ${hostMinHeight};
                        max-height: ${hostMaxHeight};
                        width: 100%;
                        height: ${hostHeight};
                        overflow: ${hostOverflow};
                        background-color: transparent;
                        color: var(--text-main, #e5e7eb);
                        font-family: ui-sans-serif, system-ui, sans-serif;
                        font-size: 0.9rem;
                        line-height: 1.6;
                    }
                    .scroll-wrapper {
                        min-height: ${hostMinHeight};
                        max-height: ${hostMaxHeight};
                        width: 100%;
                        height: ${wrapperHeight};
                        overflow: ${wrapperOverflow};
                        padding: 1rem;
                        box-sizing: border-box;
                    }
                    img { max-width: 100%; border-radius: 4px; }
                    a { color: var(--accent-main, #2563eb); }
                    blockquote { border-left: 4px solid var(--accent-main, #2563eb); padding-left: 1em; margin: 1em 0; opacity: 0.8; }
                    /* 代码块样式修复 */
                    pre { background: rgba(0,0,0,0.3); padding: 1em; border-radius: 6px; overflow-x: auto; }
                    code { font-family: monospace; }
                </style>
            `;

    const looksLikeTrustedHtml = /^\s*<(?:[a-z][\w:-]*|!doctype|!--)/i.test(rawContent);

    let renderedHtml = rawContent;
    if (looksLikeTrustedHtml) {
        renderedHtml = rawContent;
    } else if (typeof marked !== 'undefined') {
        renderedHtml = marked.parse(rawContent || "", { breaks: true });
    } else {
        renderedHtml = (rawContent || "").replace(/\n/g, "<br>");
    }

    const htmlWrapper = renderedHtml || '<div style="color: gray; font-style: italic;">空内容</div>';
    shadow.innerHTML = style + `<div class="scroll-wrapper markdown-body">${htmlWrapper}</div>`;
}

export function updateMixedPreviewContent(el, content, options = {}) {
    if (!el) return;

    const renderVersion = Number(el.__stmMixedPreviewVersion || 0) + 1;
    el.__stmMixedPreviewVersion = renderVersion;
    const scrollMode = Boolean(options.scroll);

    destroyMixedPreviewHost(el);

    if (!el.shadowRoot) {
        el.attachShadow({ mode: 'open' });
    }

    const minHeight = Number.parseInt(options.minHeight, 10);
    const maxHeight = Number.parseInt(options.maxHeight, 10);
    const hostMinHeight = Number.isFinite(minHeight) ? `${Math.max(0, minHeight)}px` : '0px';
    const hostMaxHeight = Number.isFinite(maxHeight) ? `${Math.max(0, maxHeight)}px` : 'none';
    const shadow = el.shadowRoot;

    shadow.innerHTML = `
        <style>
            :host {
                display: block;
                min-height: ${hostMinHeight};
                max-height: ${hostMaxHeight};
                width: 100%;
                height: ${scrollMode ? '100%' : 'auto'};
                overflow: ${scrollMode ? 'hidden' : 'visible'};
                background-color: transparent;
                color: var(--text-main, #e5e7eb);
                font-family: ui-sans-serif, system-ui, sans-serif;
                font-size: 0.9rem;
                line-height: 1.6;
            }
            .mixed-preview-scroll {
                min-height: ${hostMinHeight};
                max-height: ${hostMaxHeight};
                width: 100%;
                height: ${scrollMode ? '100%' : 'auto'};
                overflow: ${scrollMode ? 'auto' : 'visible'};
                box-sizing: border-box;
                padding: 1rem;
                scrollbar-gutter: stable both-edges;
                scrollbar-width: thin;
                scrollbar-color: color-mix(in srgb, var(--accent-main, #3b82f6) 48%, var(--border-light, #475569)) transparent;
            }
            .mixed-preview-host {
                width: 100%;
                min-width: 0;
                overflow-wrap: anywhere;
                word-break: break-word;
            }
            .mixed-preview-host .chat-message-render-chunk {
                display: block;
                width: 100%;
                min-width: 0;
                margin: 0;
                overflow-wrap: anywhere;
                word-break: break-word;
            }
            .mixed-preview-host .chat-message-render-chunk + .chat-message-render-chunk,
            .mixed-preview-host .chat-message-render-chunk + .chat-message-pre-anchor,
            .mixed-preview-host .chat-message-pre-anchor + .chat-message-render-chunk,
            .mixed-preview-host .chat-message-pre-anchor + .chat-message-pre-anchor {
                margin-top: 0.9rem;
            }
            .mixed-preview-host .chat-message-pre-anchor {
                display: block;
                width: 100%;
                min-width: 0;
                max-width: 100%;
                overflow: hidden;
                overflow-wrap: anywhere;
                word-break: break-word;
            }
            .mixed-preview-host .chat-reader-app-stage-shell,
            .mixed-preview-host .chat-reader-app-stage-frame,
            .mixed-preview-host .stm-render-shell,
            .mixed-preview-host .stm-render-frame {
                min-height: 0 !important;
                width: 100% !important;
                max-width: 100% !important;
            }
            .mixed-preview-host .chat-reader-app-stage-shell,
            .mixed-preview-host .stm-render-shell {
                overflow: hidden !important;
            }
            .mixed-preview-host img {
                max-width: 100%;
                height: auto;
            }
            .mixed-preview-host pre {
                background: rgba(0,0,0,0.3);
                padding: 1em;
                border-radius: 6px;
                overflow-x: auto;
                white-space: pre-wrap;
                overflow-wrap: anywhere;
                word-break: break-word;
            }
            .mixed-preview-host code {
                font-family: monospace;
                white-space: inherit;
                overflow-wrap: anywhere;
                word-break: break-word;
            }
            .mixed-preview-scroll::-webkit-scrollbar,
            .mixed-preview-host pre::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }
            .mixed-preview-scroll::-webkit-scrollbar-track,
            .mixed-preview-host pre::-webkit-scrollbar-track {
                background: transparent;
            }
            .mixed-preview-scroll::-webkit-scrollbar-thumb,
            .mixed-preview-host pre::-webkit-scrollbar-thumb {
                border-radius: 999px;
                background: color-mix(in srgb, var(--accent-main, #3b82f6) 42%, var(--border-light, #475569));
                border: 2px solid transparent;
                background-clip: padding-box;
            }
            .mixed-preview-scroll::-webkit-scrollbar-thumb:hover,
            .mixed-preview-host pre::-webkit-scrollbar-thumb:hover {
                background: color-mix(in srgb, var(--accent-main, #3b82f6) 62%, var(--border-light, #475569));
                border: 2px solid transparent;
                background-clip: padding-box;
            }
        </style>
        <div class="mixed-preview-scroll markdown-body">
            <div class="mixed-preview-host"></div>
        </div>
    `;

    const host = shadow.querySelector('.mixed-preview-host');
    if (!(host instanceof HTMLElement)) {
        return;
    }

    el.__stmMixedPreviewHost = host;

    const source = String(content || '');
    if (!source.trim()) {
        const emptyHtml = options.emptyHtml || '<span class="text-gray-500 italic">空内容</span>';
        host.innerHTML = emptyHtml;
        return;
    }

    const parts = buildMixedPreviewParts(source, options);

    loadMessageSegmentRendererModule()
        .then((module) => {
            if (el.__stmMixedPreviewVersion !== renderVersion || !el.isConnected) {
                return;
            }

            module.mountMessageSegmentHost(host, {
                source,
                parts,
                classifyFrontendText: (text) => classifyPreviewFrontendText(text, options),
                assetBase: options.assetBase || '',
                runtimeOwner: options.runtimeOwner || 'preview',
                runtimeLabel: options.runtimeLabel || 'Preview Segment',
            });
        })
        .catch(() => {
            if (el.__stmMixedPreviewVersion !== renderVersion || !el.isConnected) {
                return;
            }
            host.innerHTML = renderMarkdown(parts
                .filter(part => part.type === 'markdown')
                .map(part => String(part.text || ''))
                .join('\n\n') || source);
        });
}
