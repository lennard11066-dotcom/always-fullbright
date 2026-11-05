package de.lenna.fullbright.mixin;

import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.textures.GpuTexture;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Exact Fabric intermediary names from Minecraft 1.21.11, selected only there. */
@Mixin(targets = "net.minecraft.class_765", remap = false)
public abstract class LegacyLightmapMixin {
    @Shadow @Final private GpuTexture field_57927;
    @Shadow private boolean field_4135;

    @Inject(method = "method_3313(F)V", at = @At("HEAD"), cancellable = true, remap = false)
    private void alwaysFullbright$illuminateLegacy(float tickDelta, CallbackInfo ci) {
        // This is the same device-level clear used by the vanilla constructor.
        // Keep the existing texture and its view so Sodium continues sampling it.
        if (field_4135) {
            RenderSystem.getDevice().createCommandEncoder().clearColorTexture(field_57927, -1);
            field_4135 = false;
        }
        ci.cancel();
    }
}
