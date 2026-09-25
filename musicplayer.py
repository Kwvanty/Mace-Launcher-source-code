"""Music logic for Mace Launcher.

Local playback is fully implemented with pygame.mixer. Online services are kept
as explicit integration points: Spotify/YouTube Music are not treated as audio
streaming APIs because their public APIs do not provide arbitrary audio streams
for a third-party Pygame player.
"""
from __future__ import annotations
import os
import time
from dataclasses import dataclass
from typing import List, Optional

try:
    import pygame
except ImportError:
    pygame = None

AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.flac'}

@dataclass
class Track:
    path: str
    title: str
    artist: str = 'Local'
    duration: float = 0.0

class MusicPlayer:
    def __init__(self):
        self.source = 'Local'
        self.library: List[Track] = []
        self.playlist: List[Track] = []
        self.current_index = -1
        self.volume = 0.70
        self.paused = False
        self.started_at = 0.0
        self.paused_at = 0.0
        self._mixer_ready = False
        self._init_mixer()

    def _init_mixer(self):
        if pygame is None: return False
        try:
            if not pygame.mixer.get_init(): pygame.mixer.init()
            pygame.mixer.music.set_volume(self.volume)
            self._mixer_ready = True
        except Exception:
            self._mixer_ready = False
        return self._mixer_ready

    @property
    def current_track(self) -> Optional[Track]:
        return self.playlist[self.current_index] if 0 <= self.current_index < len(self.playlist) else None

    def scan_folder(self, folder: str) -> List[Track]:
        tracks = []
        if not folder or not os.path.isdir(folder): return tracks
        for root, _, files in os.walk(folder):
            for name in sorted(files):
                if os.path.splitext(name)[1].lower() in AUDIO_EXTENSIONS:
                    title = os.path.splitext(name)[0]
                    tracks.append(Track(os.path.join(root, name), title))
        self.library = tracks
        self.playlist = list(tracks)
        self.current_index = -1
        return tracks

    def search(self, query: str) -> List[Track]:
        q = (query or '').lower().strip()
        return [t for t in self.library if not q or q in t.title.lower() or q in t.artist.lower()]

    def play_index(self, index: int) -> bool:
        if not (0 <= index < len(self.playlist)) or not self._init_mixer(): return False
        track = self.playlist[index]
        try:
            pygame.mixer.music.load(track.path)
            pygame.mixer.music.play()
            self.current_index = index
            self.paused = False
            self.started_at = time.monotonic()
            self.paused_at = 0.0
            return True
        except Exception:
            return False

    def toggle_play_pause(self) -> bool:
        if self.current_index < 0:
            return self.play_index(0) if self.playlist else False
        if not self._mixer_ready: return False
        if self.paused:
            pygame.mixer.music.unpause(); self.started_at = time.monotonic() - self.paused_at; self.paused = False
        elif pygame.mixer.music.get_busy():
            self.paused_at = self.position; pygame.mixer.music.pause(); self.paused = True
        else: return self.play_index(self.current_index)
        return True

    def next(self):
        return self.play_index((self.current_index + 1) % len(self.playlist)) if self.playlist else False
    def previous(self):
        return self.play_index((self.current_index - 1) % len(self.playlist)) if self.playlist else False

    @property
    def position(self) -> float:
        if self.current_index < 0: return 0.0
        if self.paused: return self.paused_at
        return max(0.0, time.monotonic() - self.started_at)

    def set_volume(self, value: float):
        self.volume = max(0.0, min(1.0, value))
        if self._mixer_ready: pygame.mixer.music.set_volume(self.volume)

    def set_source(self, source: str):
        if source in ('YouTube Music', 'Spotify', 'Local'): self.source = source

    def service_status(self):
        if self.source == 'Local': return 'Выберите папку с музыкой'
        return 'Подключение требует официальной интеграции OAuth/API; аудиопоток не имитируется.'
