import { useEffect, useState, type RefObject } from "react";

/** 그래프가 뷰포트 안으로 스크롤되어 들어오는 순간을 한 번만 잡아낸다 —
 * 등장 애니메이션을 마운트 즉시가 아니라 실제로 눈에 보일 때 재생하기
 * 위한 용도라, 한 번 보인 뒤에는(스크롤을 다시 벗어나도) 계속 true를
 * 유지한다. 각 차트가 이미 갖고 있는 컨테이너 ref를 그대로 받아서 쓴다
 * (ResizeObserver용 ref와 별도로 새 ref를 만들 필요가 없다).
 *
 * threshold=0.2(뷰포트 바닥에 살짝 걸치기만 해도 트리거)로는 사용자가
 * 스크롤을 다 내리기도 전에 애니메이션이 끝나버려 효과가 체감되지
 * 않았다 — rootMargin으로 관찰 영역 자체를 화면 아래쪽에서 안으로
 * 당겨서(viewport bottom을 -20%만큼 줄임), 요소가 화면 중하단부까지
 * 충분히 올라온 뒤에야 "보였다"고 판단하게 늦춘다. */
export function useInView(
  ref: RefObject<Element | null>,
  options: { threshold?: number; rootMargin?: string } = {},
): boolean {
  const { threshold = 0.2, rootMargin = "0px 0px -20% 0px" } = options;
  const [inView, setInView] = useState(false);
  useEffect(() => {
    if (inView) return;
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setInView(true);
          observer.disconnect();
        }
      },
      { threshold, rootMargin },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [inView, threshold, rootMargin, ref]);
  return inView;
}
