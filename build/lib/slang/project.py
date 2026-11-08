from __future__ import annotations
import json
import re
import hashlib
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 fallback for the simple manifest subset
    tomllib = None

MANIFEST = 'slang.toml'


def init_project(directory: str | Path = ".", *, name: str | None = None, version: str = "0.1.0") -> Path:
    """Create a minimal runnable S-Lang project deterministically.

    The command refuses to overwrite an existing manifest or entry point.
    """
    root = Path(directory).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest = root / MANIFEST
    src = root / "src"
    entry = src / "main.sl"
    if manifest.exists():
        raise ValueError(f"S-Lang project manifest already exists: {manifest}")
    if entry.exists():
        raise ValueError(f"S-Lang entry point already exists: {entry}")
    package_name = name or root.name
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", package_name):
        raise ValueError(f"invalid package name: {package_name!r}")
    _parse_version(version)
    src.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        f'[package]\nname = "{package_name}"\nversion = "{version}"\nentry = "src/main.sl"\nsource_roots = ["src"]\n',
        encoding="utf-8",
    )
    entry.write_text(
        '# S-Lang project entry point\n'
        'let value = 0\n'
        'show value\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        f"# {package_name}\n\nCreated with S-Lang {version} project initialization.\n",
        encoding="utf-8",
    )
    return root

def find_root(start: str | Path) -> Path | None:
    p = Path(start).resolve()
    if p.is_file():
        p = p.parent
    for cur in (p, *p.parents):
        if (cur / MANIFEST).is_file():
            return cur
    return None

def load_manifest(root: str | Path) -> dict:
    root = Path(root).resolve()
    path = root / MANIFEST
    if not path.is_file():
        raise ValueError(f"S-Lang project manifest not found: {path}")
    if tomllib is not None:
        return tomllib.loads(path.read_text(encoding='utf-8'))
    # Minimal TOML fallback: package strings/arrays and string dependencies.
    data = {'package': {}, 'dependencies': {}}
    section = None
    for raw in path.read_text(encoding='utf-8').splitlines():
        s = raw.split('#', 1)[0].strip()
        if not s:
            continue
        if s.startswith('[') and s.endswith(']'):
            section = s[1:-1].strip()
            data.setdefault(section, {})
            continue
        if '=' not in s or section is None:
            raise ValueError(f"unsupported manifest syntax: {raw}")
        k, v = [x.strip() for x in s.split('=', 1)]
        if v.startswith('[') and v.endswith(']'):
            vals = [x.strip().strip('"') for x in v[1:-1].split(',') if x.strip()]
            data[section][k] = vals
        else:
            data[section][k] = v.strip('"')
    return data

def _parse_version(value: str):
    m = re.fullmatch(r"\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+].*)?\s*", str(value))
    if not m:
        raise ValueError(f"invalid package version: {value!r}")
    return tuple(int(x or 0) for x in m.groups())

def _version_satisfies(version: str, constraint: str | None) -> bool:
    if not constraint or constraint in ("*", "latest"):
        return True
    v = _parse_version(version)
    for raw in str(constraint).split(','):
        c = raw.strip()
        if not c or c == '*':
            continue
        op = None
        for candidate in (">=", "<=", "==", ">", "<", "^", "~"):
            if c.startswith(candidate):
                op = candidate; c = c[len(candidate):].strip(); break
        target = _parse_version(c)
        if op == '==': ok = v == target
        elif op == '>=': ok = v >= target
        elif op == '<=': ok = v <= target
        elif op == '>': ok = v > target
        elif op == '<': ok = v < target
        elif op == '^': ok = v[0] == target[0] and v >= target
        elif op == '~': ok = v[:2] == target[:2] and v >= target
        else: ok = v == target
        if not ok:
            return False
    return True

def _dependency_specs(root: str | Path) -> dict:
    m = load_manifest(root)
    raw = m.get('dependencies', {}) or {}
    out = {}
    for name, spec in raw.items():
        if isinstance(spec, str):
            out[name] = {'path': spec, 'version': None}
        elif isinstance(spec, dict):
            path = spec.get('path')
            if not path:
                raise ValueError(f"dependency '{name}' requires a path")
            out[name] = {'path': path, 'version': spec.get('version')}
        else:
            raise ValueError(f"invalid dependency specification for '{name}'")
    return out

def project_info(root: str | Path) -> dict:
    root = Path(root).resolve()
    m = load_manifest(root)
    package = m.get('package', {})
    roots = package.get('source_roots', ['src'])
    if isinstance(roots, str): roots = [roots]
    specs = _dependency_specs(root)
    return {
        'root': str(root),
        'manifest': str(root / MANIFEST),
        'name': package.get('name', root.name),
        'version': package.get('version', '0.0.0'),
        'entry': package.get('entry', 'src/main.sl'),
        'source_roots': [str((root / x).resolve()) for x in roots],
        'dependencies': {k: str((root / v['path']).resolve()) for k, v in specs.items()},
        'dependency_specs': specs,
    }

def _resolve_dependencies_unlocked(root: str | Path) -> dict:
    """Resolve the complete local dependency graph deterministically.

    Dependencies are local packages in 1.9.6. Each package has a name/version
    in its own manifest. A dependency is selected by its declared name and
    optional version constraint. The graph is walked transitively and cycles
    are reported rather than silently recursing forever.
    """
    root = Path(root).resolve()
    state = {}  # path -> visiting/visited
    nodes = {}
    edges = {}

    def visit(pkg_root: Path, chain: list[Path]):
        pkg_root = pkg_root.resolve()
        if pkg_root in chain:
            cycle = chain[chain.index(pkg_root):] + [pkg_root]
            labels = [project_info(x)['name'] for x in cycle]
            raise ValueError("cyclic package dependency: " + " -> ".join(labels))
        if pkg_root in nodes:
            return
        info = project_info(pkg_root)
        nodes[pkg_root] = info
        edges[pkg_root] = {}
        for dep_name in sorted(info['dependency_specs']):
            spec = info['dependency_specs'][dep_name]
            dep_root = (pkg_root / spec['path']).resolve()
            if not (dep_root / MANIFEST).is_file():
                # 1.9.4 compatibility: a dependency may still be a plain
                # source directory. Such a package has no transitive manifest.
                if not dep_root.is_dir():
                    raise ValueError(f"dependency '{dep_name}' of '{info['name']}' not found: {dep_root}")
                dep_info = {
                    'name': dep_name, 'version': '0.0.0', 'root': str(dep_root),
                    'manifest': str(dep_root / MANIFEST), 'entry': 'main.sl',
                    'source_roots': [str(dep_root)], 'dependencies': {},
                    'dependency_specs': {},
                }
                nodes[dep_root] = dep_info
                edges[dep_root] = {}
            else:
                dep_info = project_info(dep_root)
            if dep_info['name'] != dep_name:
                raise ValueError(f"dependency name mismatch: '{dep_name}' resolves to package '{dep_info['name']}'")
            if not _version_satisfies(dep_info['version'], spec.get('version')):
                want = spec.get('version') or '*'
                raise ValueError(f"dependency '{dep_name}' requires version '{want}', found '{dep_info['version']}'")
            edges[pkg_root][dep_name] = dep_root
            if (dep_root / MANIFEST).is_file():
                visit(dep_root, chain + [pkg_root])

    visit(root, [])
    packages = []
    for path in sorted(nodes, key=lambda x: (nodes[x]['name'], nodes[x]['version'], str(x))):
        info = nodes[path]
        packages.append({
            'name': info['name'], 'version': info['version'], 'root': str(path),
            'dependencies': {name: str(path2) for name, path2 in sorted(edges[path].items())}
        })
    return {'root': str(root), 'packages': packages}


LOCKFILE = "slang.lock"
LOCK_FORMAT = 2

def _normalize_text_bytes(data: bytes) -> bytes:
    """Normalize text line endings before computing platform-independent hashes."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _manifest_digest(root: str | Path) -> str:
    path = Path(root).resolve() / MANIFEST
    if not path.is_file():
        return ""
    return hashlib.sha256(_normalize_text_bytes(path.read_bytes())).hexdigest()

def _source_digest(root: str | Path) -> str:
    """Return a deterministic digest of all S-Lang source files in a package.

    The digest covers relative paths and normalized text bytes, so additions,
    deletions, renames, and edits are detected independently of platform line
    endings. Generated caches and the lock file are intentionally excluded.
    """
    root = Path(root).resolve()
    files = sorted(p for p in root.rglob("*.sl") if p.is_file())
    h = hashlib.sha256()
    for path in files:
        rel = path.relative_to(root).as_posix().encode("utf-8")
        data = _normalize_text_bytes(path.read_bytes())
        h.update(len(rel).to_bytes(8, "big"))
        h.update(rel)
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return h.hexdigest()

def lock_path(root: str | Path) -> Path:
    return Path(root).resolve() / LOCKFILE

def _relative_lock_path(root: Path, package_root: Path) -> str:
    try:
        return package_root.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(__import__("os").path.relpath(package_root.resolve(), root.resolve())).as_posix()

def _lock_data_from_graph(root: Path, graph: dict) -> dict:
    packages = []
    for pkg in graph["packages"]:
        package_root = Path(pkg["root"]).resolve()
        packages.append({
            "name": pkg["name"],
            "version": pkg["version"],
            "path": _relative_lock_path(root, package_root),
            "dependencies": {
                name: _relative_lock_path(root, Path(dep_root))
                for name, dep_root in sorted(pkg.get("dependencies", {}).items())
            },
            "manifest_sha256": _manifest_digest(package_root),
            "source_sha256": _source_digest(package_root),
        })
    packages.sort(key=lambda p: (p["name"], p["version"], p["path"]))
    root_info = next(p for p in packages if Path(root / p["path"]).resolve() == root.resolve())
    return {
        "format": LOCK_FORMAT,
        "root": root_info["name"],
        "root_version": root_info["version"],
        "packages": packages,
    }

def _toml_quote(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)

def _write_lock(path: Path, data: dict) -> None:
    lines = [
        "# S-Lang dependency lock file. Generated by `slang lock`.",
        f"format = {int(data['format'])}",
        f"root = {_toml_quote(data['root'])}",
        f"root_version = {_toml_quote(data['root_version'])}",
        "",
    ]
    for pkg in data["packages"]:
        lines.append("[[package]]")
        lines.append(f"name = {_toml_quote(pkg['name'])}")
        lines.append(f"version = {_toml_quote(pkg['version'])}")
        lines.append(f"path = {_toml_quote(pkg['path'])}")
        lines.append(f"manifest_sha256 = {_toml_quote(pkg['manifest_sha256'])}")
        lines.append(f"source_sha256 = {_toml_quote(pkg['source_sha256'])}")
        if pkg["dependencies"]:
            dep_items = ", ".join(f"{_toml_quote(k)} = {_toml_quote(v)}" for k, v in sorted(pkg["dependencies"].items()))
            lines.append(f"dependencies = {{{dep_items}}}")
        else:
            lines.append("dependencies = {}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")

def _load_lock(root: str | Path) -> dict:
    root = Path(root).resolve()
    path = lock_path(root)
    if not path.is_file():
        raise ValueError(f"S-Lang lock file not found: {path}")
    if tomllib is None:
        raise ValueError("S-Lang lock files require Python 3.11+")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != LOCK_FORMAT:
        raise ValueError(f"unsupported S-Lang lock format: {data.get('format')!r}")
    packages = data.get("package")
    if not isinstance(packages, list):
        raise ValueError("invalid S-Lang lock file: package entries are required")
    return data

def _resolve_locked_dependencies(root: str | Path) -> dict:
    root = Path(root).resolve()
    data = _load_lock(root)
    package_entries = data["package"]
    by_name = {}
    by_path = {}
    for pkg in package_entries:
        if not isinstance(pkg, dict):
            raise ValueError("invalid S-Lang lock file: package entry must be a table")
        for key in ("name", "version", "path", "manifest_sha256", "source_sha256", "dependencies"):
            if key not in pkg:
                raise ValueError(f"invalid S-Lang lock file: package entry missing '{key}'")
        name = str(pkg["name"])
        path = (root / str(pkg["path"])).resolve()
        if name in by_name:
            raise ValueError(f"invalid S-Lang lock file: duplicate package '{name}'")
        by_name[name] = pkg
        by_path[path] = pkg

    root_pkg = by_name.get(data.get("root"))
    if root_pkg is None:
        raise ValueError(f"lock file does not contain root package '{data.get('root')}'")
    if str(root_pkg["path"]) not in (".", "") and (root / str(root_pkg["path"])).resolve() != root:
        raise ValueError("lock root package path does not match project root")

    # Every locked package must still exist, have the same identity, and have
    # the same manifest that was used to create the lock.
    for name, pkg in by_name.items():
        path = (root / str(pkg["path"])).resolve()
        if not path.is_dir():
            raise ValueError(f"locked package '{name}' is missing: {path}")
        if (path / MANIFEST).is_file():
            info = project_info(path)
            if info["name"] != name:
                raise ValueError(f"lock package name mismatch: '{name}' resolves to '{info['name']}'")
            if info["version"] != str(pkg["version"]):
                raise ValueError(f"locked package '{name}' changed version: lock has '{pkg['version']}', manifest has '{info['version']}'")
            if _manifest_digest(path) != pkg["manifest_sha256"]:
                raise ValueError(f"locked package '{name}' manifest changed; run 'slang lock' to update")
            if _source_digest(path) != pkg["source_sha256"]:
                raise ValueError(f"locked package '{name}' source changed; run 'slang lock' to update")
            actual_deps = {
                dep_name: dep_root.resolve()
                for dep_name, dep_root in _dependency_paths(path).items()
            }
            info_specs = info["dependency_specs"]
        else:
            if str(pkg["version"]) != "0.0.0" or pkg["manifest_sha256"] != "":
                raise ValueError(f"locked package '{name}' has no manifest but is not a legacy source dependency")
            if _source_digest(path) != pkg["source_sha256"]:
                raise ValueError(f"locked package '{name}' source changed; run 'slang lock' to update")
            info = {
                "name": name, "version": "0.0.0", "root": str(path),
                "manifest": str(path / MANIFEST), "entry": "main.sl",
                "source_roots": [str(path)], "dependencies": {},
                "dependency_specs": {},
            }
            actual_deps = {}
            info_specs = {}
        expected_deps = {}
        for dep_name, dep_path in dict(pkg.get("dependencies", {})).items():
            expected_deps[str(dep_name)] = (root / str(by_name[str(dep_name)]["path"])).resolve() if str(dep_name) in by_name else Path(dep_path).resolve()
        # The lock stores the resolved dependency path. Compare by package name
        # and path, while also validating current manifest constraints below.
        if set(actual_deps) != set(expected_deps):
            raise ValueError(f"locked package '{name}' dependency set changed; run 'slang lock' to update")
        for dep_name, actual_path in actual_deps.items():
            if dep_name not in by_name:
                raise ValueError(f"locked dependency '{dep_name}' is not present in lock file")
            locked_path = (root / str(by_name[dep_name]["path"])).resolve()
            if actual_path != locked_path:
                raise ValueError(f"locked dependency '{dep_name}' path changed; run 'slang lock' to update")
            spec = info_specs[dep_name]
            if not _version_satisfies(str(by_name[dep_name]["version"]), spec.get("version")):
                want = spec.get("version") or "*"
                raise ValueError(f"locked dependency '{dep_name}' no longer satisfies version '{want}'")

    # Validate graph closure and cycles from the lock itself.
    edges = {}
    nodes = {}
    for pkg in package_entries:
        path = (root / str(pkg["path"])).resolve()
        nodes[path] = project_info(path)
        edges[path] = {}
        for dep_name in sorted(dict(pkg.get("dependencies", {}))):
            if dep_name not in by_name:
                raise ValueError(f"locked dependency '{dep_name}' is not present in lock file")
            edges[path][dep_name] = (root / str(by_name[dep_name]["path"])).resolve()

    # Ensure there are no unreachable packages and no cycles.
    reachable = set()
    visiting = set()
    def walk(path):
        if path in visiting:
            raise ValueError("cyclic package dependency in lock file")
        if path in reachable:
            return
        visiting.add(path)
        for dep in edges.get(path, {}).values():
            walk(dep)
        visiting.remove(path)
        reachable.add(path)
    walk(root)
    if reachable != set(nodes):
        extra = sorted(nodes[p]["name"] for p in set(nodes) - reachable)
        raise ValueError("lock file contains unreachable packages: " + ", ".join(extra))

    packages = []
    for path in sorted(nodes, key=lambda x: (nodes[x]["name"], nodes[x]["version"], str(x))):
        packages.append({
            "name": nodes[path]["name"],
            "version": nodes[path]["version"],
            "root": str(path),
            "dependencies": {name: str(path2) for name, path2 in sorted(edges[path].items())},
        })
    return {"root": str(root), "packages": packages}

def _dependency_paths(root: str | Path) -> dict:
    info = project_info(root)
    return {
        dep_name: (Path(root).resolve() / spec["path"]).resolve()
        for dep_name, spec in info["dependency_specs"].items()
    }

def resolve_dependencies(root: str | Path, *, use_lock: bool = True) -> dict:
    """Resolve dependencies, using slang.lock when present.

    A lock file is authoritative once it exists. Set use_lock=False to perform
    a fresh resolution (used by `slang lock` when regenerating the file).
    """
    root = Path(root).resolve()
    if use_lock and lock_path(root).is_file():
        return _resolve_locked_dependencies(root)
    return _resolve_dependencies_unlocked(root)

def write_lock(root: str | Path) -> dict:
    root = Path(root).resolve()
    graph = _resolve_dependencies_unlocked(root)
    data = _lock_data_from_graph(root, graph)
    _write_lock(lock_path(root), data)
    return data


# ---------------------------------------------------------------------------
# Local package registry (1.9.8)
# ---------------------------------------------------------------------------

PACKAGE_FORMAT = 1
PACKAGE_SUFFIX = ".slpkg"
PACKAGE_METADATA = "package.json"


def registry_path() -> Path:
    """Return the local S-Lang package registry.

    ``SLANG_REGISTRY`` may override the location. The default is kept outside
    projects so installing a package does not modify the compiler tree.
    """
    value = os.environ.get("SLANG_REGISTRY")
    if value:
        return Path(value).expanduser().resolve()
    return (Path.home() / ".slang" / "registry").resolve()


def _package_archive_name(name: str, version: str) -> str:
    return f"{name}-{version}{PACKAGE_SUFFIX}"


def _safe_package_identity(root: str | Path) -> tuple[str, str]:
    info = project_info(root)
    name, version = str(info["name"]), str(info["version"])
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        raise ValueError(f"invalid package name: {name!r}")
    _parse_version(version)
    return name, version


def _package_files(root: Path):
    # Packages are source distributions: manifest + S-Lang sources + a small
    # set of conventional documentation files when present.
    files = [root / MANIFEST]
    for path in root.rglob("*.sl"):
        if path.is_file():
            files.append(path)
    for name in ("README.md", "LICENSE"):
        path = root / name
        if path.is_file():
            files.append(path)
    return sorted(set(files), key=lambda x: x.relative_to(root).as_posix())


def package_archive(root: str | Path, output: str | Path | None = None) -> Path:
    """Build a deterministic ``.slpkg`` source archive."""
    root = Path(root).resolve()
    name, version = _safe_package_identity(root)
    if not (root / MANIFEST).is_file():
        raise ValueError(f"S-Lang project manifest not found: {root / MANIFEST}")
    if output is None:
        output = root / _package_archive_name(name, version)
    output = Path(output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = _package_files(root)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            rel = path.relative_to(root).as_posix()
            data = path.read_bytes()
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, data)
    return output


def check_package(root: str | Path, archive: str | Path | None = None) -> dict:
    """Validate package identity, sources, dependency constraints, and archive safety."""
    root = Path(root).resolve()
    name, version = _safe_package_identity(root)
    info = project_info(root)
    for dep_name, spec in sorted(info["dependency_specs"].items()):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", str(dep_name)):
            raise ValueError(f"invalid dependency name: {dep_name!r}")
        if not isinstance(spec, dict):
            raise ValueError(f"invalid dependency specification for {dep_name!r}")
        if spec.get("version"):
            for raw in str(spec["version"]).split(","):
                c = raw.strip()
                for op in (">=", "<=", "==", ">", "<", "^", "~"):
                    if c.startswith(op):
                        c = c[len(op):].strip()
                        break
                _parse_version(c)
    files = _package_files(root)
    if not files or not (root / MANIFEST).is_file():
        raise ValueError("package contains no manifest")
    for path in files:
        rel = path.relative_to(root).as_posix()
        if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError(f"unsafe package path: {rel}")
    archive_path = Path(archive).expanduser().resolve() if archive else None
    if archive_path is None:
        with tempfile.TemporaryDirectory(prefix="slang-package-check-") as td:
            archive_path = Path(td) / _package_archive_name(name, version)
            package_archive(root, archive_path)
            _validate_package_archive(archive_path, name, version)
    else:
        if not archive_path.is_file():
            raise ValueError(f"package archive not found: {archive_path}")
        _validate_package_archive(archive_path, name, version)
    return {"name": name, "version": version, "files": [p.relative_to(root).as_posix() for p in files], "status": "valid"}


def _validate_package_archive(archive: Path, name: str, version: str) -> None:
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        if not names or MANIFEST not in names:
            raise ValueError("package archive does not contain slang.toml")
        for raw in names:
            p = Path(raw)
            if p.is_absolute() or ".." in p.parts:
                raise ValueError(f"unsafe package archive entry: {raw}")
        with tempfile.TemporaryDirectory(prefix="slang-package-validate-") as td:
            dest = Path(td)
            zf.extractall(dest)
            identity = _safe_package_identity(dest)
            if identity != (name, version):
                raise ValueError(f"package archive identity mismatch: expected {name}@{version}, got {identity[0]}@{identity[1]}")
            check_package(dest) if False else None


def _registry_metadata_path(destination: Path) -> Path:
    return destination / PACKAGE_METADATA

def _write_registry_metadata(destination: Path, name: str, version: str, archive: Path) -> Path:
    import json
    metadata = {"format": PACKAGE_FORMAT, "name": name, "version": version, "archive": archive.name, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
    path = _registry_metadata_path(destination)
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def publish_package(root: str | Path, registry: str | Path | None = None, *, force: bool = False) -> dict:
    """Build and publish a package into the local registry."""
    root = Path(root).resolve()
    name, version = _safe_package_identity(root)
    reg = Path(registry).expanduser().resolve() if registry else registry_path()
    destination = reg / name / version
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / _package_archive_name(name, version)
    existed = archive.exists()
    if existed and not force:
        raise ValueError(f"package {name}@{version} already exists in local registry; use --force to replace it")
    package_archive(root, archive)
    _validate_package_archive(archive, name, version)
    metadata = _write_registry_metadata(destination, name, version, archive)
    return {"name": name, "version": version, "archive": str(archive), "metadata": str(metadata), "registry": str(reg), "replaced": bool(force and existed)}


def _registry_versions(name: str, registry: str | Path | None = None) -> list[str]:
    reg = Path(registry).expanduser().resolve() if registry else registry_path()
    base = reg / name
    if not base.is_dir():
        return []
    versions = []
    for p in base.iterdir():
        if p.is_dir():
            try:
                _parse_version(p.name)
                if (p / _package_archive_name(name, p.name)).is_file():
                    versions.append(p.name)
            except ValueError:
                continue
    return sorted(versions, key=_parse_version)


def registry_list(registry: str | Path | None = None) -> list[dict]:
    reg = Path(registry).expanduser().resolve() if registry else registry_path()
    rows = []
    if not reg.is_dir():
        return rows
    for name_dir in sorted((p for p in reg.iterdir() if p.is_dir()), key=lambda p: p.name):
        for version in _registry_versions(name_dir.name, reg):
            archive = reg / name_dir.name / version / _package_archive_name(name_dir.name, version)
            metadata = _registry_metadata_path(archive.parent)
            row = {"name": name_dir.name, "version": version, "archive": str(archive)}
            if metadata.is_file():
                try:
                    row.update(json.loads(metadata.read_text(encoding="utf-8")))
                except Exception:
                    row["metadata_valid"] = False
            rows.append(row)
    return rows


def remove_registry_package(name: str, version: str, registry: str | Path | None = None) -> dict:
    reg = Path(registry).expanduser().resolve() if registry else registry_path()
    _parse_version(version)
    destination = reg / name / version
    if not destination.is_dir():
        raise ValueError(f"package {name}@{version} not found in local registry")
    shutil.rmtree(destination)
    parent = destination.parent
    if parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
    return {"name": name, "version": version, "removed": True, "registry": str(reg)}


def _select_registry_version(name: str, constraint: str | None, registry: str | Path | None = None) -> str:
    versions = _registry_versions(name, registry)
    matches = [v for v in versions if _version_satisfies(v, constraint)]
    if not matches:
        want = constraint or "*"
        raise ValueError(f"package '{name}' with version '{want}' not found in local registry")
    return matches[-1]


def _extract_package(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        for name in names:
            p = Path(name)
            if p.is_absolute() or ".." in p.parts:
                raise ValueError(f"unsafe package archive entry: {name}")
        zf.extractall(destination)


def _rewrite_installed_dependencies(package_root: Path) -> None:
    """Normalize installed package dependency paths to sibling packages."""
    path = package_root / MANIFEST
    text = path.read_text(encoding="utf-8")
    manifest = load_manifest(package_root)
    deps = manifest.get("dependencies", {}) or {}
    if not deps:
        return
    lines = text.splitlines()
    in_deps = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_deps = stripped == "[dependencies]"
            continue
        if in_deps and "=" in line and not stripped.startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in deps:
                spec = deps[key]
                if isinstance(spec, str):
                    lines[i] = f'{key} = "../{key}"'
                elif isinstance(spec, dict):
                    version = spec.get("version")
                    if version:
                        lines[i] = f'{key} = {{ path = "../{key}", version = "{version}" }}'
                    else:
                        lines[i] = f'{key} = {{ path = "../{key}" }}'
    path.write_text("\n".join(lines) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")


def _set_project_dependency(root: Path, name: str, path_value: str, version: str) -> None:
    """Add/update one dependency while preserving the rest of the manifest."""
    path = root / MANIFEST
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "[dependencies]":
            start = i
            continue
        if start is not None and stripped.startswith("[") and stripped.endswith("]"):
            end = i
            break
    replacement = f'{name} = {{ path = "{path_value}", version = "{version}" }}'
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines += ["[dependencies]", replacement]
    else:
        found = False
        for i in range(start + 1, end):
            stripped = lines[i].strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key = stripped.split("=", 1)[0].strip()
            if key == name:
                lines[i] = replacement
                found = True
                break
        if not found:
            lines.insert(end, replacement)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def install_package(root: str | Path, name: str, constraint: str | None = None,
                    registry: str | Path | None = None) -> dict:
    """Install a registry package and its transitive registry dependencies."""
    root = Path(root).resolve()
    reg = Path(registry).expanduser().resolve() if registry else registry_path()
    vendor = root / "packages"
    vendor.mkdir(parents=True, exist_ok=True)
    installed: dict[str, dict] = {}
    visiting: set[str] = set()

    def install_one(pkg_name: str, pkg_constraint: str | None, target_name: str | None = None):
        if pkg_name in visiting:
            raise ValueError("cyclic registry dependency: " + " -> ".join(list(visiting) + [pkg_name]))
        version = _select_registry_version(pkg_name, pkg_constraint, reg)
        if pkg_name in installed:
            if installed[pkg_name]["version"] != version:
                raise ValueError(f"registry dependency '{pkg_name}' requires incompatible versions '{installed[pkg_name]['version']}' and '{version}'")
            return installed[pkg_name]
        archive = reg / pkg_name / version / _package_archive_name(pkg_name, version)
        dest = vendor / (target_name or pkg_name)
        if dest.exists():
            shutil.rmtree(dest)
        visiting.add(pkg_name)
        with tempfile.TemporaryDirectory(prefix="slang-install-") as td:
            temp = Path(td) / pkg_name
            _extract_package(archive, temp)
            info = project_info(temp)
            for dep_name in sorted(info["dependency_specs"]):
                dep_spec = info["dependency_specs"][dep_name]
                install_one(dep_name, dep_spec.get("version"))
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(temp, dest)
        _rewrite_installed_dependencies(dest)
        visiting.remove(pkg_name)
        installed[pkg_name] = {"name": pkg_name, "version": version, "path": str(dest)}
        return installed[pkg_name]

    result = install_one(name, constraint)
    _set_project_dependency(root, name, Path(result["path"]).relative_to(root).as_posix(), result["version"])
    # Installation changes the project's dependency graph, so immediately
    # refresh the reproducibility lock instead of leaving a stale graph behind.
    lock_data = write_lock(root)
    return {"installed": list(sorted(installed.values(), key=lambda x: x["name"])),
            "registry": str(reg), "lock_file": str(lock_path(root)),
            "lock_format": lock_data["format"]}

def resolve_import(base_dir: str | Path, raw_import: str) -> Path | None:
    base_dir = Path(base_dir).resolve()
    if raw_import.startswith('std.'):
        return None
    dotted = raw_import.replace('.', '/')
    names = [raw_import]
    if not raw_import.endswith('.sl'):
        names.insert(0, dotted + '.sl')
    candidates = [base_dir / name for name in names]
    cur = base_dir
    while cur.parent != cur:
        for name in names:
            candidates.append(cur / name)
        cur = cur.parent
    root = find_root(base_dir)
    if root:
        info = project_info(root)
        for src in info['source_roots']:
            for name in names:
                candidates.append(Path(src) / name)
        graph = resolve_dependencies(root)
        dep_roots = {p['name']: Path(p['root']) for p in graph['packages']}
        for dep_name, dep_root in sorted(dep_roots.items()):
            if raw_import == dep_name or raw_import.startswith(dep_name + '.'):
                tail = raw_import[len(dep_name):].lstrip('.').replace('.', '/')
                dep_names = [tail, tail + '.sl'] if tail else ['main.sl']
                for name in dep_names:
                    candidates.append(dep_root / name)
    seen = set()
    for c in candidates:
        c = c.resolve()
        if c in seen: continue
        seen.add(c)
        if c.is_file(): return c
    return None

def explain_project(root: str | Path) -> dict:
    info = project_info(root)
    return info
