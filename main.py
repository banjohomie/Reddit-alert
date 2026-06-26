import argparse
import calendar
import hashlib
import html
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import feedparser
import requests
from dotenv import load_dotenv


BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
CONFIG_EXAMPLE_PATH = BASE_DIR / "config.example.json"
SEEN_POSTS_PATH = BASE_DIR / "seen_posts.json"
FOR_HIRE_POSTS_PATH = BASE_DIR / "for_hire_posts.json"
SUBREDDIT_RULES_PATH = BASE_DIR / "subreddit_rules.json"
SUBREDDIT_RULES_PRESETS_PATH = BASE_DIR / "subreddit_rules_presets.json"
RSS_URL_TEMPLATE = "https://www.reddit.com/r/{subreddit}/new/.rss?limit={limit}"
RSS_ACCEPT_HEADER = "application/atom+xml, application/rss+xml, application/xml;q=0.9,*/*;q=0.8"

DEFAULT_CONFIG = {
    "FAST_SUBREDDITS": [
        "freelance_forhire",
        "forhire",
        "slavelabour",
        "DoneDirtCheap",
        "jobbit",
        "Jobs4Crypto",
    ],
    "SLOW_SUBREDDITS": [
        "remotepython",
        "PythonJobs",
        "webdevjobs",
        "hiring",
        "WorkOnline",
        "VirtualAssistant",
        "HireaWriter",
        "DesignJobs",
        "gameDevClassifieds",
        "jobs4bitcoins",
    ],
    "FAST_CHECK_INTERVAL_SECONDS": 300,
    "SLOW_CHECK_INTERVAL_SECONDS": 1800,
    "REQUEST_DELAY_MIN_SECONDS": 8,
    "REQUEST_DELAY_MAX_SECONDS": 15,
    "JITTER_MIN_SECONDS": 10,
    "JITTER_MAX_SECONDS": 30,
    "RATE_LIMIT_BASE_COOLDOWN_SECONDS": 600,
    "RATE_LIMIT_MAX_COOLDOWN_SECONDS": 3600,
    "RSS_LIMIT": 10,
    "USER_AGENT": "RedditQuickWorkBot/1.0 by u/your_username",
    "MAX_POST_AGE_MINUTES": 60,
    "MIN_SCORE": 4,
    "SEEN_POST_RETENTION_DAYS": 7,
    "RULES_ASSISTANT_ENABLED": True,
    "RULES_CHECK_INTERVAL_DAYS": 7,
    "RULES_REQUEST_DELAY_SECONDS": 10,
    "RULES_CONFIDENCE_MIN_TO_SUGGEST": 0.65,
    "RULES_MAX_TEXT_CHARS": 12000,
    "RULES_FETCH_ENABLED": False,
    "RULES_FETCH_MAX_SOURCES_PER_SUBREDDIT": 1,
    "RULES_FETCH_COOLDOWN_HOURS": 24,
    "DRY_RUN": False,
    "FOR_HIRE_ASSISTANT_ENABLED": True,
    "FOR_HIRE_CHECK_INTERVAL_SECONDS": 3600,
    "FOR_HIRE_MIN_DAYS_BETWEEN_SAME_SUBREDDIT": 7,
    "FOR_HIRE_MAX_POSTS_PER_WEEK": 3,
    "FOR_HIRE_SUBREDDITS": [
        "freelance_forhire",
        "slavelabour",
        "DoneDirtCheap",
        "forhire",
        "jobbit",
        "remotepython",
        "PythonJobs",
    ],
    "FOR_HIRE_GITHUB_URL": "https://github.com/your_username",
    "FOR_HIRE_PRICE_RANGE": "$10-$40 fixed",
    "FOR_HIRE_SMALL_PRICE_RANGE": "$10-$20",
    "FOR_HIRE_MEDIUM_PRICE_RANGE": "$25-$40",
    "FOR_HIRE_SERVICES": [
        "simple Python scripts",
        "Telegram/Discord notification bots",
        "CSV/Excel automation",
        "data cleanup",
        "API to CSV/Excel exporters",
        "simple allowed web scraping",
    ],
    "FOR_HIRE_BANNED_SERVICE_WORDS": [
        "spam",
        "mass DM",
        "vote manipulation",
        "fake reviews",
        "account creation",
        "captcha bypass",
        "scraping private data",
    ],
}

DEFAULT_SUBREDDIT_RULE_PRESETS = {
    "freelance_forhire": {
        "confidence": 0.75,
        "parsed": {
            "allows_for_hire": True,
            "title_required_tags": ["[For Hire]"],
            "price_required": True,
            "portfolio_required": True,
            "flair_required": None,
            "posting_cooldown_days": 7,
            "banned_topics": ["spam", "illegal", "adult", "scam"],
            "notes": ["Preset rules are approximate. Manually verify before posting."],
        },
    },
    "forhire": {
        "confidence": 0.65,
        "parsed": {
            "allows_for_hire": True,
            "title_required_tags": ["[For Hire]"],
            "price_required": True,
            "portfolio_required": True,
            "flair_required": None,
            "posting_cooldown_days": 7,
            "banned_topics": ["spam", "illegal", "adult", "scam"],
            "notes": ["Preset is approximate. Verify manually."],
        },
    },
    "slavelabour": {
        "confidence": 0.65,
        "parsed": {
            "allows_for_hire": True,
            "title_required_tags": ["[For Hire]"],
            "price_required": True,
            "portfolio_required": True,
            "flair_required": None,
            "posting_cooldown_days": 7,
            "banned_topics": ["spam", "illegal", "adult", "scam"],
            "notes": ["Preset is approximate. Verify manually."],
        },
    },
    "DoneDirtCheap": {
        "confidence": 0.65,
        "parsed": {
            "allows_for_hire": True,
            "title_required_tags": ["[For Hire]"],
            "price_required": True,
            "portfolio_required": True,
            "flair_required": None,
            "posting_cooldown_days": 7,
            "banned_topics": ["spam", "illegal", "adult", "scam"],
            "notes": ["Preset is approximate. Verify manually."],
        },
    },
    "jobbit": {
        "confidence": 0.65,
        "parsed": {
            "allows_for_hire": True,
            "title_required_tags": ["[For Hire]"],
            "price_required": True,
            "portfolio_required": True,
            "flair_required": None,
            "posting_cooldown_days": 7,
            "banned_topics": ["spam", "illegal", "adult", "scam"],
            "notes": ["Preset is approximate. Verify manually."],
        },
    },
    "remotepython": {
        "confidence": 0.65,
        "parsed": {
            "allows_for_hire": True,
            "title_required_tags": ["[For Hire]"],
            "price_required": True,
            "portfolio_required": True,
            "flair_required": None,
            "posting_cooldown_days": 7,
            "banned_topics": ["spam", "illegal", "adult", "scam"],
            "notes": ["Preset is approximate. Verify manually."],
        },
    },
    "PythonJobs": {
        "confidence": 0.65,
        "parsed": {
            "allows_for_hire": True,
            "title_required_tags": ["[For Hire]"],
            "price_required": True,
            "portfolio_required": True,
            "flair_required": None,
            "posting_cooldown_days": 7,
            "banned_topics": ["spam", "illegal", "adult", "scam"],
            "notes": ["Preset is approximate. Verify manually."],
        },
    },
}

GOOD_TAGS = ("hiring", "task", "paid", "job", "gig")
OFFER_TAG = "offer"
OFFER_SELLER_PHRASES = (
    "i will",
    "i can",
    "my service",
    "for hire",
    "available for",
    "hire me",
)
OFFER_TASK_PHRASES = (
    "need someone",
    "looking for someone",
    "paying",
    "paid task",
    "quick task",
    "small task",
)
STRONG_PHRASES = (
    "quick task",
    "simple task",
    "small task",
    "need someone",
    "looking for someone",
)
POSITIVE_KEYWORDS = (
    "hiring",
    "paid",
    "quick task",
    "simple task",
    "small task",
    "need someone",
    "looking for someone",
    "can someone",
    "virtual assistant",
    "data entry",
    "research",
    "find emails",
    "lead generation",
    "copy paste",
    "spreadsheet",
    "google sheets",
    "excel",
    "write",
    "rewrite",
    "proofread",
    "transcribe",
    "test website",
    "review website",
    "discord",
    "telegram",
    "outreach",
    "cold email",
    "dm",
)
NEGATIVE_PHRASES = {
    "commission only": -5,
    "unpaid": -5,
    "equity": -5,
    "no pay": -5,
    "forex": -4,
    "investment": -4,
    "wallet": -4,
    "gambling": -4,
    "adult": -4,
    "nsfw": -4,
    "onlyfans": -4,
    "upfront fee": -5,
    "deposit": -5,
    "seed phrase": -5,
    "private key": -5,
    "connect wallet": -5,
}
CRYPTO_SUBREDDITS = {"jobs4bitcoins", "jobs4crypto"}
CONFIG_KEY_ALIASES = {
    "FAST_CHECK_INTERVAL_SECONDS": "CHECK_INTERVAL_SECONDS",
    "RSS_LIMIT": "rss_limit_per_subreddit",
    "MAX_POST_AGE_MINUTES": "max_post_age_minutes",
    "MIN_SCORE": "min_score",
    "SEEN_POST_RETENTION_DAYS": "seen_retention_days",
}

FOR_HIRE_TITLE_TEMPLATES = (
    "{tag} Small Python scripts, Telegram bots, CSV/Excel automation - {price_range}",
    "{tag} I can build simple Python tools, bots, and spreadsheet automations",
    "{tag} Python scripts, Telegram/Discord bots, and data cleanup for small tasks",
    "{tag} Small automation tasks: Python scripts, bots, CSV/Excel work",
    "{tag} Fixed-price Python automation, simple bots, and data cleanup",
    "{tag} Simple Python scripts and automation for small fixed tasks",
    "{tag} Python automation, Telegram/Discord bots, and spreadsheet cleanup",
    "{tag} Small fixed-price tools: Python, bots, CSV/Excel cleanup",
)
FOR_HIRE_OPENINGS = (
    "Hi, I'm looking for small fixed-price tasks.",
    "I'm available for small Python automation tasks and simple bot projects.",
    "I can help with small scripts, bots, and spreadsheet automation.",
    "I'm taking on small fixed-price automation and data cleanup tasks.",
    "I can help with practical Python scripts, notifications, and spreadsheet cleanup.",
)


class RateLimitError(Exception):
    def __init__(self, subreddit_name: str, retry_after_seconds: Optional[int] = None) -> None:
        self.subreddit_name = subreddit_name
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Reddit RSS returned HTTP 429 for r/{subreddit_name}")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        config = load_config_example_or_default()
        save_json(CONFIG_PATH, config)
        logging.warning("config.json not found. Created it from config.example.json or built-in defaults.")
        return config

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except (json.JSONDecodeError, OSError) as exc:
        logging.error("Could not read config.json: %s", exc)
        logging.info("Using default configuration for this run.")
        return DEFAULT_CONFIG.copy()

    config = migrate_config_keys(config)
    merged = DEFAULT_CONFIG.copy()
    merged.update(config)

    if merged != config:
        save_json(CONFIG_PATH, merged)

    return merged


def load_config_example_or_default() -> Dict[str, Any]:
    if CONFIG_EXAMPLE_PATH.exists():
        try:
            with CONFIG_EXAMPLE_PATH.open("r", encoding="utf-8") as file:
                config = json.load(file)
            if isinstance(config, dict):
                migrated = migrate_config_keys(config)
                merged = DEFAULT_CONFIG.copy()
                merged.update(migrated)
                return merged
        except (json.JSONDecodeError, OSError) as exc:
            logging.error("Could not read config.example.json: %s", exc)

    return DEFAULT_CONFIG.copy()


def migrate_config_keys(config: Dict[str, Any]) -> Dict[str, Any]:
    migrated = dict(config)

    migrated.pop("RATE_LIMIT_COOLDOWN_SECONDS", None)

    if "subreddits" in migrated and "FAST_SUBREDDITS" not in migrated:
        migrated["FAST_SUBREDDITS"] = migrated["subreddits"]
    migrated.pop("subreddits", None)

    if "check_interval_seconds" in migrated and "FAST_CHECK_INTERVAL_SECONDS" not in migrated:
        migrated["FAST_CHECK_INTERVAL_SECONDS"] = migrated["check_interval_seconds"]
    migrated.pop("check_interval_seconds", None)

    for new_key, old_key in CONFIG_KEY_ALIASES.items():
        if old_key in migrated:
            if new_key not in migrated:
                migrated[new_key] = migrated[old_key]
            migrated.pop(old_key, None)

    return migrated


def get_config_int(config: Dict[str, Any], key: str) -> int:
    return int(config.get(key, DEFAULT_CONFIG[key]))


def get_config_str(config: Dict[str, Any], key: str) -> str:
    return str(config.get(key, DEFAULT_CONFIG[key]))


def get_config_bool(config: Dict[str, Any], key: str) -> bool:
    return bool(config.get(key, DEFAULT_CONFIG[key]))


def get_config_list(config: Dict[str, Any], key: str) -> List[str]:
    value = config.get(key, DEFAULT_CONFIG[key])
    if not isinstance(value, list):
        return list(DEFAULT_CONFIG[key])
    return [str(item) for item in value if str(item).strip()]


def calculate_next_check(interval_seconds: int, jitter_min_seconds: int, jitter_max_seconds: int) -> float:
    if jitter_max_seconds < jitter_min_seconds:
        jitter_min_seconds, jitter_max_seconds = jitter_max_seconds, jitter_min_seconds

    jitter = random.uniform(max(0, jitter_min_seconds), max(0, jitter_max_seconds))
    return time.time() + max(interval_seconds, 1) + jitter


def load_seen_posts() -> Dict[str, Any]:
    default_seen_posts = {
        "initialized": False,
        "initialized_groups": {"fast": False, "slow": False},
        "initialized_group_subreddits": {"fast": [], "slow": []},
        "posts": {},
    }

    if not SEEN_POSTS_PATH.exists():
        save_json(SEEN_POSTS_PATH, {})
        data: Any = {}
    else:
        try:
            with SEEN_POSTS_PATH.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, OSError) as exc:
            logging.error("Could not read seen_posts.json: %s", exc)
            logging.info("Starting with an empty seen post list for this run.")
            return default_seen_posts

    if isinstance(data, list):
        now = utc_now_iso()
        data = {"initialized": True, "posts": {post_id: now for post_id in data}}
    elif not isinstance(data, dict):
        data = default_seen_posts

    data.setdefault("initialized", False)
    data.setdefault("initialized_groups", None)
    data.setdefault("initialized_group_subreddits", None)
    data.setdefault("posts", {})

    if not isinstance(data["initialized_groups"], dict):
        data["initialized_groups"] = {"fast": False, "slow": False}
    else:
        data["initialized_groups"].setdefault("fast", False)
        data["initialized_groups"].setdefault("slow", False)

    if not isinstance(data["initialized_group_subreddits"], dict):
        data["initialized_group_subreddits"] = {"fast": [], "slow": []}
    else:
        data["initialized_group_subreddits"].setdefault("fast", [])
        data["initialized_group_subreddits"].setdefault("slow", [])

    if not isinstance(data["posts"], dict):
        data["posts"] = {}

    return data


def sync_seen_group_bootstrap_state(seen_posts: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    initialized_groups = seen_posts.setdefault("initialized_groups", {"fast": False, "slow": False})
    initialized_group_subreddits = seen_posts.setdefault("initialized_group_subreddits", {"fast": [], "slow": []})

    current_groups = {
        "fast": get_config_list(config, "FAST_SUBREDDITS"),
        "slow": get_config_list(config, "SLOW_SUBREDDITS"),
    }

    for group_name, current_subreddits in current_groups.items():
        previous_subreddits = initialized_group_subreddits.get(group_name, [])
        if normalize_subreddit_list(previous_subreddits) != normalize_subreddit_list(current_subreddits):
            initialized_groups[group_name] = False

    seen_posts["initialized"] = all(bool(initialized_groups.get(name, False)) for name in ("fast", "slow"))
    return seen_posts


def normalize_subreddit_list(subreddits: Iterable[Any]) -> List[str]:
    return sorted(str(subreddit).lower() for subreddit in subreddits)


def save_seen_posts(seen_posts: Dict[str, Any]) -> None:
    save_json(SEEN_POSTS_PATH, seen_posts)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.write("\n")


def ensure_runtime_files_exist() -> None:
    if not SEEN_POSTS_PATH.exists():
        save_json(SEEN_POSTS_PATH, {})
    if not FOR_HIRE_POSTS_PATH.exists():
        save_json(FOR_HIRE_POSTS_PATH, {"posts": [], "stats": {}})
    if not SUBREDDIT_RULES_PATH.exists():
        save_json(SUBREDDIT_RULES_PATH, {})


def default_subreddit_rules_entry() -> Dict[str, Any]:
    return {
        "last_checked_at": None,
        "source_urls": [],
        "raw_text_hash": "",
        "confidence": 0.0,
        "parsed": {
            "allows_for_hire": None,
            "title_required_tags": [],
            "required_title_words": [],
            "forbidden_title_words": [],
            "price_required": None,
            "min_hourly_rate": None,
            "min_fixed_price": None,
            "portfolio_required": None,
            "flair_required": None,
            "required_flair": None,
            "posting_cooldown_days": None,
            "karma_requirement": None,
            "account_age_requirement": None,
            "comment_before_dm_required": None,
            "banned_topics": [],
            "required_sections": [],
            "notes": [],
        },
        "warnings": [],
        "raw_summary": "",
    }


def load_subreddit_rules() -> Dict[str, Any]:
    if not SUBREDDIT_RULES_PATH.exists():
        save_json(SUBREDDIT_RULES_PATH, {})
        return {}

    try:
        with SUBREDDIT_RULES_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError) as exc:
        logging.error("Could not read subreddit_rules.json: %s", exc)
        return {}

    return data if isinstance(data, dict) else {}


def save_subreddit_rules(data: Dict[str, Any]) -> None:
    save_json(SUBREDDIT_RULES_PATH, data)


def load_subreddit_rule_presets() -> Dict[str, Any]:
    if not SUBREDDIT_RULES_PRESETS_PATH.exists():
        save_json(SUBREDDIT_RULES_PRESETS_PATH, DEFAULT_SUBREDDIT_RULE_PRESETS)
        return DEFAULT_SUBREDDIT_RULE_PRESETS

    try:
        with SUBREDDIT_RULES_PRESETS_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError) as exc:
        logging.error("Could not read subreddit_rules_presets.json: %s", exc)
        return {}

    return data if isinstance(data, dict) else {}


def get_cached_or_fetch_rules(subreddit: str, config: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
    rules_cache = load_subreddit_rules()
    entry = rules_cache.get(subreddit)
    fetch_enabled = get_config_bool(config, "RULES_FETCH_ENABLED")
    if entry and not subreddit_rules_stale(entry, config) and (not force or not fetch_enabled):
        return normalize_rules_entry(entry)

    presets = load_subreddit_rule_presets()
    preset_entry = preset_to_rules_entry(subreddit, presets.get(subreddit))

    if not fetch_enabled:
        if preset_entry:
            rules_cache[subreddit] = preset_entry
            save_subreddit_rules(rules_cache)
            return preset_entry
        if entry:
            return normalize_rules_entry(entry)
        return unavailable_rules_entry(subreddit)

    if entry and rules_fetch_on_cooldown(entry):
        return preset_entry or normalize_rules_entry(entry)

    updated_entry = fetch_and_parse_subreddit_rules(subreddit, config)
    if not updated_entry.get("source_urls") and preset_entry:
        updated_entry = merge_rules_entries(preset_entry, updated_entry)

    rules_cache[subreddit] = updated_entry
    save_subreddit_rules(rules_cache)
    return updated_entry


def preset_to_rules_entry(subreddit: str, preset: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(preset, dict):
        return None

    entry = default_subreddit_rules_entry()
    parsed = default_subreddit_rules_entry()["parsed"]
    parsed.update(preset.get("parsed", {}))
    warnings = ["Preset rules are approximate. Verify manually before posting."]
    notes = parsed.get("notes") or []
    for note in notes:
        if not isinstance(note, str):
            continue
        normalized_note = normalize_text(note)
        is_same_preset_warning = all(term in normalized_note for term in ("preset", "approximate", "verify"))
        if note not in warnings and not is_same_preset_warning:
            warnings.append(note)

    entry.update(
        {
            "last_checked_at": local_now_iso(),
            "source_urls": [f"preset:{subreddit}"],
            "raw_text_hash": hashlib.sha256(json.dumps(preset, sort_keys=True).encode("utf-8")).hexdigest(),
            "confidence": float(preset.get("confidence", 0.65)),
            "parsed": parsed,
            "warnings": dedupe_keep_order(warnings),
            "raw_summary": "Preset rules are approximate. Manually verify before posting.",
        }
    )
    return entry


def unavailable_rules_entry(subreddit: str) -> Dict[str, Any]:
    entry = default_subreddit_rules_entry()
    entry.update(
        {
            "last_checked_at": local_now_iso(),
            "confidence": 0.2,
            "warnings": ["Rules could not be fetched automatically. Check subreddit rules manually before posting."],
            "raw_summary": f"No cached or preset rules available for r/{subreddit}.",
        }
    )
    return entry


def merge_rules_entries(primary: Dict[str, Any], secondary: Dict[str, Any]) -> Dict[str, Any]:
    merged = normalize_rules_entry(primary)
    merged["warnings"] = dedupe_keep_order(list(merged.get("warnings", [])) + list(secondary.get("warnings", [])))
    merged["raw_summary"] = secondary.get("raw_summary") or merged.get("raw_summary", "")
    if secondary.get("fetch_cooldown_until"):
        merged["fetch_cooldown_until"] = secondary["fetch_cooldown_until"]
    return merged


def rules_fetch_on_cooldown(entry: Dict[str, Any]) -> bool:
    cooldown_until = parse_iso_timestamp(entry.get("fetch_cooldown_until"))
    return cooldown_until > time.time()


def subreddit_rules_stale(entry: Dict[str, Any], config: Dict[str, Any]) -> bool:
    checked_at = parse_iso_timestamp(entry.get("last_checked_at"))
    if checked_at == 0:
        return True

    interval_seconds = max(1, get_config_int(config, "RULES_CHECK_INTERVAL_DAYS")) * 24 * 60 * 60
    return time.time() - checked_at >= interval_seconds


def fetch_and_parse_subreddit_rules(subreddit: str, config: Dict[str, Any]) -> Dict[str, Any]:
    max_chars = get_config_int(config, "RULES_MAX_TEXT_CHARS")
    delay_seconds = get_config_int(config, "RULES_REQUEST_DELAY_SECONDS")
    max_sources = max(1, get_config_int(config, "RULES_FETCH_MAX_SOURCES_PER_SUBREDDIT"))
    user_agent = get_config_str(config, "USER_AGENT")
    source_texts: List[str] = []
    source_urls: List[str] = []
    source_flags = {
        "rules_page": False,
        "wiki_page": False,
        "explicit_for_hire": False,
        "price_rule": False,
        "cooldown_rule": False,
        "source_error_count": 0,
    }
    warnings: List[str] = []

    sources = [
        ("rules_page", f"https://www.reddit.com/r/{subreddit}/about/rules"),
        ("wiki_page", f"https://www.reddit.com/r/{subreddit}/wiki/rules"),
    ][:max_sources]

    for index, (source_name, url) in enumerate(sources):
        text, stop_fetching = fetch_rules_source_text(url, source_name, user_agent, subreddit, warnings)
        if text:
            source_urls.append(url)
            source_texts.append(text)
            if source_name == "rules_page":
                source_flags["rules_page"] = True
            if source_name == "wiki_page":
                source_flags["wiki_page"] = True
        else:
            source_flags["source_error_count"] += 1

        if stop_fetching:
            break

        if index < len(sources) - 1:
            time.sleep(max(0, delay_seconds))

    raw_text = "\n\n".join(source_texts)
    if len(raw_text) > max_chars:
        raw_text = raw_text[:max_chars]

    if not raw_text:
        entry = unavailable_rules_entry(subreddit)
        entry["warnings"] = dedupe_keep_order(list(warnings) + list(entry.get("warnings", [])))
        if any("fetch cooldown" in warning.lower() for warning in entry["warnings"]):
            entry["fetch_cooldown_until"] = (
                datetime.fromtimestamp(time.time() + get_config_int(config, "RULES_FETCH_COOLDOWN_HOURS") * 3600)
                .replace(microsecond=0)
                .isoformat()
            )
        return entry

    parsed, parse_warnings = parse_subreddit_rules_text(raw_text)
    warnings.extend(parse_warnings)
    normalized = normalize_text(raw_text)
    source_flags["explicit_for_hire"] = any(term in normalized for term in ("for hire", "[for hire]", "[offer]", "offer post"))
    source_flags["price_rule"] = any(term in normalized for term in ("price", "pricing", "rate", "budget", "$"))
    source_flags["cooldown_rule"] = any(term in normalized for term in ("cooldown", "repost", "once per", "every 7 days", "per week"))
    confidence = calculate_rules_confidence(source_flags, parsed, warnings)

    entry = default_subreddit_rules_entry()
    entry.update(
        {
            "last_checked_at": local_now_iso(),
            "source_urls": source_urls,
            "raw_text_hash": hashlib.sha256(raw_text.encode("utf-8")).hexdigest() if raw_text else "",
            "confidence": confidence,
            "parsed": parsed,
            "warnings": dedupe_keep_order(warnings),
            "raw_summary": summarize_rules_text(raw_text),
        }
    )
    if any("fetch cooldown" in warning.lower() for warning in warnings):
        entry["fetch_cooldown_until"] = (
            datetime.fromtimestamp(time.time() + get_config_int(config, "RULES_FETCH_COOLDOWN_HOURS") * 3600)
            .replace(microsecond=0)
            .isoformat()
        )
    return entry


def fetch_rules_source_text(
    url: str,
    source_name: str,
    user_agent: str,
    subreddit: str,
    warnings: List[str],
) -> Tuple[str, bool]:
    headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
    try:
        response = requests.get(url, headers=headers, timeout=20)
    except requests.RequestException as exc:
        logging.warning("Rules fetch failed for r/%s %s: %s", subreddit, source_name, exc)
        warnings.append(f"{source_name} unavailable: request failed")
        return "", False

    if response.status_code in (403, 429):
        logging.warning("Rules fetch got HTTP %s for r/%s. Stopping rules fetch for this subreddit.", response.status_code, subreddit)
        warnings.append(f"{source_name} unavailable: HTTP {response.status_code}; fetch cooldown set")
        return "", True

    if response.status_code == 404:
        warnings.append(f"{source_name} unavailable: HTTP 404")
        return "", False

    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.warning("Rules fetch error for r/%s %s: %s", subreddit, source_name, exc)
        warnings.append(f"{source_name} unavailable: HTTP error")
        return "", False

    return clean_text(response.text), False


def extract_text_from_reddit_json(payload: Any) -> str:
    parts: List[str] = []
    if not isinstance(payload, dict):
        return ""

    data = payload.get("data", payload)
    if isinstance(data, dict):
        for key in ("title", "public_description", "description", "submit_text", "content_md", "reason"):
            value = data.get(key)
            if isinstance(value, str):
                parts.append(value)

        rules = data.get("rules") or payload.get("rules")
        if isinstance(rules, list):
            for rule in rules:
                if isinstance(rule, dict):
                    for key in ("short_name", "description", "violation_reason"):
                        value = rule.get(key)
                        if isinstance(value, str):
                            parts.append(value)

    return clean_text("\n".join(parts))


def parse_subreddit_rules_text(raw_text: str) -> Tuple[Dict[str, Any], List[str]]:
    parsed = default_subreddit_rules_entry()["parsed"]
    warnings: List[str] = []
    text = normalize_text(raw_text)

    if not text:
        warnings.append("No rule text could be collected.")
        return parsed, warnings

    allow_patterns = (
        r"\[for hire\]",
        r"for hire posts? (are )?(allowed|permitted|welcome)",
        r"offer posts? (are )?(allowed|permitted|welcome)",
    )
    deny_patterns = (
        r"no for hire",
        r"for hire posts? (are )?(not allowed|prohibited|forbidden|banned)",
        r"do not post.*for hire",
        r"no self promotion",
    )
    allows = any(re.search(pattern, text) for pattern in allow_patterns)
    denies = any(re.search(pattern, text) for pattern in deny_patterns)
    if allows and denies:
        warnings.append("Rules contain both allow and deny language for For Hire posts.")
        parsed["allows_for_hire"] = None
    elif denies:
        parsed["allows_for_hire"] = False
    elif allows:
        parsed["allows_for_hire"] = True

    tags = dedupe_keep_order(f"[{match.strip()}]" for match in re.findall(r"\[(for hire|offer|hiring|task|job|gig)\]", text, re.I))
    if tags:
        parsed["title_required_tags"] = tags

    if any(term in text for term in ("price required", "include price", "include pricing", "include your rate", "must include rate", "budget required")):
        parsed["price_required"] = True
        parsed["required_sections"].append("Pricing")
    elif any(term in text for term in ("do not include price", "no prices")):
        parsed["price_required"] = False

    hourly_match = re.search(r"\$(\d+(?:\.\d+)?)\s*(?:/|per)?\s*(?:hour|hr)", text)
    if hourly_match:
        parsed["min_hourly_rate"] = float(hourly_match.group(1))

    fixed_matches = [float(value) for value in re.findall(r"\$(\d+(?:\.\d+)?)", text)]
    if fixed_matches and any(term in text for term in ("minimum", "min", "at least", "fixed")):
        parsed["min_fixed_price"] = max(fixed_matches)

    if any(term in text for term in ("portfolio required", "include portfolio", "examples required", "include examples", "github")):
        parsed["portfolio_required"] = True
        parsed["required_sections"].append("Portfolio/GitHub")

    if "flair" in text and any(term in text for term in ("required flair", "flair required", "must flair", "select flair")):
        parsed["flair_required"] = True
        flair_match = re.search(r"(?:flair|select flair).*?(for hire|offer|services|hiring)", text)
        if flair_match:
            parsed["required_flair"] = flair_match.group(1)

    cooldown_match = re.search(r"(?:once|one post|repost|post).*?(?:every|per|each)\s+(\d+)\s+(day|days|week|weeks|month|months)", text)
    if cooldown_match:
        amount = int(cooldown_match.group(1))
        unit = cooldown_match.group(2)
        multiplier = 1
        if "week" in unit:
            multiplier = 7
        elif "month" in unit:
            multiplier = 30
        parsed["posting_cooldown_days"] = amount * multiplier
    elif "once per week" in text or "one post per week" in text:
        parsed["posting_cooldown_days"] = 7

    karma_match = re.search(r"(\d+)\s+(?:comment\s+)?karma", text)
    if karma_match:
        parsed["karma_requirement"] = f"{karma_match.group(1)} karma"

    age_match = re.search(r"account.*?(\d+)\s+(day|days|week|weeks|month|months)", text)
    if age_match:
        parsed["account_age_requirement"] = f"{age_match.group(1)} {age_match.group(2)}"

    if any(term in text for term in ("comment before dm", "comment before messaging", "comment before pm", "comment first")):
        parsed["comment_before_dm_required"] = True

    banned_topics = []
    for topic in ("spam", "repost", "adult", "nsfw", "homework", "essay", "fake reviews", "vote manipulation", "mass dm", "account creation", "captcha bypass"):
        if topic in text:
            banned_topics.append(topic)
    parsed["banned_topics"] = dedupe_keep_order(banned_topics)

    if "vague" in text:
        parsed["notes"].append("Rules mention avoiding vague posts.")
    if "spam" in text or "repost" in text:
        parsed["notes"].append("Rules mention spam/repost limits.")

    parsed["required_sections"] = dedupe_keep_order(parsed["required_sections"])
    return parsed, warnings


def calculate_rules_confidence(source_flags: Dict[str, Any], parsed: Dict[str, Any], warnings: List[str]) -> float:
    confidence = 0.0
    if source_flags.get("rules_page"):
        confidence += 0.25
    if source_flags.get("wiki_page"):
        confidence += 0.15
    if source_flags.get("explicit_for_hire"):
        confidence += 0.15
    if source_flags.get("price_rule") or parsed.get("price_required") is not None:
        confidence += 0.15
    if source_flags.get("cooldown_rule") or parsed.get("posting_cooldown_days") is not None:
        confidence += 0.10
    if source_flags.get("source_error_count", 0) >= 3:
        confidence -= 0.25
    if any("both allow and deny" in warning.lower() for warning in warnings):
        confidence -= 0.20
    return round(max(0.0, min(1.0, confidence)), 2)


def summarize_rules_text(raw_text: str) -> str:
    text = clean_text(raw_text)
    if len(text) <= 800:
        return text
    return text[:800].rstrip() + "..."


def normalize_rules_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    normalized = default_subreddit_rules_entry()
    normalized.update(entry)
    parsed = default_subreddit_rules_entry()["parsed"]
    parsed.update(normalized.get("parsed", {}))
    normalized["parsed"] = parsed
    normalized.setdefault("warnings", [])
    normalized.setdefault("source_urls", [])
    normalized.setdefault("raw_summary", "")
    normalized.setdefault("confidence", 0.0)
    return normalized


def load_for_hire_posts() -> Dict[str, Any]:
    default_data = {"posts": [], "stats": {}}

    if not FOR_HIRE_POSTS_PATH.exists():
        save_json(FOR_HIRE_POSTS_PATH, default_data)
        return default_data

    try:
        with FOR_HIRE_POSTS_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError) as exc:
        logging.error("Could not read for_hire_posts.json: %s", exc)
        return default_data

    if not isinstance(data, dict):
        return default_data

    data.setdefault("posts", [])
    data.setdefault("stats", {})

    if not isinstance(data["posts"], list):
        data["posts"] = []
    if not isinstance(data["stats"], dict):
        data["stats"] = {}

    return data


def save_for_hire_posts(data: Dict[str, Any]) -> None:
    save_json(FOR_HIRE_POSTS_PATH, data)


def ensure_for_hire_stats(data: Dict[str, Any], subreddit: str) -> Dict[str, int]:
    stats = data.setdefault("stats", {})
    subreddit_stats = stats.setdefault(
        subreddit,
        {"suggested": 0, "posted": 0, "replies": 0, "good_leads": 0, "bad_leads": 0},
    )

    for key in ("suggested", "posted", "replies", "good_leads", "bad_leads"):
        subreddit_stats.setdefault(key, 0)

    return subreddit_stats


def run_for_hire_assistant(config: Dict[str, Any]) -> None:
    if not get_config_bool(config, "FOR_HIRE_ASSISTANT_ENABLED"):
        return

    data = load_for_hire_posts()
    subreddit = choose_for_hire_subreddit(config, data)
    if not subreddit:
        logging.info("For Hire Assistant: no eligible subreddit right now.")
        save_for_hire_posts(data)
        return

    record, message = create_for_hire_suggestion(subreddit, config, data)
    data["posts"].append(record)
    ensure_for_hire_stats(data, subreddit)["suggested"] += 1
    save_for_hire_posts(data)

    if send_telegram_message(message, config):
        logging.info("For Hire Assistant suggested a manual post for r/%s.", subreddit)


def choose_for_hire_subreddit(config: Dict[str, Any], data: Dict[str, Any]) -> Optional[str]:
    max_posts_per_week = get_config_int(config, "FOR_HIRE_MAX_POSTS_PER_WEEK")
    now = time.time()
    week_ago = now - 7 * 24 * 60 * 60

    recent_suggestions = [
        post for post in data.get("posts", [])
        if parse_iso_timestamp(post.get("suggested_at") or post.get("planned_at")) >= week_ago
    ]
    if len(recent_suggestions) >= max_posts_per_week:
        return None

    eligible = []
    for subreddit in get_config_list(config, "FOR_HIRE_SUBREDDITS"):
        rules_entry = get_cached_or_fetch_rules(subreddit, config) if get_config_bool(config, "RULES_ASSISTANT_ENABLED") else default_subreddit_rules_entry()
        cooldown_days = get_for_hire_cooldown_days(config, rules_entry)
        min_gap_seconds = max(1, cooldown_days) * 24 * 60 * 60
        last_activity = latest_for_hire_activity_timestamp(data, subreddit)
        if last_activity == 0 or now - last_activity >= min_gap_seconds:
            eligible.append(subreddit)

    if not eligible:
        return None

    random.shuffle(eligible)
    return eligible[0]


def latest_for_hire_activity_timestamp(data: Dict[str, Any], subreddit: str) -> float:
    latest = 0.0
    for post in data.get("posts", []):
        if str(post.get("subreddit", "")).lower() != subreddit.lower():
            continue

        latest = max(
            latest,
            parse_iso_timestamp(post.get("suggested_at") or post.get("planned_at")),
            parse_iso_timestamp(post.get("marked_posted_at")),
        )

    return latest


def create_for_hire_suggestion(subreddit: str, config: Dict[str, Any], data: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    rules_entry = get_cached_or_fetch_rules(subreddit, config) if get_config_bool(config, "RULES_ASSISTANT_ENABLED") else default_subreddit_rules_entry()
    title, draft, status, warnings = generate_for_hire_draft(subreddit, config, data, rules_entry)
    confidence = float(rules_entry.get("confidence", 0.0))
    record = {
        "subreddit": subreddit,
        "suggested_at": local_now_iso(),
        "rules_confidence": confidence,
        "status": status,
        "title": title,
        "draft": draft,
        "warnings": warnings,
        "marked_posted_at": None,
        "replies": 0,
        "good_leads": 0,
        "bad_leads": 0,
    }
    message = format_for_hire_reminder(subreddit, title, draft, rules_entry, status, warnings)
    return record, message


def generate_for_hire_draft(
    subreddit: str,
    config: Dict[str, Any],
    data: Optional[Dict[str, Any]] = None,
    rules_entry: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, str, List[str]]:
    rules_entry = normalize_rules_entry(rules_entry or default_subreddit_rules_entry())
    parsed = rules_entry["parsed"]
    warnings = list(rules_entry.get("warnings", []))
    confidence = float(rules_entry.get("confidence", 0.0))
    min_confidence = float(config.get("RULES_CONFIDENCE_MIN_TO_SUGGEST", DEFAULT_CONFIG["RULES_CONFIDENCE_MIN_TO_SUGGEST"]))
    status = "safe"

    if confidence < min_confidence:
        status = "low_confidence"
        warnings.append("Low confidence rules parsing. Manually verify subreddit rules before posting.")

    if parsed.get("allows_for_hire") is False:
        status = "risky"
        warnings.append("This subreddit may not allow For Hire posts.")
        return (
            "Draft not recommended",
            "Draft not generated because this subreddit may not allow For Hire posts. Manually verify the rules before posting.",
            status,
            dedupe_keep_order(warnings),
        )

    if parsed.get("flair_required"):
        flair = parsed.get("required_flair") or "check subreddit rules"
        warnings.append(f"Select required flair manually: {flair}")

    min_fixed_price = parsed.get("min_fixed_price")
    if min_fixed_price and min_fixed_price > max_configured_price(config):
        warnings.append("Your configured price may be below subreddit minimum.")

    banned_service_warnings = find_banned_service_warnings(config, parsed)
    if banned_service_warnings:
        status = "risky"
        warnings.extend(banned_service_warnings)

    existing_pairs = set()
    if data:
        existing_pairs = {
            (str(post.get("title", "")), str(post.get("draft", "")))
            for post in data.get("posts", [])
        }

    fallback: Tuple[str, str] = ("", "")
    for _ in range(10):
        title, draft = build_for_hire_draft(subreddit, config, rules_entry)
        fallback = (title, draft)
        if (title, draft) not in existing_pairs:
            return title, draft, status, dedupe_keep_order(warnings)

    return fallback[0], fallback[1], status, dedupe_keep_order(warnings)


def build_for_hire_draft(subreddit: str, config: Dict[str, Any], rules_entry: Dict[str, Any]) -> Tuple[str, str]:
    parsed = rules_entry["parsed"]
    price_range = get_config_str(config, "FOR_HIRE_PRICE_RANGE")
    small_price_range = get_config_str(config, "FOR_HIRE_SMALL_PRICE_RANGE")
    medium_price_range = get_config_str(config, "FOR_HIRE_MEDIUM_PRICE_RANGE")
    services = get_config_list(config, "FOR_HIRE_SERVICES")
    github_url = get_config_str(config, "FOR_HIRE_GITHUB_URL")
    tag = get_required_title_tag(parsed)
    title_template = random.choice(FOR_HIRE_TITLE_TEMPLATES)
    opening = random.choice(FOR_HIRE_OPENINGS)
    title = title_template.format(tag=tag, price_range=price_range)
    services_block = "\n".join(f"- {service}" for service in services)
    required_sections = parsed.get("required_sections") or []
    extra_sections = []
    for section in required_sections:
        if section.lower() in ("pricing", "portfolio/github"):
            continue
        extra_sections.append(f"{section}:\n- Please review this section manually for r/{subreddit}.")

    draft = (
        f"{opening}\n\n"
        "I can help with:\n"
        f"{services_block}\n\n"
        "Pricing:\n"
        f"Small tasks: {small_price_range}\n"
        f"Medium tasks: {medium_price_range}\n\n"
        f"GitHub: {github_url}\n\n"
        "Send me what you need, and I'll tell you if I can do it."
    )
    if extra_sections:
        draft += "\n\n" + "\n\n".join(extra_sections)

    return title, draft


def format_for_hire_reminder(
    subreddit: str,
    title: str,
    draft: str,
    rules_entry: Dict[str, Any],
    status: str,
    warnings: List[str],
) -> str:
    parsed = rules_entry["parsed"]
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    return (
        "\U0001f4dd For Hire draft ready\n\n"
        f"Subreddit: r/{subreddit}\n\n"
        f"Rules confidence: {float(rules_entry.get('confidence', 0.0)):.2f}\n"
        f"Status: {status}\n\n"
        "Rules summary:\n"
        f"- Allows For Hire: {format_unknown_bool(parsed.get('allows_for_hire'))}\n"
        f"- Required title tag: {', '.join(parsed.get('title_required_tags') or []) or 'unknown'}\n"
        f"- Price required: {format_unknown_bool(parsed.get('price_required'))}\n"
        f"- Min price: {parsed.get('min_fixed_price') or parsed.get('min_hourly_rate') or 'unknown'}\n"
        f"- Portfolio required: {format_unknown_bool(parsed.get('portfolio_required'))}\n"
        f"- Flair required: {format_unknown_bool(parsed.get('flair_required'))}\n"
        f"- Cooldown: {parsed.get('posting_cooldown_days') or 'unknown'} days\n\n"
        "Suggested title:\n"
        f"{title}\n\n"
        "Draft:\n"
        f"{draft}\n\n"
        "Warnings:\n"
        f"{warning_lines}\n\n"
        "Manual action:\n"
        "Read the rules summary, open the subreddit rules if needed, then post manually."
    )


def get_for_hire_cooldown_days(config: Dict[str, Any], rules_entry: Dict[str, Any]) -> int:
    parsed_cooldown = normalize_rules_entry(rules_entry)["parsed"].get("posting_cooldown_days")
    if isinstance(parsed_cooldown, (int, float)) and parsed_cooldown > 0:
        return int(parsed_cooldown)
    return get_config_int(config, "FOR_HIRE_MIN_DAYS_BETWEEN_SAME_SUBREDDIT")


def get_required_title_tag(parsed: Dict[str, Any]) -> str:
    tags = parsed.get("title_required_tags") or []
    if tags:
        preferred = ("[For Hire]", "[Offer]", "[Hiring]", "[Task]", "[Job]", "[Gig]")
        for tag in preferred:
            if tag.lower() in {str(item).lower() for item in tags}:
                return tag
        return str(tags[0])
    return "[For Hire]"


def max_configured_price(config: Dict[str, Any]) -> float:
    values = []
    for key in ("FOR_HIRE_PRICE_RANGE", "FOR_HIRE_SMALL_PRICE_RANGE", "FOR_HIRE_MEDIUM_PRICE_RANGE"):
        values.extend(float(value) for value in re.findall(r"\$(\d+(?:\.\d+)?)", get_config_str(config, key)))
    return max(values) if values else 0.0


def find_banned_service_warnings(config: Dict[str, Any], parsed: Dict[str, Any]) -> List[str]:
    service_text = normalize_text(" ".join(get_config_list(config, "FOR_HIRE_SERVICES")))
    banned_terms = list(parsed.get("banned_topics") or [])
    banned_terms.extend(get_config_list(config, "FOR_HIRE_BANNED_SERVICE_WORDS"))
    warnings = []
    for term in dedupe_keep_order(banned_terms):
        normalized_term = normalize_text(term)
        if normalized_term and normalized_term in service_text:
            warnings.append(f"Configured service may conflict with banned topic: {term}")
    return warnings


def format_unknown_bool(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unknown"


def get_for_hire_status_text(data: Dict[str, Any]) -> str:
    lines = ["For Hire Assistant status", ""]
    posts = data.get("posts", [])

    if posts:
        lines.append("Recent suggestions:")
        for post in posts[-10:]:
            marked = post.get("marked_posted_at") or "-"
            lines.append(
                f"- r/{post.get('subreddit')} | {post.get('status')} | "
                f"suggested {post.get('suggested_at') or post.get('planned_at')} | posted {marked}"
            )
    else:
        lines.append("No suggestions yet.")

    lines.append("")
    lines.append("Stats:")
    stats = data.get("stats", {})
    if stats:
        for subreddit, values in sorted(stats.items()):
            lines.append(
                f"- r/{subreddit}: suggested={values.get('suggested', 0)}, "
                f"posted={values.get('posted', 0)}, replies={values.get('replies', 0)}, "
                f"good={values.get('good_leads', 0)}, bad={values.get('bad_leads', 0)}"
            )
    else:
        lines.append("- none")

    return "\n".join(lines)


def mark_for_hire_posted(data: Dict[str, Any], subreddit: str) -> bool:
    for post in reversed(data.get("posts", [])):
        if str(post.get("subreddit", "")).lower() != subreddit.lower():
            continue
        if post.get("marked_posted_at"):
            continue

        post["marked_posted_at"] = local_now_iso()
        ensure_for_hire_stats(data, str(post.get("subreddit")))["posted"] += 1
        return True

    return False


def record_for_hire_reply(data: Dict[str, Any], subreddit: str, quality: str) -> None:
    stats = ensure_for_hire_stats(data, subreddit)
    stats["replies"] += 1
    if quality == "good":
        stats["good_leads"] += 1
    else:
        stats["bad_leads"] += 1

    for post in reversed(data.get("posts", [])):
        if str(post.get("subreddit", "")).lower() != subreddit.lower():
            continue
        post["replies"] = int(post.get("replies", 0)) + 1
        if quality == "good":
            post["good_leads"] = int(post.get("good_leads", 0)) + 1
        else:
            post["bad_leads"] = int(post.get("bad_leads", 0)) + 1
        break


def parse_iso_timestamp(value: Any) -> float:
    if not value:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return 0.0

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def local_now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def handle_for_hire_cli(args: argparse.Namespace, config: Dict[str, Any]) -> bool:
    if args.command is None:
        return False

    if args.command == "rules-check":
        subreddits = [args.subreddit] if args.subreddit else get_config_list(config, "FOR_HIRE_SUBREDDITS")
        rules_cache = load_subreddit_rules()
        for index, subreddit in enumerate(subreddits):
            entry = get_cached_or_fetch_rules(subreddit, config, force=True)
            rules_cache[subreddit] = entry
            print(f"Checked r/{subreddit}: confidence={entry.get('confidence', 0.0):.2f}")
            if get_config_bool(config, "RULES_FETCH_ENABLED") and index < len(subreddits) - 1:
                time.sleep(max(0, get_config_int(config, "RULES_REQUEST_DELAY_SECONDS")))
        save_subreddit_rules(rules_cache)
        return True

    if args.command == "rules-show":
        rules_cache = load_subreddit_rules()
        entry = rules_cache.get(args.subreddit)
        if not entry:
            print(f"No cached rules found for r/{args.subreddit}. Run rules-check first.")
        else:
            print(json.dumps(normalize_rules_entry(entry), indent=2, ensure_ascii=False))
        return True

    data = load_for_hire_posts()

    if args.command == "forhire-draft":
        record, message = create_for_hire_suggestion(args.subreddit, config, data)
        data["posts"].append(record)
        ensure_for_hire_stats(data, args.subreddit)["suggested"] += 1
        save_for_hire_posts(data)
        print(message)
        return True

    if args.command == "forhire-status":
        print(get_for_hire_status_text(data))
        return True

    if args.command == "forhire-posted":
        if mark_for_hire_posted(data, args.subreddit):
            save_for_hire_posts(data)
            print(f"Marked latest suggested draft for r/{args.subreddit} as posted.")
        else:
            print(f"No suggested draft found for r/{args.subreddit}.")
        return True

    if args.command == "forhire-reply":
        record_for_hire_reply(data, args.subreddit, args.quality)
        save_for_hire_posts(data)
        print(f"Recorded {args.quality} reply for r/{args.subreddit}.")
        return True

    logging.error("Unknown command: %s", args.command)
    return True


def cleanup_seen_posts(seen_posts: Dict[str, Any], retention_days: int) -> Dict[str, Any]:
    cutoff_timestamp = time.time() - max(retention_days, 1) * 24 * 60 * 60
    cleaned_posts = {}

    for post_id, seen_at in seen_posts.get("posts", {}).items():
        seen_timestamp = parse_seen_timestamp(seen_at)
        if seen_timestamp >= cutoff_timestamp:
            cleaned_posts[post_id] = seen_at

    seen_posts["posts"] = cleaned_posts
    return seen_posts


def parse_seen_timestamp(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, dict):
        value = value.get("seen_at")

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return time.time()

    return time.time()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def send_telegram_message(message: str, config: Dict[str, Any]) -> bool:
    if config.get("DRY_RUN", False):
        print("\n--- DRY RUN TELEGRAM MESSAGE ---")
        print(message)
        print("--- END MESSAGE ---\n")
        return True

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        logging.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID. Enable DRY_RUN or update .env.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": False,
    }

    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.error("Telegram API error: %s", exc)
        return False

    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor Reddit RSS quick work posts and send Telegram alerts.")
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="Send one test Telegram message and exit.",
    )
    subparsers = parser.add_subparsers(dest="command")

    rules_check_parser = subparsers.add_parser("rules-check", help="Fetch and parse subreddit rules.")
    rules_check_parser.add_argument("subreddit", nargs="?", help="Optional subreddit name. If omitted, checks all For Hire subreddits.")

    rules_show_parser = subparsers.add_parser("rules-show", help="Show cached parsed rules for a subreddit.")
    rules_show_parser.add_argument("subreddit", help="Subreddit name, for example freelance_forhire.")

    draft_parser = subparsers.add_parser("forhire-draft", help="Generate and save a rules-aware For Hire draft.")
    draft_parser.add_argument("subreddit", help="Subreddit name, for example freelance_forhire.")

    subparsers.add_parser("forhire-status", help="Show For Hire Assistant suggestion and stats history.")

    posted_parser = subparsers.add_parser("forhire-posted", help="Mark the latest suggested draft as posted.")
    posted_parser.add_argument("subreddit", help="Subreddit name, for example freelance_forhire.")

    reply_parser = subparsers.add_parser("forhire-reply", help="Record a good or bad reply for a subreddit.")
    reply_parser.add_argument("subreddit", help="Subreddit name, for example freelance_forhire.")
    reply_parser.add_argument("quality", choices=("good", "bad"), help="Reply quality.")

    return parser.parse_args()


def calculate_score(post: Dict[str, Any]) -> Tuple[int, List[str], List[str]]:
    text = normalize_text(f"{post.get('title', '')} {post.get('summary', '')}")
    subreddit_lower = str(post.get("subreddit", "")).lower()
    age_minutes = get_post_age_minutes(post)
    score = 0.0
    matched: List[str] = []
    suspicious_words: List[str] = []

    found_good_tags = [tag for tag in GOOD_TAGS if has_tag(text, tag)]
    if found_good_tags:
        score += 3
        matched.extend(f"[{tag.title()}]" for tag in found_good_tags)

    if has_tag(text, OFFER_TAG):
        matched.append("[Offer]")

    for phrase in STRONG_PHRASES:
        if phrase in text:
            score += 2
            matched.append(phrase)

    if age_minutes < 15:
        score += 2
        matched.append("fresh post")

    positive_matches = unique_matches(text, POSITIVE_KEYWORDS)
    if positive_matches:
        score += min(2, len(positive_matches) * 0.5)
        matched.extend(positive_matches)

    for phrase, penalty in NEGATIVE_PHRASES.items():
        if phrase in text:
            score += penalty
            suspicious_words.append(phrase)

    if subreddit_lower in CRYPTO_SUBREDDITS:
        matched.append("crypto subreddit rules applied")

    score = int(round(max(0, min(10, score))))
    return score, dedupe_keep_order(matched), dedupe_keep_order(suspicious_words)


def should_skip_offer_post(post: Dict[str, Any]) -> bool:
    text = normalize_text(f"{post.get('title', '')} {post.get('summary', '')}")

    if not has_tag(text, OFFER_TAG):
        return False

    has_seller_language = any(phrase in text for phrase in OFFER_SELLER_PHRASES)
    has_task_language = any(phrase in text for phrase in OFFER_TASK_PHRASES)

    return has_seller_language and not has_task_language


def format_post_message(
    post: Dict[str, Any],
    score: int,
    matched: Iterable[str],
    suspicious_words: Iterable[str],
) -> str:
    age_minutes = int(get_post_age_minutes(post))

    message_lines = [
        "⚡ New quick work post",
        "",
        f"Title: {post.get('title', '').strip()}",
        f"Subreddit: r/{post.get('subreddit', 'unknown')}",
        f"Age: {age_minutes} min",
        "Comments: unknown",
        f"Score: {score}/10",
        f"Matched: {', '.join(matched) if matched else 'none'}",
        f"Link: {post.get('link', '')}",
    ]

    suspicious_words = list(suspicious_words)
    if suspicious_words:
        message_lines.append(f"Warning: suspicious words found: {', '.join(suspicious_words)}")

    return "\n".join(message_lines)


def check_subreddits(
    group_name: str,
    subreddits: List[str],
    config: Dict[str, Any],
    seen_posts: Dict[str, Any],
    rate_limit_cooldowns: Dict[str, float],
    rate_limit_counts: Dict[str, int],
) -> None:
    initialized_groups = seen_posts.setdefault("initialized_groups", {"fast": False, "slow": False})
    initialized = bool(initialized_groups.get(group_name, False))
    max_age_minutes = get_config_int(config, "MAX_POST_AGE_MINUTES")
    min_score = get_config_int(config, "MIN_SCORE")
    limit = get_config_int(config, "RSS_LIMIT")
    request_delay_min = get_config_int(config, "REQUEST_DELAY_MIN_SECONDS")
    request_delay_max = get_config_int(config, "REQUEST_DELAY_MAX_SECONDS")
    base_cooldown_seconds = get_config_int(config, "RATE_LIMIT_BASE_COOLDOWN_SECONDS")
    max_cooldown_seconds = get_config_int(config, "RATE_LIMIT_MAX_COOLDOWN_SECONDS")
    user_agent = get_config_str(config, "USER_AGENT")
    now_iso = utc_now_iso()

    for subreddit_name in subreddits:
        subreddit_key = subreddit_name.lower()
        cooldown_until = rate_limit_cooldowns.get(subreddit_key, 0)
        now = time.time()

        if cooldown_until > now:
            logging.info("r/%s is on cooldown, skipping", subreddit_name)
            continue

        try:
            posts = fetch_rss_posts(subreddit_name, limit, user_agent)
        except RateLimitError as exc:
            rate_limit_count = rate_limit_counts.get(subreddit_key, 0) + 1
            rate_limit_counts[subreddit_key] = rate_limit_count
            backoff_seconds = min(
                base_cooldown_seconds * (2 ** (rate_limit_count - 1)),
                max_cooldown_seconds,
            )
            cooldown_seconds = exc.retry_after_seconds if exc.retry_after_seconds is not None else backoff_seconds
            cooldown_until = time.time() + cooldown_seconds
            rate_limit_cooldowns[subreddit_key] = cooldown_until
            cooldown_time = datetime.fromtimestamp(cooldown_until).strftime("%H:%M:%S")
            cooldown_minutes = max(1, int(round(cooldown_seconds / 60)))
            logging.warning(
                "r/%s rate limited. Cooldown: %d min, until %s",
                subreddit_name,
                cooldown_minutes,
                cooldown_time,
            )
            continue
        except requests.RequestException as exc:
            logging.error("RSS request error while reading r/%s: %s", subreddit_name, exc)
            continue
        except Exception as exc:
            logging.error("RSS parse error while reading r/%s: %s", subreddit_name, exc)
            continue
        finally:
            sleep_between_requests(request_delay_min, request_delay_max)

        rate_limit_counts[subreddit_key] = 0
        rate_limit_cooldowns.pop(subreddit_key, None)

        for post in reversed(posts):
            post_id = post.get("id")
            if not post_id or post_id in seen_posts["posts"]:
                continue

            seen_posts["posts"][post_id] = now_iso

            if not initialized:
                continue

            age_minutes = get_post_age_minutes(post)
            if age_minutes > max_age_minutes:
                logging.info("Skipping old post %s from r/%s (%d min old).", post_id, subreddit_name, age_minutes)
                continue

            if should_skip_offer_post(post):
                logging.info("Skipping likely freelancer [Offer] post %s from r/%s.", post_id, subreddit_name)
                continue

            score, matched, suspicious_words = calculate_score(post)
            if score < min_score:
                logging.info(
                    "Skipping low-score post %s from r/%s (score %s/%s).",
                    post_id,
                    subreddit_name,
                    score,
                    min_score,
                )
                continue

            message = format_post_message(post, score, matched, suspicious_words)
            if send_telegram_message(message, config):
                logging.info("Sent alert for post %s from r/%s.", post_id, subreddit_name)

    if not initialized:
        initialized_groups[group_name] = True
        seen_posts.setdefault("initialized_group_subreddits", {"fast": [], "slow": []})[group_name] = subreddits
        seen_posts["initialized"] = all(bool(initialized_groups.get(name, False)) for name in ("fast", "slow"))
        logging.info(
            "First %s run complete. Existing posts were marked as seen without Telegram alerts.",
            group_name,
        )

    save_seen_posts(seen_posts)


def fetch_rss_posts(subreddit_name: str, limit: int, user_agent: str) -> List[Dict[str, Any]]:
    url = RSS_URL_TEMPLATE.format(subreddit=subreddit_name, limit=limit)
    headers = {
        "User-Agent": user_agent,
        "Accept": RSS_ACCEPT_HEADER,
    }
    response = requests.get(url, headers=headers, timeout=20)

    if response.status_code == 429:
        raise RateLimitError(subreddit_name, parse_retry_after(response.headers.get("Retry-After")))

    response.raise_for_status()

    feed = feedparser.parse(response.content)
    if getattr(feed, "bozo", False):
        logging.warning("RSS feed for r/%s had parse warnings: %s", subreddit_name, feed.get("bozo_exception"))

    posts = []
    for entry in feed.entries[:limit]:
        posts.append(
            {
                "id": entry.get("id") or entry.get("link"),
                "title": clean_text(entry.get("title", "")),
                "summary": clean_text(entry.get("summary", "")),
                "subreddit": subreddit_name,
                "created_utc": parse_entry_timestamp(entry),
                "link": entry.get("link", ""),
            }
        )

    return posts


def parse_retry_after(value: Optional[str]) -> Optional[int]:
    if not value:
        return None

    value = value.strip()
    if value.isdigit():
        return max(1, int(value))

    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None

    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)

    retry_seconds = int((retry_at - datetime.now(timezone.utc)).total_seconds())
    return max(1, retry_seconds)


def sleep_between_requests(delay_min: int, delay_max: int) -> None:
    if delay_max < delay_min:
        delay_min, delay_max = delay_max, delay_min

    delay = random.uniform(max(0, delay_min), max(0, delay_max))
    if delay > 0:
        time.sleep(delay)


def parse_entry_timestamp(entry: Any) -> float:
    parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed_time:
        return float(calendar.timegm(parsed_time))
    return time.time()


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def has_tag(text: str, tag: str) -> bool:
    escaped_tag = re.escape(tag.lower())
    return bool(re.search(rf"\[\s*{escaped_tag}\s*\]", text))


def unique_matches(text: str, phrases: Iterable[str]) -> List[str]:
    return [phrase for phrase in phrases if phrase in text]


def dedupe_keep_order(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def get_post_age_minutes(post: Dict[str, Any]) -> int:
    created_utc = float(post.get("created_utc") or time.time())
    return max(0, int((time.time() - created_utc) / 60))


def main() -> None:
    setup_logging()
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        logging.warning(".env not found. Telegram sending will not work until you create it from .env.example.")
    load_dotenv(env_path)

    args = parse_args()
    config = load_config()
    ensure_runtime_files_exist()

    if args.test_telegram:
        test_message = (
            "⚡ Reddit Quick Work Alert Bot test\n\n"
            "Telegram delivery is configured correctly."
        )
        if send_telegram_message(test_message, config):
            logging.info("Telegram test message sent successfully.")
        return

    if handle_for_hire_cli(args, config):
        return

    seen_posts = load_seen_posts()
    seen_posts = sync_seen_group_bootstrap_state(seen_posts, config)
    seen_posts = cleanup_seen_posts(
        seen_posts,
        get_config_int(config, "SEEN_POST_RETENTION_DAYS"),
    )
    save_seen_posts(seen_posts)

    fast_subreddits = get_config_list(config, "FAST_SUBREDDITS")
    slow_subreddits = get_config_list(config, "SLOW_SUBREDDITS")
    fast_interval = get_config_int(config, "FAST_CHECK_INTERVAL_SECONDS")
    slow_interval = get_config_int(config, "SLOW_CHECK_INTERVAL_SECONDS")
    jitter_min = get_config_int(config, "JITTER_MIN_SECONDS")
    jitter_max = get_config_int(config, "JITTER_MAX_SECONDS")
    for_hire_enabled = get_config_bool(config, "FOR_HIRE_ASSISTANT_ENABLED")
    for_hire_interval = get_config_int(config, "FOR_HIRE_CHECK_INTERVAL_SECONDS")

    logging.info("Reddit Quick Work Alert Bot started.")
    logging.info("Fast Reddit RSS feeds: %s", ", ".join(fast_subreddits))
    logging.info("Slow Reddit RSS feeds: %s", ", ".join(slow_subreddits))
    rate_limit_cooldowns: Dict[str, float] = {}
    rate_limit_counts: Dict[str, int] = {}
    next_fast_check = 0.0
    next_slow_check = 0.0
    next_for_hire_check = 0.0

    while True:
        try:
            now = time.time()

            if now >= next_fast_check:
                logging.info("Starting fast subreddit check.")
                check_subreddits("fast", fast_subreddits, config, seen_posts, rate_limit_cooldowns, rate_limit_counts)
                next_fast_check = calculate_next_check(fast_interval, jitter_min, jitter_max)

            now = time.time()
            if now >= next_slow_check:
                logging.info("Starting slow subreddit check.")
                check_subreddits("slow", slow_subreddits, config, seen_posts, rate_limit_cooldowns, rate_limit_counts)
                next_slow_check = calculate_next_check(slow_interval, jitter_min, jitter_max)

            now = time.time()
            if for_hire_enabled and now >= next_for_hire_check:
                logging.info("Starting For Hire Assistant check.")
                run_for_hire_assistant(config)
                next_for_hire_check = calculate_next_check(for_hire_interval, 0, 0)
        except KeyboardInterrupt:
            logging.info("Bot stopped by user.")
            break
        except Exception as exc:
            logging.exception("Unexpected error during check cycle: %s", exc)

        due_times = [next_fast_check, next_slow_check]
        if for_hire_enabled:
            due_times.append(next_for_hire_check)
        next_due = min(due_times)
        sleep_seconds = max(1, min(30, next_due - time.time()))
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
