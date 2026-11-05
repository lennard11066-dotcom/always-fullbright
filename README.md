# Always Fullbright

[![Build and verify](https://github.com/lennard11066-dotcom/always-fullbright/actions/workflows/build.yml/badge.svg)](https://github.com/lennard11066-dotcom/always-fullbright/actions/workflows/build.yml)

![Always Fullbright sun icon](src/main/resources/assets/always_fullbright/icon.png)

Always-on Fullbright for Minecraft Java Edition, built for Fabric and designed
for use alongside Sodium. No keybinds, settings menu or Fabric API dependency.

[Download on Modrinth](https://modrinth.com/mod/always-fullbright)

## Features

- Fullbright is automatically enabled while the mod is installed.
- One universal JAR selects the appropriate lightmap implementation.
- Includes the golden sun icon.
- Does not change saved gamma settings or server-side light levels.
- Dimension fog and Blindness retain their normal behavior.

## Compatibility

| Minecraft | Validation for 1.1.0 |
| --- | --- |
| 1.21.11 | Fabric loader and legacy lightmap hook tested on Java 21 |
| 26.1.2 | Fabric loader and modern lightmap hook tested |
| 26.2 | Fabric loader and modern lightmap hook tested |
| 26.3 | Fabric loader and modern lightmap hook tested; additional Sodium 0.9.2 loader check |
| 26.1, 26.1.1 | Included in metadata; exact game binaries not separately tested |

Loader checks are not full graphical playtests. Shader packs that replace the
lighting system may override the effect. Earlier Sodium releases were not
available for testing.

## Installation

1. Install Fabric Loader 0.19.5 or newer for your Minecraft version.
2. Put the matching release JAR in the instance's `mods` folder.
3. Remove any earlier Always Fullbright JAR before starting the game.

Minecraft 1.21.11 requires Java 21; Minecraft 26.x requires Java 25 or newer.
Fabric API is not required by this mod, but other installed mods may need it.

## Reporting a bug

Open an [issue](https://github.com/lennard11066-dotcom/always-fullbright/issues/new/choose) with the Minecraft version, mod version,
Fabric Loader version and Sodium version. Describe what happened and what you
expected. Include a screenshot or the relevant part of `latest.log` if helpful.

## Source and local build

`src/main` contains the 26.x lightmap hook and the version selector.
`src/legacy` contains the 1.21.11 hook using Fabric intermediary names.
`src/test` contains Fabric loader and lightmap regression checks.

Install **Python 3.11 or newer** and **JDK 25 or newer**. Set `JAVA_HOME` to the
JDK directory, or put `java` and `javac` on your PATH. Then run from this folder:

```sh
python build.py
```

No Minecraft installation, Gradle installation, launcher, extra Python packages,
account or token is needed. The first build needs internet access and downloads
the game and libraries from Mojang, Fabric and Maven Central into `build/downloads`.
Pinned build dependencies are checked against `dependencies.lock.json`; game and
game-library downloads are checked against Mojang's SHA-1 metadata.

The script remaps the 1.21.11 client locally, compiles the two renderer hooks,
packages one universal Java 21-compatible mod JAR, and runs headless Fabric
checks for every Minecraft version listed in `fabric.mod.json`. Generated game
binaries and build dependencies remain local and are never bundled in the mod.

The resulting JAR and checksum are in `build/libs/`. The machine-readable result
is `build/verification.json`. The mod version comes from `fabric.mod.json`.

If you also have JDK 21 installed, set `FULLBRIGHT_JAVA21_HOME` to its directory
to run the legacy runtime check on Java 21. Compilation and modern checks still
use `JAVA_HOME` (JDK 25+). GitHub Actions installs and uses both JDKs automatically.

For a later build with fully cached dependencies, use `python build.py --offline`.
For a targeted runtime check, use e.g. `python build.py --test-versions 1.21.11 26.3`.
The default checks every supported version; a failed check fails the build.

## Automatic GitHub builds

The **Build and verify** workflow runs on pushes, pull requests and manual
dispatches. It builds from a clean checkout on Linux and Windows, tests download
integrity handling, and executes the Fabric hook checks.

To download a build, open [Actions](https://github.com/lennard11066-dotcom/always-fullbright/actions/workflows/build.yml),
select a successful run and download an `Always-Fullbright-...` artifact from the
Artifacts section. Extract the ZIP to obtain the mod JAR and its SHA-256 checksum.
These artifacts are kept for 30 days; verification logs are kept for 7 days.

These are development builds. Headless checks do not replace an in-game test
with Sodium. The workflow does not publish releases or upload to Modrinth.

## Credits and license

MIT License. See LICENSE.
The source code, sun icon and project text were created with generative AI.
