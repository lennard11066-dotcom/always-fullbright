package de.lenna.fullbright;

import net.minecraft.client.renderer.state.LightmapRenderState;
import org.joml.Vector3f;
import org.joml.Vector3fc;

/** Rendering only: does not change world lighting, effects or saved options. */
public final class FullbrightLighting {
    private static final Vector3fc WHITE = new Vector3f(1.0f);

    private FullbrightLighting() {}

    public static void apply(LightmapRenderState state) {
        // The 26.3 shader adds nonnegative block/sky light to ambient light and
        // clamps the result. White ambient therefore illuminates all 256 cells.
        state.ambientColor = WHITE;
        state.darknessEffectScale = 0.0f;
        state.bossOverlayWorldDarkening = 0.0f;
        state.brightness = 1.0f;
    }
}
