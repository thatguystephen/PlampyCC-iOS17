"""Source integration and native constant contract; not UIKit/render proof."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "src/Tweak.xm").read_text()
assert '#include "FlashlightOpticalPolicy.hpp"' in source, "optical policy not integrated"
assert 'SizedGlyphArt(name, image.size)' in source, "header baseline changed"
assert 'SizedCompactGlyphArt(name, image)' in source, "compact push bypasses optical policy"
for name in ("Off", "On"):
    assert f'SizedCompactGlyphArt(@"Flashlight{name}", currentGlyph)' in source
assert 'objc_getAssociatedObject(peer, &kGlyphSourceCanvas)' in source
assert 'objc_setAssociatedObject(rendered, &kGlyphSourceCanvas,' in source
assert 'NSValue *sourceCanvas' in source and '[sourceCanvas CGSizeValue]' in source
assert 'canvas.width *= opticalScale;' in source and 'canvas.height *= opticalScale;' in source
assert 'canvas.width, canvas.height, opticalScale' in source, "cache must separate header/compact"
assert '[gSizedArt removeAllObjects]' in source, "reload must invalidate sized renders"

# Compile/run the actual production constant. The feedback model below is
# deliberately labelled a model: Objective-C associations need device proof.
with tempfile.TemporaryDirectory(prefix="flashlight-optical-", dir=os.environ.get("TMPDIR")) as temp:
    binary = str(Path(temp) / "contract")
    subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                    str(ROOT / "tests/native-flashlight-optical.cpp"), "-o", binary], check=True)
    subprocess.run([binary], check=True)
print("PASS: optical source wiring, source-canvas recovery, separate cache keys, reload invalidation")
