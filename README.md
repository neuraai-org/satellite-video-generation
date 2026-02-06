# Geovideo

Generate short vertical real-estate map videos from geographic inputs using Python.

## Features
- Satellite or street basemaps via OSM/Mapbox/custom tiles
- Animated pins, ripple rings, and labels (UTF-8/Vietnamese supported)
- Optional polygon boundaries and overlay UI PNG
- Deterministic rendering with a seed
- Audio mix with background music + voiceover and ducking
- CLI commands for render/preview/validate/demo

## Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

## FFmpeg requirement
MoviePy requires FFmpeg. On Ubuntu:
```bash
sudo apt-get update && sudo apt-get install -y ffmpeg
```

## Quick start
```bash
geovideo demo --out demo.mp4 --verbose
```

## Provider setup
- **OSM (default)**: no API key required.
- **Mapbox**: set `provider.name=mapbox` and `provider.api_key`.
- **Custom**: set `provider.name=custom` and `provider.url_template`.

## JSON schema example
```json
{
  "center": {"name": "Trung tâm", "lat": 21.028511, "lon": 105.804817},
  "pois": [
    {"name": "Trường học", "lat": 21.0309, "lon": 105.8072, "type": "school"}
  ],
  "style": {
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "subtitle": "Khu vực trung tâm Hà Nội"
  },
  "timeline": {"duration": 10.0},
  "output": {"path": "out.mp4"},
  "provider": {"name": "osm"}
}
```

## Commands
### Minimal run
```bash
geovideo render --input examples/project.sample.json --out output.mp4
```

### Advanced run
```bash
geovideo render \
  --input examples/project.sample.json \
  --out output.mp4 \
  --fps 30 \
  --duration 12 \
  --width 1080 \
  --height 1920 \
  --provider mapbox \
  --api-key "$MAPBOX_TOKEN" \
  --seed 123 \
  --verbose
```

### Preview a single frame
```bash
geovideo preview --input examples/project.sample.json --frame-time 3.2 --out frame.png
```

### Validate config
```bash
geovideo validate --input examples/project.sample.json
```

## Troubleshooting
- **Fonts**: If Vietnamese characters render incorrectly, set `style.font_path` to a Unicode font file.
- **Tiles not loading**: Check API key, internet access, and tile provider rate limits. Use `provider.cache_dir` to cache tiles.
- **FFmpeg**: Ensure `ffmpeg` is in your PATH.

## Legal notes
Respect tile provider terms and attribution requirements. The default attribution text overlays the map, but you should confirm compliance with your chosen provider.

## Example input
See `examples/project.sample.json` for a full working config.
