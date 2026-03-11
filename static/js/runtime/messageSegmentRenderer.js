import { renderMarkdown } from '../utils/dom.js';
import { clearIsolatedHtml, renderIsolatedHtml } from './renderRuntime.js';
import { ChatAppStage } from './chatAppStage.js';

const registry = new Map();
let cleanupObserverAttached = false;

function cleanupDisconnectedHosts() {
    for (const [host, state] of registry.entries()) {
        if (!host.isConnected) {
            destroyAnchors(state);
            registry.delete(host);
        }
    }
}

function ensureCleanupObserver() {
    if (cleanupObserverAttached) {
        return;
    }

    cleanupObserverAttached = true;
    const observer = new MutationObserver(() => {
        cleanupDisconnectedHosts();
    });
    observer.observe(document.body, { childList: true, subtree: true });
}

function mountAnchorContent(anchor, classification, text, options = {}) {
    anchor.dataset.runtimeOwner = String(options.runtimeOwner || '');
    anchor.dataset.runtimeLabel = String(options.runtimeLabel || 'Chat Segment');

    if (classification.type === 'app-stage') {
        const stage = new ChatAppStage({
            onTriggerSlash: options.onTriggerSlash,
            onToast: options.onToast,
            onAppError: options.onAppError,
            minHeight: Number(classification.minHeight || 0),
            maxHeight: Number(classification.maxHeight || 0),
        });
        stage.attachHost(anchor);
        stage.update({
            htmlPayload: text,
            assetBase: options.assetBase || '',
            context: options.appContext || {},
        });
        return { anchor, stage };
    }

    renderIsolatedHtml(anchor, {
        htmlPayload: text,
        minHeight: Number(classification.minHeight || 28),
        maxHeight: Number(classification.maxHeight || 520),
        assetBase: options.assetBase || '',
    });
    return { anchor };
}

function destroyAnchors(state) {
    (state?.anchors || []).forEach(anchorState => {
        if (anchorState.stage) {
            anchorState.stage.destroy();
        }
        if (anchorState.anchor) {
            clearIsolatedHtml(anchorState.anchor, { clearShadow: true });
            anchorState.anchor.innerHTML = '';
        }
    });
}

function getFrontendTextFromElement(element) {
    if (!(element instanceof HTMLElement)) {
        return '';
    }

    if (element.matches('pre')) {
        return element.querySelector('code')?.textContent || element.textContent || '';
    }

    return element.textContent || '';
}

function isFrontendAnchorElement(element, classify) {
    if (!(element instanceof HTMLElement) || element.classList.contains('chat-message-pre-anchor')) {
        return false;
    }

    if (!element.matches('pre, div.TH-render')) {
        return false;
    }

    return Boolean(classify(getFrontendTextFromElement(element)));
}

function containsFrontendAnchorElement(element, classify) {
    if (!(element instanceof HTMLElement)) {
        return false;
    }

    if (isFrontendAnchorElement(element, classify)) {
        return true;
    }

    return Array.from(element.querySelectorAll('pre, div.TH-render')).some((child) => isFrontendAnchorElement(child, classify));
}

function chunkTopLevelNodes(container, classify) {
    const chunks = [];
    let normalNodes = [];

    const flushNormal = () => {
        if (normalNodes.length === 0) return;
        chunks.push({ type: 'normal', nodes: normalNodes });
        normalNodes = [];
    };

    Array.from(container.childNodes).forEach((node) => {
        if (node instanceof HTMLElement && isFrontendAnchorElement(node, classify)) {
            flushNormal();
            chunks.push({ type: 'iframe', element: node, text: getFrontendTextFromElement(node) });
            return;
        }

        if (node instanceof HTMLElement && containsFrontendAnchorElement(node, classify)) {
            flushNormal();
            chunks.push({ type: 'nested_iframe', element: node });
            return;
        }

        normalNodes.push(node);
    });

    flushNormal();
    return chunks;
}

function scanNestedFrontendAnchors(container, classify, options, anchors, labelPrefix = '') {
    container.querySelectorAll('pre, div.TH-render').forEach((preLike) => {
        if (!(preLike instanceof HTMLElement) || !isFrontendAnchorElement(preLike, classify)) {
            return;
        }

        const text = getFrontendTextFromElement(preLike);
        const classification = classify(text);
        if (!classification) return;

        const anchor = document.createElement('div');
        anchor.className = 'chat-message-pre-anchor';
        preLike.replaceWith(anchor);
        anchors.push(mountAnchorContent(anchor, classification, text, {
            ...options,
            runtimeOwner: `${options.runtimeOwner || 'chat'}:${labelPrefix}${anchors.length}`,
            runtimeLabel: `${options.runtimeLabel || 'Chat Segment'} ${labelPrefix}${anchors.length + 1}`,
        }));
    });
}

function mountMarkdownSource(host, source, classify, options, anchors) {
    const temp = document.createElement('div');
    temp.innerHTML = renderMarkdown(source);

    chunkTopLevelNodes(temp, classify).forEach((chunk, index) => {
        if (chunk.type === 'normal') {
            const wrapper = document.createElement('div');
            wrapper.className = 'chat-message-render-chunk';
            chunk.nodes.forEach((node) => wrapper.appendChild(node));
            host.appendChild(wrapper);
            return;
        }

        const anchor = document.createElement('div');
        anchor.className = 'chat-message-pre-anchor';
        host.appendChild(anchor);

        if (chunk.type === 'iframe') {
            const classification = classify(chunk.text);
            if (!classification) {
                return;
            }
            anchors.push(mountAnchorContent(anchor, classification, chunk.text, {
                ...options,
                runtimeOwner: `${options.runtimeOwner || 'chat'}:chunk:${index}`,
                runtimeLabel: `${options.runtimeLabel || 'Chat Segment'} chunk#${index + 1}`,
            }));
            return;
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'chat-message-render-chunk';
        wrapper.appendChild(chunk.element);
        anchor.replaceWith(wrapper);
        scanNestedFrontendAnchors(wrapper, classify, options, anchors, `nested:${index}:`);
    });
}

export function destroyMessageSegmentHost(host) {
    const state = registry.get(host);
    if (!state) return;
    destroyAnchors(state);
    host.innerHTML = '';
    registry.delete(host);
}

export function mountMessageSegmentHost(host, options = {}) {
    if (!host) return;
    ensureCleanupObserver();

    const signature = JSON.stringify({
        source: String(options.source || ''),
        assetBase: String(options.assetBase || ''),
        parts: Array.isArray(options.parts) ? options.parts.map(part => ({
            type: part.type,
            text: part.text,
            minHeight: part.minHeight || 0,
            maxHeight: part.maxHeight || 0,
        })) : [],
    });

    const current = registry.get(host);
    if (current?.signature === signature) {
        return;
    }

    if (current) {
        destroyAnchors(current);
    }

    const classify = typeof options.classifyFrontendText === 'function'
        ? options.classifyFrontendText
        : () => null;

    const parts = Array.isArray(options.parts) ? options.parts : [];
    if (parts.length > 0) {
        host.innerHTML = '';
        const anchors = [];

        parts.forEach((part) => {
            if (part.type === 'markdown') {
                mountMarkdownSource(host, String(part.text || ''), classify, options, anchors);
                return;
            }

            const anchor = document.createElement('div');
            anchor.className = 'chat-message-pre-anchor';
            host.appendChild(anchor);
            anchors.push(mountAnchorContent(anchor, part, String(part.text || ''), {
                ...options,
                runtimeOwner: `${options.runtimeOwner || 'chat'}:${anchors.length}`,
                runtimeLabel: `${options.runtimeLabel || 'Chat Segment'} #${anchors.length + 1}`,
            }));
        });

        registry.set(host, { signature, anchors });
        return;
    }

    const source = String(options.source || '');
    const directClassification = classify(source);
    if (directClassification && !source.includes('```')) {
        host.innerHTML = '';
        const anchor = document.createElement('div');
        anchor.className = 'chat-message-pre-anchor';
        host.appendChild(anchor);
        registry.set(host, {
            signature,
            anchors: [mountAnchorContent(anchor, directClassification, source, {
                ...options,
                runtimeOwner: `${options.runtimeOwner || 'chat'}:0`,
                runtimeLabel: `${options.runtimeLabel || 'Chat Segment'} #1`,
            })],
        });
        return;
    }

    host.innerHTML = renderMarkdown(source);

    host.innerHTML = '';
    const anchors = [];
    mountMarkdownSource(host, source, classify, options, anchors);

    registry.set(host, { signature, anchors });
}
