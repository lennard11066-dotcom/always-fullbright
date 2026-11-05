"""Build and verify Always Fullbright with Python 3.11+ and JDK 25+.

Downloads dependencies from Mojang, Fabric and Maven Central into build/.
No Minecraft installation, Gradle cache, Python packages or token is required.
No Minecraft or dependency binaries are bundled in the resulting mod.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"


def digest(path, algorithm="sha256"):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def download(url, target, checksum=None, algorithm="sha256", offline=False):
    """Atomically cache downloads and reject corrupt cached or incoming data."""
    target = Path(target)
    if target.is_file() and (checksum is None or digest(target, algorithm) == checksum):
        return target
    if offline:
        raise RuntimeError(f"Missing or corrupt offline dependency: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "AlwaysFullbright-Build/1.0"})
            with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as stream:
                shutil.copyfileobj(response, stream)
            if checksum and digest(temporary, algorithm) != checksum:
                raise RuntimeError(f"Checksum mismatch for {url}")
            temporary.replace(target)
            return target
        except (OSError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
        finally:
            temporary.unlink(missing_ok=True)
    raise RuntimeError(f"Download failed: {url}")


def java_tool(name, home=None):
    home = home or os.environ.get("JAVA_HOME")
    suffix = ".exe" if os.name == "nt" else ""
    candidate = Path(home) / "bin" / (name + suffix) if home else None
    if candidate and candidate.is_file():
        return str(candidate)
    if home:
        raise RuntimeError(f"{name} not found in JDK: {home}")
    candidate = shutil.which(name)
    if not candidate:
        raise RuntimeError("Install JDK 25 or newer and set JAVA_HOME (a JRE alone is insufficient).")
    return candidate


def run(executable, arguments, directory, label):
    directory.mkdir(parents=True, exist_ok=True)
    argfile = directory / (label + ".args")
    # Java argument files handle paths with spaces and Windows command limits.
    argfile.write_text("\n".join('"' + str(a).replace("\\", "\\\\").replace('"', '\\"') + '"'
                                  for a in arguments), encoding="utf-8")
    result = subprocess.run([executable, "@" + str(argfile)], cwd=directory,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    (directory / (label + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    print(result.stdout + result.stderr, end="", flush=True)
    result.check_returncode()
    return result.stdout


class Builder:
    def __init__(self, offline=False):
        self.offline = offline
        self.build = ROOT / "build"
        self.cache = self.build / "downloads"
        self.work = self.build / "work"
        self.classes = self.work / "classes"
        self.tests = self.work / "tests"
        self.metadata = json.loads((ROOT / "src/main/resources/fabric.mod.json").read_text(encoding="utf-8"))
        self.supported = self.metadata["depends"]["minecraft"]
        self.output = self.build / "libs" / f'always-fullbright-{self.metadata["version"]}-mc1.21.11-26.3.jar'
        self.lock = json.loads((ROOT / "dependencies.lock.json").read_text(encoding="utf-8"))
        self.dependencies = {}

    def prepare_dependencies(self):
        def fetch(item):
            name = item["url"].rsplit("/", 1)[1]
            return item["id"], download(item["url"], self.cache / "tools" / name,
                                        item["sha256"], offline=self.offline)
        with ThreadPoolExecutor(max_workers=6) as executor:
            self.dependencies = dict(executor.map(fetch, self.lock["artifacts"]))
        self.bootstrap = [self.dependencies[n] for n in ["fabric-loader", "sponge-mixin", "asm",
                          "asm-tree", "asm-commons", "asm-util", "asm-analysis"]]

    def context(self, version):
        directory = self.cache / "versions" / version
        manifest = directory / "manifest.json"
        if not manifest.is_file():
            index = download(MANIFEST_URL, self.cache / "version_manifest_v2.json", offline=self.offline)
            entries = json.loads(index.read_text(encoding="utf-8"))["versions"]
            entry = next((v for v in entries if v["id"] == version), None)
            if entry is None:
                raise RuntimeError(f"Minecraft {version} is missing from Mojang's version manifest.")
            download(entry["url"], manifest, entry["sha1"], "sha1", self.offline)
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
        if metadata["id"] != version:
            raise RuntimeError(f"Wrong Minecraft metadata for {version}")
        client = metadata["downloads"]["client"]
        game = download(client["url"], directory / "client.jar", client["sha1"], "sha1", self.offline)
        # Headless checks need Java libraries, not platform-native classifiers.
        artifacts = [lib["downloads"]["artifact"] for lib in metadata["libraries"]
                     if "artifact" in lib.get("downloads", {}) and lib["name"].count(":") == 2]

        def fetch(artifact):
            return download(artifact["url"], self.cache / "libraries" / artifact["path"],
                            artifact["sha1"], "sha1", self.offline)
        with ThreadPoolExecutor(max_workers=6) as executor:
            libraries = list(executor.map(fetch, artifacts))
        if version == "1.21.11":
            libraries.append(self.dependencies["intermediary"])
        return {"version": version, "game": game, "libraries": libraries,
                "classpath": os.pathsep.join(map(str, [game, *self.bootstrap, *libraries]))}

    def prepare_legacy(self, context):
        directory = self.work / "remapper"
        directory.mkdir(parents=True, exist_ok=True)
        mapping = directory / "intermediary.tiny"
        with zipfile.ZipFile(self.dependencies["intermediary"]) as archive:
            mapping.write_bytes(archive.read("mappings/mappings.tiny"))
        tools = os.pathsep.join(map(str, [self.dependencies["tiny-remapper"],
                                         self.dependencies["mapping-io"], *self.bootstrap[2:]]))
        run(java_tool("javac"), ["--release", "21", "-encoding", "UTF-8", "-proc:none", "-cp", tools,
            "-d", directory, ROOT / "tools/RemapJar.java"], directory, "compile-remapper")
        mapped = directory / "minecraft-intermediary.jar"
        run(java_tool("java"), ["-Xmx2G", "-cp", str(directory) + os.pathsep + tools, "RemapJar",
            context["game"], mapped, mapping, "official", "intermediary", *context["libraries"]],
            directory, "remap-legacy")
        context["mapped"] = mapped

    def compile(self, modern, legacy):
        for directory in [self.classes, self.tests]:
            if directory.resolve().parent != self.work.resolve():
                raise RuntimeError("Invalid compiler output directory")
            if directory.exists():
                shutil.rmtree(directory)
            directory.mkdir(parents=True)
        common = ["--release", "21", "-encoding", "UTF-8", "-proc:none", "-implicit:none"]
        legacy_cp = os.pathsep.join(map(str, [legacy["mapped"], *self.bootstrap, *legacy["libraries"]]))
        for source, classpath, output, name in [
            ("src/main/java", modern["classpath"], self.classes, "compile-modern"),
            ("src/legacy/java", legacy_cp, self.classes, "compile-legacy"),
            ("src/test/java", modern["classpath"], self.tests, "compile-checks"),
        ]:
            run(java_tool("javac"), [*common, "-cp", classpath, "-d", output,
                *sorted((ROOT / source).rglob("*.java"))], self.work, name)

    def package(self):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.output, "w", zipfile.ZIP_DEFLATED) as archive:
            def add(path, name):
                info = zipfile.ZipInfo(name, (2026, 11, 5, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes())
            for path in sorted(self.classes.rglob("*.class")):
                add(path, path.relative_to(self.classes).as_posix())
            for path in sorted((ROOT / "src/main/resources").rglob("*")):
                if path.is_file():
                    add(path, path.relative_to(ROOT / "src/main/resources").as_posix())
            for folder in ["src", "tools"]:
                for path in sorted((ROOT / folder).rglob("*")):
                    if path.is_file():
                        add(path, "META-INF/sources/" + path.relative_to(ROOT).as_posix())
            for name in ["README.md", "LICENSE", "CHANGELOG.md", "build_universal.py", "build.py", "dependencies.lock.json"]:
                add(ROOT / name, name if name.endswith((".md", "LICENSE")) else "META-INF/sources/" + name)
        with zipfile.ZipFile(self.output) as archive:
            if archive.testzip() is not None or json.loads(archive.read("fabric.mod.json")) != self.metadata:
                raise RuntimeError("Corrupt packaged JAR or incorrect metadata")
            icon = archive.read(self.metadata["icon"])
            if icon[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", icon[16:24]) != (256, 256):
                raise RuntimeError("Invalid mod icon")
            for name in archive.namelist():
                if name.endswith(".class"):
                    if not name.startswith("de/lenna/fullbright/") or struct.unpack(">H", archive.read(name)[6:8])[0] != 65:
                        raise RuntimeError(f"Bundled dependency or incompatible bytecode: {name}")

    def smoke(self, context):
        version = context["version"]
        directory = self.work / ("smoke-" + version)
        directory.mkdir(parents=True, exist_ok=True)
        if version == "1.21.11":
            # Seed Fabric's cache with remapped classes and original resources.
            # Also works when Windows sandbox permissions restrict Java ZipFS.
            cache = directory / ".fabric/remappedJars" / ("minecraft-1.21.11-" + self.lock["fabric_loader"])
            cache.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(context["mapped"]) as mapped, zipfile.ZipFile(context["game"]) as original:
                with zipfile.ZipFile(cache / "client-intermediary.jar", "w", zipfile.ZIP_DEFLATED) as output:
                    for name in mapped.namelist():
                        output.writestr(name, mapped.read(name))
                    for name in original.namelist():
                        if not name.endswith(".class") and not name.startswith("META-INF/"):
                            output.writestr(name, original.read(name))
        legacy_home = os.environ.get("FULLBRIGHT_JAVA21_HOME") if version == "1.21.11" else None
        print(f"Checking Fabric hook on Minecraft {version}...", flush=True)
        run(java_tool("java", legacy_home), ["-Djava.awt.headless=true", "--enable-native-access=ALL-UNNAMED",
            "-Dfabric.gameJarPath=" + str(context["game"]), "-Dfabric.addMods=" + str(self.output),
            "-Dfabric.log.disableAnsi=true", "-Dfullbright.version=" + version,
            "-cp", str(self.tests) + os.pathsep + context["classpath"], "de.lenna.fullbright.LoaderCheck",
            "--gameDir", directory, "--version", version, "--assetsDir", self.cache / "assets"],
            directory, "loader-check")
        return 21 if legacy_home else "build JDK"

    def build_and_test(self, versions):
        # Do not leave a success report from an earlier build after a failure.
        (self.build / "verification.json").unlink(missing_ok=True)
        self.prepare_dependencies()
        contexts = {v: self.context(v) for v in dict.fromkeys(["26.3", "1.21.11", *versions])}
        self.prepare_legacy(contexts["1.21.11"])
        self.compile(contexts["26.3"], contexts["1.21.11"])
        self.package()
        checked = {v: self.smoke(contexts[v]) for v in versions}
        report = {"file": self.output.name, "bytes": self.output.stat().st_size,
                  "sha256": digest(self.output), "mod_version": self.metadata["version"],
                  "supported_versions": self.supported, "runtime_checked": checked,
                  "java_bytecode": 21, "fabric_loader": self.lock["fabric_loader"],
                  "graphical_playtest": False, "sodium_playtest": False,
                  "note": "Headless Fabric hook checks only; test in-game before publishing."}
        (self.build / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        self.output.with_suffix(".jar.sha256").write_text(f'{report["sha256"]}  {self.output.name}\n', encoding="utf-8")
        print(json.dumps(report, indent=2), flush=True)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Use previously downloaded files only")
    parser.add_argument("--test-versions", nargs="+", help="Runtime test versions (all supported by default)")
    args = parser.parse_args()
    builder = Builder(args.offline)
    versions = args.test_versions or builder.supported
    if not set(versions) <= set(builder.supported):
        parser.error("Runtime test versions must be declared in fabric.mod.json")
    builder.build_and_test(versions)


if __name__ == "__main__":
    main()
