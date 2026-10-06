from __future__ import annotations

import html
import json
import logging
import math
import os
import re
import tempfile
import threading
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


APP_DIR = Path(__file__).resolve().parent
DEFAULT_REGISTRY_FILE = APP_DIR / "batches.txt"
DEFAULT_API_BASE = "https://gdgoenkaratia.com"
DEFAULT_LIST_ENDPOINTS = (
    "/api/courses/active?userId={user_id}",
    "/api/courses/purchased?userId={user_id}",
)

BATCH_ID_RE = re.compile(r"^[0-9a-fA-F]{24}$")
TOPIC_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,128}$")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)
MEDIA_EXTENSIONS = {
    ".pdf": "document",
    ".doc": "document",
    ".docx": "document",
    ".ppt": "document",
    ".pptx": "document",
    ".xls": "document",
    ".xlsx": "document",
    ".zip": "document",
    ".mp4": "video",
    ".m3u8": "video",
    ".mkv": "video",
    ".webm": "video",
}
DOCUMENT_HINTS = (
    "pdf",
    "note",
    "handwritten",
    "sheet",
    "dpp",
    "document",
    "attachment",
    "ebook",
    "material",
    "booklet",
    "assignment",
)
VIDEO_HINTS = ("video", "recording", "mp4", "m3u8", "hls", "lecture")
API_LINK_HINTS = ("sheet", "note", "pdf", "document", "material", "dpp", "attachment")
ID_KEYS = ("id", "_id", "courseId", "batchId")
TITLE_KEYS = ("courseName", "batchName", "title", "name")
URL_KEYS = (
    "url",
    "fileUrl",
    "fileURL",
    "pdfUrl",
    "pdfURL",
    "videoUrl",
    "downloadUrl",
    "attachmentUrl",
    "documentUrl",
    "mediaUrl",
    "href",
    "link",
    "file",
    "path",
)
NAME_KEYS = (
    "displayName",
    "fileName",
    "pdfName",
    "noteName",
    "notesName",
    "documentName",
    "className",
    "classTitle",
    "lectureTitle",
    "topicName",
    "sectionName",
    "title",
    "name",
)


def clean_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or default


def safe_filename(value: str, fallback: str = "batch") -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", clean_text(value))
    value = value.strip(" ._")
    return (value[:120] or fallback).strip()


def split_env_list(name: str, defaults: Sequence[str] = ()) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return list(defaults)
    if raw.startswith("["):
        try:
            value = json.loads(raw)
            if isinstance(value, list):
                return [clean_text(item) for item in value if clean_text(item)]
        except json.JSONDecodeError:
            pass
    return [item.strip() for item in raw.split(";") if item.strip()]


def iter_dicts(value: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[dict[str, Any], tuple[str, ...]]]:
    if isinstance(value, dict):
        yield value, path
        for key, child in value.items():
            yield from iter_dicts(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_dicts(child, path + (str(index),))


@dataclass(frozen=True)
class Batch:
    course_id: str
    title: str


class BatchRegistry:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()

    def load(self) -> list[Batch]:
        with self._lock:
            if not self.path.exists():
                return []
            batches: OrderedDict[str, Batch] = OrderedDict()
            for raw_line in self.path.read_text(encoding="utf-8-sig").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "|" in line:
                    course_id, title = line.split("|", 1)
                elif "\t" in line:
                    course_id, title = line.split("\t", 1)
                else:
                    continue
                course_id = clean_text(course_id).lower()
                title = clean_text(title, f"Batch {course_id}")
                if BATCH_ID_RE.fullmatch(course_id):
                    batches[course_id] = Batch(course_id, title)
            return list(batches.values())

    def save(self, batches: Iterable[Batch]) -> None:
        with self._lock:
            merged: OrderedDict[str, Batch] = OrderedDict()
            for batch in batches:
                course_id = clean_text(batch.course_id).lower()
                if not BATCH_ID_RE.fullmatch(course_id):
                    continue
                title = clean_text(batch.title, f"Batch {course_id}").replace("|", "-")
                merged[course_id] = Batch(course_id, title)

            self.path.parent.mkdir(parents=True, exist_ok=True)
            header = (
                "# Selection Way batch registry (UTF-8)\n"
                "# Format: BATCH_ID|COURSE_NAME\n"
                "# This file is auto-merged. You can also add rows manually.\n"
            )
            body = "".join(f"{b.course_id}|{b.title}\n" for b in merged.values())
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent)
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(header + body)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_name, self.path)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)

    def merge(self, additions: Iterable[Batch], prefer_new_titles: bool = True) -> tuple[int, int]:
        with self._lock:
            merged: OrderedDict[str, Batch] = OrderedDict((b.course_id, b) for b in self.load())
            added = 0
            updated = 0
            for batch in additions:
                course_id = clean_text(batch.course_id).lower()
                if not BATCH_ID_RE.fullmatch(course_id):
                    continue
                title = clean_text(batch.title, f"Batch {course_id}")
                current = merged.get(course_id)
                if current is None:
                    merged[course_id] = Batch(course_id, title)
                    added += 1
                elif prefer_new_titles and title and title != current.title and not title.startswith("Batch "):
                    merged[course_id] = Batch(course_id, title)
                    updated += 1
            self.save(merged.values())
            return added, updated

    def resolve(self, value: str) -> Batch | None:
        text = clean_text(value)
        batches = self.load()
        if text.isdigit():
            index = int(text) - 1
            if 0 <= index < len(batches):
                return batches[index]
        candidate_id = text.split("|", 1)[0].strip().lower()
        for batch in batches:
            if batch.course_id == candidate_id:
                return batch
        return None


class APIRequestError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class CourseAPI:
    def __init__(self, base_url: str, user_id: str, auth_token: str = "", cookie: str = ""):
        self.base_url = base_url.rstrip("/") + "/"
        self.user_id = clean_text(user_id)
        self.base_host = (urlparse(self.base_url).hostname or "").lower()
        self.session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.7,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(("GET",)),
            respect_retry_after_header=True,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8))
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SelectionWayAuthorizedExporter/2.0",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.selectionway.com/",
            }
        )
        if auth_token:
            token = auth_token.strip()
            self.session.headers["Authorization"] = token if " " in token else f"Bearer {token}"
        if cookie:
            self.session.headers["Cookie"] = cookie.strip()

    def close(self) -> None:
        self.session.close()

    def _safe_url(self, endpoint: str) -> str:
        url = urljoin(self.base_url, endpoint)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() != self.base_host:
            raise APIRequestError(f"Blocked non-API endpoint: {url}")
        return url

    def get_json(self, endpoint: str) -> Any:
        url = self._safe_url(endpoint)
        try:
            response = self.session.get(url, timeout=(10, 45))
        except requests.RequestException as exc:
            raise APIRequestError(f"Network error for {url}: {exc}") from exc
        if response.status_code in {401, 403}:
            raise APIRequestError(
                f"Access denied ({response.status_code}) for {url}. Set your own COURSE_AUTH_TOKEN/COURSE_COOKIE.",
                response.status_code,
            )
        if response.status_code == 404:
            raise APIRequestError(f"Endpoint not found (404): {url}", 404)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise APIRequestError(f"HTTP {response.status_code} for {url}", response.status_code) from exc
        try:
            return response.json()
        except ValueError as exc:
            raise APIRequestError(f"Non-JSON response from {url}") from exc

    def fetch_live_courses(self) -> tuple[list[Batch], list[str]]:
        endpoints = split_env_list("COURSE_LIST_ENDPOINTS", DEFAULT_LIST_ENDPOINTS)
        found: OrderedDict[str, Batch] = OrderedDict()
        errors: list[str] = []
        for template in endpoints:
            endpoint = template.format(user_id=self.user_id)
            try:
                payload = self.get_json(endpoint)
            except APIRequestError as exc:
                errors.append(str(exc))
                continue
            for batch in find_batches(payload):
                found[batch.course_id] = batch
        return list(found.values()), errors

    def fetch_course_tree(self, course_id: str) -> Any:
        return self.get_json(f"/api/topic-and-section?courseId={course_id}&userId={self.user_id}")

    def fetch_topic_classes(self, topic_id: str, course_id: str) -> Any:
        return self.get_json(f"/api/topics/{topic_id}/classes?courseId={course_id}")

    def fetch_configured_extras(self, course_id: str) -> tuple[list[tuple[str, Any]], list[str]]:
        payloads: list[tuple[str, Any]] = []
        errors: list[str] = []
        for template in split_env_list("COURSE_EXTRA_ENDPOINTS"):
            try:
                endpoint = template.format(course_id=course_id, user_id=self.user_id)
                payloads.append((endpoint, self.get_json(endpoint)))
            except (KeyError, ValueError) as exc:
                errors.append(f"Invalid COURSE_EXTRA_ENDPOINTS template {template!r}: {exc}")
            except APIRequestError as exc:
                errors.append(str(exc))
        return payloads, errors


def find_batches(payload: Any) -> list[Batch]:
    found: OrderedDict[str, Batch] = OrderedDict()
    for obj, path in iter_dicts(payload):
        course_id = ""
        for key in ID_KEYS:
            candidate = clean_text(obj.get(key)).lower()
            if BATCH_ID_RE.fullmatch(candidate):
                course_id = candidate
                break
        if not course_id:
            continue
        title = ""
        for key in TITLE_KEYS:
            title = clean_text(obj.get(key))
            if title:
                break
        path_hint = "/".join(path).lower()
        has_course_key = any(key in obj for key in ("courseId", "courseName", "batchId", "batchName"))
        if title and (has_course_key or "course" in path_hint or "batch" in path_hint or "title" in obj):
            found[course_id] = Batch(course_id, title)
    return list(found.values())


def find_course_title(payload: Any, course_id: str) -> str:
    exact: list[str] = []
    fallback: list[str] = []
    for obj, path in iter_dicts(payload):
        titles = [clean_text(obj.get(key)) for key in TITLE_KEYS]
        titles = [title for title in titles if title]
        if not titles:
            continue
        ids = {clean_text(obj.get(key)).lower() for key in ID_KEYS}
        if course_id.lower() in ids:
            exact.extend(titles)
        elif any(key in obj for key in ("courseName", "batchName")) or "course" in "/".join(path).lower():
            fallback.extend(titles)
    return (exact or fallback or [""])[0]


def find_topic_refs(payload: Any) -> list[tuple[str, str]]:
    found: OrderedDict[str, str] = OrderedDict()
    for obj, path in iter_dicts(payload):
        topic_id = clean_text(obj.get("topicId") or obj.get("topic_id")).lower()
        name = clean_text(obj.get("topicName") or obj.get("topicTitle") or obj.get("name") or obj.get("title"))
        path_hint = "/".join(path).lower()
        if not topic_id and ("topic" in path_hint or "topicName" in obj):
            candidate = clean_text(obj.get("id") or obj.get("_id")).lower()
            if TOPIC_ID_RE.fullmatch(candidate):
                topic_id = candidate
        if TOPIC_ID_RE.fullmatch(topic_id):
            found[topic_id] = name or f"Topic {topic_id}"
    return list(found.items())


def _dict_locked(obj: dict[str, Any]) -> bool:
    for key in ("isLocked", "locked", "is_lock", "lock"):
        value = obj.get(key)
        if value is True or clean_text(value).lower() in {"true", "1", "yes", "locked"}:
            return True
    for key in ("hasAccess", "canAccess", "isAccessible", "isPurchased", "purchased", "unlocked"):
        if key in obj:
            value = obj.get(key)
            if value is False or clean_text(value).lower() in {"false", "0", "no", "locked"}:
                return True
    status = clean_text(obj.get("accessStatus") or obj.get("status")).lower()
    return status in {"locked", "denied", "not_purchased", "not purchased", "unauthorized"}


def _best_name(obj: dict[str, Any], default: str = "") -> str:
    for key in NAME_KEYS:
        value = clean_text(obj.get(key))
        if value and not URL_RE.match(value):
            return value
    return default


def _quality(obj: dict[str, Any], hint: str) -> str:
    for key in ("quality", "resolution", "videoQuality", "label"):
        value = clean_text(obj.get(key))
        if re.search(r"\b\d{3,4}p?\b", value, re.IGNORECASE):
            return value
    match = re.search(r"\b(\d{3,4})p\b", hint, re.IGNORECASE)
    return f"{match.group(1)}p" if match else ""


def _size_text(obj: dict[str, Any]) -> str:
    for key in ("size", "fileSize", "file_size", "sizeInMb"):
        value = obj.get(key)
        if value not in (None, ""):
            text = clean_text(value)
            if text.isdigit() and int(text) > 1024 * 1024:
                return f"{int(text) / (1024 * 1024):.1f} MB"
            return text
    return ""


def classify_media(url: str, hint: str) -> tuple[str, str] | None:
    parsed = urlparse(url)
    extension = Path(parsed.path.lower()).suffix
    kind = MEDIA_EXTENSIONS.get(extension)
    lowered = f"{hint} {url}".lower()
    if kind is None:
        if any(word in lowered for word in DOCUMENT_HINTS):
            kind = "document"
        elif any(word in lowered for word in VIDEO_HINTS):
            kind = "video"
        else:
            return None
    subtype = ""
    if kind == "document":
        if "handwritten" in lowered or "hand written" in lowered:
            subtype = "Handwritten Notes"
        elif "dpp" in lowered:
            subtype = "DPP"
        elif "sheet" in lowered:
            subtype = "Sheet"
        elif "note" in lowered:
            subtype = "Notes"
        elif extension:
            subtype = extension.lstrip(".").upper()
        else:
            subtype = "Document"
    return kind, subtype


@dataclass
class Asset:
    kind: str
    subtype: str
    title: str
    url: str
    section: str
    source: str
    quality: str = ""
    size: str = ""
    locked: bool = False

    @property
    def dedupe_key(self) -> tuple[str, str]:
        if self.url:
            return self.kind, self.url.strip().lower()
        return self.kind, f"locked:{self.section}:{self.title}".lower()


def collect_assets(
    payload: Any,
    source: str,
    api_base: str,
    initial_section: str = "Course Sheets / Notes",
) -> list[Asset]:
    assets: OrderedDict[tuple[str, str], Asset] = OrderedDict()

    def visit(value: Any, path: tuple[str, ...], section: str, inherited_locked: bool, parent_name: str) -> None:
        if isinstance(value, dict):
            local_locked = inherited_locked or _dict_locked(value)
            local_name = _best_name(value, parent_name)
            local_section = section
            for key in ("topicName", "sectionName", "className", "classTitle", "lectureTitle"):
                candidate = clean_text(value.get(key))
                if candidate:
                    local_section = candidate
                    break

            text_values = " ".join(
                clean_text(item) for item in value.values() if isinstance(item, (str, int, float))
            )
            object_hint = " ".join(path) + " " + text_values
            media_found = False
            for key, child in value.items():
                if not isinstance(child, str):
                    continue
                raw_url = child.strip()
                if not raw_url:
                    continue
                looks_relative_media = raw_url.startswith("/") and Path(urlparse(raw_url).path).suffix.lower() in MEDIA_EXTENSIONS
                if not URL_RE.match(raw_url) and not looks_relative_media:
                    continue
                url = urljoin(api_base.rstrip("/") + "/", raw_url)
                parsed_url = urlparse(url)
                if "/api/" in parsed_url.path.lower() and Path(parsed_url.path).suffix.lower() not in MEDIA_EXTENSIONS:
                    continue
                hint = f"{object_hint} {key} {local_name}"
                media_type = classify_media(url, hint)
                if media_type is None:
                    continue
                media_found = True
                kind, subtype = media_type
                title = local_name or Path(parsed_url.path).name or f"{kind.title()} file"
                asset = Asset(
                    kind=kind,
                    subtype=subtype,
                    title=title,
                    url="" if local_locked else url,
                    section=local_section or initial_section,
                    source=source,
                    quality=_quality(value, hint),
                    size=_size_text(value),
                    locked=local_locked,
                )
                existing = assets.get(asset.dedupe_key)
                if existing is None or (existing.locked and not asset.locked):
                    assets[asset.dedupe_key] = asset

            if local_locked and not media_found:
                lock_hint = f"{object_hint} {local_name}".lower()
                if local_name and any(word in lock_hint for word in DOCUMENT_HINTS + VIDEO_HINTS):
                    kind = "video" if any(word in lock_hint for word in VIDEO_HINTS) else "document"
                    subtype = classify_media("https://invalid.local/file", lock_hint)
                    asset = Asset(
                        kind=kind,
                        subtype=(subtype[1] if subtype else "Locked item"),
                        title=local_name,
                        url="",
                        section=local_section or initial_section,
                        source=source,
                        locked=True,
                    )
                    assets.setdefault(asset.dedupe_key, asset)

            for key, child in value.items():
                visit(child, path + (str(key),), local_section, local_locked, local_name)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, path + (str(index),), section, inherited_locked, parent_name)

    visit(payload, (), initial_section, False, "")
    return list(assets.values())


def find_linked_api_endpoints(payload: Any, api_base: str, base_host: str) -> list[str]:
    found: OrderedDict[str, None] = OrderedDict()
    for obj, path in iter_dicts(payload):
        for key, value in obj.items():
            if not isinstance(value, str):
                continue
            hint = f"{' '.join(path)} {key} {value}".lower()
            if not any(word in hint for word in API_LINK_HINTS):
                continue
            if value.lower().endswith(tuple(MEDIA_EXTENSIONS.keys())):
                continue
            if not (value.startswith("/") or URL_RE.match(value)):
                continue
            url = urljoin(api_base.rstrip("/") + "/", value)
            parsed = urlparse(url)
            if (parsed.hostname or "").lower() == base_host and "/api/" in parsed.path.lower():
                found[url] = None
            if len(found) >= 12:
                return list(found)
    return list(found)


def _video_group_key(asset: Asset) -> tuple[str, str]:
    title = re.sub(r"\b\d{3,4}p\b", "", asset.title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip().lower()
    return asset.section.lower(), title


def select_requested_videos(assets: list[Asset], requested_quality: str) -> list[Asset]:
    groups: OrderedDict[tuple[str, str], list[Asset]] = OrderedDict()
    for asset in assets:
        if asset.kind == "video":
            groups.setdefault(_video_group_key(asset), []).append(asset)
    selected: list[Asset] = []
    needle = requested_quality.lower().rstrip("p")
    
    for variants in groups.values():
        match = next(
            (
                asset
                for asset in variants
                if needle in asset.quality.lower().rstrip("p")
                or re.search(rf"\b{re.escape(needle)}p\b", f"{asset.title} {asset.url}", re.IGNORECASE)
            ),
            None,
        )
        # Strict Filter: Only append if the requested quality matches
        if match:
            selected.append(match)
            
    return selected


@dataclass
class ExtractionResult:
    course_id: str
    title: str
    mode: str
    assets: list[Asset] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    topic_count: int = 0

    @property
    def documents(self) -> list[Asset]:
        return [asset for asset in self.assets if asset.kind == "document"]

    @property
    def videos(self) -> list[Asset]:
        return [asset for asset in self.assets if asset.kind == "video"]

    @property
    def locked(self) -> list[Asset]:
        return [asset for asset in self.assets if asset.locked]


class CourseExtractor:
    def __init__(self, api: CourseAPI, registry: BatchRegistry, quality: str = "480"):
        self.api = api
        self.registry = registry
        self.quality = clean_text(quality, "480")

    def extract(self, course_id: str, title_hint: str, mode: str) -> ExtractionResult:
        if not BATCH_ID_RE.fullmatch(course_id):
            raise ValueError("Batch ID must be exactly 24 hexadecimal characters.")
        
        if mode not in {"full", "notes"}:
            raise ValueError("Mode must be 'full' or 'notes'.")

        tree = self.api.fetch_course_tree(course_id)
        discovered_title = find_course_title(tree, course_id)
        title = discovered_title or clean_text(title_hint, f"Batch {course_id}")
        result = ExtractionResult(course_id=course_id, title=title, mode=mode)

        combined: OrderedDict[tuple[str, str], Asset] = OrderedDict()

        def add_assets(items: Iterable[Asset]) -> None:
            for asset in items:
                existing = combined.get(asset.dedupe_key)
                if existing is None or (existing.locked and not asset.locked):
                    combined[asset.dedupe_key] = asset

        add_assets(collect_assets(tree, "course tree / sheets", self.api.base_url))
        topics = find_topic_refs(tree)
        result.topic_count = len(topics)
        payloads_for_discovery: list[Any] = [tree]

        for topic_id, topic_name in topics:
            try:
                classes = self.api.fetch_topic_classes(topic_id, course_id)
            except APIRequestError as exc:
                result.warnings.append(f"{topic_name}: {exc}")
                continue
            payloads_for_discovery.append(classes)
            add_assets(collect_assets(classes, f"topic {topic_id}", self.api.base_url, topic_name))

        extra_payloads, extra_errors = self.api.fetch_configured_extras(course_id)
        result.warnings.extend(extra_errors)
        for endpoint, payload in extra_payloads:
            payloads_for_discovery.append(payload)
            add_assets(collect_assets(payload, endpoint, self.api.base_url))

        linked: OrderedDict[str, None] = OrderedDict()
        for payload in payloads_for_discovery:
            for endpoint in find_linked_api_endpoints(payload, self.api.base_url, self.api.base_host):
                linked[endpoint] = None
        for endpoint in list(linked)[:12]:
            try:
                payload = self.api.get_json(endpoint)
            except APIRequestError as exc:
                result.warnings.append(str(exc))
                continue
            add_assets(collect_assets(payload, endpoint, self.api.base_url))

        all_assets = list(combined.values())
        documents = [asset for asset in all_assets if asset.kind == "document"]
        
        if mode == "notes":
            result.assets = documents
        else:
            videos = select_requested_videos(all_assets, self.quality)
            result.assets = videos + documents

        self.registry.merge([Batch(course_id, title)], prefer_new_titles=True)
        return result


def render_report(result: ExtractionResult, quality: str) -> str:
    if result.mode == "notes":
        type_text = "NOTES / SHEETS ONLY"
    else:
        type_text = f"FULL BATCH (STRICTLY {quality}p Videos + Documents)"
        
    lines = [
        f"Course: {result.title}",
        f"Course ID: {result.course_id}",
        f"Type: {type_text}",
        f"Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "=" * 72,
        "",
        f"Topics scanned: {result.topic_count}",
        f"Videos listed: {len(result.videos)}",
        f"PDFs / notes / sheets listed: {len(result.documents)}",
        f"Locked or unavailable entries: {len(result.locked)}",
        "",
    ]

    if not result.assets:
        lines.extend(
            [
                "NO MATCHING MEDIA FOUND.",
                "The API may require your valid auth token/cookie, or the Sheets endpoint may need",
                "to be supplied through COURSE_EXTRA_ENDPOINTS. See README_HINDI.txt.",
                "",
            ]
        )
    else:
        sections: OrderedDict[str, list[Asset]] = OrderedDict()
        for asset in result.assets:
            sections.setdefault(asset.section or "Other", []).append(asset)
        for section, assets in sections.items():
            lines.extend([f"SECTION: {section}", "-" * 72])
            for index, asset in enumerate(assets, 1):
                tag = "VIDEO" if asset.kind == "video" else (asset.subtype or "DOCUMENT").upper()
                meta = " | ".join(part for part in (asset.quality, asset.size) if part)
                meta_text = f" ({meta})" if meta else ""
                if asset.locked:
                    lines.append(f"{index}. [{tag}][LOCKED / NO ACCESS] {asset.title}{meta_text}")
                    lines.append("   URL: Not exported. Open/purchase access in the official app.")
                else:
                    lines.append(f"{index}. [{tag}] {asset.title}{meta_text}")
                    lines.append(f"   URL: {asset.url}")
                lines.append(f"   Source: {asset.source}")
            lines.append("")

    if result.warnings:
        lines.extend(["WARNINGS", "-" * 72])
        lines.extend(f"- {warning}" for warning in result.warnings[:50])
        if len(result.warnings) > 50:
            lines.append(f"- ... plus {len(result.warnings) - 50} more warnings")
        lines.append("")

    lines.extend(
        [
            "Important: This exporter only records URLs returned to your authenticated account.",
            "It does not bypass locks, payment, DRM, or access controls.",
        ]
    )
    return "\n".join(lines)


def write_report(result: ExtractionResult, quality: str, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    if result.mode == "notes":
        suffix = "Notes"
    else:
        suffix = f"Full_{quality}p"
        
    filename = f"{safe_filename(result.title)}_{suffix}.txt"
    path = directory / filename
    path.write_text(render_report(result, quality), encoding="utf-8", newline="\n")
    return path


def parse_course_input(value: str, registry: BatchRegistry) -> Batch:
    text = clean_text(value)
    resolved = registry.resolve(text)
    if resolved:
        return resolved
    if "|" in text:
        course_id, title = (part.strip() for part in text.split("|", 1))
    else:
        course_id, title = text, ""
    course_id = course_id.lower()
    if not BATCH_ID_RE.fullmatch(course_id):
        raise ValueError("Send a 24-character Batch ID, list number, or: BatchID | Course Name")
    return Batch(course_id, title or f"Batch {course_id}")


def build_runtime() -> tuple[BatchRegistry, CourseAPI, CourseExtractor, str]:
    registry_path = Path(os.getenv("BATCHES_FILE", str(DEFAULT_REGISTRY_FILE))).expanduser().resolve()
    registry = BatchRegistry(registry_path)
    api_base = os.getenv("COURSE_API_BASE", DEFAULT_API_BASE)
    user_id = os.getenv("COURSE_USER_ID", "2086041")
    api = CourseAPI(
        base_url=api_base,
        user_id=user_id,
        auth_token=os.getenv("COURSE_AUTH_TOKEN", ""),
        cookie=os.getenv("COURSE_COOKIE", ""),
    )
    quality = clean_text(os.getenv("VIDEO_QUALITY", "480"), "480").lower().rstrip("p")
    return registry, api, CourseExtractor(api, registry, quality), quality


def sync_registry(registry: BatchRegistry, api: CourseAPI) -> tuple[int, int, int, list[str]]:
    courses, errors = api.fetch_live_courses()
    added, updated = registry.merge(courses, prefer_new_titles=True)
    return len(courses), added, updated, errors


def _owner_ids() -> set[int]:
    raw = os.getenv("TELEGRAM_OWNER_IDS", "")
    result: set[int] = set()
    for part in re.split(r"[,;\s]+", raw.strip()):
        if part.isdigit():
            result.add(int(part))
    return result


def run_bot() -> None:
    try:
        import telebot
        from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError as exc:
        raise SystemExit("Missing pyTelegramBotAPI. Run: pip install -r requirements.txt") from exc

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN before starting the bot.")

    registry, api, extractor, quality = build_runtime()
    owners = _owner_ids()
    page_size = max(5, min(20, int(os.getenv("ITEMS_PER_PAGE", "8"))))
    bulk_limit = max(1, min(153, int(os.getenv("BULK_LIMIT", "20"))))
    output_dir = APP_DIR / ".generated"
    pending_mode: dict[int, str] = {}
    bot = telebot.TeleBot(token, parse_mode="HTML", threaded=True, num_threads=4)

    def actor_id(message_or_call: Any) -> int:
        user = getattr(message_or_call, "from_user", None)
        return int(getattr(user, "id", 0) or 0)

    def authorized(message_or_call: Any, reply: bool = True) -> bool:
        user_id = actor_id(message_or_call)
        allowed = bool(owners) and user_id in owners
        if not allowed and reply:
            target = getattr(message_or_call, "message", message_or_call)
            chat_id = getattr(getattr(target, "chat", None), "id", user_id)
            if owners:
                bot.send_message(chat_id, "⛔ This private exporter is owner-only.")
            else:
                bot.send_message(
                    chat_id,
                    "⚙️ TELEGRAM_OWNER_IDS is not configured. Send /whoami, then set that ID and restart.",
                )
        return allowed

    def menu_markup() -> InlineKeyboardMarkup:
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(InlineKeyboardButton("📚 All Batches", callback_data="list:1"))
        markup.add(
            InlineKeyboardButton("🎥 Full TXT (480p)", callback_data="ask:full"),
            InlineKeyboardButton("📝 Notes Only TXT", callback_data="ask:notes"),
        )
        markup.add(
            InlineKeyboardButton("🔄 Sync", callback_data="sync"),
            InlineKeyboardButton("🚀 Bulk Extract", callback_data="bulk:help"),
        )
        return markup

    def list_page(page: int) -> tuple[str, InlineKeyboardMarkup]:
        batches = registry.load()
        total_pages = max(1, math.ceil(len(batches) / page_size))
        page = max(1, min(page, total_pages))
        start = (page - 1) * page_size
        rows = batches[start : start + page_size]
        text = [
            f"📚 <b>Saved Batches — Page {page}/{total_pages}</b>",
            f"Total: <b>{len(batches)}</b>",
            "",
        ]
        for index, batch in enumerate(rows, start + 1):
            text.append(f"<b>{index}. {html.escape(batch.title)}</b>")
            text.append(f"<code>{batch.course_id}</code>")
            text.append("")
        markup = InlineKeyboardMarkup()
        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"list:{page - 1}"))
        if page < total_pages:
            nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"list:{page + 1}"))
        if nav:
            markup.row(*nav)
        markup.row(InlineKeyboardButton("🏠 Menu", callback_data="menu"))
        return "\n".join(text), markup

    def send_menu(chat_id: int, prefix: str = "") -> None:
        text = (
            f"{prefix}\n" if prefix else ""
        ) + (
            "🌟 <b>Authorized Batch TXT Exporter</b>\n\n"
            "• <b>Full TXT:</b> Sirf 480p (or custom) videos + PDFs/Docs\n"
            "• <b>Notes TXT:</b> Sirf PDFs, Sheets aur Notes\n\n"
            "Direct commands:\n"
            "<code>/full ID</code> (default 480p)\n"
            "<code>/full 720 ID</code> (custom quality)\n"
            "<code>/notes ID</code>"
        )
        bot.send_message(chat_id, text, reply_markup=menu_markup())

    def do_extract(chat_id: int, raw_value: str, mode: str, custom_quality: str = None) -> None:
        try:
            batch = parse_course_input(raw_value, registry)
        except ValueError as exc:
            bot.send_message(chat_id, f"⚠️ {html.escape(str(exc))}")
            return
            
        active_quality = custom_quality if custom_quality else quality
            
        if mode == "notes": mode_label = "Notes / Sheets"
        else: mode_label = f"Full (STRICTLY {active_quality}p)"
            
        progress = bot.send_message(
            chat_id,
            f"⏳ <b>{html.escape(batch.title)}</b>\nMode: {html.escape(mode_label)}\nScanning authorized API data…",
        )
        
        original_quality = extractor.quality
        extractor.quality = active_quality
        
        try:
            result = extractor.extract(batch.course_id, batch.title, mode)
            output_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="report-", dir=str(output_dir)) as temp_dir:
                report_path = write_report(result, active_quality, Path(temp_dir))
                with report_path.open("rb") as document:
                    bot.send_document(
                        chat_id,
                        document,
                        caption=(
                            f"✅ <b>{html.escape(result.title)}</b>\n"
                            f"🎥 {active_quality}p Videos: {len(result.videos)} | 📄 Documents: {len(result.documents)} | "
                            f"🔒 Locked: {len(result.locked)}"
                        ),
                    )
            bot.edit_message_text(
                f"✅ Completed: <b>{html.escape(result.title)}</b>",
                chat_id=chat_id,
                message_id=progress.message_id,
            )
        except (APIRequestError, ValueError, OSError) as exc:
            bot.edit_message_text(
                f"❌ <b>Extraction failed</b>\n<code>{html.escape(str(exc))}</code>",
                chat_id=chat_id,
                message_id=progress.message_id,
            )
        except Exception:
            logging.exception("Unexpected extraction error")
            bot.edit_message_text(
                "❌ Unexpected error. Check the server log; secrets were not printed.",
                chat_id=chat_id,
                message_id=progress.message_id,
            )
        finally:
            extractor.quality = original_quality

    @bot.message_handler(commands=["whoami"])
    def whoami(message: Any) -> None:
        bot.reply_to(message, f"Your Telegram user ID: <code>{actor_id(message)}</code>")

    @bot.message_handler(commands=["start", "menu"])
    def start(message: Any) -> None:
        if not authorized(message):
            return
        found, added, updated, errors = sync_registry(registry, api)
        sync_text = f"🔄 API: {found} found, {added} added, {updated} renamed."
        if errors and not found:
            sync_text += " Old TXT registry kept safely; API sync needs auth/network."
        send_menu(message.chat.id, sync_text)

    @bot.message_handler(commands=["list", "batches"])
    def batches(message: Any) -> None:
        if not authorized(message):
            return
        text, markup = list_page(1)
        bot.send_message(message.chat.id, text, reply_markup=markup)

    @bot.message_handler(commands=["sync"])
    def sync(message: Any) -> None:
        if not authorized(message):
            return
        found, added, updated, errors = sync_registry(registry, api)
        reply = f"✅ API found: {found}\n➕ Added: {added}\n✏️ Renamed: {updated}\n📚 Saved total: {len(registry.load())}"
        if errors:
            reply += f"\n⚠️ Endpoint errors: {len(errors)} (old entries were preserved)"
        bot.send_message(message.chat.id, reply)

    @bot.message_handler(commands=["add"])
    def add_batch(message: Any) -> None:
        if not authorized(message):
            return
        raw = message.text.partition(" ")[2]
        try:
            batch = parse_course_input(raw, BatchRegistry(Path("__nonexistent_registry__")))
            if batch.title.startswith("Batch "):
                raise ValueError("Use: /add BatchID | Course Name")
            added, updated = registry.merge([batch], prefer_new_titles=True)
            bot.reply_to(message, f"✅ Saved. Added: {added}, updated: {updated}")
        except ValueError as exc:
            bot.reply_to(message, f"⚠️ {html.escape(str(exc))}")

    @bot.message_handler(commands=["full", "notes"])
    def direct_extract(message: Any) -> None:
        if not authorized(message):
            return
        parts = message.text.split()
        command = parts[0].lower()
        raw = message.text.partition(" ")[2].strip()
        
        if not raw:
            bot.reply_to(message, f"Usage: <code>{command} [quality] BatchID</code>\nExample: <code>/full 720 1234567890abcdef</code>")
            return
            
        mode = "notes" if command.startswith("/notes") else "full"
        custom_quality = None
        
        match_start = re.match(r"^(360|480|720|1080)p?\s+(.+)$", raw, re.IGNORECASE)
        match_end = re.search(r"\s+(360|480|720|1080)p?$", raw, re.IGNORECASE)
        
        if match_start:
            custom_quality = match_start.group(1)
            raw = match_start.group(2)
        elif match_end:
            custom_quality = match_end.group(1)
            raw = raw[:match_end.start()].strip()
            
        do_extract(message.chat.id, raw, mode, custom_quality)

    @bot.message_handler(commands=["bulk"])
    def bulk(message: Any) -> None:
        if not authorized(message):
            return
        parts = message.text.split()
        if len(parts) < 2 or parts[1].lower() != "confirm":
            bot.reply_to(
                message,
                f"Bulk can be heavy. Run <code>/bulk confirm</code> to process the first {bulk_limit} saved batches. "
                "Change BULK_LIMIT to adjust.",
            )
            return
        batches_to_run = registry.load()[:bulk_limit]
        bot.send_message(message.chat.id, f"🚀 Bulk started for {len(batches_to_run)} batches.")
        for index, batch in enumerate(batches_to_run, 1):
            bot.send_message(message.chat.id, f"[{index}/{len(batches_to_run)}] {html.escape(batch.title)}")
            do_extract(message.chat.id, batch.course_id, "full") 
        bot.send_message(message.chat.id, "🎉 Bulk finished.")

    @bot.callback_query_handler(func=lambda call: True)
    def callbacks(call: Any) -> None:
        if not authorized(call):
            bot.answer_callback_query(call.id, "Not authorized", show_alert=True)
            return
        data = call.data or ""
        chat_id = call.message.chat.id
        bot.answer_callback_query(call.id)
        if data == "menu":
            bot.edit_message_text(
                "🌟 <b>Main Menu</b>",
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=menu_markup(),
            )
        elif data.startswith("list:"):
            page = int(data.split(":", 1)[1])
            text, markup = list_page(page)
            bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup)
        elif data.startswith("ask:"):
            mode = data.split(":", 1)[1]
            pending_mode[chat_id] = mode
            if mode == "notes": label = "Notes / Sheets Only"
            else: label = "Full Batch (STRICT 480p default)"
            bot.send_message(chat_id, f"Send Batch ID or <code>BatchID | Course Name</code> for {label}.")
        elif data == "sync":
            found, added, updated, errors = sync_registry(registry, api)
            bot.send_message(
                chat_id,
                f"✅ Found {found}; added {added}; renamed {updated}; errors {len(errors)}; total {len(registry.load())}.",
            )
        elif data == "bulk:help":
            bot.send_message(chat_id, f"Use <code>/bulk confirm</code>. Current BULK_LIMIT={bulk_limit}.")

    @bot.message_handler(func=lambda message: True)
    def plain_text(message: Any) -> None:
        if not authorized(message):
            return
        mode = pending_mode.pop(message.chat.id, "full")
        do_extract(message.chat.id, message.text, mode)

    logging.info("Starting owner-only Telegram exporter with %d saved batches", len(registry.load()))
    try:
        bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
    finally:
        api.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    run_bot()
