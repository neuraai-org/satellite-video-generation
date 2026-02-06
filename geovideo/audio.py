from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from moviepy.editor import AudioFileClip, CompositeAudioClip

from geovideo.schemas import AudioConfig


@dataclass
class AudioTracks:
    music: Optional[AudioFileClip]
    voiceover: Optional[AudioFileClip]


def load_audio(config: AudioConfig, duration: float) -> AudioTracks:
    music = AudioFileClip(config.music_path).volumex(config.music_volume) if config.music_path else None
    voice = (
        AudioFileClip(config.voiceover_path).volumex(config.voiceover_volume)
        if config.voiceover_path
        else None
    )
    if music:
        music = music.subclip(0, min(duration, music.duration)).audio_fadein(config.fade_in).audio_fadeout(
            config.fade_out
        )
    if voice:
        voice = voice.subclip(0, min(duration, voice.duration))
    return AudioTracks(music=music, voiceover=voice)


def mix_audio(tracks: AudioTracks, config: AudioConfig) -> Optional[CompositeAudioClip]:
    clips = []
    if tracks.music:
        clips.append(tracks.music)
    if tracks.voiceover:
        clips.append(tracks.voiceover)
    if not clips:
        return None
    if tracks.music and tracks.voiceover:
        music = tracks.music.volumex(config.ducking_ratio)
        return CompositeAudioClip([music, tracks.voiceover])
    return CompositeAudioClip(clips)
