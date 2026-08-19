"""Source list (design doc section 20/21) — kept small and manually
verified rather than exhaustive, per "관리 가능한 수준으로 제한". Each
entry's feed_url was checked by hand (real HTTP 200 + rss/xml content-type)
before being added here; don't add a source without doing the same.

Sources that return slightly malformed metadata are allowed only when the
production parser still receives a successful response with real entries.
디스이즈게임 remains excluded because all verified candidates returned 404."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    name: str
    feed_url: str
    category: str  # "GAME" | "AI"
    source_type: str  # "media" | "official"


SOURCES: list[Source] = [
    # GAME
    Source("GamesIndustry.biz", "https://www.gamesindustry.biz/feed", "GAME", "media"),
    Source("PC Gamer", "https://www.pcgamer.com/rss/", "GAME", "media"),
    Source("인벤", "https://webzine.inven.co.kr/news/rss.php", "GAME", "media"),
    Source("게임메카", "https://www.gamemeca.com/rss.php", "GAME", "media"),
    # AI
    Source("삼성전자 뉴스룸", "https://news.samsung.com/kr/feed/rss", "AI", "official"),
    Source("OpenAI", "https://openai.com/news/rss.xml", "AI", "official"),
    Source("Microsoft", "https://blogs.microsoft.com/feed/", "AI", "official"),
    Source("NVIDIA", "https://blogs.nvidia.com/feed/", "AI", "official"),
    Source("TechCrunch", "https://techcrunch.com/feed/", "AI", "media"),
    Source("The Verge", "https://www.theverge.com/rss/index.xml", "AI", "media"),
    Source("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "AI", "media"),
    Source("AI타임스", "https://www.aitimes.com/rss/allArticle.xml", "AI", "media"),
    Source("전자신문 AI", "http://rss.etnews.com/04046.xml", "AI", "media"),
]


# Pending articles from these outlets are classified first so a small manual
# batch still produces a Korea-focused brief. This affects Industry Brief only.
KOREAN_SOURCE_NAMES: tuple[str, ...] = (
    "인벤",
    "게임메카",
    "크래프톤",
    "넥슨게임즈",
    "넷마블",
    "삼성전자 뉴스룸",
    "AI타임스",
    "전자신문 AI",
    "한국콘텐츠진흥원",
    "문화체육관광부",
    "대한민국 정책브리핑",
    "게임물관리위원회",
)

NAVER_SOURCE_PREFIX = "NAVER · "


def is_korean_source(source_name: str) -> bool:
    """NAVER News is a Korean discovery source even though its publisher varies."""
    return source_name in KOREAN_SOURCE_NAMES or source_name.startswith(NAVER_SOURCE_PREFIX)
