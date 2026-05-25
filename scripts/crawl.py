#!/usr/bin/env python3
"""외부 소스에서 스킬을 수집해 skills.json에 병합합니다.

우선순위: zarvis > community
중복 기준: command 필드
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

SKILLS_FILE = Path(__file__).parent.parent / "skills.json"

CATEGORIES_KEYWORDS = {
    "생산성": ["plan", "schedule", "task", "productivity", "time", "focus", "habit"],
    "콘텐츠 제작": ["content", "write", "blog", "social", "post", "caption", "script"],
    "비즈니스/전략": ["business", "strategy", "market", "revenue", "startup"],
    "퍼스널 브랜딩": ["brand", "personal", "audience", "niche", "portfolio"],
    "코딩/기술": ["code", "debug", "refactor", "api", "database", "software", "dev"],
    "AI 추론 스타일": ["analyze", "reason", "think", "logic", "argument"],
    "실행/출력 모드": ["format", "output", "list", "step", "summary"],
    "커리어/직업": ["career", "resume", "job", "interview", "salary"],
    "학습": ["learn", "study", "teach", "explain", "understand"],
    "고급 프롬프트 제어": ["prompt", "role", "context", "style", "tone"],
}


def load_existing() -> dict:
    """기존 skills.json 로드, zarvis 소스를 command 키로 인덱싱."""
    if SKILLS_FILE.exists():
        skills = json.loads(SKILLS_FILE.read_text(encoding="utf-8"))
        return {s["command"]: s for s in skills}
    return {}


def fetch_url(url: str) -> str:
    """URL에서 텍스트를 가져옵니다. 실패 시 빈 문자열 반환."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "zarvis-crawler/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  fetch 실패 {url}: {e}", file=sys.stderr)
        return ""


def guess_category(text: str) -> str:
    """텍스트에서 키워드를 찾아 카테고리를 추측합니다."""
    text_lower = text.lower()
    for category, keywords in CATEGORIES_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return category
    return "고급 프롬프트 제어"


def parse_awesome_chatgpt_prompts(readme: str) -> list:
    """f/awesome-chatgpt-prompts README에서 역할 기반 프롬프트를 파싱합니다.

    형식: ## Act as a <Role>\n> <prompt>
    """
    skills = []
    pattern = re.compile(
        r"##\s+Act as (?:a |an )?(.+?)\n+>\s*(.+?)(?=\n##|\Z)", re.DOTALL
    )
    for match in pattern.finditer(readme):
        role = match.group(1).strip()
        prompt = re.sub(r"\s+", " ", match.group(2).strip())
        if len(prompt) < 20:
            continue
        command = "/" + re.sub(r"[^a-z0-9]", "", role.lower().replace(" ", ""))[:20]
        skills.append({
            "command": command,
            "description": f"{role} 역할",
            "prompt": prompt,
            "category": guess_category(role + " " + prompt),
            "platforms": ["chatgpt"],
            "source": "community",
        })
    return skills


def parse_awesome_claude_prompts(readme: str) -> list:
    """langgptai/awesome-claude-prompts README에서 프롬프트를 파싱합니다.

    형식: ### <Title>\n<prompt>
    """
    skills = []
    pattern = re.compile(r"###\s+(.+?)\n+(.+?)(?=\n###|\Z)", re.DOTALL)
    for match in pattern.finditer(readme):
        title = match.group(1).strip()
        prompt_text = re.sub(r"\s+", " ", match.group(2).strip())
        if len(prompt_text) < 20 or prompt_text.startswith("#"):
            continue
        command = "/" + re.sub(r"[^a-z0-9]", "", title.lower().replace(" ", ""))[:20]
        skills.append({
            "command": command,
            "description": title,
            "prompt": prompt_text[:500],
            "category": guess_category(title + " " + prompt_text),
            "platforms": ["claude"],
            "source": "community",
        })
    return skills


def merge(existing: dict, new_skills: list) -> list:
    """새 스킬을 기존에 병합합니다. zarvis 소스 항목은 덮어쓰지 않습니다."""
    result = dict(existing)
    added = 0
    for skill in new_skills:
        cmd = skill["command"]
        if cmd not in result:
            result[cmd] = skill
            added += 1
    print(f"  신규 추가: {added}개")
    return list(result.values())


def main(dry_run: bool = False) -> None:
    print("기존 skills.json 로드 중...")
    existing = load_existing()
    print(f"  기존: {len(existing)}개")

    all_new: list = []

    sources = [
        (
            "https://raw.githubusercontent.com/f/awesome-chatgpt-prompts/main/README.md",
            parse_awesome_chatgpt_prompts,
            "awesome-chatgpt-prompts",
        ),
        (
            "https://raw.githubusercontent.com/langgptai/awesome-claude-prompts/main/README.md",
            parse_awesome_claude_prompts,
            "awesome-claude-prompts",
        ),
    ]

    for url, parser, name in sources:
        print(f"{name} 수집 중...")
        readme = fetch_url(url)
        if readme:
            parsed = parser(readme)
            print(f"  파싱: {len(parsed)}개")
            all_new.extend(parsed)

    merged = merge(existing, all_new)
    print(f"최종: {len(merged)}개")

    if not dry_run:
        SKILLS_FILE.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"저장 완료: {SKILLS_FILE}")
    else:
        print("(dry-run: 저장 건너뜀)")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
