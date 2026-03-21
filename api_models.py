from pydantic import BaseModel, ConfigDict, Field


class InfoRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    mode: str = "m4b"


class GoogleDriveFolderRequest(BaseModel):
    folder_id: str = ""


class GoogleDriveImportRequest(BaseModel):
    file_id: str
    metadata_file_id: str = ""
    cover_file_id: str = ""


class BookmarkUpdateRequest(BaseModel):
    time: float = 0.0
    duration: float = 0.0
    track: int = 0
    file_name: str = ""
    source: str = ""


class StatusResponse(BaseModel):
    status: str


class FolderResponse(BaseModel):
    folder: str


class FolderSelectionResponse(BaseModel):
    status: str
    folder: str


class BookInfoResponse(BaseModel):
    title: str
    chapters: list[dict] = Field(default_factory=list)
    cover: str | None = None


class DownloadStartResponse(BaseModel):
    task_id: str
    reused: bool = False


class ProgressPayload(BaseModel):
    status: str
    phase: str | None = None
    percent: float | None = None
    current_frag: int | None = None
    total_frags: int | None = None
    file_name: str | None = None
    source_url: str | None = None
    mode: str | None = None
    message: str | None = None
    updated_at: float | None = None


class BookmarkPayload(BaseModel):
    time: float = 0.0
    duration: float = 0.0
    track: int = 0
    file_name: str = ""
    source: str = ""
    updated_at: float | None = None


class BookmarkResponse(BaseModel):
    bookmark: BookmarkPayload | None


class BookmarksResponse(BaseModel):
    bookmarks: dict[str, BookmarkPayload]


class SaveBookmarkResponse(BaseModel):
    status: str
    bookmark: BookmarkPayload


class ImportedBookIdsResponse(BaseModel):
    book_ids: list[str] = Field(default_factory=list)


class LibraryItemResponse(BaseModel):
    name: str
    book_id: str
    size_bytes: int
    size_mb: float
    has_meta: bool
    duration_seconds: float | None = None
    chapter_count: int | None = None
    mtime: float
    source: str | None = None
    drive_file_id: str = ""
    drive_metadata_file_id: str = ""
    drive_cover_file_id: str = ""
    mime_type: str = ""
    web_view_link: str = ""
    streamable: bool = False


class LibraryFilesResponse(BaseModel):
    files: list[LibraryItemResponse] = Field(default_factory=list)


class ChapterItemResponse(BaseModel):
    title: str = ""
    start: float = 0.0
    end: float = 0.0

    model_config = ConfigDict(extra="allow")


class PlaylistItemResponse(BaseModel):
    title: str = ""
    file: str = ""

    model_config = ConfigDict(extra="allow")


class PlaybackMetadataResponse(BaseModel):
    title: str = ""
    mode: str = "single"
    file_name: str = ""
    book_id: str | None = None
    source: str | None = None
    chapters: list[ChapterItemResponse] = Field(default_factory=list)
    playlist: list[PlaylistItemResponse] = Field(default_factory=list)
    cover_url: str | None = None
    local_cover: str | None = None
    drive_file_id: str = ""
    stream_url: str = ""

    model_config = ConfigDict(extra="allow")


class GoogleDriveStatusResponse(BaseModel):
    configured: bool
    connected: bool
    folder_id: str = ""
    account_email: str = ""
    account_name: str = ""
    expires_at: float | None = None
    expired: bool = False


class GoogleDriveAuthUrlResponse(BaseModel):
    auth_url: str
    state: str


class GoogleDriveFolderSaveResponse(BaseModel):
    status: str
    folder_id: str


class GoogleDriveImportResponse(BaseModel):
    status: str
    file_name: str
    metadata_name: str = ""
    cover_name: str = ""
