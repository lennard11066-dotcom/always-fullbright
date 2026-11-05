# Always Fullbright

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

`build.py` runs `build_universal.py`. This is the author's offline build script,
not a self-contained Gradle project. It expects locally installed game JARs and
cached Fabric Loader 0.20.1, Sponge Mixin 0.17.5+mixin.0.8.7 and ASM 9.10.1.
Minecraft and dependency binaries are not part of this repository.

The script currently targets a Windows installation and can be configured with
FULLBRIGHT_MC, FULLBRIGHT_META and FULLBRIGHT_JDK. Its 1.21.11 mapping cache
references a sibling `hf11-deps` directory containing the official client JAR,
its Fabric intermediary JAR and the intermediary mappings JAR. Those locally
cached files are not included. Update these paths for another build environment.

Run `python build.py` after preparing those dependencies. The built JAR is saved
to `build/libs/always-fullbright-1.1.0-mc1.21.11-26.3.jar`.

## Credits and license

MIT License. See LICENSE.
The source code, sun icon and project text were created with generative AI.
