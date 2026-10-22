Experimental remote camera preview (local test build)

Transport reference: https://github.com/eugeneRover/micam
Pinned source commit: 2cc9d9e7607014d1d05c17bc5676544fbb0d5d24
Only miss/, pppp/ and server/ are compiled. The upstream cloud login, CLI and
credential persistence are not used. CameraRelay.java is this app's pipe adapter.

Build: python tools/install_camera_backend.py
Optional existing compiler: --jdk <JDK 21 directory>
The build verifies SHA256 for the source archive and Temurin JDK archive. A small
Java runtime is created locally; users need no system-wide Java installation.
The runtime preserves its legal/ notices. The source checkout and full JDK are
only temporary build inputs. Generated binaries/runtime are excluded from Git.

This is a local experiment. The transport repository has no explicit license
file at this commit. Its source has not been copied into this repository; confirm
upstream reuse/distribution permission before publishing bundled binaries.

Existing MiHome cloud authentication prepares fresh X25519 video keys, the
camera UID and relay-server init string. Only these temporary values are sent to
the helper's stdin; no account login credentials are sent to it. The helper uses
CS2 UDP relay, without requiring the camera's LAN IP. Decoded video is repackaged
as MPEG-TS on 127.0.0.1 under a random 128-bit path. No media is recorded.
Only status codes and optional base64 PCM audio use the private stdout pipe;
raw server responses and keys are never logged. Audio defaults off. G.711 A-law
and mu-law frames are decoded to 8 kHz mono PCM in memory. Other audio codecs are
reported as unsupported. QUALITY/AUDIO/PTZ commands use the existing stdin pipe;
PTZ uses a single MISS 0x112 motor step per drag gesture, never a continuous move.
Closing preview sends STOP and terminates any unresponsive owned process.
