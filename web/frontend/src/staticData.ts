export const isStaticSite = import.meta.env.VITE_STATIC_SITE === "true";

export function staticDataUrl(file: string): string {
  return `${import.meta.env.BASE_URL}data/${file}`;
}
