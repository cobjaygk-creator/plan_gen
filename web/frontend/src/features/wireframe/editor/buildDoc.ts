import type { Patch } from "../types";

export type DocMode = "view" | "edit";

function jsonForScript(patches: Patch[]): string {
  return JSON.stringify(patches)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026")
    .replace(new RegExp(String.fromCharCode(0x2028), "g"), "\\u2028")
    .replace(new RegExp(String.fromCharCode(0x2029), "g"), "\\u2029");
}

/** 서버의 build_document와 같은 규칙으로 원본 HTML에 수정 목록과 스크립트를 붙인다. */
export function buildDoc(html: string, patches: Patch[], mode: DocMode, assets: { runtime: string; editor: string }): string {
  if (mode === "view" && patches.length === 0) return html;
  const parts = [
    `<script>window.__QP_MODE=${JSON.stringify(mode)};</script>`,
    `<script id="qp-patches" type="application/json">${jsonForScript(patches)}</script>`,
    `<script>${assets.runtime}</script>`,
  ];
  if (mode === "edit") parts.push(`<script>${assets.editor}</script>`);
  const block = parts.join("\n");
  const index = html.toLowerCase().lastIndexOf("</body>");
  return index === -1 ? html + block : html.slice(0, index) + block + html.slice(index);
}

const HREF_RE =
  /^(?:https?:\/\/[^\s"'<>()\\]{1,1000}|mailto:[^\s"'<>()\\]{1,200}|tel:[0-9+\-() ]{3,30}|#[\w-]{0,100}|\.\/[\w\-./]{1,200}|\/[\w\-./]{1,200}|page:[A-Za-z0-9._-]{1,80})$/;

export function isValidHref(href: string): boolean {
  return href === "" || HREF_RE.test(href);
}

/** getComputedStyle의 rgb(a) 문자열을 color input용 #rrggbb로 바꾼다. */
export function rgbToHex(value: string): string {
  const m = /rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/.exec(value);
  if (!m) return "#000000";
  return "#" + [m[1], m[2], m[3]].map((n) => Number(n).toString(16).padStart(2, "0")).join("");
}

export function isTransparent(value: string): boolean {
  return value === "transparent" || /rgba\(\d+,\s*\d+,\s*\d+,\s*0\)/.test(value);
}
