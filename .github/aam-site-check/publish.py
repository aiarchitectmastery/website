#!/usr/bin/env python3
"""Fail-closed AAM publication; standard library only, no rsync or shared clone.

Internal checker CLI is the PLAN's --site / --registry / --mode strict.
check.py API v1 export_public_contract(registry) supplies the field-allowlisted
public facts. The publisher wraps those facts with explicit classified paths
and validates their serialization types; it does not duplicate P0 site rules.
The served stage uses the SAME checker with --public-contract.

The exact public workflow below must be installed only after baseline approval.
No command here establishes that Pages has completed a deployment.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile


EXPECTED_REMOTE = "https://github.com/aiarchitectmastery/website.git"
BRANCH = "main"
COPILOT_TRAILER = "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
SAFE_PATH_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.@+/- "
)
BUNDLE = ".github/aam-site-check"
WORKFLOW_PATH = ".github/workflows/deploy.yml"
ROOT = Path(__file__).resolve().parents[2]
CONTRACT_KEYS = {
    "schema_version", "registry", "site_paths", "repository_paths",
    "excluded_paths",
}
BUNDLE_PATHS = {
    f"{BUNDLE}/check.py", f"{BUNDLE}/publish.py",
    f"{BUNDLE}/contract.json", f"{BUNDLE}/registry.json",
    f"{BUNDLE}/manifest.json",
}

# Deliberately exact, rather than accepting a YAML substring that might occur
# in comments while an unchecked upload still publishes ".".
PUBLIC_WORKFLOW = """# Generated contract: tools/aam_website/publish.py PUBLIC_WORKFLOW
name: Validate and deploy AAM site

on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

concurrency:
  group: aam-pages-${{ github.ref }}
  cancel-in-progress: false

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Validate public contract and create served-only artifact
        run: python3 .github/aam-site-check/publish.py public-stage --site . --output "$RUNNER_TEMP/aam-site-stage"
      - uses: actions/upload-pages-artifact@v3
        with:
          path: ${{ runner.temp }}/aam-site-stage
  deploy:
    if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'
    needs: validate
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/configure-pages@v5
      - name: Deploy validated artifact
        id: deployment
        uses: actions/deploy-pages@v4
"""


class PublishError(ValueError):
    """An unmet release gate (never a reason to relax strict)."""


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True,
                       indent=2) + "\n").encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_json(path):
    # Duplicate keys can conceal a different meaning from reviewers.
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise PublishError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=unique)


def safe_path(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise PublishError("Invalid publication path")
    parts = value.split("/")
    # Ordinary internal ASCII spaces are safe with argv/list subprocesses.
    # Keep leading/trailing component whitespace, controls and traversal banned.
    if (any(p in ("", ".", "..", ".git") or p != p.strip() for p in parts)
            or PurePosixPath(value).is_absolute()
            or any(character not in SAFE_PATH_CHARACTERS for character in value)):
        raise PublishError(f"Unsafe publication path: {value!r}")
    return value


def regular_bytes(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise PublishError(f"Not an unlinked regular file: {path.name}")
    # O_NOFOLLOW prevents a final-component symlink swap on supported hosts.
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise PublishError("File changed while reading")
        return stream.read()


def read_tree(root, *, public=False):
    """Read bytes, reject links/special files, never follow excluded symlinks."""
    root = Path(root).absolute()
    if root.is_symlink() or not root.is_dir():
        raise PublishError("Site must be a real directory")
    files = {}

    def walk(directory):
        for path in sorted(directory.iterdir()):
            relative = path.relative_to(root).as_posix()
            if public and relative == ".git":
                if path.is_symlink() or not path.is_dir():
                    raise PublishError("Public fixture .git must be a directory")
                continue
            safe_path(relative)
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode):
                walk(path)
            elif stat.S_ISREG(mode):
                files[relative] = regular_bytes(path)
            else:
                raise PublishError(f"Symlink or special file: {relative}")
    walk(root)
    return files


def file_manifest(files):
    entries = [{"path": name, "sha256": sha(data), "bytes": len(data)}
               for name, data in sorted(files.items())]
    return {"schema_version": 1, "files": entries,
            "sha256": sha(canonical(entries))}


def run(command, *, cwd=None, binary=False):
    # No shell expansion; no secrets/credentials printed or stored.
    environment = os.environ.copy()
    if command[0] == "git":
        # Inherited GIT_DIR/WORK_TREE/CONFIG_COUNT can redirect work into the
        # user's repository or inject config. Normal credential helpers remain
        # available, but interactive authentication and hooks are disabled.
        environment = {k: v for k, v in environment.items()
                       if not k.startswith("GIT_")}
        environment["GIT_TERMINAL_PROMPT"] = "0"
        command = ["git", "-c", "core.hooksPath=/dev/null", *command[1:]]
    result = subprocess.run(command, cwd=cwd, check=True, text=not binary,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=environment)
    return result.stdout if binary else result.stdout.strip()


def strict(checker, site, registry, *, public=False):
    try:
        output = run([sys.executable, str(checker), "--site", str(site),
                      "--public-contract" if public else "--registry",
                      str(registry), "--mode", "strict", "--environment",
                      "public-artifact" if public else "source"])
        if output:
            print(output, file=sys.stderr)
    except subprocess.CalledProcessError as exc:
        # Preserve diagnostic evidence locally, never in the public bundle.
        print(exc.stdout or "", file=sys.stderr)
        print(exc.stderr or "", file=sys.stderr)
        raise PublishError("Strict validation failed; no publication") from exc


def checker_module(checker):
    # Prevent import bytecode writes before strict source validation.
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("aam_public_checker", checker)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = previous


def validate_contract(contract, checker):
    """Envelope checks plus the SAME checker's explicit public field schema."""
    if not isinstance(contract, dict) or set(contract) != CONTRACT_KEYS:
        raise PublishError("Unexpected public contract fields")
    if contract["schema_version"] != 1 or not isinstance(contract["registry"], dict):
        raise PublishError("Unsupported public contract version/registry")
    groups = []
    for key in ("site_paths", "repository_paths", "excluded_paths"):
        paths = contract[key]
        if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
            raise PublishError(f"{key} must be an explicit path list")
        if paths != sorted(set(paths)):
            raise PublishError(f"{key} must be sorted and unique")
        groups.append({safe_path(p) for p in paths})
    site, repository, excluded = groups
    if not site or "index.html" not in site:
        raise PublishError("Empty/incomplete served allowlist")
    if site & repository or site & excluded or repository & excluded:
        raise PublishError("Publication path classifications overlap")
    if repository != {WORKFLOW_PATH}:
        raise PublishError("Only the reviewed deploy workflow is repository-only")
    if any(p.startswith(".") or "/." in p for p in site if p != ".nojekyll"):
        raise PublishError("Hidden paths must not be served")
    if (site | repository | excluded) & BUNDLE_PATHS:
        raise PublishError("Checker bundle is generated, not source content")
    validate_public_registry(contract["registry"], checker)
    declared = {p["path"] for p in contract["registry"]["pages"]}
    declared.update(a["path"] for a in contract["registry"]["assets"])
    if site != declared:
        raise PublishError("Served allowlist differs from checker public facts")
    return contract


def validate_public_registry(registry, checker):
    """Delegate field/type allowlisting to the SAME checker's API v1."""
    module = checker_module(checker)
    exporter = getattr(module, "export_public_contract", None)
    validator = getattr(module, "validate_public_contract", None)
    if (getattr(module, "API_VERSION", None) != 1
            or not callable(exporter) or not callable(validator)):
        raise PublishError("BLOCKED: checker public export/validation API v1 missing")
    # Re-export must be identical: unknown fields at ANY projected boundary
    # (including relation objects) are not silently carried into public JSON.
    if exporter(registry) != registry:
        raise PublishError("Private/unknown fields in public checker contract")
    expected = {"schema_version", "contract_kind", "api_version", "origin",
                "pages", "assets", "entities", "exceptions", "rules"}
    if (set(registry) != expected or registry["schema_version"] != 1
            or registry["api_version"] != 1
            or registry["contract_kind"] != "aam-public-check"
            or registry["origin"] != "https://aiarchitectmastery.com"
            or registry["entities"] != [] or registry["exceptions"] != []):
        raise PublishError("Unexpected public registry envelope")
    if validator(registry) is not True:
        raise PublishError("Checker rejected public serialization contract")
    # Publisher adds only filesystem safety; no duplicated semantic rules.
    for page in registry["pages"]:
        safe_path(page["path"])
    for asset in registry["assets"]:
        if asset.get("public_status") != "public":
            raise PublishError("Nonpublic asset in exported registry")
        safe_path(asset["path"])
        if "source_path" in asset:
            safe_path(asset["source_path"])
        for member in asset.get("archive_members", []):
            safe_path(member.rstrip("/"))


def export_contract(checker, registry):
    module = checker_module(checker)
    exporter = getattr(module, "export_public_contract", None)
    if not callable(exporter):
        raise PublishError("BLOCKED: checker export_public_contract interface missing")
    internal = load_json(registry)
    exported = exporter(internal)
    contract = {
        "schema_version": 1,
        "registry": exported,
        "site_paths": sorted({p["path"] for p in exported["pages"]} |
                             {a["path"] for a in exported["assets"]}),
        "repository_paths": sorted(a["path"] for a in internal["assets"]
                                   if a.get("public_status") == "repository-only"),
        "excluded_paths": sorted(a["path"] for a in internal["assets"]
                                 if a.get("public_status") == "excluded"),
    }
    return validate_contract(contract, checker)


def classify(files, contract, *, public=False):
    expected = set(contract["site_paths"]) | set(contract["repository_paths"])
    if public:
        expected |= BUNDLE_PATHS
        unknown = set(files) - expected
    else:
        unknown = set(files) - expected - set(contract["excluded_paths"])
    missing = expected - set(files)
    if unknown or missing:
        raise PublishError(f"Unclassified files: {sorted(unknown)}; missing: {sorted(missing)}")
    if files.get(WORKFLOW_PATH) != PUBLIC_WORKFLOW.encode("utf-8"):
        raise PublishError("BLOCKED: safe public workflow not installed/confirmed")


def write_files(root, files):
    """Only called with a newly created, owned, empty directory."""
    if any(root.iterdir()):
        raise PublishError("Refusing to reuse a nonempty staging directory")
    for name, data in sorted(files.items()):
        target = root / safe_path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
        target.chmod(0o644)


def source_revision(repo):
    revision = run(["git", "-C", str(repo), "rev-parse", "--verify", "HEAD"])
    if not re.fullmatch(r"[0-9a-f]{40,64}", revision):
        raise PublishError("Cannot establish source commit")
    return revision


def prepare(site, registry, checker, repo, workspace):
    """Source strict succeeds before staging, local git, clone, sync or writes."""
    before = read_tree(site)
    checker_bytes = regular_bytes(checker)
    registry_bytes = regular_bytes(registry)
    publisher_bytes = regular_bytes(Path(__file__))
    strict(checker, site, registry)
    contract = export_contract(checker, registry)
    classify(before, contract)
    served = {p: before[p] for p in contract["site_paths"]}
    # Even names of classified private source exclusions stay internal.
    contract = {**contract, "excluded_paths": []}
    validate_contract(contract, checker)
    public_manifest = file_manifest(served)
    public_files = dict(served)
    public_files.update({p: before[p] for p in contract["repository_paths"]})
    public_files.update({
        f"{BUNDLE}/check.py": checker_bytes,
        f"{BUNDLE}/publish.py": publisher_bytes,
        f"{BUNDLE}/registry.json": canonical(contract["registry"]),
        f"{BUNDLE}/contract.json": canonical(contract),
        f"{BUNDLE}/manifest.json": canonical(public_manifest),
    })
    # The caller creates this workspace only AFTER source strict (see main).
    stage = workspace / "served"
    stage.mkdir()
    write_files(stage, served)
    bundle_stage = workspace / "repository"
    bundle_stage.mkdir()
    write_files(bundle_stage, public_files)
    strict(checker, stage, bundle_stage / BUNDLE / "registry.json", public=True)
    # Also validate using only the exported public checker/registry.
    strict(bundle_stage / BUNDLE / "check.py", stage,
           bundle_stage / BUNDLE / "registry.json", public=True)
    if (read_tree(stage) != served
            or read_tree(bundle_stage) != public_files
            or read_tree(site) != before
            or regular_bytes(checker) != checker_bytes
            or regular_bytes(registry) != registry_bytes
            or regular_bytes(Path(__file__)) != publisher_bytes):
        raise PublishError("Source/tool/stage changed during validation")
    approval = {
        "schema_version": 1,
        "remote": EXPECTED_REMOTE,
        "branch": BRANCH,
        "source_commit": source_revision(repo),
        # Includes dirty/untracked content and classified exclusions; no paths
        # or internal registry bytes are exported to the public repository.
        "source_tree": file_manifest(before),
        "registry_sha256": sha(registry_bytes),
        "checker_sha256": sha(checker_bytes),
        "publisher_sha256": sha(publisher_bytes),
        "served": public_manifest,
        "repository": file_manifest(public_files),
    }
    return approval, public_files


def git_at(directory, *arguments):
    return run(["git", "-C", str(directory), *arguments])


def verify_index(clone, files):
    """Git filters/line-ending settings must not alter approved stored bytes."""
    records = git_at(clone, "ls-files", "--stage", "-z")
    actual = {}
    for record in records.split("\0"):
        if not record:
            continue
        header, name = record.split("\t", 1)
        mode, blob, stage = header.split()
        safe_path(name)
        if mode != "100644" or stage != "0" or name in actual:
            raise PublishError("Unexpected index mode/stage/path")
        actual[name] = run(["git", "-C", str(clone), "cat-file", "blob", blob],
                           binary=True)
    if actual != files:
        raise PublishError("Git index bytes differ from approved repository manifest")
    return git_at(clone, "write-tree")


def verified_remote(clone):
    fetch = git_at(clone, "remote", "get-url", "--all", "origin").splitlines()
    push = git_at(clone, "remote", "get-url", "--push", "--all", "origin").splitlines()
    if fetch != [EXPECTED_REMOTE] or push != [EXPECTED_REMOTE]:
        raise PublishError("Unexpected fetch/push remote; refusing to sync")
    if git_at(clone, "symbolic-ref", "--short", "HEAD") != BRANCH:
        raise PublishError("Unexpected remote branch")
    if git_at(clone, "status", "--porcelain"):
        raise PublishError("Fresh clone is unexpectedly dirty")


def publication_commit_message(message):
    """Keep user text, with exactly one required attribution trailer at end."""
    lines = [line for line in message.strip().splitlines()
             if line.strip().casefold() != COPILOT_TRAILER.casefold()]
    body = "\n".join(lines).strip() or "update: publish approved AAM artifact"
    return body + "\n\n" + COPILOT_TRAILER


def publish(public_files, workspace, message):
    """Only operates on a fresh owned clone, never the user's worktree."""
    clone = workspace / "remote"
    # --get-url performs local config expansion only (no remote request).
    # Refuse global insteadOf rewrites BEFORE contacting the clone URL.
    if run(["git", "ls-remote", "--get-url", EXPECTED_REMOTE]) != EXPECTED_REMOTE:
        raise PublishError("Git URL rewrite changes expected remote")
    # --no-hardlinks avoids sharing local objects; URL is never user-supplied.
    run(["git", "clone", "--no-hardlinks", "--single-branch", "--branch",
         BRANCH, "--", EXPECTED_REMOTE, str(clone)])
    verified_remote(clone)  # Before any deletion or sync.
    current = read_tree(clone, public=True)
    if current == public_files:
        # Checkout filters must not make different stored blobs LOOK identical.
        verify_index(clone, public_files)
        print("No-op: public repository bytes already match; no commit or push. "
              "Pages deployment status remains unverified.")
        return
    # Delete only regular files enumerated inside THIS fresh owned clone.
    # Reject symlinks/special files in read_tree before touching anything.
    for name in sorted(current):
        (clone / name).unlink()
    # Remove empty directories only, bottom-up; never .git.
    directories = sorted(
        (p for p in clone.rglob("*") if p.is_dir()
         and ".git" not in p.relative_to(clone).parts),
        key=lambda p: len(p.parts), reverse=True)
    for directory in directories:
        directory.rmdir()
    for name, data in sorted(public_files.items()):
        target = clone / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
        target.chmod(0o644)
    if read_tree(clone, public=True) != public_files:
        raise PublishError("Post-sync bytes differ from approved manifest")
    strict(clone / BUNDLE / "check.py", workspace / "served",
           clone / BUNDLE / "registry.json", public=True)
    # Verify actual clone's served bytes too, using the isolated public path.
    public_stage(clone, workspace / "post-sync")
    git_at(clone, "add", "--all")
    approved_tree = verify_index(clone, public_files)
    if not git_at(clone, "diff", "--cached", "--name-only"):
        print("No-op: no staged change; no commit/push. Pages unverified.")
        return
    git_at(clone, "-c", "core.hooksPath=/dev/null", "commit", "--no-gpg-sign",
           "-m", publication_commit_message(message))
    if git_at(clone, "rev-parse", "HEAD^{tree}") != approved_tree:
        raise PublishError("Committed tree differs from approved index; no push")
    revision = git_at(clone, "rev-parse", "HEAD")
    # No force, reset, fetch, pull, credential persistence or remote rewrite.
    # A concurrent remote update causes a normal non-fast-forward failure.
    git_at(clone, "-c", "core.hooksPath=/dev/null", "push", EXPECTED_REMOTE,
           f"HEAD:refs/heads/{BRANCH}")
    print(f"Pushed public repository revision {revision}. PUSH != DEPLOYED. "
          "Verify successful Pages workflow, deployment revision and production "
          "bytes separately before recording publication.")


def public_inputs(site):
    files = read_tree(site, public=True)
    required = BUNDLE_PATHS | {WORKFLOW_PATH}
    if not required <= set(files):
        raise PublishError("Public validation bundle is incomplete")
    contract = load_json(site / BUNDLE / "contract.json")
    validate_contract(contract, site / BUNDLE / "check.py")
    if contract["excluded_paths"]:
        raise PublishError("Public contract must not contain private source exclusions")
    if files[f"{BUNDLE}/registry.json"] != canonical(contract["registry"]):
        raise PublishError("Exported registry differs from public contract")
    classify(files, contract, public=True)
    served = {p: files[p] for p in contract["site_paths"]}
    return files, served


def public_stage(site, output, *, refresh=False):
    site, output = Path(site).absolute(), Path(output).absolute()
    # Existing outputs are never reused, emptied or removed.
    if (output.exists() or output.is_symlink()
            or output.resolve().is_relative_to(site.resolve())):
        raise PublishError("Stage must be a new directory outside the repository")
    if output.parent.is_symlink() or output.parent.resolve() != output.parent:
        raise PublishError("Stage parent must not traverse symlinks")
    files, served = public_inputs(site)
    manifest = file_manifest(served)
    if not refresh and files[f"{BUNDLE}/manifest.json"] != canonical(manifest):
        raise PublishError("Public manifest stale; review direct changes, then "
                           "run public-manifest and commit the updated manifest")
    output.mkdir(mode=0o700)
    write_files(output, served)
    strict(site / BUNDLE / "check.py", output, site / BUNDLE / "registry.json",
           public=True)
    if read_tree(output) != served or read_tree(site, public=True) != files:
        raise PublishError("Public source/stage changed during validation")
    if refresh:
        # This local explicit command never commits/pushes or changes content.
        (site / BUNDLE / "manifest.json").write_bytes(canonical(manifest))
        print("Manifest refreshed after strict validation; review and commit "
              "the manifest with direct public changes. Not deployed.")
    return manifest


def save_review(output, site, approval, files):
    """Persist a NEW owned INTERNAL review directory; never an upload root."""
    output = Path(output).absolute()
    if (output.exists() or output.is_symlink()
            or output.resolve().is_relative_to(Path(site).resolve())
            or output.parent.resolve() != output.parent):
        raise PublishError("Review output must be new, outside site, without symlink parents")
    output.mkdir(mode=0o700)
    repository = output / "repository"
    repository.mkdir()
    write_files(repository, files)
    served = output / "served"
    served.mkdir()
    paths = {entry["path"] for entry in approval["served"]["files"]}
    write_files(served, {name: files[name] for name in paths})
    (output / "approval.json").write_bytes(canonical(approval))
    print(f"Internal review saved in {output}; do NOT upload this parent "
          "directory (it contains internal approval evidence).", file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="check",
                        choices=("check", "public-stage", "public-manifest"))
    parser.add_argument("--site", type=Path, default=ROOT / "gh-pages")
    parser.add_argument("--registry", type=Path, default=ROOT /
                        "agent-workflow/resources/aam-web-discovery/content-registry.json")
    parser.add_argument("--checker", type=Path, default=ROOT / "tools/aam_website/check.py")
    parser.add_argument("--repo", type=Path, default=ROOT)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--check-only", action="store_true")
    modes.add_argument("--publish", action="store_true")
    parser.add_argument("--approved-manifest", type=Path)
    parser.add_argument("--manifest-out", type=Path,
                        help="Create a NEW internal approval manifest; never overwrite")
    parser.add_argument("--review-out", type=Path,
                        help="NEW internal directory retaining served/repository bytes and approval")
    parser.add_argument("--message", default="update: publish approved AAM artifact")
    parser.add_argument("--output", type=Path, help="NEW public served-only directory")
    args = parser.parse_args(argv)
    try:
        if args.command != "check":
            if (not args.output or args.publish or args.approved_manifest
                    or args.manifest_out or args.review_out or args.dry_run or args.check_only):
                raise PublishError("Public commands require only --site and --output")
            public_stage(args.site, args.output,
                         refresh=args.command == "public-manifest")
            return 0
        if args.output:
            raise PublishError("--output is for public-stage/public-manifest only")
        if args.publish != bool(args.approved_manifest):
            raise PublishError("--publish requires a separately approved exact manifest")
        # No stage, git, remote or output write before strict succeeds.
        read_tree(args.site)
        strict(args.checker, args.site, args.registry)
        with tempfile.TemporaryDirectory(prefix="aam-publish-") as temporary:
            # Canonicalize only the freshly OWNED tempfile root. On macOS the
            # returned /var/folders path may alias /private/var/folders.
            # public_stage still rejects arbitrary symlinked output parents.
            workspace = Path(temporary).resolve()
            approval, files = prepare(args.site, args.registry, args.checker,
                                      args.repo, workspace)
            if args.approved_manifest:
                approved = regular_bytes(args.approved_manifest)
                if approved != canonical(approval):
                    raise PublishError("Exact approval mismatch; no remote contacted. "
                                       "Regenerate, review and obtain new approval.")
            if args.manifest_out:
                # Avoid putting internal release evidence inside public source.
                target = args.manifest_out.absolute()
                if target.resolve().is_relative_to(args.site.resolve()):
                    raise PublishError("Internal manifest must stay outside public site")
                with target.open("xb") as stream:
                    stream.write(canonical(approval))
            if args.review_out:
                save_review(args.review_out, args.site, approval, files)
            if args.publish:
                publish(files, workspace, args.message)
            else:
                print(canonical(approval).decode(), end="")
                print("LOCAL ONLY: strict source + served/public-export checks. "
                      "No remote contacted; no deployment authorization implied.",
                      file=sys.stderr)
        return 0
    except (PublishError, OSError, ValueError, KeyError, TypeError, RecursionError,
            subprocess.CalledProcessError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
