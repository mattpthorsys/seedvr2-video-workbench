from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AudioStream(BaseModel):
    index: int
    codec: str | None = None
    channels: int | None = None
    language: str | None = None


class VideoMetadata(BaseModel):
    filename: str
    duration_seconds: float | None = None
    frame_count_estimate: int | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: float | None = None
    scan_type: str | None = None
    audio_streams: list[AudioStream] = Field(default_factory=list)
    video_codec: str | None = None


class ProbeRequest(BaseModel):
    input_path: str


class TargetOptions(BaseModel):
    mode: Literal["keep", "720p", "1080p", "1440p", "4k", "custom"] = "1080p"
    width: int | None = None
    height: int | None = None


class PreprocessOptions(BaseModel):
    deinterlace: Literal["none", "bwdif", "qtgmc"] = "none"
    inverse_telecine: Literal["off", "auto", "force_23_976"] = "off"
    denoise: Literal["off", "light", "medium", "heavy"] = "off"
    deblock: Literal["off", "light", "medium"] = "off"


class SeedVR2Options(BaseModel):
    model: Literal["3B", "7B", "custom"] = "3B"
    custom_model_path: str | None = None
    precision: Literal["FP8", "GGUF", "FP16", "auto"] = "auto"
    batch_size: int = 5
    temporal_overlap: int = 2
    vae_tiling: bool = True
    blockswap: bool = False
    colour_correction: bool = True


class EncodeOptions(BaseModel):
    codec: Literal["h264", "h265", "av1"] = "h265"
    hardware: Literal["auto", "cpu", "nvenc"] = "auto"
    container: Literal["mkv", "mp4", "mov", "webm"] = "mkv"
    quality: float = 20
    preset: str = "medium"
    copy_audio: bool = True
    audio_mode: Literal["copy", "aac", "opus", "none"] = "copy"
    audio_bitrate: str = "192k"


class JobCreate(BaseModel):
    input_path: str
    output_path: str | None = None
    preset: str = "Progressive"
    target: TargetOptions = Field(default_factory=TargetOptions)
    preprocessing: PreprocessOptions = Field(default_factory=PreprocessOptions)
    seedvr2: SeedVR2Options = Field(default_factory=SeedVR2Options)
    encode: EncodeOptions = Field(default_factory=EncodeOptions)
    source_metadata: VideoMetadata | None = None



class JobRead(BaseModel):
    id: int
    input_path: str
    output_path: str | None = None
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    current_stage: str | None = None
    frames_total: int = 0
    frames_processed: int = 0
    progress: float = 0
    estimated_total_seconds_initial: float | None = None
    eta_confidence_initial: str | None = None
    error_message: str | None = None


class StageEstimate(BaseModel):
    stage_name: str
    estimated_seconds: float
    fps: float
    basis: str


class EtaResponse(BaseModel):
    estimated_total_seconds: float
    estimated_stage_seconds: list[StageEstimate]
    confidence: Literal["low", "medium", "high"]
    explanation: str
    samples_used: int


class HealthResponse(BaseModel):
    ok: bool
    data_dir: str
    database: str
    gpu: dict[str, Any] | None = None


class ModelTestRequest(BaseModel):
    model: Literal["3B", "7B", "custom"] = "3B"
    custom_model_path: str | None = None
    precision: Literal["FP8", "GGUF", "FP16", "auto"] = "auto"
    batch_size: int = 1
    temporal_overlap: int = 0
    run_inference: bool = False
    timeout_seconds: int = 300


class ModelDownloadRequest(BaseModel):
    model: Literal["3B", "7B", "7B-sharp"] = "3B"
