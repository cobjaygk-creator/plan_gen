/** 업계동향/타사 이벤트/타사 사이트는 이제 로그인 없이 공개 열람할 수
 * 있다 — 기획서 생성/생성 이력/민심 체크기 메뉴만 이 계정으로 로그인
 *했을 때만 보여준다. 백엔드는 이 값을 web/backend/app/config.py의
 * ADMIN_EMAIL로 따로 갖고 있다(프런트가 백엔드 설정을 직접 import할 수
 * 없어서 부득이하게 두 곳에 둔다) — 바꿀 땐 둘 다 바꿔야 한다. */
export const ADMIN_EMAIL = "stkim@actoz.com";
