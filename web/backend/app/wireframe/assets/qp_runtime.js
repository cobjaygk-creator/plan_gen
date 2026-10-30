(function () {
  "use strict";
  if (window.__qpRuntime) return;

  var MODE = window.__QP_MODE || "view";
  var inIframe = window.parent !== window;
  var STYLE_PROPS = {
    color: 1, backgroundColor: 1, fontSize: 1, fontWeight: 1, textAlign: 1,
    borderRadius: 1, padding: 1, margin: 1, opacity: 1, lineHeight: 1, letterSpacing: 1,
  };

  var patches = [];
  try {
    var dataEl = document.getElementById("qp-patches");
    patches = JSON.parse(dataEl ? dataEl.textContent : "[]");
  } catch (e) {
    patches = [];
  }

  var css = document.createElement("style");
  css.textContent =
    "[data-qp-img].ph > .ph-label,[data-qp-img] > .ph-label{display:none!important}" +
    "[data-qp-href]{cursor:pointer}";
  (document.head || document.documentElement).appendChild(css);

  function collapse(text) {
    return (text || "").replace(/\s+/g, " ").trim();
  }

  function refOf(el) {
    return collapse(el.textContent).slice(0, 40);
  }

  function tagOfPath(path) {
    var match = /([a-z][a-z0-9-]*):nth-child\(\d+\)$/.exec(path);
    return match ? match[1] : "body";
  }

  function pathOf(el) {
    var parts = [];
    var node = el;
    while (node && node !== document.body && node.nodeType === 1) {
      var index = 1;
      var sibling = node;
      while ((sibling = sibling.previousElementSibling)) index++;
      parts.unshift(node.tagName.toLowerCase() + ":nth-child(" + index + ")");
      node = node.parentElement;
    }
    if (node !== document.body) return null;
    return parts.length ? "body>" + parts.join(">") : "body";
  }

  function find(patch, live) {
    var el = null;
    try {
      el = patch.path === "body" ? document.body : document.querySelector(patch.path);
    } catch (e) {
      el = null;
    }
    if (live || !patch.ref) return el;
    if (el && refOf(el) === patch.ref) return el;
    var candidates = document.getElementsByTagName(tagOfPath(patch.path));
    for (var i = 0; i < candidates.length; i++) {
      if (refOf(candidates[i]) === patch.ref) return candidates[i];
    }
    return el && !refOf(el) ? el : null;
  }

  function textNodes(el) {
    var nodes = [];
    for (var i = 0; i < el.childNodes.length; i++) {
      var node = el.childNodes[i];
      if (node.nodeType === 3 && collapse(node.nodeValue) !== "") nodes.push(node);
    }
    return nodes;
  }

  function setLink(el, href, target) {
    if (!href) {
      el.removeAttribute("data-qp-href");
      el.removeAttribute("data-qp-target");
      if (el.tagName === "A") {
        el.removeAttribute("href");
        el.removeAttribute("target");
      }
      return;
    }
    var page = /^page:(.+)$/.exec(href);
    var real = page ? "./" + page[1] + ".html" : href;
    if (el.tagName === "A") {
      el.setAttribute("href", real);
      if (target) {
        el.setAttribute("target", target);
        el.setAttribute("rel", "noopener");
      } else {
        el.removeAttribute("target");
      }
    }
    el.setAttribute("data-qp-href", href);
    if (target) el.setAttribute("data-qp-target", target);
    else el.removeAttribute("data-qp-target");
  }

  function setImage(el, src) {
    if (el.tagName === "IMG") {
      if (src) el.setAttribute("src", src);
      return;
    }
    if (!src) {
      el.style.backgroundImage = "";
      el.style.backgroundSize = "";
      el.style.backgroundPosition = "";
      el.removeAttribute("data-qp-img");
      return;
    }
    el.style.backgroundImage = 'url("' + src + '")';
    el.style.backgroundSize = "cover";
    el.style.backgroundPosition = "center";
    el.setAttribute("data-qp-img", "1");
  }

  // 영상 주소를 <video> 또는 유튜브·비메오 임베드로 바꾼다
  function buildVideo(src) {
    var el;
    var yt = /^https:\/\/(?:www\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([\w-]{11})/.exec(src);
    var vm = /^https:\/\/(?:www\.)?vimeo\.com\/(\d+)/.exec(src);
    if (yt || vm) {
      el = document.createElement("iframe");
      el.src = yt ? "https://www.youtube.com/embed/" + yt[1] : "https://player.vimeo.com/video/" + vm[1];
      el.setAttribute("allowfullscreen", "");
      el.setAttribute("allow", "autoplay; encrypted-media; picture-in-picture; fullscreen");
      el.style.cssText = "display:block;width:100%;max-width:960px;aspect-ratio:16/9;border:0;background:#000";
    } else {
      el = document.createElement("video");
      el.src = src;
      el.controls = true;
      el.setAttribute("playsinline", "");
      el.style.cssText = "display:block;width:100%;max-width:960px;aspect-ratio:16/9;background:#000";
    }
    el.setAttribute("data-qp-video", src);
    return el;
  }

  function build(kind, patch) {
    var el;
    if (kind === "video") {
      el = buildVideo(patch.src);
    } else if (kind === "text") {
      el = document.createElement("p");
      el.textContent = "새 텍스트";
      el.style.margin = "8px 0";
    } else if (kind === "button") {
      el = document.createElement("a");
      el.textContent = "버튼";
      el.setAttribute("href", "#");
      el.setAttribute("data-qp-href", "#");
      el.style.cssText =
        "display:inline-flex;align-items:center;justify-content:center;min-width:92px;height:40px;" +
        "padding:0 18px;border:1px solid #2b2f33;background:#2b2f33;color:#fff;font-weight:700;" +
        "text-decoration:none;cursor:pointer";
    } else if (kind === "divider") {
      el = document.createElement("hr");
      el.style.cssText = "border:0;border-top:1px solid #d9dcdf;margin:16px 0";
    } else {
      el = document.createElement("div");
      el.className = "ph";
      el.style.cssText =
        "min-height:160px;display:flex;align-items:center;justify-content:center;" +
        "background:#e9ecee;color:#6b7178;font-size:12px";
      el.textContent = "이미지 영역";
    }
    return el;
  }

  // 반환값: 작업 결과로 선택해야 할 요소 (실패하면 null)
  function apply(patch, live) {
    var el = find(patch, live);
    if (!el) return null;
    switch (patch.op) {
      case "text": {
        var nodes = textNodes(el);
        var node = nodes[patch.node || 0];
        if (!node) return null;
        var parts = /^(\s*)([\s\S]*?)(\s*)$/.exec(node.nodeValue);
        node.nodeValue = parts[1] + patch.value + parts[3];
        return el;
      }
      case "link":
        setLink(el, patch.href, patch.target);
        return el;
      case "style":
        for (var prop in patch.style) {
          if (STYLE_PROPS[prop] && Object.prototype.hasOwnProperty.call(patch.style, prop)) {
            el.style[prop] = patch.style[prop];
          }
        }
        return el;
      case "image":
        setImage(el, patch.src);
        return el;
      case "delete": {
        var parent = el.parentElement;
        if (!parent || el === document.body) return null;
        parent.removeChild(el);
        return parent;
      }
      case "duplicate": {
        if (!el.parentNode || el === document.body) return null;
        var clone = el.cloneNode(true);
        el.parentNode.insertBefore(clone, el.nextSibling);
        return clone;
      }
      case "move": {
        if (!el.parentNode || el === document.body) return null;
        var sibling = patch.dir === "up" ? el.previousElementSibling : el.nextElementSibling;
        if (!sibling) return null;
        if (patch.dir === "up") el.parentNode.insertBefore(el, sibling);
        else el.parentNode.insertBefore(sibling, el);
        return el;
      }
      case "insert": {
        var created = build(patch.kind, patch);
        if (el === document.body) el.appendChild(created);
        else el.parentNode.insertBefore(created, el.nextSibling);
        return created;
      }
      default:
        return null;
    }
  }

  function applyAll() {
    var failed = [];
    patches.forEach(function (patch, index) {
      if (!apply(patch, false)) failed.push(index);
    });
    return failed;
  }

  function finish(failed) {
    window.dispatchEvent(new CustomEvent("qp:applied", { detail: { failed: failed.length } }));
  }

  function run() {
    var failed = applyAll();
    if (!failed.length) {
      finish(failed);
      return;
    }
    // 페이지 스크립트가 늦게 그리는 요소를 한 번 더 기다린다
    setTimeout(function () {
      var still = [];
      failed.forEach(function (index) {
        if (!apply(patches[index], false)) still.push(index);
      });
      finish(still);
    }, 900);
  }

  document.addEventListener(
    "click",
    function (event) {
      if (MODE === "edit" && !window.__qpPreview) return;
      var target = event.target && event.target.closest ? event.target : null;
      if (!target) return;
      var el = target.closest("[data-qp-href]") || target.closest("a[href]");
      if (!el) return;
      var href = el.getAttribute("data-qp-href") || el.getAttribute("href") || "";
      var target_ = el.getAttribute("data-qp-target") || el.getAttribute("target") || "";
      var page = /^page:(.+)$/.exec(href);
      if (href.charAt(0) === "#") {
        if (href.length > 1) {
          var anchor = document.getElementById(href.slice(1));
          if (anchor) {
            event.preventDefault();
            anchor.scrollIntoView({ behavior: "smooth" });
          }
        } else {
          event.preventDefault();
        }
        return;
      }
      if (inIframe) {
        event.preventDefault();
        parent.postMessage(
          page ? { qp: "navigate", pageId: page[1] } : { qp: "open", href: href, target: target_ },
          "*"
        );
        return;
      }
      if (el.tagName === "A") return;
      event.preventDefault();
      var real = page ? "./" + page[1] + ".html" : href;
      if (target_ === "_blank") window.open(real, "_blank", "noopener");
      else window.location.href = real;
    },
    true
  );

  window.__qpRuntime = { apply: apply, pathOf: pathOf, refOf: refOf, find: find, textNodes: textNodes, collapse: collapse };

  if (document.readyState === "complete") run();
  else window.addEventListener("load", run);
})();
