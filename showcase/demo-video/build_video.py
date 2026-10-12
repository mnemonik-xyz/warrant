"""Assemble warrant-demo.mp4 from build/s{i}.png slides and build/v{i}.wav voiceover.

Each scene lasts as long as its narration plus a short lead-in and tail,
with a gentle zoom on the slide and a cross-fade into the next scene.
"""
import subprocess, json, pathlib
root = pathlib.Path(__file__).parent; b = root / "build"
N, FPS, XF = 6, 30, 0.6
LEAD, TAIL = 0.4, 0.6
EXTRA = {1: 1.0, 6: 1.4}          # hold the title and closing slides a bit longer

def dur(p):
    o = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "json", str(p)])
    return float(json.loads(o)["format"]["duration"])

D = [dur(b / f"v{i}.wav") + LEAD + TAIL + EXTRA.get(i, 0) for i in range(1, N + 1)]
args = ["ffmpeg", "-y"]
for i in range(1, N + 1):
    args += ["-i", str(b / f"s{i}.png")]   # single frame; zoompan generates the scene frames
for i in range(1, N + 1):
    args += ["-i", str(b / f"v{i}.wav")]

f = []
for i in range(N):
    frames = int(D[i] * FPS)
    f.append(f"[{i}:v]scale=1920:1080,zoompan=z='min(1+0.00035*on,1.06)':d={frames}"
             f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps={FPS},"
             f"format=yuv420p,setsar=1[v{i}]")
    f.append(f"[{N+i}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
             f"adelay={int(LEAD*1000)}|{int(LEAD*1000)},apad=whole_dur={D[i]:.3f}[a{i}]")

# chain cross-fades
vprev, aprev, off = "v0", "a0", 0.0
for i in range(1, N):
    off += D[i-1] - XF
    f.append(f"[{vprev}][v{i}]xfade=transition=fade:duration={XF}:offset={off:.3f}[vx{i}]")
    f.append(f"[{aprev}][a{i}]acrossfade=d={XF}:c1=tri:c2=tri[ax{i}]")
    vprev, aprev = f"vx{i}", f"ax{i}"
f.append(f"[{vprev}]fade=t=in:st=0:d=0.5,fade=t=out:st={sum(D)-5*XF-0.8:.3f}:d=0.8[vout]")
f.append(f"[{aprev}]afade=t=out:st={sum(D)-5*XF-0.8:.3f}:d=0.8[aout]")

args += ["-filter_complex", ";".join(f), "-map", "[vout]", "-map", "[aout]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(root / "warrant-demo.mp4")]
print("scene durations:", [round(d, 1) for d in D], "total ~", round(sum(D) - 5 * XF, 1), "s")
subprocess.run(args, check=True, stderr=subprocess.DEVNULL)
print("wrote", root / "warrant-demo.mp4")
