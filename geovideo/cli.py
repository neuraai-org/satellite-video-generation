from __future__ import annotations

import json
import random
import shutil
from pathlib import Path
from typing import Optional

import numpy as np
import typer
from moviepy.video.VideoClip import VideoClip

from geovideo.audio import load_audio, mix_audio
from geovideo.camera import CameraState, auto_camera
from geovideo.compositor import Compositor, FrameContext
from geovideo.providers import build_provider
from geovideo.schemas import InputConfig

app = typer.Typer(help="Generate vertical real-estate map videos from geographic inputs.")


def _load_config(path: Path) -> InputConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    return InputConfig.model_validate(data)


def _build_camera(config: InputConfig, fit: str) -> CameraState:
    points = [(poi.lat, poi.lon) for poi in config.pois]
    if fit == "center":
        zoom_override = config.timeline.camera_start_zoom or config.timeline.camera_end_zoom
        return auto_camera(
            (config.center.lat, config.center.lon),
            points,
            config.style.width,
            config.style.height,
            config.style.margin_ratio,
            zoom_override=zoom_override,
        )
    return auto_camera(
        (config.center.lat, config.center.lon),
        points,
        config.style.width,
        config.style.height,
        config.style.margin_ratio,
    )


def _render_video(config: InputConfig, seed: Optional[int], fit: str, verbose: bool) -> None:
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    provider = build_provider(config.provider)
    camera = _build_camera(config, fit)
    compositor = Compositor(config, provider)

    def make_frame(t: float) -> np.ndarray:
        ctx = FrameContext(time_s=t, camera=camera)
        return compositor.render_frame(ctx)

    clip = VideoClip(make_frame, duration=config.timeline.duration)
    if verbose:
        typer.echo("Rendering video frames...")

    tracks = load_audio(config.audio, config.timeline.duration)
    audio = mix_audio(tracks, config.audio)
    if audio:
        clip = clip.with_audio(audio)

    output = Path(config.output.path)
    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_params = []
    if config.output.faststart:
        ffmpeg_params += ["-movflags", "+faststart"]
    ffmpeg_params += ["-pix_fmt", "yuv420p", "-crf", str(config.output.crf)]
    codec_params = {"codec": "libx264", "audio_codec": "aac", "fps": config.style.fps}
    if config.output.bitrate:
        codec_params["bitrate"] = config.output.bitrate
    clip.write_videofile(
        str(output),
        **codec_params,
        preset=config.output.preset,
        ffmpeg_params=ffmpeg_params,
        threads=4,
        logger="bar" if verbose else None,
    )


@app.command()
def render(
    input: Path = typer.Option(..., "--input", exists=True),
    out: Optional[Path] = typer.Option(None, "--out"),
    fps: Optional[int] = typer.Option(None, "--fps"),
    duration: Optional[float] = typer.Option(None, "--duration"),
    width: Optional[int] = typer.Option(None, "--width"),
    height: Optional[int] = typer.Option(None, "--height"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    cache_dir: Optional[str] = typer.Option(None, "--cache-dir"),
    user_agent: Optional[str] = typer.Option(None, "--user-agent"),
    seed: Optional[int] = typer.Option(None, "--seed"),
    fit: str = typer.Option("all", "--fit"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    config = _load_config(input)
    if out:
        config.output.path = str(out)
    if fps:
        config.style.fps = fps
    if duration:
        config.timeline.duration = duration
    if width:
        config.style.width = width
    if height:
        config.style.height = height
    if provider:
        config.provider.name = provider
    if api_key:
        config.provider.api_key = api_key
    if cache_dir:
        config.provider.cache_dir = cache_dir
    if user_agent:
        config.provider.user_agent = user_agent
    config = InputConfig.model_validate(config.model_dump())
    _render_video(config, seed, fit, verbose)


@app.command()
def preview(
    input: Path = typer.Option(..., "--input", exists=True),
    frame_time: float = typer.Option(3.2, "--frame-time"),
    out: Path = typer.Option(..., "--out"),
) -> None:
    config = _load_config(input)
    provider = build_provider(config.provider)
    camera = _build_camera(config, fit="all")
    compositor = Compositor(config, provider)
    ctx = FrameContext(time_s=frame_time, camera=camera)
    frame = compositor.render_frame(ctx)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    import cv2

    cv2.imwrite(str(out), frame)


@app.command()
def validate(input: Path = typer.Option(..., "--input", exists=True)) -> None:
    _ = _load_config(input)
    typer.echo("Valid configuration")


@app.command()
def clear_cache(
    provider: str = typer.Option("osm", "--provider", help="Cache namespace: osm, mapbox, custom, or all."),
    cache_dir: Path = typer.Option(Path(".cache/tiles"), "--cache-dir", help="Base cache directory."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    provider_name = provider.strip().lower()
    if provider_name not in {"osm", "mapbox", "custom", "all"}:
        raise typer.BadParameter("--provider must be one of: osm, mapbox, custom, all")

    targets = [cache_dir] if provider_name == "all" else [cache_dir / provider_name]
    existing_targets = [target for target in targets if target.exists()]
    if not existing_targets:
        typer.echo("No cache directory found to clear.")
        return

    for target in existing_targets:
        if not yes and not typer.confirm(f"Delete cache at '{target}'?"):
            typer.echo("Cancelled.")
            return
        shutil.rmtree(target)
        typer.echo(f"Cleared cache: {target}")


@app.command()
def demo(out: Path = typer.Option("demo.mp4", "--out"), verbose: bool = False) -> None:
    sample = Path("examples/project.sample.json")
    config = _load_config(sample)
    config.output.path = str(out)
    _render_video(config, seed=42, fit="all", verbose=verbose)
