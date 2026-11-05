package de.lenna.fullbright.mixin;

import de.lenna.fullbright.FullbrightLighting;
import net.minecraft.client.renderer.Lightmap;
import net.minecraft.client.renderer.state.LightmapRenderState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Sodium samples this same Minecraft lightmap for terrain rendering. */
@Mixin(Lightmap.class)
public abstract class LightmapMixin {
    @Inject(method = "render(Lnet/minecraft/client/renderer/state/LightmapRenderState;)V",
            at = @At("HEAD"))
    private void alwaysFullbright$illuminate(LightmapRenderState state, CallbackInfo ci) {
        FullbrightLighting.apply(state);
    }
}
