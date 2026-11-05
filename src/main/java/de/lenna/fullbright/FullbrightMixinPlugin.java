package de.lenna.fullbright;

import java.util.List;
import java.util.Set;
import net.fabricmc.loader.api.FabricLoader;
import org.objectweb.asm.tree.ClassNode;
import org.spongepowered.asm.mixin.extensibility.IMixinConfigPlugin;
import org.spongepowered.asm.mixin.extensibility.IMixinInfo;

/** Selects a renderer before Mixin attempts to resolve version-specific classes. */
public final class FullbrightMixinPlugin implements IMixinConfigPlugin {
    private boolean legacy;

    @Override public void onLoad(String mixinPackage) {
        String version = FabricLoader.getInstance().getModContainer("minecraft")
                .orElseThrow().getMetadata().getVersion().getFriendlyString();
        legacy = version.equals("1.21.11");
    }
    @Override public List<String> getMixins() {
        return List.of(legacy ? "LegacyLightmapMixin" : "LightmapMixin");
    }
    @Override public String getRefMapperConfig() { return null; }
    @Override public boolean shouldApplyMixin(String targetClassName, String mixinClassName) { return true; }
    @Override public void acceptTargets(Set<String> myTargets, Set<String> otherTargets) {}
    @Override public void preApply(String name, ClassNode node, String mixin, IMixinInfo info) {}
    @Override public void postApply(String name, ClassNode node, String mixin, IMixinInfo info) {}
}
