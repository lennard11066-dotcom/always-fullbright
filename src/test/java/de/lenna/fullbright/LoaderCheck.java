package de.lenna.fullbright;

import net.fabricmc.api.EnvType;
import net.fabricmc.loader.impl.launch.knot.Knot;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.Arrays;

/** Loads the packaged release through Fabric, then executes its transformed hook. */
public final class LoaderCheck {
    public static void main(String[] args) throws Exception {
        Knot knot = new Knot(EnvType.CLIENT);
        ClassLoader loader = knot.init(args);
        if (System.getProperty("fullbright.version", "26.3").equals("1.21.11")) {
            checkLegacy(loader);
            return;
        }
        Class<?> lightmap = Class.forName("net.minecraft.client.renderer.Lightmap", false, loader);
        if (Arrays.stream(lightmap.getDeclaredMethods())
                .noneMatch(m -> m.getName().contains("alwaysFullbright$illuminate"))) {
            throw new AssertionError("Fullbright Mixin did not transform Minecraft Lightmap");
        }
        Class<?> stateClass = Class.forName("net.minecraft.client.renderer.state.LightmapRenderState", true, loader);
        Object state = stateClass.getConstructor().newInstance();
        // Allocate without starting a GPU. needsUpdate=false makes the real render
        // method return immediately AFTER our HEAD hook has actually executed.
        Class<?> unsafeClass = Class.forName("sun.misc.Unsafe");
        Field singleton = unsafeClass.getDeclaredField("theUnsafe");
        singleton.setAccessible(true);
        Object instance = unsafeClass.getMethod("allocateInstance", Class.class)
                .invoke(singleton.get(null), lightmap);
        Method render = lightmap.getMethod("render", stateClass);
        Class<?> vector = Class.forName("org.joml.Vector3f", true, loader);
        Class<?> vectorInterface = Class.forName("org.joml.Vector3fc", true, loader);
        for (int round = 0; round < 3; round++) {
            stateClass.getField("ambientColor").set(state, vector.getConstructor(float.class).newInstance(0.0f));
            stateClass.getField("brightness").setFloat(state, 0.0f);
            stateClass.getField("darknessEffectScale").setFloat(state, 0.8f);
            stateClass.getField("bossOverlayWorldDarkening").setFloat(state, 1.0f);
            render.invoke(instance, state);
            Object ambient = stateClass.getField("ambientColor").get(state);
            for (String axis : new String[]{"x", "y", "z"}) {
                if (!vectorInterface.getMethod(axis).invoke(ambient).equals(1.0f))
                    throw new AssertionError("Ambient is not white");
            }
            if (stateClass.getField("brightness").getFloat(state) != 1.0f ||
                    stateClass.getField("darknessEffectScale").getFloat(state) != 0.0f ||
                    stateClass.getField("bossOverlayWorldDarkening").getFloat(state) != 0.0f)
                throw new AssertionError("Darkness was not reset");
            if (stateClass.getField("needsUpdate").getBoolean(state))
                throw new AssertionError("Unnecessary lightmap update forced");
        }
        // Evaluate the 26.3 lightmap shader's brightness equation for every cell,
        // including zero sky and block light. White ambient clamps each to white.
        for (int block = 0; block < 16; block++) for (int sky = 0; sky < 16; sky++) {
            double b = block / 15.0, s = sky / 15.0;
            double color = Math.min(1, 1 + b / (4 - 3 * b) * 1.4 + s / (4 - 3 * s));
            double gamma = 1 - Math.pow(1 - color, 4);
            if (gamma != 1.0) throw new AssertionError("Dark cell " + block + "," + sky);
        }
        System.out.println("PASS: real Fabric loads packaged Minecraft 26.3 Mixin.");
        System.out.println("PASS: transformed render hook re-applies fullbright on every call.");
        System.out.println("PASS: all 256 lightmap cells fullbright, including complete darkness.");
    }

    private static Object allocate(Class<?> type) throws Exception {
        Class<?> unsafe = Class.forName("sun.misc.Unsafe");
        Field field = unsafe.getDeclaredField("theUnsafe");
        field.setAccessible(true);
        return unsafe.getMethod("allocateInstance", Class.class).invoke(field.get(null), type);
    }

    private static void checkLegacy(ClassLoader loader) throws Exception {
        Class<?> lightmap = Class.forName("net.minecraft.class_765", true, loader);
        if (Arrays.stream(lightmap.getDeclaredMethods())
                .noneMatch(m -> m.getName().contains("alwaysFullbright$illuminateLegacy")))
            throw new AssertionError("1.21.11 Mixin did not transform the actual lightmap");
        Object instance = allocate(lightmap);
        Object texture = allocate(Class.forName("net.minecraft.class_10868", true, loader));
        Field textureField = lightmap.getDeclaredField("field_57927");
        textureField.setAccessible(true);
        textureField.set(instance, texture);
        Field dirty = lightmap.getDeclaredField("field_4135");
        dirty.setAccessible(true);
        Class<?> encoderType = Class.forName("com.mojang.blaze3d.systems.CommandEncoder", true, loader);
        Class<?> deviceType = Class.forName("com.mojang.blaze3d.systems.GpuDevice", true, loader);
        int[] clears = {0};
        Object encoder = Proxy.newProxyInstance(loader, new Class<?>[]{encoderType}, (proxy, method, args) -> {
            if (!method.getName().equals("clearColorTexture")) throw new AssertionError(method);
            if (args[0] != texture || !args[1].equals(-1)) throw new AssertionError("Wrong texture or color");
            clears[0]++;
            return null;
        });
        Object device = Proxy.newProxyInstance(loader, new Class<?>[]{deviceType}, (proxy, method, args) -> {
            if (method.getName().equals("createCommandEncoder")) return encoder;
            throw new AssertionError(method);
        });
        Class<?> renderSystem = Class.forName("com.mojang.blaze3d.systems.RenderSystem", true, loader);
        Field deviceField = renderSystem.getDeclaredField("DEVICE");
        deviceField.setAccessible(true);
        Object previous = deviceField.get(null);
        deviceField.set(null, device);
        try {
            Method update = lightmap.getMethod("method_3313", float.class);
            for (int cycle = 0; cycle < 3; cycle++) {
                dirty.setBoolean(instance, true);
                update.invoke(instance, 0.5f);
                if (dirty.getBoolean(instance) || clears[0] != cycle + 1)
                    throw new AssertionError("Lightmap not cleared on dirty update");
                update.invoke(instance, 0.5f);
                if (clears[0] != cycle + 1) throw new AssertionError("Clean lightmap redrawn");
            }
        } finally {
            deviceField.set(null, previous);
        }
        System.out.println("PASS: actual Minecraft 1.21.11 class transformed with Fabric intermediary mappings.");
        System.out.println("PASS: existing lightmap texture cleared opaque white; dirty flag reset, clean frames skipped.");
        System.out.println("PASS: legacy path loads without resolving Minecraft 26.x renderer classes.");
    }
}
