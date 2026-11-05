import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import net.fabricmc.tinyremapper.TinyRemapper;
import net.fabricmc.tinyremapper.TinyUtils;

/** Build tool only: maps the official 1.21.11 client to Fabric intermediary. */
public final class RemapJar {
    public static void main(String[] args) throws Exception {
        TinyRemapper remapper = TinyRemapper.newRemapper()
                .withMappings(TinyUtils.createTinyMappingProvider(Path.of(args[2]), args[3], args[4])).build();
        try {
            Path[] classpath = new Path[args.length - 5];
            for (int i = 5; i < args.length; i++) classpath[i - 5] = Path.of(args[i]);
            remapper.readClassPath(classpath);
            remapper.readInputs(Path.of(args[0]));
            try (ZipOutputStream zip = new ZipOutputStream(Files.newOutputStream(Path.of(args[1])))) {
                remapper.apply((name, bytes) -> {
                    synchronized (zip) {
                        try {
                            ZipEntry entry = new ZipEntry(name + ".class");
                            entry.setTime(0);
                            zip.putNextEntry(entry);
                            zip.write(bytes);
                            zip.closeEntry();
                        } catch (IOException error) {
                            throw new UncheckedIOException(error);
                        }
                    }
                });
            }
        } finally {
            remapper.finish();
        }
    }
}
