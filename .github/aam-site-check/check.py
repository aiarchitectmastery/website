#!/usr/bin/env python3
"""Read-only, offline AAM discovery checks. Python 3.9+, standard library only.

Public API (version 1):
    build_manifest(site) -> {relative_posix_path: sha256}
    manifest_digest(manifest) -> sha256 of compact, sorted-key JSON
    export_public_contract(registry) -> explicitly allowlisted public facts
    check_site(site, registry, *, environment="source", baseline=None) -> report

The public contract is checked by the SAME check_site implementation. Point
--site at the served staging directory, not the public repository containing
the .github validation bundle. No network, subprocess, extraction or deployment.
Machine success is NOT editorial acceptance, schema truth or release approval.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from datetime import date
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import unicodedata
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET
import zipfile

API_VERSION = 1
SCHEMA_VOCABULARY_VERSION = "aam-observed-subset-2026-10-04-v1"
SCHEMA_SOURCES = ["https://schema.org/docs/full.html", "https://schema.org/docs/schemas.html"]
# Deliberately a finite vocabulary, not a full schema.org validator. New usages
# require review of this set, not a silent generic acceptance of arbitrary keys.
SCHEMA_TYPES = set("""
Organization Person Course Offer FAQPage Question Answer WebPage Article
BreadcrumbList ListItem Thing Audience CollectionPage ItemList LearningResource
EducationalOccupationalCredential VideoObject ImageObject WebSite CreativeWork
""".split())
SCHEMA_PROPERTIES = set("""
name url logo description founder sameAs provider inLanguage offers availability
mainEntity acceptedAnswer text educationalLevel audience audienceType hasPart
itemListElement position item headline mainEntityOfPage dateModified datePublished
author isPartOf publisher about image license copyrightHolder copyrightYear
keywords alternateName identifier teaches learningResourceType timeRequired
educationalCredentialAwarded numberOfItems itemListOrder contentUrl embedUrl
thumbnailUrl uploadDate duration potentialAction target address jobTitle
price priceCurrency priceValidUntil category aggregateRating ratingValue
reviewCount bestRating worstRating review reviewBody
""".split())
SCHEMA_REQUIRED = {
    "Organization": {"name"}, "Person": {"name"}, "Course": {"name"},
    "Offer": {"url"}, "Question": {"name", "acceptedAnswer"}, "Answer": {"text"},
    "BreadcrumbList": {"itemListElement"}, "ListItem": {"position"},
    "Article": {"headline"}, "WebPage": {"name"},
}
CORE_VIDEOS = {
    "methodology/prd.html": "qJ2m_tF0pRk",
    "methodology/plan.html": "XkG8_hsnaYA",
    "methodology/task.html": "h99uBn6cdSw",
    "methodology/implementation.html": "NuDzn_Osu7c",
}
PRIMARY_PATHS = ["methodology/index.html", *CORE_VIDEOS]
TEXT_EXTENSIONS = {".html", ".htm", ".md", ".txt", ".xml", ".json", ".js", ".css", ".svg", ".yml", ".yaml"}
RETIRED = re.compile(r"\bstructured[\s-]*vibe[\s-]*coding\b", re.I)
TRACKING = re.compile(
    r"google-analytics\.com|googletagmanager\.com|connect\.facebook\.net|"
    r"facebook\.com/tr\b|analytics\.google\.com|static\.cloudflareinsights\.com|"
    r"clarity\.ms|hotjar\.com|plausible\.io|scripts\.simpleanalyticscdn\.com|"
    r"\b(?:gtag|fbq|ga)\s*\(|\bdataLayer\s*\.|\bml\s*\(|"
    r"assets\.mailerlite\.com|static\.mlcdn\.com", re.I)
SALES = re.compile(r"\b(?:enroll|buy|purchase|subscribe|newsletter|coupon)\b|"
                   r"\b(?:paid|premium)\s+course\b|course\s+(?:coming\s+soon|placeholder)", re.I)
BLOCK_TAGS = set("address article aside blockquote br dd div dl dt fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6 header hr li main nav ol p pre section table td th tr ul".split())
VOID_TAGS = set("area base br col embed hr img input link meta param source track wbr".split())


def canonical_json(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def load_json(text):
    """Reject duplicate keys and NaN/Infinity rather than hiding ambiguities."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError("non-JSON numeric constant: " + value)
    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid_constant)


def manifest_digest(manifest):
    return hashlib.sha256(canonical_json(manifest).encode("utf-8")).hexdigest()


def safe_relative(value):
    if (not isinstance(value, str) or not value or "\\" in value
            or any(unicodedata.category(ch) in ("Cc", "Cf") for ch in value)):
        return False
    p = PurePosixPath(value)
    return not p.is_absolute() and not re.match(r"^[A-Za-z]:", value) and all(
        x not in ("", ".", "..") for x in value.split("/"))


def build_manifest(site):
    """Hash every regular file, including dotfiles; reject symlinks/special files."""
    root = Path(site)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("site must be an existing non-symlink directory")
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            p = Path(directory) / name
            mode = p.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise ValueError("unsafe filesystem entry: " + p.relative_to(root).as_posix())
        for name in sorted(files):
            p = Path(directory) / name
            result[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return dict(sorted(result.items()))


def normalize_text(text):
    text = unicodedata.normalize("NFKC", unescape(text)).casefold()
    return "".join(" " if ch.isspace() else "-" if unicodedata.category(ch) == "Pd" or ch in "\u2212\u2043"
                   else "" if unicodedata.category(ch) == "Cf" else ch for ch in text)


def has_retired(text):
    return bool(RETIRED.search(normalize_text(text)))


def page_url(origin, path):
    if path == "index.html":
        return origin + "/"
    if path.endswith("/index.html"):
        return origin + "/" + path[:-10]
    return origin + "/" + path


def local_target(origin, base_url, reference):
    """Return decoded relative path, fragment; None means genuinely external."""
    u = urlsplit(urljoin(base_url, reference))
    o = urlsplit(origin)
    if u.scheme not in ("http", "https") or u.netloc.lower() != o.netloc.lower():
        return None
    path = unquote(u.path).lstrip("/")
    if not path or path.endswith("/"):
        path += "index.html"
    if not safe_relative(path):
        raise ValueError("unsafe local URL path")
    return path, unquote(u.fragment).split(":~:text=", 1)[0]


def json_nodes(value):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from json_nodes(v)
    elif isinstance(value, list):
        for v in value:
            yield from json_nodes(v)


def json_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from json_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from json_strings(v)


class Page(HTMLParser):
    """Extract semantics without executing HTML, CSS or JavaScript."""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.text = []
        self.title = []
        self.title_count = 0
        self.h1 = []
        self.headings = []
        self.ids = []
        self.links = []
        self.references = []
        self.canonicals = []
        self.meta = defaultdict(list)
        self.accessible = []
        self.scripts = []
        self.json_ld = []
        self.times = []
        self.nav_links = []
        self.base = []
        self.forms = []
        self.comments = []
        self.image_alts = []
        self._script = None
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in BLOCK_TAGS:
            self.text.append("\n")
        if tag == "title":
            self.title_count += 1
        if tag == "img":
            self.image_alts.append(a.get("alt"))
        if a.get("id"):
            self.ids.append(a["id"])
        if tag == "a" and a.get("name"):
            self.ids.append(a["name"])
        for key in ("alt", "title", "aria-label", "aria-description", "placeholder", "value"):
            if a.get(key):
                self.accessible.append(a[key])
        if tag == "meta":
            self.meta[(a.get("name") or a.get("property") or a.get("http-equiv") or "").lower()].append(a.get("content", ""))
        if tag == "base":
            self.base.append(a.get("href", ""))
        if tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonicals.append(a.get("href", ""))
        for key in ("href", "src", "poster", "action", "data-src"):
            if a.get(key) and not (tag == "link" and "canonical" in a.get("rel", "").lower().split()):
                self.references.append((tag, key, a[key]))
        if a.get("srcset"):
            for candidate in a["srcset"].split(","):
                if candidate.strip():
                    self.references.append((tag, "srcset", candidate.strip().split()[0]))
        if tag == "a" and "href" in a:
            self.links.append(a["href"])
            if any(t == "nav" and ("site-nav" in d.get("class", "").split()
                                  or d.get("aria-label") == "Methodology navigation")
                   for t, d in self.stack):
                self.nav_links.append(a["href"])
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append(int(tag[1]))
        if tag == "h1":
            self.h1.append([])
        if tag == "time":
            self.times.append({"datetime": a.get("datetime"), "text": ""})
        if tag == "form":
            self.forms.append(a.get("action", ""))
        if tag == "script":
            self._script = {"type": a.get("type", "").lower(), "src": a.get("src"), "text": ""}
        if tag not in VOID_TAGS:
            self.stack.append((tag, a))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_data(self, data):
        tags = [t for t, _ in self.stack]
        if self._script is not None:
            self._script["text"] += data
            return
        if "style" in tags:
            return
        if "title" in tags:
            self.title.append(data)
        if "h1" in tags and self.h1:
            self.h1[-1].append(data)
        if "time" in tags and self.times:
            self.times[-1]["text"] += data
        if "head" not in tags:
            self.text.append(data)

    def handle_comment(self, data):
        self.comments.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._script is not None:
            self.scripts.append(self._script)
            if self._script["type"] == "application/ld+json":
                self.json_ld.append(self._script["text"])
            self._script = None
        if tag in BLOCK_TAGS:
            self.text.append("\n")
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def extracted(self):
        return {
            "title": "".join(self.title).strip(),
            "description": self.meta.get("description", []),
            "h1": ["".join(x).strip() for x in self.h1],
            "headings": self.headings, "canonical": self.canonicals,
            "og_url": self.meta.get("og:url", []),
            "ids": sorted(set(self.ids)), "links": sorted(set(self.links)),
            "metadata": dict(sorted(self.meta.items())),
            "json_ld_blocks": len(self.json_ld), "visible_times": self.times,
        }


class Robots:
    """RFC9309 group selection, merging, longest rule and Allow-on-tie.

    Offline policy check only: cannot infer actual WAF or provider-account state.
    """

    def __init__(self, text):
        self.groups = []
        self.sitemaps = []
        agents, rules = [], []
        for raw in text.splitlines() + ["User-agent: __end__"]:
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            field, value = [x.strip() for x in line.split(":", 1)]
            field = field.lower()
            if field == "sitemap":
                self.sitemaps.append(value)
            elif field == "user-agent":
                if rules:
                    self.groups.append((agents, rules))
                    agents, rules = [], []
                agents.append(value.lower())
            elif field in ("allow", "disallow") and agents:
                rules.append((field, value))
        if rules:
            self.groups.append((agents, rules))

    def allowed(self, agent, path):
        candidates = []
        for agents, rules in self.groups:
            scores = [0 if a == "*" else len(a) for a in agents
                      if a == "*" or a in agent.lower()]
            if scores:
                candidates.append((max(scores), rules))
        if not candidates:
            return True
        specificity = max(x[0] for x in candidates)
        matches = []
        for score, rules in candidates:
            if score != specificity:
                continue
            for directive, pattern in rules:
                if not pattern:
                    continue
                normalized = unquote(pattern)
                anchor = normalized.endswith("$")
                expression = re.escape(normalized[:-1] if anchor else normalized).replace(r"\*", ".*")
                if re.match(expression + ("$" if anchor else ""), unquote(path)):
                    matches.append((len(normalized.replace("*", "").rstrip("$")), directive == "allow"))
        return max(matches)[1] if matches else True


PUBLIC_PAGE_FIELDS = (
    "content_id", "concept_ids", "path", "preferred_url", "page_type",
    "indexing_intent", "modified_at", "journey", "relations",
    "protected_fragments", "protected_video_ids",
)
PUBLIC_ASSET_FIELDS = (
    "asset_id", "path", "kind", "public_status", "indexing_intent",
    "source_path", "archive_members",
)


def export_public_contract(registry):
    """No copying of internal arbitrary dictionaries or free-form notes."""
    pages = []
    for p in registry["pages"]:
        # JSON round-trip returns an independent object rather than references
        # to mutable private registry lists.
        item = {k: json.loads(json.dumps(p[k])) for k in PUBLIC_PAGE_FIELDS if k in p and k != "relations"}
        item["relations"] = [
            {"type": r["type"], "target": r["target"]}
            for r in p.get("relations", [])]
        pages.append(item)
    assets = [{k: json.loads(json.dumps(a[k])) for k in PUBLIC_ASSET_FIELDS if k in a}
              for a in registry["assets"] if a.get("public_status") == "public"]
    return {
        "schema_version": 1, "contract_kind": "aam-public-check",
        "api_version": API_VERSION, "origin": registry["origin"],
        "pages": pages, "assets": assets,
        "entities": [], "exceptions": [],
        "rules": {
            "sitemaps": list(registry.get("rules", {}).get("sitemaps", ["sitemap.xml", "methodology/sitemap.xml"])),
            "protected_primary_paths": list(registry.get("rules", {}).get("protected_primary_paths", PRIMARY_PATHS)),
            "core_videos": dict(registry.get("rules", {}).get("core_videos", CORE_VIDEOS)),
        },
    }


def validate_public_contract(contract):
    """Validate the serialization boundary, NOT human/publication approval.

    Reprojection rejects extra fields even within relation objects. Primitive
    type checks prevent hiding private dictionaries inside allowed field names.
    """
    if not isinstance(contract, dict) or export_public_contract(contract) != contract:
        raise ValueError("public contract contains private/unknown fields or unsupported envelope")
    if contract.get("contract_kind") != "aam-public-check" or contract.get("api_version") != API_VERSION:
        raise ValueError("unsupported public contract")
    for p in contract["pages"]:
        if set(p) != set(PUBLIC_PAGE_FIELDS):
            raise ValueError("public page requires the complete v1 field contract")
        for field in ("content_id", "path", "preferred_url", "page_type", "indexing_intent", "journey"):
            if not isinstance(p[field], str):
                raise ValueError("public page field must be a string: " + field)
        for field in ("concept_ids", "protected_fragments", "protected_video_ids"):
            if not isinstance(p[field], list) or not all(isinstance(x, str) for x in p[field]):
                raise ValueError("public page field must be a string array: " + field)
        if p["modified_at"] is not None and not isinstance(p["modified_at"], str):
            raise ValueError("public date must be a string or null")
        if not safe_relative(p["path"]):
            raise ValueError("unsafe public page path")
        for rel in p["relations"]:
            if not isinstance(rel["type"], str) or not isinstance(rel["target"], str):
                raise ValueError("public relations contain only type and target strings")
    for asset in contract["assets"]:
        for key, value in asset.items():
            if key == "archive_members":
                if not isinstance(value, list) or not all(isinstance(x, str) and safe_relative(x.rstrip("/")) for x in value):
                    raise ValueError("invalid archive member list")
            elif not isinstance(value, str):
                raise ValueError("public asset scalar must be a string: " + key)
        if not safe_relative(asset.get("path")):
            raise ValueError("unsafe public asset path")
        if "source_path" in asset and not safe_relative(asset["source_path"]):
            raise ValueError("unsafe archive source path")
    rules = contract["rules"]
    for field in ("sitemaps", "protected_primary_paths"):
        if not isinstance(rules[field], list) or not all(safe_relative(x) for x in rules[field]):
            raise ValueError("public rule requires safe paths")
    if not isinstance(rules["core_videos"], dict) or not all(
            safe_relative(p) and isinstance(v, str) for p, v in rules["core_videos"].items()):
        raise ValueError("public Core video rules require path/string pairs")
    return True


class Checker:
    def __init__(self, site, registry, environment, baseline):
        self.site = Path(site)
        self.registry = registry
        self.environment = environment
        self.baseline = baseline
        self.manifest = build_manifest(site)
        self.fingerprint = manifest_digest(self.manifest)
        self.findings = []
        self.human = []
        self.pages = {}
        self.records = {}
        self.graph = defaultdict(set)
        self.sitemap_entries = defaultdict(list)
        self.stubs = {}
        self.archive_inventory = {}
        self.public = registry.get("contract_kind") == "aam-public-check"
        self.origin = registry.get("origin", "").rstrip("/")

    def finding(self, requirement, code, path, observed, expected, severity="error"):
        self.findings.append({
            "requirement_id": requirement, "code": code, "file_or_url": path,
            "severity": severity, "observed": observed, "expected": expected,
            "environment": self.environment, "source_fingerprint": self.fingerprint,
        })

    def review(self, path, topic, detail):
        self.human.append({"file_or_url": path, "topic": topic, "status": "pending-human-review", "detail": detail})

    def read(self, path):
        return (self.site / path).read_text(encoding="utf-8-sig")

    def validate_registry(self):
        r = self.registry
        if r.get("schema_version") != 1:
            self.finding("CONTENT-01", "registry-version", "registry", r.get("schema_version"), 1)
        if not self.origin.startswith("https://") or urlsplit(self.origin).path:
            self.finding("DISC-03", "registry-origin", "registry", self.origin, "HTTPS origin without path")
        ids, paths, urls, concepts = Counter(), Counter(), Counter(), Counter()
        for p in r.get("pages", []):
            path = p.get("path", "")
            for field in PUBLIC_PAGE_FIELDS:
                if field not in p:
                    self.finding("CONTENT-01", "registry-field", path, field, "required page field")
            if not safe_relative(path):
                self.finding("CONTENT-01", "registry-path", path, path, "safe relative POSIX path")
                continue
            self.records[path] = p
            ids[p.get("content_id")] += 1
            paths[path] += 1
            urls[p.get("preferred_url")] += 1
            concepts.update(p.get("concept_ids", []))
            if p.get("preferred_url") != page_url(self.origin, path):
                self.finding("DISC-03", "registry-url", path, p.get("preferred_url"), page_url(self.origin, path))
            if p.get("indexing_intent") not in ("index", "noindex"):
                self.finding("DISC-01", "registry-indexing-intent", path, p.get("indexing_intent"), "index or explicitly approved noindex")
            if not p.get("concept_ids") or not isinstance(p.get("content_id"), str):
                self.finding("CONTENT-01", "registry-identity", path, p.get("content_id"), "stable ID and concept home")
            if path.startswith("methodology/") and p.get("journey") != "reference-only":
                self.finding("CONTENT-01", "registry-journey", path, p.get("journey"), "reference-only")
            self.check_date(p.get("modified_at"), path, "registry modified_at")
            if not self.public:
                for field in ("locale", "primary_question", "definition_reference", "term_scope", "aliases",
                              "owner", "reviewer", "source", "publication_status", "reviewed_at",
                              "next_review_due", "change_rationale", "evidence", "technical_sources", "course_mapping"):
                    if field not in p:
                        self.finding("CONTENT-01", "registry-governance", path, field, "explicit state, null when unknown")
                for field in ("reviewed_at", "next_review_due"):
                    self.check_date(p.get(field), path, field)
                self.review(path, "source-and-claims", {
                    "reviewer": p.get("reviewer"), "source": p.get("source"),
                    "evidence": p.get("evidence"), "reviewed_at": p.get("reviewed_at")})
                if p.get("page_type") in ("brand-home", "onboarding", "certification-hub", "methodology-overview", "core-phase"):
                    self.review(path, "detailed-editorial-cohort", "Review direct answer, scope, original evidence, limitations, source accuracy, related reading and permitted next action; text must stand alone.")
        for kind, counts in (("content-id", ids), ("page-path", paths), ("preferred-url", urls), ("concept-home", concepts)):
            for value, count in counts.items():
                if count > 1:
                    self.finding("CONTENT-01", "duplicate-" + kind, "registry", value, "one authoritative home")
        entity_ids = [e.get("entity_id") for e in r.get("entities", [])]
        for value, count in Counter(entity_ids + list(ids)).items():
            if count > 1:
                self.finding("CONTENT-01", "duplicate-entity-id", "registry", value, "unique stable IDs")
        edges = {"parent": defaultdict(list), "precedes": defaultdict(list)}
        for p in r.get("pages", []):
            for rel in p.get("relations", []):
                if rel.get("type") not in ("parent", "related", "precedes", "applies", "evidence_for"):
                    self.finding("CONTENT-01", "relation-type", p.get("path"), rel, "known typed relation")
                if rel.get("target") not in ids:
                    self.finding("CONTENT-01", "dangling-relation", p.get("path"), rel, "existing content_id")
                if rel.get("type") in edges:
                    edges[rel["type"]][p["content_id"]].append(rel.get("target"))
        for relation, graph in edges.items():
            active, visited = set(), set()
            def visit(node):
                if node in active:
                    self.finding("CONTENT-01", "relation-cycle", "registry", relation + ":" + str(node), "acyclic")
                    return
                if node in visited:
                    return
                active.add(node)
                for child in graph.get(node, []):
                    visit(child)
                active.remove(node)
                visited.add(node)
            for node in sorted(ids):
                visit(node)
        asset_paths, asset_ids = Counter(), Counter()
        optional_exclusions = set()
        for a in r.get("assets", []):
            path = a.get("path", "")
            asset_paths[path] += 1
            asset_ids[a.get("asset_id")] += 1
            for field in ("asset_id", "path", "kind", "public_status", "indexing_intent"):
                if field not in a:
                    self.finding("DISC-01", "asset-field", path, field, "required classification")
            if a.get("public_status") not in ("public", "repository-only", "excluded"):
                self.finding("DISC-01", "asset-public-status", path, a.get("public_status"), "explicit publication classification")
            if not safe_relative(path):
                self.finding("DISC-01", "asset-path", path, path, "safe relative POSIX path")
            presence = a.get("source_presence", "required")
            if presence not in ("required", "optional"):
                self.finding("DISC-01", "asset-source-presence", path, presence, "required or explicitly classified optional exclusion")
            if presence == "optional":
                expected_hash = a.get("expected_sha256")
                if (a.get("public_status") != "excluded" or not isinstance(expected_hash, str)
                        or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)):
                    self.finding("DISC-01", "unsafe-optional-asset", path, presence, "excluded-only with exact expected_sha256")
                else:
                    optional_exclusions.add(path)
                    if path in self.manifest and self.manifest[path] != expected_hash:
                        self.finding("DISC-01", "excluded-asset-byte-change", path, self.manifest[path], expected_hash)
            if not self.public:
                for field in ("owner", "terminology_review"):
                    if field not in a:
                        self.finding("DISC-01", "asset-governance", path, field, "explicit ownership/review")
        for kind, counts in (("asset-path", asset_paths), ("asset-id", asset_ids)):
            for value, count in counts.items():
                if count > 1:
                    self.finding("DISC-01", "duplicate-" + kind, "registry", value, "unique")
        for ident in set(asset_ids) & (set(ids) | set(entity_ids)):
            self.finding("CONTENT-01", "cross-kind-id-collision", "registry", ident, "globally unique stable IDs")
        declared = set(paths) | set(asset_paths)
        for path in sorted(set(paths) & set(asset_paths)):
            self.finding("DISC-01", "classification-overlap", path, "page and asset", "one classification")
        for path in sorted(set(self.manifest) - declared):
            self.finding("DISC-01", "unregistered-file", path, "present", "explicit page or asset classification")
        for path in sorted(declared - set(self.manifest) - optional_exclusions):
            self.finding("DISC-01", "missing-file", path, "absent", "registered file exists")
        actual_html = {p for p in self.manifest if Path(p).suffix.lower() in (".html", ".htm")}
        for path in sorted(actual_html - set(paths)):
            self.finding("CONTENT-01", "unregistered-page", path, "HTML outside pages", "registered page")
        for path in sorted(set(paths) - actual_html):
            self.finding("CONTENT-01", "missing-page", path, "not HTML in inventory", "registered HTML exists")
        for exception in r.get("exceptions", []):
            self.review("registry", "exception-not-machine-waiver", exception)

    def check_date(self, value, path, source):
        if value is None:
            return
        try:
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError()
            date.fromisoformat(value)
        except ValueError:
            self.finding("DISC-05", "invalid-date", path, {source: value}, "YYYY-MM-DD or null when unknown")

    def compare_date(self, value, path, source):
        self.check_date(value, path, source)
        expected = self.records.get(path, {}).get("modified_at")
        if value != expected:
            self.finding("DISC-05", "date-disagreement", path, {source: value}, {"registry.modified_at": expected})

    def terminology(self, path, text, surface):
        if has_retired(text):
            self.finding("CONTENT-09", "retired-terminology", path, surface, "AI Driven Development; no retired alias")

    def schema(self, path, page):
        modified = []
        for i, raw in enumerate(page.json_ld):
            try:
                value = load_json(raw)
            except (ValueError, RecursionError) as exc:
                self.finding("DATA-01", "json-ld-parse", path, f"block {i}: {exc}", "valid JSON")
                continue
            if not isinstance(value, (dict, list)):
                self.finding("DATA-01", "json-ld-shape", path, type(value).__name__, "object or array")
                continue
            for s in json_strings(value):
                self.terminology(path, s, "JSON-LD string")
            for node in json_nodes(value):
                for key in node:
                    if not key.startswith("@") and key not in SCHEMA_PROPERTIES:
                        self.finding("DATA-01", "schema-property", path, key, SCHEMA_VOCABULARY_VERSION)
                    elif key.startswith("@") and key not in ("@context", "@graph", "@id", "@type", "@value", "@language", "@list"):
                        self.finding("DATA-01", "json-ld-keyword", path, key, "reviewed JSON-LD keyword")
                types = node.get("@type", [])
                types = types if isinstance(types, list) else [types]
                for t in types:
                    if not isinstance(t, str) or t not in SCHEMA_TYPES:
                        self.finding("DATA-01", "schema-type", path, t, SCHEMA_VOCABULARY_VERSION)
                    else:
                        for required in sorted(SCHEMA_REQUIRED.get(t, set())):
                            if not node.get(required):
                                self.finding("DATA-01", "schema-required-property", path, {"type": t, "missing": required}, "required subset field")
                    if t in ("Course", "Offer", "AggregateRating", "Review", "VideoObject"):
                        self.review(path, "schema-claim:" + str(t), "Validate visible support, identity, availability and evidence; JSON parsing is not acceptance.")
                    if t == "Offer" and isinstance(node.get("url"), str):
                        offer = urljoin(page_url(self.origin, path), node["url"])
                        # Query parameters may differ for legitimate campaign
                        # attribution; compare destination, not referral tokens.
                        destination = lambda u: (urlsplit(u).scheme, urlsplit(u).netloc.lower(), urlsplit(u).path.rstrip("/"))
                        linked = {destination(urljoin(page_url(self.origin, path), href)) for href in page.links}
                        if destination(offer) not in linked:
                            self.finding("DATA-03", "offer-without-visible-link", path, node["url"], "visible link to the claimed offer; human truth review also required")
                if "dateModified" in node:
                    modified.append(node["dateModified"])
                    self.compare_date(node["dateModified"], path, "JSON-LD.dateModified")
                if "datePublished" in node:
                    self.check_date(node["datePublished"], path, "JSON-LD.datePublished")
                if "BreadcrumbList" in types:
                    items = node.get("itemListElement", [])
                    if not isinstance(items, list):
                        self.finding("DATA-04", "breadcrumb-shape", path, items, "ordered ListItem array")
                    else:
                        for number, item in enumerate(items, 1):
                            if not isinstance(item, dict) or item.get("position") != number:
                                self.finding("DATA-04", "breadcrumb-order", path, item, number)
                            elif isinstance(item.get("item"), str):
                                self.resolve_link(path, item["item"], "schema-breadcrumb")
                for field in ("url", "mainEntityOfPage"):
                    if isinstance(node.get(field), str):
                        self.resolve_link(path, node[field], "schema-" + field)
        self.review(path, "schema-truth-and-identity", "Vocabulary subset checks only; review every statement against visible content and authoritative sources.")
        return modified

    def resolve_link(self, path, ref, kind):
        try:
            target = local_target(self.origin, page_url(self.origin, path), ref)
        except ValueError as exc:
            self.finding("DISC-06", "unsafe-url", path, ref, str(exc))
            return None
        if target is None:
            return None
        dest, fragment = target
        if dest not in self.manifest:
            self.finding("DISC-07", "broken-local-link", path, {"reference": ref, "kind": kind}, "existing local target")
        elif fragment and dest in self.pages and fragment not in self.pages[dest].ids:
            self.finding("DISC-06", "broken-fragment", path, {"reference": ref, "kind": kind}, "existing target ID")
        return dest

    def redirect_stub(self, path, page):
        """Return the target URL when `path` is a declared redirect stub, else None.

        A stub is registered with indexing_intent "noindex", answers with an
        immediate meta refresh and names the same registered indexable page as
        its canonical. It stays out of the sitemap and may be unlinked
        (GitHub Pages has no server-side 301). Any other combination keeps the
        normal self-canonical rules, so a mistyped stub still fails strict.
        """
        if self.records.get(path, {}).get("indexing_intent") != "noindex":
            return None
        indexable = {r.get("preferred_url") for r in self.records.values()
                     if r.get("indexing_intent") == "index"}
        for value in page.meta.get("refresh", []):
            match = re.fullmatch(r"\s*0\s*;\s*url\s*=\s*['\"]?([^'\"\s]+)['\"]?\s*", value, re.I)
            if match:
                target = urljoin(page_url(self.origin, path), match.group(1))
                if page.canonicals == [target] and target in indexable:
                    return target
        return None

    def html_checks(self):
        for path in sorted(self.manifest):
            if Path(path).suffix.lower() in (".html", ".htm"):
                try:
                    self.pages[path] = Page(self.read(path))
                except (UnicodeError, ValueError) as exc:
                    self.finding("DISC-07", "html-read", path, str(exc), "UTF-8 parseable HTML")
        extracted = {}
        titles, descriptions = defaultdict(list), defaultdict(list)
        self.stubs = {}
        for path, page in sorted(self.pages.items()):
            info = page.extracted()
            extracted[path] = info
            stub = self.redirect_stub(path, page)
            if stub:
                self.stubs[path] = stub
            expected = stub or self.records.get(path, {}).get("preferred_url", page_url(self.origin, path))
            if page.canonicals != [expected]:
                self.finding("DISC-03", "canonical-agreement", path, page.canonicals, [expected])
            og_urls = page.meta.get("og:url", [])
            og_allowed = [[], [expected]] if stub else [[expected]]
            if og_urls not in og_allowed:
                self.finding("DISC-03", "og-url-agreement", path, og_urls, [expected])
            if page.base:
                self.finding("DISC-06", "unsupported-base-url", path, page.base, "no base override; preserve local URL resolution")
            if len(page.h1) != 1 or not info["h1"][0]:
                self.finding("DISC-07", "one-h1", path, info["h1"], "one nonempty H1")
            if not info["title"] or page.title_count != 1:
                self.finding("DISC-07", "missing-title", path, {"text": info["title"], "count": page.title_count}, "one nonempty unique title")
            if len(info["description"]) != 1 or not info["description"][0].strip():
                self.finding("DISC-07", "description-count", path, info["description"], "one nonempty unique description")
            titles[info["title"]].append(path)
            descriptions[tuple(info["description"])].append(path)
            if not 50 <= len(info["title"]) <= 60:
                self.finding("DISC-07", "title-length", path, len(info["title"]), "editorial review (50–60 guidance, not ranking rule)", "warning")
            if info["description"] and not 150 <= len(info["description"][0]) <= 160:
                self.finding("DISC-07", "description-length", path, len(info["description"][0]), "editorial review (150–160 guidance)", "warning")
            for previous, current in zip(page.headings, page.headings[1:]):
                if current > previous + 1:
                    self.finding("DISC-07", "heading-skip", path, [previous, current], "logical hierarchy", "warning")
            for ident, count in Counter(page.ids).items():
                if count > 1:
                    self.finding("DISC-06", "duplicate-fragment", path, ident, "unique ID")
            for required in self.records.get(path, {}).get("protected_fragments", []):
                if required not in page.ids:
                    self.finding("DISC-06", "protected-fragment", path, required, "retained original fragment")
            for name, values in page.meta.items():
                if name in ("robots", "googlebot", "bingbot", "oai-searchbot", "perplexitybot", "x-robots-tag"):
                    for value in values:
                        v = value.lower()
                        if re.search(r"\b(noindex|none|nofollow|nosnippet|noarchive|nocache|noimageindex)\b|"
                                     r"max-snippet\s*:\s*0\b|max-image-preview\s*:\s*none", v):
                            self.finding("DISC-02", "blocking-index-directive", path, {name: value}, "indexable, followable, snippet-eligible")
                for value in values:
                    self.terminology(path, value, "metadata:" + name)
                    if name in ("article:modified_time", "og:updated_time", "last-modified"):
                        self.compare_date(value, path, name)
            self.terminology(path, "".join(page.text), "decoded rendered text including adjacent inline elements")
            for comment in page.comments:
                self.terminology(path, comment, "public HTML comment")
            for value in page.accessible:
                self.terminology(path, value, "accessibility or UI attribute")
            for script in page.scripts:
                if script["type"] != "application/ld+json":
                    self.terminology(path, script["text"], "inline script strings")
            info["date_modified"] = self.schema(path, page)
            for time in page.times:
                self.check_date(time["datetime"], path, "visible time datetime")
                # "Reviewed" is NOT a substantive-change date. Keep separately
                # inventoried; never copy it to modified_at automatically.
            if any(alt is None for alt in page.image_alts):
                self.finding("NFR-02", "missing-image-alt", path, "image without alt", "descriptive alt or empty alt for decoration")
            for tag, key, ref in page.references:
                self.resolve_link(path, ref, tag + ":" + key)
            for ref in page.links:
                dest = self.resolve_link(path, ref, "crawlable-anchor")
                if dest in self.pages:
                    self.graph[path].add(dest)
            for field in ("og:image", "twitter:image"):
                for ref in page.meta.get(field, []):
                    self.resolve_link(path, ref, field)
            if path.startswith("methodology/"):
                self.methodology(path, page)
            self.review(path, "terminology-media", "Text checks do not inspect raster pixels, video speech, third-party thumbnails or immutable external media.")
        for kind, groups in (("title", titles), ("description", descriptions)):
            for value, paths in groups.items():
                if len(paths) > 1:
                    self.finding("DISC-07", "duplicate-" + kind, paths[0], paths, "intent-specific unique " + kind)
        reachable, queue = set(), deque(["index.html"])
        while queue:
            node = queue.popleft()
            if node not in reachable:
                reachable.add(node)
                queue.extend(sorted(self.graph[node] - reachable))
        for path in sorted(set(self.pages) - reachable - set(self.stubs)):
            self.finding("DISC-07", "orphan-page", path, "unreachable from homepage via HTML anchors", "crawlable path")
        return extracted, sorted(reachable & set(self.pages))

    def methodology(self, path, page):
        for tag, key, ref in page.references:
            if TRACKING.search(ref):
                self.finding("NFR-04", "methodology-tracking", path, ref, "no site analytics or marketing requests")
            if tag in ("script", "link", "img", "source") and key in ("href", "src", "srcset"):
                target = local_target(self.origin, page_url(self.origin, path), ref)
                if target and not target[0].startswith("methodology/"):
                    self.finding("NFR-05", "methodology-root-dependency", path, ref, "methodology-local assets")
            if key in ("href", "action"):
                u = urlsplit(urljoin(page_url(self.origin, path), ref))
                if ("udemy.com" in (u.hostname or "") or "mailerlite" in (u.hostname or "")
                        or u.fragment.lower() in ("courses", "newsletter", "free-course", "lead-magnet")
                        or "/get-started" in u.path):
                    self.finding("CONTENT-01", "methodology-sales-link", path, ref, "reference-only journey")
        for script in page.scripts:
            if script["type"] != "application/ld+json":
                if TRACKING.search(script["text"]):
                    self.finding("NFR-04", "methodology-tracking", path, "inline script", "no tracking")
                if script.get("src"):
                    target = local_target(self.origin, page_url(self.origin, path), script["src"])
                    if target and target[0] in self.manifest and TRACKING.search(self.read(target[0])):
                        self.finding("NFR-04", "methodology-tracking", path, target[0], "no tracking in loaded local script")
        if page.forms:
            self.finding("CONTENT-01", "methodology-form", path, page.forms, "reference-only; no signup or commercial forms")
        # Flag obvious sales wording for review without treating normal discussion
        # of "course" or "production" as a forbidden CTA.
        if SALES.search("".join(page.text)):
            self.finding("CONTENT-01", "methodology-sales-copy", path, "commercial action wording", "no sales/placeholder CTA")
        primary = self.registry.get("rules", {}).get("protected_primary_paths", PRIMARY_PATHS)
        if path in primary:
            observed = []
            for ref in page.nav_links:
                target = local_target(self.origin, page_url(self.origin, path), ref)
                observed.append(target[0] if target else ref)
            if observed != primary:
                self.finding("CONTENT-01", "methodology-primary-navigation", path, observed, primary)
        ids = self.records.get(path, {}).get("protected_video_ids", [])
        core = self.registry.get("rules", {}).get("core_videos", CORE_VIDEOS)
        ids = sorted(set(ids + ([core[path]] if path in core else [])))
        for video in ids:
            urls = [ref for tag, key, ref in page.references if tag == "iframe" and key == "src"]
            if not any(urlsplit(ref).hostname in ("www.youtube-nocookie.com", "www.youtube.com", "youtube.com")
                       and urlsplit(ref).path == "/embed/" + video for ref in urls):
                self.finding("DISC-06", "protected-core-video", path, urls, video)

    def sitemap_checks(self):
        intended = self.registry.get("rules", {}).get("sitemaps", ["sitemap.xml", "methodology/sitemap.xml"])
        ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        links = defaultdict(set)
        parsed = set()
        queue = deque(intended)
        while queue:
            path = queue.popleft()
            if path in parsed:
                continue
            parsed.add(path)
            if not safe_relative(path) or path not in self.manifest:
                self.finding("DISC-04", "missing-sitemap", path, "absent or unsafe", "intended sitemap exists")
                continue
            try:
                raw = self.read(path)
                if "<!DOCTYPE" in raw.upper() or "<!ENTITY" in raw.upper():
                    raise ValueError("DTD/entities are not allowed")
                root = ET.fromstring(raw)
                if root.tag not in (ns + "urlset", ns + "sitemapindex"):
                    raise ValueError("expected sitemap namespace and urlset/sitemapindex")
                for element in root:
                    expected_tag = ns + ("sitemap" if root.tag == ns + "sitemapindex" else "url")
                    if element.tag != expected_tag:
                        self.finding("DISC-04", "sitemap-entry-type", path, element.tag, expected_tag)
                        continue
                    locs = element.findall(ns + "loc")
                    if len(locs) != 1 or not (locs[0].text or "").strip():
                        self.finding("DISC-04", "sitemap-location", path, "missing/duplicate loc", "one absolute URL")
                        continue
                    loc = locs[0].text.strip()
                    if root.tag == ns + "sitemapindex":
                        target = local_target(self.origin, self.origin + "/", loc)
                        if not target or target[1] or loc != self.origin + "/" + target[0]:
                            self.finding("DISC-04", "sitemap-index-location", path, loc, "local absolute sitemap URL")
                        else:
                            links[path].add(target[0])
                            queue.append(target[0])
                        continue
                    mods = element.findall(ns + "lastmod")
                    if len(mods) > 1:
                        self.finding("DISC-05", "duplicate-lastmod", path, loc, "zero or one lastmod")
                    modified = (mods[0].text or "").strip() if mods else None
                    self.sitemap_entries[loc].append({"sitemap": path, "lastmod": modified})
            except (ET.ParseError, ValueError, UnicodeError) as exc:
                self.finding("DISC-04", "sitemap-parse", path, str(exc), "safe valid sitemap XML")
        expected = {p["preferred_url"]: path for path, p in self.records.items() if p.get("indexing_intent") == "index"}
        for url in sorted(set(expected) - set(self.sitemap_entries)):
            self.finding("DISC-04", "sitemap-missing-page", expected[url], url, "canonical in sitemap union")
        for url, entries in sorted(self.sitemap_entries.items()):
            if url not in expected:
                self.finding("DISC-04", "sitemap-unexpected-url", url, entries, "registered indexable canonical")
                continue
            counts = Counter(e["sitemap"] for e in entries)
            if any(count > 1 for count in counts.values()):
                self.finding("DISC-04", "sitemap-duplicate-url", url, entries, "at most once per sitemap")
            for entry in entries:
                self.compare_date(entry["lastmod"], expected[url], "sitemap:" + entry["sitemap"])
        return intended, links

    def robots_checks(self, intended, sitemap_links):
        if "robots.txt" not in self.manifest:
            self.finding("DISC-04", "missing-robots", "robots.txt", "absent", "root crawl policy and sitemaps")
            return
        policy = Robots(self.read("robots.txt"))
        advertised = set()
        for url in policy.sitemaps:
            target = local_target(self.origin, self.origin + "/", url)
            if not target or url != self.origin + "/" + target[0]:
                self.finding("DISC-04", "robots-sitemap-url", "robots.txt", url, "absolute local sitemap URL")
            else:
                advertised.add(target[0])
                if target[0] not in self.manifest:
                    self.finding("DISC-04", "robots-missing-sitemap", "robots.txt", url, "existing sitemap")
        queue = deque(advertised)
        while queue:
            for child in sitemap_links.get(queue.popleft(), []):
                if child not in advertised:
                    advertised.add(child)
                    queue.append(child)
        for path in intended:
            if path not in advertised:
                self.finding("DISC-04", "robots-undiscoverable-sitemap", "robots.txt", path, "advertised directly or through index")
        bots = ["Googlebot", "Googlebot-Image", "Googlebot-Video", "Bingbot", "OAI-SearchBot", "PerplexityBot"]
        resources = [p for p in self.records if self.records[p].get("indexing_intent") == "index"]
        resources += [a["path"] for a in self.registry.get("assets", []) if a.get("public_status") == "public"]
        for path in sorted(resources):
            urlpath = urlsplit(page_url(self.origin, path)).path if path in self.records else "/" + path
            for bot in bots:
                if not policy.allowed(bot, urlpath):
                    self.finding("AI-01", "robots-block", path, {"agent": bot, "path": urlpath}, "search retrieval allowed")
        self.review("robots.txt", "owner-policy-and-serving-layer", "Training choice, Google AI property settings, real crawler access and HTTP headers require owner/production evidence.")

    def archive_checks(self, asset):
        path = asset["path"]
        if path not in self.manifest:
            return
        source = asset.get("source_path")
        expected = asset.get("archive_members", [])
        if not safe_relative(source) or not expected:
            self.finding("DISC-01", "zip-contract", path, asset, "explicit safe source path and member contract")
            return
        try:
            with zipfile.ZipFile(self.site / path) as archive:
                infos = archive.infolist()
                if len(infos) > 1000 or sum(x.file_size for x in infos) > 16 * 1024 * 1024:
                    raise ValueError("archive exceeds bounded inspection limits")
                names = [x.filename for x in infos]
                self.archive_inventory[path] = [
                    {"path": x.filename, "size": x.file_size, "directory": x.is_dir()} for x in infos]
                if sorted(names) != sorted(expected) or len(names) != len(set(names)):
                    self.finding("DISC-01", "zip-member-contract", path, sorted(names), sorted(expected))
                source_files = {p for p in self.manifest if p.startswith(source + "/")}
                seen_sources = set()
                for info in infos:
                    name = info.filename
                    mode = info.external_attr >> 16
                    if (not safe_relative(name.rstrip("/")) or name.count("/") < 1
                            or stat.S_ISLNK(mode) or info.flag_bits & 1
                            or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))):
                        self.finding("DISC-01", "unsafe-zip-member", path, name, "unencrypted regular member; no traversal, drive or symlink")
                        continue
                    if name not in expected:
                        continue
                    if info.is_dir():
                        continue
                    if info.file_size > 4 * 1024 * 1024 or info.file_size / max(1, info.compress_size) > 200:
                        self.finding("DISC-01", "zip-size-limit", path, name, "bounded non-bomb member")
                        continue
                    relative = name.split("/", 1)[1]
                    source_file = source + "/" + relative
                    seen_sources.add(source_file)
                    data = archive.read(info)  # CRC checked; never extract or execute.
                    if source_file not in self.manifest or hashlib.sha256(data).hexdigest() != self.manifest[source_file]:
                        self.finding("DISC-01", "zip-source-mismatch", path, name, source_file + " byte equality")
                    if Path(name).suffix.lower() in TEXT_EXTENSIONS:
                        try:
                            self.terminology(path + "!" + name, data.decode("utf-8-sig"), "archive text")
                        except UnicodeError:
                            self.finding("CONTENT-09", "archive-text-encoding", path, name, "UTF-8 inspectable text")
                if source_files != seen_sources:
                    self.finding("DISC-01", "zip-source-set", path, sorted(seen_sources), sorted(source_files))
        except (OSError, ValueError, RuntimeError, NotImplementedError, zipfile.BadZipFile) as exc:
            self.finding("DISC-01", "zip-read", path, str(exc), "safe readable ZIP")

    def asset_checks(self):
        for asset in self.registry.get("assets", []):
            path = asset.get("path", "")
            if asset.get("public_status") != "public" or path not in self.manifest:
                continue
            suffix = Path(path).suffix.lower()
            if suffix == ".zip":
                self.archive_checks(asset)
            elif suffix in TEXT_EXTENSIONS:
                try:
                    text = self.read(path)
                    if suffix == ".json":
                        for s in json_strings(load_json(text)):
                            self.terminology(path, s, "decoded JSON strings")
                    else:
                        self.terminology(path, text, "public text asset")
                    if suffix in (".md", ".txt"):
                        # Markdown destinations, not HTML parsing by regex.
                        for ref in re.findall(r"\]\(([^)\s]+)(?:\s+[^)]*)?\)", text):
                            self.resolve_link(path, ref, "text-directory-link")
                except (UnicodeError, ValueError) as exc:
                    self.finding("CONTENT-09", "text-asset-parse", path, str(exc), "inspectable text")
            elif suffix == ".pdf":
                self.finding("CONTENT-09", "pdf-review-required", path, "new PDF surface", "approved extraction and terminology check")
            else:
                self.review(path, "asset-visual-terminology", "Raster/media contents need human inspection; no OCR or video review inferred.")

    def baseline_checks(self):
        if not self.baseline:
            return
        old = self.baseline.get("pages", {})
        for path, facts in old.items():
            if path not in self.pages:
                self.finding("DISC-06", "baseline-page-removed", path, "absent", "original URL retained")
                continue
            for fragment in facts.get("ids", []):
                if fragment not in self.pages[path].ids:
                    self.finding("DISC-06", "baseline-fragment-removed", path, fragment, "retained")
            # A declared redirect stub intentionally moves its canonical to the
            # successor page; the original URL itself is retained.
            if (facts.get("canonical") != self.pages[path].canonicals
                    and self.stubs.get(path) not in self.pages[path].canonicals):
                self.finding("DISC-06", "baseline-canonical-changed", path, self.pages[path].canonicals, facts.get("canonical"))
        # A no-op source cannot acquire a new freshness date. Content-change
        # approval itself remains human judgment, not mtime or a build clock.
        old_manifest = self.baseline.get("manifest", {})
        for path, facts in old.items():
            if old_manifest.get(path) and old_manifest[path] == self.manifest.get(path):
                before = facts.get("registry_modified_at")
                after = self.records.get(path, {}).get("modified_at")
                if "registry_modified_at" in facts and before != after:
                    original_dates = set(facts.get("date_modified", [])) - {None}
                    original_dates.update(
                        entry["lastmod"] for entry in self.baseline.get("sitemap_entries", {}).get(
                            page_url(self.origin, path), []) if entry.get("lastmod") is not None)
                    # Registering an already-declared historical date is not
                    # refreshing freshness on a no-op deploy. Invented dates
                    # still fail; this does not assign human approval.
                    if not (before is None and after in original_dates):
                        self.finding("DISC-05", "no-op-date-change", path, after, before)

    def run(self):
        self.validate_registry()
        protected = self.registry.get("rules", {}).get("protected_primary_paths", PRIMARY_PATHS)
        for path in protected:
            if path not in self.records or path not in self.manifest:
                self.finding("DISC-06", "protected-primary-page", path, "missing from registry or source", "preserved original primary page")
        extracted, reachable = self.html_checks()
        intended, links = self.sitemap_checks()
        self.robots_checks(intended, links)
        self.asset_checks()
        self.baseline_checks()
        for path, facts in extracted.items():
            facts["registry_modified_at"] = self.records.get(path, {}).get("modified_at")
        after = build_manifest(self.site)
        if after != self.manifest:
            self.finding("NFR-06", "source-changed-during-check", "site", manifest_digest(after), self.fingerprint)
        # Deduplicate repeated link/surface findings deterministically.
        findings = sorted({canonical_json(f): f for f in self.findings}.values(),
                          key=lambda f: (f["file_or_url"], f["requirement_id"], f["code"], canonical_json(f["observed"])))
        human = sorted({canonical_json(h): h for h in self.human}.values(),
                       key=lambda h: (h["file_or_url"], h["topic"], canonical_json(h["detail"])))
        return {
            "report_version": 1, "api_version": API_VERSION,
            "environment": self.environment, "source_fingerprint": self.fingerprint,
            "fingerprint_algorithm": "sha256(compact sorted-key JSON of relative path to file SHA256)",
            "manifest": self.manifest, "pages": extracted,
            "archives": self.archive_inventory,
            "sitemap_entries": dict(sorted(self.sitemap_entries.items())),
            "reachable_pages": reachable, "findings": findings,
            "summary": {
                "files": len(self.manifest), "html_pages": len(self.pages),
                "json_ld_blocks": sum(len(p.json_ld) for p in self.pages.values()),
                "sitemap_unique_urls": len(self.sitemap_entries),
                "errors": sum(f["severity"] == "error" for f in findings),
                "warnings": sum(f["severity"] == "warning" for f in findings),
            },
            "machine_status": "fail" if any(f["severity"] == "error" for f in findings) else "pass",
            "human_acceptance": "pending", "human_review": human,
            "schema_vocabulary": {"version": SCHEMA_VOCABULARY_VERSION,
                                  "sources": SCHEMA_SOURCES, "scope": "finite subset; external vocabulary review pending"},
            "limitations": ["No network or production checks", "No W3C conformance certification",
                            "No schema truth/eligibility certification", "No raster/video content inspection",
                            "No release or owner approval implied"],
        }


def check_site(site, registry, *, environment="source", baseline=None):
    if not isinstance(registry, dict) or not isinstance(registry.get("pages"), list) or not isinstance(registry.get("assets"), list):
        raise ValueError("registry/contract requires pages and assets arrays")
    for records in (registry["pages"], registry["assets"]):
        if any(not isinstance(record, dict) for record in records):
            raise ValueError("page/asset records must be JSON objects")
    if registry.get("contract_kind") == "aam-public-check":
        validate_public_contract(registry)
    return Checker(site, registry, environment, baseline).run()


def write_json(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True, type=Path)
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--registry", type=Path)
    sources.add_argument("--public-contract", type=Path)
    parser.add_argument("--mode", choices=("inventory", "strict"), default="inventory")
    parser.add_argument("--environment", choices=("source", "preview", "public-artifact"), default="source")
    parser.add_argument("--baseline", type=Path, help="Prior checker inventory: preserve original URLs/IDs and no-op dates")
    parser.add_argument("--report", type=Path, help="Write JSON outside site; stdout is always JSON")
    parser.add_argument("--export-public-contract", type=Path, help="Write allowlisted contract outside site")
    args = parser.parse_args(argv)
    try:
        for output in (args.report, args.export_public_contract):
            if output and (output.resolve() == args.site.resolve() or args.site.resolve() in output.resolve().parents):
                raise ValueError("outputs must be outside --site (checks never mutate source)")
            if output and output.resolve() in {p.resolve() for p in (args.registry, args.public_contract, args.baseline) if p}:
                raise ValueError("output must not overwrite an input contract/baseline")
        registry = load_json((args.registry or args.public_contract).read_text(encoding="utf-8"))
        if args.public_contract and registry.get("contract_kind") != "aam-public-check":
            raise ValueError("--public-contract requires an exported public contract")
        baseline = load_json(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
        report = check_site(args.site, registry, environment=args.environment, baseline=baseline)
        if args.export_public_contract:
            write_json(args.export_public_contract, export_public_contract(registry))
        if args.report:
            write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
        return 1 if args.mode == "strict" and report["summary"]["errors"] else 0
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps({"machine_status": "input-error", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
