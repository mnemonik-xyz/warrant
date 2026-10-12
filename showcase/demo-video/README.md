# Warrant demo video

A one-minute slide-and-voiceover presentation of the Warrant project,
generated from text so it can be regenerated after edits.

Files

- `script.md`: the narration, one paragraph per scene. Edit this to change what is said.
- `s1.html` to `s6.html` and `common.css`: the six slides, rendered at 1920x1080.
- `build_audio.py`: reads `script.md` and writes one WAV per scene with Piper TTS.
- `build_video.py`: assembles `warrant-demo.mp4` with ffmpeg (gentle zoom, cross-fades,
  fade in and out). Each scene lasts as long as its narration plus a short pause.
- `build/`: rendered slides and voiceover clips (not committed).

Regenerate

```
pip install piper-tts
python3 -m piper.download_voices en_US-ryan-high
for i in 1 2 3 4 5 6; do
  chromium --headless=new --hide-scrollbars --window-size=1920,1080 \
    --screenshot=build/s$i.png "file://$PWD/s$i.html"
done
python3 build_audio.py
python3 build_video.py
```

On macOS, `say -o build/v1.aiff -f -` can replace Piper if you prefer the system
voice, or record your own narration in iMovie over the slide images instead.
