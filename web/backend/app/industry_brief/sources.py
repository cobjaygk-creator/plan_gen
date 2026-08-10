"""Source list (design doc section 20/21) — kept small and manually
verified rather than exhaustive, per "관리 가능한 수준으로 제한". Each
entry's feed_url was checked by hand (real HTTP 200 + rss/xml content-type)
before being added here; don't add a source without doing the same.

Several sources named in the spec (게임메카, 디스이즈게임, Anthropic) don't
expose a discoverable RSS feed as of this check — spec section 20 itself
flags "실제 RSS 제공 여부는 구현 단계에서 확인", so they're left out rather
than guessed at. Revisit if a real feed URL turns up later."""
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
    # AI
    Source("OpenAI", "https://openai.com/news/rss.xml", "AI", "official"),
    Source("TechCrunch", "https://techcrunch.com/feed/", "AI", "media"),
    Source("The Verge", "https://www.theverge.com/rss/index.xml", "AI", "media"),
    Source("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "AI", "media"),
]
