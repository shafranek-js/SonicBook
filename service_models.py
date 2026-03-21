import time as time_module

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator


class ProgressEntryModel(BaseModel):
    status: str = "searching"
    phase: str = "searching"
    percent: float = 0.0
    current_frag: int = 0
    total_frags: int = 0
    file_name: str = ""
    source_url: str = ""
    mode: str = ""
    message: str = ""
    updated_at: float = Field(
        default_factory=time_module.time,
        validation_alias=AliasChoices("updated_at", "timestamp"),
        serialization_alias="updated_at",
    )

    @field_validator("percent", mode="before")
    @classmethod
    def _normalize_percent(cls, value):
        percent = float(value or 0.0)
        return max(0.0, min(100.0, percent))

    @field_validator("current_frag", "total_frags", mode="before")
    @classmethod
    def _normalize_counts(cls, value):
        return max(0, int(value or 0))


class BookmarkRecordModel(BaseModel):
    time: float = 0.0
    duration: float = 0.0
    track: int = 0
    file_name: str = ""
    source: str = ""
    updated_at: float = Field(default_factory=time_module.time)

    @field_validator("time", "duration", mode="before")
    @classmethod
    def _normalize_float_fields(cls, value):
        return float(value or 0.0)

    @field_validator("track", mode="before")
    @classmethod
    def _normalize_track(cls, value):
        return int(value or 0)

    @model_validator(mode="after")
    def _clamp_values(self):
        self.duration = max(0.0, self.duration)
        self.time = max(0.0, self.time)
        if self.duration > 0:
            self.time = min(self.time, self.duration)
        self.track = max(0, self.track)
        self.time = round(self.time, 3)
        self.duration = round(self.duration, 3)
        return self


class LibraryFileRecordModel(BaseModel):
    name: str
    book_id: str = ""
    size_bytes: int = 0
    size_mb: float = 0.0
    has_meta: bool = False
    duration_seconds: float | None = None
    chapter_count: int | None = None
    mtime: float = 0.0
    source: str | None = None
    drive_file_id: str = ""
    drive_metadata_file_id: str = ""
    drive_cover_file_id: str = ""
    mime_type: str = ""
    web_view_link: str = ""

    @field_validator("size_bytes", mode="before")
    @classmethod
    def _normalize_size_bytes(cls, value):
        return max(0, int(value or 0))

    @field_validator("size_mb", mode="before")
    @classmethod
    def _normalize_size_mb(cls, value):
        return max(0.0, float(value or 0.0))

    @field_validator("duration_seconds", mode="before")
    @classmethod
    def _normalize_duration_seconds(cls, value):
        if value in (None, ""):
            return None
        duration = float(value)
        return round(duration, 2) if duration > 0 else None

    @field_validator("chapter_count", mode="before")
    @classmethod
    def _normalize_chapter_count(cls, value):
        if value in (None, ""):
            return None
        count = int(value)
        return count if count >= 0 else 0

    @field_validator("mtime", mode="before")
    @classmethod
    def _normalize_mtime(cls, value):
        return float(value or 0.0)


class LibraryIndexEntryModel(BaseModel):
    size_bytes: int = 0
    mtime_ns: int = 0
    sidecar_mtime_ns: int = 0
    file: LibraryFileRecordModel

    @field_validator("size_bytes", "mtime_ns", "sidecar_mtime_ns", mode="before")
    @classmethod
    def _normalize_int_fields(cls, value):
        return max(0, int(value or 0))
