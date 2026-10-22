"""Turnstile DOM 检测脚本模板。"""

from __future__ import annotations


def build_detect_script(
    container_selectors: list[str] | tuple[str, ...],
    token_selector: str,
) -> str:
    """按选择器列表构造页面 evaluate 脚本。"""
    # ZeroAPI 等站点用 .turnstile-container; iframe 可能 0x0, 必须回退容器 rect.
    return """() => {
        const selectors = %s;
        const tokenSelector = %s;
        const rectOf = (el) => {
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {
                x: Math.round(r.left),
                y: Math.round(r.top),
                width: Math.round(r.width),
                height: Math.round(r.height),
                right: Math.round(r.right),
                bottom: Math.round(r.bottom),
            };
        };
        const usable = (r) => Boolean(r && r.width >= 10 && r.height >= 10);
        const inViewport = (r) => {
            if (!r || r.width < 1 || r.height < 1) return false;
            const vw = window.innerWidth || 0;
            const vh = window.innerHeight || 0;
            return r.right > 0 && r.bottom > 0 && r.x < vw && r.y < vh;
        };
        const isVisible = (r) => usable(r) && inViewport(r);
        const isCf = (src) => {
            const s = String(src || "").toLowerCase();
            return (
                s.includes("challenges.cloudflare.com")
                || s.includes("turnstile")
                || s.includes("cdn-cgi/challenge")
            );
        };

        // 遍历 document + open shadowRoot, 收集全部节点.
        const walk = (root, out) => {
            if (!root || !root.querySelectorAll) return;
            for (const el of root.querySelectorAll("*")) {
                out.push(el);
                if (el.shadowRoot) walk(el.shadowRoot, out);
            }
        };
        const all = [];
        walk(document, all);

        const containers = [];
        const seen = new Set();
        const pushContainer = (el) => {
            if (!el || seen.has(el)) return;
            seen.add(el);
            containers.push(el);
        };
        for (const selector of selectors) {
            for (const el of document.querySelectorAll(selector)) pushContainer(el);
        }
        // shadow 内可能只有 class/id 特征, 再补一轮.
        for (const el of all) {
            if (seen.has(el)) continue;
            const cls = String(el.className || "");
            const id = String(el.id || "");
            if (
                cls.includes("turnstile")
                || cls.includes("cf-turnstile")
                || id.includes("turnstile")
                || (el.getAttribute && el.getAttribute("data-sitekey"))
            ) {
                pushContainer(el);
            }
        }

        const frames = [];
        const pushFrame = (frame) => {
            const src = frame.getAttribute("src") || frame.src || "";
            const rect = rectOf(frame);
            frames.push({
                rect,
                cf: isCf(src),
                visible: isVisible(rect),
                el: frame,
            });
        };
        for (const frame of document.querySelectorAll("iframe")) pushFrame(frame);
        for (const el of all) {
            if (el.tagName === "IFRAME") pushFrame(el);
        }

        // 优先: 可见 CF iframe > 尺寸像 widget 的 iframe > 可见容器.
        // 关键: 容器内 iframe 尺寸不可用时, 必须回退容器自身 rect.
        let rect = null;
        let target_kind = "none";

        for (const info of frames) {
            if (info.cf && info.visible && usable(info.rect)) {
                rect = info.rect;
                target_kind = "cf_iframe";
                break;
            }
        }
        if (!rect) {
            for (const info of frames) {
                if (
                    info.visible
                    && info.rect
                    && info.rect.width >= 100
                    && info.rect.height >= 40
                    && info.rect.height <= 120
                ) {
                    rect = info.rect;
                    target_kind = "sized_iframe";
                    break;
                }
            }
        }
        if (!rect) {
            for (const container of containers) {
                const containerRect = rectOf(container);
                if (!usable(containerRect) || !inViewport(containerRect)) continue;
                const inner = container.querySelector && container.querySelector("iframe");
                if (inner) {
                    const innerRect = rectOf(inner);
                    // 仅当 iframe 几何可用时才优先它; 0x0 时回退容器.
                    if (usable(innerRect)) {
                        rect = innerRect;
                        target_kind = "container_iframe";
                        break;
                    }
                }
                rect = containerRect;
                target_kind = "container";
                break;
            }
        }

        let token = "";
        const tokenEl = document.querySelector(tokenSelector);
        if (tokenEl && tokenEl.value) token = String(tokenEl.value);

        return {
            present: Boolean(
                containers.length
                || frames.some((item) => item.cf)
                || window.turnstile
                || token
            ),
            visible: Boolean(rect && isVisible(rect)),
            rect,
            target_kind,
            source: "dom",
            token,
            container_count: containers.length,
            iframe_count: frames.length,
        };
    }""" % (
        repr(list(container_selectors)),
        repr(token_selector),
    )
