"""Generate one voiceover WAV per scene from script.md using Piper TTS."""
import os, re, subprocess, sys, pathlib
root = pathlib.Path(__file__).parent
text = (root / "script.md").read_text()
scenes = [b.split("\n", 1)[1].strip() for b in re.split(r"^## \d+\. ", text, flags=re.M)[1:]]
model = sys.argv[1] if len(sys.argv) > 1 else "en_US-ryan-high"   # voice .onnx looked up in PIPER_VOICES_DIR (default: build/)
out = root / "build"; out.mkdir(exist_ok=True)
for i, para in enumerate(scenes, 1):
    para = " ".join(para.split())
    subprocess.run([sys.executable, "-m", "piper", "-m", model, "--length-scale", "1.0",
                    "--sentence-silence", "0.35", "-f", str(out / f"v{i}.wav")],
                   input=para.encode(), check=True, cwd=os.environ.get("PIPER_VOICES_DIR", str(out)))
    print(i, para[:50])
