(function () {
  "use strict";
  var R = window.__qpRuntime;
  if (!R || window.__QP_MODE !== "edit" || window.__qpEditor) return;
  window.__qpEditor = true;

  var hovered = null;
  var selected = null;
  var scrollTimer = null;

  var style = document.createElement("style");
  style.textContent =
    "[data-qp-hover]{outline:2px dashed #0b7ff5!important;outline-offset:-2px;cursor:pointer!important}" +
    "[data-qp-selected]{outline:2px solid #0052cc!important;outline-offset:-2px;" +
    "box-shadow:0 0 0 4px rgba(0,82,204,.18)!important}";
  document.head.appendChild(style);

  function post(message) {
    try {
      parent.postMessage(message, "*");
    } catch (e) {
      /* 부모가 없으면 무시 */
    }
  }

  function label(el) {
    var cls = typeof el.className === "string" ? el.className.trim().split(/\s+/)[0] : "";
    return el.tagName.toLowerCase() + (cls ? "." + cls : "");
  }

  function info(el) {
    var cs = window.getComputedStyle(el);
    var rect = el.getBoundingClientRect();
    var ancestors = [];
    var node = el.parentElement;
    while (node && ancestors.length < 5) {
      ancestors.push({ path: R.pathOf(node), label: label(node) });
      if (node === document.body) break;
      node = node.parentElement;
    }
    var href = el.getAttribute("data-qp-href") || el.getAttribute("href") || "";
    return {
      path: R.pathOf(el),
      ref: R.refOf(el),
      tag: el.tagName.toLowerCase(),
      label: label(el),
      isBody: el === document.body,
      textNodes: R.textNodes(el).map(function (node) {
        return node.nodeValue.replace(/^\s+|\s+$/g, "");
      }),
      href: href,
      target: el.getAttribute("data-qp-target") || el.getAttribute("target") || "",
      isImg: el.tagName === "IMG",
      styles: {
        color: cs.color,
        backgroundColor: cs.backgroundColor,
        fontSize: cs.fontSize,
        fontWeight: cs.fontWeight,
        textAlign: cs.textAlign,
        borderRadius: cs.borderRadius,
        padding: cs.padding,
        margin: cs.margin,
        opacity: cs.opacity,
      },
      rect: { x: rect.left, y: rect.top, w: rect.width, h: rect.height },
      ancestors: ancestors,
      canUp: !!el.previousElementSibling && el !== document.body,
      canDown: !!el.nextElementSibling && el !== document.body,
      canDelete: el !== document.body,
    };
  }

  function clearHover() {
    if (hovered) hovered.removeAttribute("data-qp-hover");
    hovered = null;
  }

  function select(el) {
    if (!el || el.nodeType !== 1) return;
    if (el === document.documentElement) el = document.body;
    if (selected) selected.removeAttribute("data-qp-selected");
    selected = el;
    clearHover();
    el.setAttribute("data-qp-selected", "1");
    post({ qp: "select", info: info(el) });
  }

  function previewOn() {
    return !!window.__qpPreview;
  }

  document.addEventListener("mouseover", function (event) {
    if (previewOn()) return;
    var el = event.target;
    if (!el || el === document.body || el === document.documentElement || el === selected) return clearHover();
    if (hovered !== el) {
      clearHover();
      hovered = el;
      el.setAttribute("data-qp-hover", "1");
    }
  });
  document.addEventListener("mouseout", function (event) {
    if (event.target === hovered) clearHover();
  });

  document.addEventListener(
    "click",
    function (event) {
      if (previewOn()) return;
      event.preventDefault();
      event.stopPropagation();
      select(event.target);
    },
    true
  );
  ["submit", "dblclick"].forEach(function (type) {
    document.addEventListener(
      type,
      function (event) {
        if (!previewOn()) event.preventDefault();
      },
      true
    );
  });

  document.addEventListener("keydown", function (event) {
    var mod = event.ctrlKey || event.metaKey;
    var key = event.key;
    var handled = (mod && (key === "z" || key === "y" || key === "s" || key === "Z")) || key === "Delete" || key === "Escape";
    if (!handled) return;
    event.preventDefault();
    post({ qp: "key", key: key, ctrl: mod, shift: event.shiftKey });
  });

  window.addEventListener("scroll", function () {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(function () {
      post({ qp: "scroll", y: window.scrollY });
    }, 120);
  });

  window.addEventListener("message", function (event) {
    if (event.source !== window.parent) return;
    var data = event.data;
    if (!data || typeof data !== "object") return;
    switch (data.qp) {
      case "op": {
        var result = R.apply(data.patch, true);
        post({ qp: "result", ok: !!result, id: data.id });
        if (result) select(result);
        break;
      }
      case "selectPath": {
        var el = null;
        try {
          el = data.path === "body" ? document.body : document.querySelector(data.path);
        } catch (e) {
          el = null;
        }
        if (el) select(el);
        break;
      }
      case "selectParent":
        if (selected && selected.parentElement) select(selected.parentElement);
        break;
      case "preview":
        window.__qpPreview = !!data.on;
        clearHover();
        if (selected) {
          if (data.on) selected.removeAttribute("data-qp-selected");
          else selected.setAttribute("data-qp-selected", "1");
        }
        break;
      case "restoreScroll":
        window.scrollTo(0, data.y || 0);
        break;
      default:
        break;
    }
  });

  window.addEventListener("qp:applied", function (event) {
    post({ qp: "ready", failed: event.detail.failed });
  });
})();
