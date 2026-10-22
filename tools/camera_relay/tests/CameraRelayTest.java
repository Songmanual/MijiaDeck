import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import micam.miss.MediaPacket;

public class CameraRelayTest {
    private short[] decode(int codec, byte[] values) {
        byte[] pcm = CameraRelay.pcm(new MediaPacket(codec, 0, 0, 0, values));
        short[] result = new short[values.length];
        ByteBuffer.wrap(pcm).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().get(result);
        return result;
    }

    @Test void alawDecodesSilenceAndBothSignsInLittleEndian() {
        assertArrayEquals(new short[]{8, -8, 32256, -32256},
            decode(1027, new byte[]{(byte)0xd5, 0x55, (byte)0xaa, 0x2a}));
    }

    @Test void mulawDecodesSilenceAndBothSignsInLittleEndian() {
        assertArrayEquals(new short[]{0, 0, 32124, -32124},
            decode(1026, new byte[]{(byte)0xff, 0x7f, (byte)0x80, 0}));
    }
}
