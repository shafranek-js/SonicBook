let playerState = {
    mode: 'single', duration: 0, chapters: [], playlist: [], currentTrackIndex: 0, fileName: null, bookTitle: "", tempCoverUrl: null, source: 'local', streamUrl: null, bookmarkKey: null, bookId: null, driveFileId: '', driveMetadataFileId: '', driveCoverFileId: '', driveResourceKey: '', driveMetadataResourceKey: '', driveCoverResourceKey: '', sizeBytes: 0
};

const audio = document.getElementById('audioElement');
let bookmarkSyncTimer = null;
let driveStreamStartupTimer = null;
let driveStreamPlayingStatusTimer = null;
const DRIVE_STREAM_START_TIMEOUT_MS = 15000;
const SLEEP_TIMER_DEFAULT_MINUTES = 60;
const SLEEP_TIMER_IDLE_POLL_MS = 5000;
const SLEEP_TIMER_ACTIVITY_EVENTS = ['mousemove', 'mousedown', 'pointerdown', 'keydown', 'wheel', 'touchstart', 'scroll'];
let sleepTimerInterval = null;
let sleepTimerDeadlineAt = 0;
let sleepTimerLastActivityAt = 0;
let sleepTimerNextIdlePollAt = 0;
let sleepTimerIdlePollInFlight = false;
let sleepTimerSystemIdleSupported = null;
let sleepTimerPausedPlayback = false;
let sleepTimerResumeScheduled = false;

function toFiniteNumber(value, fallback = 0) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : fallback;
}

function hasFiniteDuration(value) {
    return Number.isFinite(value) && value > 0;
}

function getSleepTimerDurationMinutes() {
    const select = document.getElementById('sleepTimerDuration');
    const rawValue = select ? select.value : appState.sleepTimer.durationMinutes;
    const minutes = Number(rawValue);
    return Number.isFinite(minutes) && minutes > 0 ? minutes : SLEEP_TIMER_DEFAULT_MINUTES;
}

function getSleepTimerDurationSeconds() {
    return getSleepTimerDurationMinutes() * 60;
}

function formatSleepTimerCountdown(seconds) {
    const safeSeconds = Math.max(0, Math.ceil(Number(seconds) || 0));
    const hours = Math.floor(safeSeconds / 3600);
    const minutes = Math.floor((safeSeconds % 3600) / 60);
    const remainder = safeSeconds % 60;
    if (hours > 0) {
        return `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`;
    }
    return `${minutes}:${String(remainder).padStart(2, '0')}`;
}

function resetSleepTimerCountdown() {
    const remainingSeconds = getSleepTimerDurationSeconds();
    appState.sleepTimer.remainingSeconds = remainingSeconds;
    sleepTimerDeadlineAt = Date.now() + remainingSeconds * 1000;
    syncSleepTimerUI();
}

function startSleepTimerTicker() {
    if (sleepTimerInterval) {
        clearInterval(sleepTimerInterval);
    }
    sleepTimerInterval = window.setInterval(tickSleepTimer, 1000);
    tickSleepTimer();
}

function stopSleepTimerTicker() {
    if (sleepTimerInterval) {
        clearInterval(sleepTimerInterval);
        sleepTimerInterval = null;
    }
}

async function syncSleepTimerWithSystemIdle(force = false) {
    if (!appState.sleepTimer.enabled || sleepTimerIdlePollInFlight) {
        return false;
    }
    const now = Date.now();
    if (!force && (sleepTimerSystemIdleSupported === false || now < sleepTimerNextIdlePollAt)) {
        return false;
    }
    sleepTimerIdlePollInFlight = true;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 3000);
    try {
        const res = await fetch('/api/system/idle', {
            cache: 'no-store',
            signal: controller.signal
        });
        if (!res.ok) {
            throw new Error(`System idle check failed: ${res.status}`);
        }
        const data = await res.json();
        if (!appState.sleepTimer.enabled) {
            return false;
        }
        const idleSeconds = Number(data.idle_seconds);
        if (!data.supported || !Number.isFinite(idleSeconds)) {
            sleepTimerSystemIdleSupported = false;
            return false;
        }
        sleepTimerSystemIdleSupported = true;
        const remainingSeconds = Math.max(0, Math.ceil(getSleepTimerDurationSeconds() - idleSeconds));
        appState.sleepTimer.remainingSeconds = remainingSeconds;
        sleepTimerDeadlineAt = Date.now() + remainingSeconds * 1000;
        if (remainingSeconds <= 0) {
            pausePlaybackForSleepTimer();
        } else {
            syncSleepTimerUI();
        }
        return true;
    } catch (e) {
        sleepTimerSystemIdleSupported = false;
        return false;
    } finally {
        window.clearTimeout(timeoutId);
        sleepTimerNextIdlePollAt = Date.now() + SLEEP_TIMER_IDLE_POLL_MS;
        sleepTimerIdlePollInFlight = false;
    }
}

function setSleepTimerEnabled(enabled, announce = false) {
    const nextEnabled = Boolean(enabled);
    appState.sleepTimer.enabled = nextEnabled;
    if (nextEnabled) {
        sleepTimerSystemIdleSupported = null;
        sleepTimerNextIdlePollAt = 0;
        resetSleepTimerCountdown();
        void syncSleepTimerWithSystemIdle(true);
        startSleepTimerTicker();
        if (announce) {
            setStatusMessage(i18n[appState.currentLang].sleepTimerActive, 'info');
        }
    } else {
        stopSleepTimerTicker();
        appState.sleepTimer.remainingSeconds = getSleepTimerDurationSeconds();
        sleepTimerDeadlineAt = 0;
        sleepTimerNextIdlePollAt = 0;
        sleepTimerIdlePollInFlight = false;
        if (announce) {
            setStatusMessage(i18n[appState.currentLang].sleepTimerOff, 'info');
        }
    }
    syncSleepTimerUI();
}

function pausePlaybackForSleepTimer() {
    const shouldResumeOnActivity = !audio.paused && Boolean(audio.src);
    setSleepTimerEnabled(false, false);
    sleepTimerPausedPlayback = shouldResumeOnActivity;
    if (!audio.paused) {
        audio.pause();
    }
    setPlayButtonState(false);
    syncLibraryPlayIcons();
    setStatusMessage(i18n[appState.currentLang].sleepTimerStopped, 'info');
}

async function resumePlaybackAfterSleepTimer() {
    if (!sleepTimerPausedPlayback || sleepTimerResumeScheduled) {
        return;
    }
    sleepTimerResumeScheduled = true;
    window.setTimeout(async () => {
        sleepTimerResumeScheduled = false;
        if (!sleepTimerPausedPlayback || !audio.src) {
            return;
        }
        sleepTimerPausedPlayback = false;
        setSleepTimerEnabled(true, false);
        if (audio.paused) {
            await requestAudioPlayback(playerState.source === 'google_drive');
        }
        setStatusMessage(i18n[appState.currentLang].sleepTimerResumed, 'info');
    }, 250);
}

function tickSleepTimer() {
    if (!appState.sleepTimer.enabled) {
        return;
    }
    if (sleepTimerSystemIdleSupported !== false) {
        void syncSleepTimerWithSystemIdle(false);
    }
    const remainingSeconds = Math.max(0, Math.ceil((sleepTimerDeadlineAt - Date.now()) / 1000));
    appState.sleepTimer.remainingSeconds = remainingSeconds;
    if (remainingSeconds <= 0) {
        if (sleepTimerSystemIdleSupported === true || sleepTimerIdlePollInFlight) {
            void syncSleepTimerWithSystemIdle(true);
            syncSleepTimerUI();
            return;
        }
        pausePlaybackForSleepTimer();
        return;
    }
    syncSleepTimerUI();
}

function handleSleepTimerActivity(event) {
    if (!appState.sleepTimer.enabled) {
        if (sleepTimerPausedPlayback) {
            void resumePlaybackAfterSleepTimer();
        }
        return;
    }
    const now = Date.now();
    if (event.type === 'mousemove' && now - sleepTimerLastActivityAt < 1000) {
        return;
    }
    sleepTimerLastActivityAt = now;
    resetSleepTimerCountdown();
}

function toggleSleepTimer() {
    setSleepTimerEnabled(!appState.sleepTimer.enabled, false);
}

function handleSleepTimerDurationChange() {
    const minutes = getSleepTimerDurationMinutes();
    appState.sleepTimer.durationMinutes = minutes;
    localStorage.setItem('sleep-timer-minutes', String(minutes));
    if (appState.sleepTimer.enabled) {
        resetSleepTimerCountdown();
        return;
    }
    appState.sleepTimer.remainingSeconds = minutes * 60;
    syncSleepTimerUI();
}

function syncSleepTimerUI() {
    const button = document.getElementById('sleepTimerBtn');
    const countdown = document.getElementById('sleepTimerCountdown');
    const select = document.getElementById('sleepTimerDuration');
    if (!button || !countdown || !select || !appState.sleepTimer) {
        return;
    }
    const t = i18n[appState.currentLang];
    const selectedMinutes = Number(select.value);
    if (!Number.isFinite(selectedMinutes) || selectedMinutes !== appState.sleepTimer.durationMinutes) {
        select.value = String(appState.sleepTimer.durationMinutes || SLEEP_TIMER_DEFAULT_MINUTES);
    }
    const remainingSeconds = appState.sleepTimer.enabled
        ? appState.sleepTimer.remainingSeconds
        : getSleepTimerDurationSeconds();
    countdown.innerText = formatSleepTimerCountdown(remainingSeconds);
    button.classList.toggle('is-active', appState.sleepTimer.enabled);
    button.setAttribute('aria-pressed', appState.sleepTimer.enabled ? 'true' : 'false');
    button.setAttribute('aria-label', t.sleepTimerTitle);
    button.title = appState.sleepTimer.enabled ? t.sleepTimerActive : t.sleepTimerOff;
    select.setAttribute('aria-label', t.sleepTimerDuration);
    select.title = t.sleepTimerDuration;
}

function initSleepTimer() {
    const select = document.getElementById('sleepTimerDuration');
    if (select) {
        select.value = String(appState.sleepTimer.durationMinutes || SLEEP_TIMER_DEFAULT_MINUTES);
    }
    appState.sleepTimer.durationMinutes = getSleepTimerDurationMinutes();
    appState.sleepTimer.remainingSeconds = appState.sleepTimer.durationMinutes * 60;
    SLEEP_TIMER_ACTIVITY_EVENTS.forEach(eventName => {
        window.addEventListener(eventName, handleSleepTimerActivity, { passive: true });
    });
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            handleSleepTimerActivity({ type: 'visibilitychange' });
        }
    });
    window.addEventListener('focus', () => handleSleepTimerActivity({ type: 'focus' }));
    syncSleepTimerUI();
}

function restoreSavedPlaybackPosition(savedBmk) {
    const bookmarkTime = toFiniteNumber(savedBmk?.time, 0);
    if (!bookmarkTime) {
        return;
    }
    if (audio.readyState >= 1) {
        const duration = toFiniteNumber(audio.duration, 0);
        audio.currentTime = duration > 0
            ? Math.max(0, Math.min(duration, bookmarkTime))
            : Math.max(0, bookmarkTime);
        return;
    }
    audio.addEventListener('loadedmetadata', function onMeta() {
        const duration = toFiniteNumber(audio.duration, 0);
        audio.currentTime = duration > 0
            ? Math.max(0, Math.min(duration, bookmarkTime))
            : Math.max(0, bookmarkTime);
        audio.removeEventListener('loadedmetadata', onMeta);
    });
}

async function requestAudioPlayback(isDriveStream = false) {
    try {
        await audio.play();
    } catch (e) {
        setPlayButtonState(false);
        syncLibraryPlayIcons();
        if (isDriveStream) {
            setDriveStreamBuffering('', false, false);
            setStatusMessage(i18n[appState.currentLang].googleDriveStreamError, 'error');
        }
        console.warn('Audio playback failed', e);
    }
}

function getCurrentDriveStreamFileId() {
    if (!playerState.streamUrl) {
        return '';
    }
    const match = playerState.streamUrl.split('?')[0].match(/\/api\/google-drive\/files\/([^/]+)\/stream$/);
    return match ? decodeURIComponent(match[1]) : '';
}

function buildGoogleDriveStreamUrl(fileId, resourceKey = '') {
    if (!fileId) {
        return '';
    }
    const params = new URLSearchParams();
    if (resourceKey) {
        params.set('resource_key', resourceKey);
    }
    const suffix = params.toString();
    return `/api/google-drive/files/${encodeURIComponent(fileId)}/stream${suffix ? `?${suffix}` : ''}`;
}

function clearDriveStreamStartupTimer() {
    if (driveStreamStartupTimer) {
        clearTimeout(driveStreamStartupTimer);
        driveStreamStartupTimer = null;
    }
}

function clearDriveStreamPlayingStatusTimer() {
    if (driveStreamPlayingStatusTimer) {
        clearTimeout(driveStreamPlayingStatusTimer);
        driveStreamPlayingStatusTimer = null;
    }
}

function scheduleDriveStreamPlayingStatusClear() {
    clearDriveStreamPlayingStatusTimer();
    driveStreamPlayingStatusTimer = window.setTimeout(() => {
        if (playerState.source === 'google_drive' && appState.driveStreamPhase === 'playing') {
            clearStatusMessage();
        }
    }, 2500);
}

function scheduleDriveStreamStartupTimeout(fileId, phase) {
    clearDriveStreamStartupTimer();
    if (!fileId || !['connecting', 'buffering'].includes(phase)) {
        return;
    }
    driveStreamStartupTimer = window.setTimeout(() => {
        if (
            playerState.source === 'google_drive' &&
            appState.driveStreamBufferingFileId === fileId &&
            ['connecting', 'buffering'].includes(appState.driveStreamPhase)
        ) {
            setStatusMessage(i18n[appState.currentLang].googleDriveStreamStartupSlow, 'error');
        }
    }, DRIVE_STREAM_START_TIMEOUT_MS);
}

function setDriveStreamBuffering(fileId, isBuffering = true, syncStatus = true, phase = '') {
    const nextFileId = isBuffering ? (fileId || '') : '';
    const nextPhase = isBuffering ? (phase || 'buffering') : 'idle';
    appState.driveStreamBufferingFileId = nextFileId;
    appState.driveStreamPhase = nextPhase;
    scheduleDriveStreamStartupTimeout(nextFileId, nextPhase);
    if (nextPhase === 'playing') {
        scheduleDriveStreamPlayingStatusClear();
    } else {
        clearDriveStreamPlayingStatusTimer();
    }
    if (syncStatus) {
        if (isBuffering && appState.driveStreamBufferingFileId) {
            const t = i18n[appState.currentLang];
            if (nextPhase === 'connecting') {
                setStatusMessage(t.googleDriveConnecting, 'info');
            } else if (nextPhase === 'playing') {
                setStatusMessage(t.googleDrivePlaying, 'success');
            } else {
                setStatusMessage(t.googleDriveBuffering, 'info');
            }
        } else if (playerState.source === 'google_drive') {
            clearStatusMessage();
        }
    }
    syncLibraryPlayIcons();
}

function readLegacyBookmark(bookmarkKey) {
    if (!bookmarkKey) {
        return null;
    }
    try {
        const raw = localStorage.getItem(bookmarkKey);
        if (raw && !raw.startsWith('{')) {
            return { time: parseFloat(raw), track: 0 };
        }
        return raw ? JSON.parse(raw) : null;
    } catch (e) {
        localStorage.removeItem(bookmarkKey);
        return null;
    }
}

async function loadSavedBookmark(bookId, bookmarkKey) {
    const legacyBookmark = readLegacyBookmark(bookmarkKey);
    if (!bookId) {
        return legacyBookmark;
    }
    const cachedBookmark = getCachedBookmark(bookId);
    if (cachedBookmark && cachedBookmark.time) {
        return cachedBookmark;
    }
    const fileName = playerState.fileName || '';
    const unsizedBookmark = fileName ? getCachedBookmark(buildClientBookId(fileName)) : null;
    if (unsizedBookmark && unsizedBookmark.time) {
        return unsizedBookmark;
    }
    const legacyServerBookmark = fileName ? getCachedBookmark(buildLegacyClientBookId(fileName)) : null;
    if (legacyServerBookmark && legacyServerBookmark.time) {
        return legacyServerBookmark;
    }
    try {
        const res = await fetch(`/api/bookmarks/${encodeURIComponent(bookId)}`);
        const data = await res.json();
        if (res.ok && data.bookmark && data.bookmark.time) {
            appState.bookmarks[bookId] = data.bookmark;
            return data.bookmark;
        }
    } catch (e) {}
    return legacyBookmark;
}

function cacheBookmarkState(bookmark) {
    if (!playerState.bookId || !bookmark) {
        return;
    }
    appState.bookmarks[playerState.bookId] = bookmark;
}

function buildActivePlaybackPayload() {
    return {
        book_id: playerState.bookId || '',
        file_name: playerState.fileName || '',
        source: playerState.source || '',
        drive_file_id: playerState.driveFileId || '',
        drive_metadata_file_id: playerState.driveMetadataFileId || '',
        drive_cover_file_id: playerState.driveCoverFileId || '',
        drive_resource_key: playerState.driveResourceKey || '',
        drive_metadata_resource_key: playerState.driveMetadataResourceKey || '',
        drive_cover_resource_key: playerState.driveCoverResourceKey || '',
        size_bytes: Number(playerState.sizeBytes) || 0
    };
}

function syncSharedActivePlayback() {
    if (typeof syncLastActivePlayback !== 'function') {
        return;
    }
    const payload = buildActivePlaybackPayload();
    if (!payload.book_id && !payload.file_name && !payload.drive_file_id) {
        return;
    }
    void syncLastActivePlayback(payload);
}

async function flushBookmarkSync(keepalive = false) {
    if (bookmarkSyncTimer) {
        clearTimeout(bookmarkSyncTimer);
        bookmarkSyncTimer = null;
    }
    const duration = toFiniteNumber(audio.duration, toFiniteNumber(playerState.duration, 0));
    if (!playerState.bookId || !hasFiniteDuration(duration)) {
        return;
    }
    const currentTime = Math.max(0, Math.min(duration, toFiniteNumber(audio.currentTime, 0)));
    const payload = {
        time: currentTime,
        duration,
        track: playerState.currentTrackIndex,
        file_name: playerState.fileName || '',
        source: playerState.source || ''
    };
    cacheBookmarkState(payload);
    try {
        const res = await fetch(`/api/bookmarks/${encodeURIComponent(playerState.bookId)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            keepalive
        });
        const data = await res.json();
        if (res.ok && data.bookmark) {
            cacheBookmarkState(data.bookmark);
        }
    } catch (e) {}
}

function scheduleBookmarkSync(immediate = false) {
    if (!playerState.bookId) {
        return;
    }
    if (immediate) {
        void flushBookmarkSync(true);
        return;
    }
    if (bookmarkSyncTimer) {
        return;
    }
    bookmarkSyncTimer = window.setTimeout(() => {
        bookmarkSyncTimer = null;
        void flushBookmarkSync();
    }, 4000);
}

audio.addEventListener('timeupdate', () => {
    if (!playerState.duration) return;
    const pct = (audio.currentTime / playerState.duration) * 100;
    document.getElementById('timelineFill').style.width = pct + '%';
    document.getElementById('timeCurrent').innerText = formatTime(audio.currentTime);
    const playerChapterEl = document.getElementById('playerChapter');
    if (playerState.mode === 'zip' && playerState.playlist.length > 0) {
        const track = playerState.playlist[playerState.currentTrackIndex];
        if (playerChapterEl) {
            playerChapterEl.innerText = `${playerState.currentTrackIndex + 1} / ${playerState.playlist.length}: ${track.title}`;
        }
    } else if (playerState.chapters.length > 0) {
        const currentChIndex = playerState.chapters.findIndex(c => audio.currentTime >= c.start && audio.currentTime < c.end);
        const safeIndex = currentChIndex !== -1 ? currentChIndex : 0;
        if (playerChapterEl) {
            playerChapterEl.innerText = playerState.chapters[safeIndex].title;
        }
        const container = document.getElementById('appContainer');
        if (container.classList.contains('panel-open')) {
            playerState.chapters.forEach((ch, idx) => {
                const fillEl = document.getElementById(`ch-fill-${idx}`);
                const timeEl = document.getElementById(`ch-time-${idx}`);
                if (!fillEl) {
                    return;
                }
                if (idx < safeIndex) {
                    fillEl.style.width = '100%';
                    if (timeEl) timeEl.innerText = formatTime(ch.start);
                } else if (idx > safeIndex) {
                    fillEl.style.width = '0%';
                    if (timeEl) timeEl.innerText = formatTime(ch.start);
                } else {
                    const dur = ch.end - ch.start;
                    const fillPct = dur > 0 ? ((audio.currentTime - ch.start) / dur) * 100 : 0;
                    fillEl.style.width = `${Math.max(0, Math.min(100, fillPct))}%`;
                    if (timeEl) timeEl.innerText = `${formatTime(Math.max(0, audio.currentTime - ch.start))} / ${formatTime(dur)}`;
                    const itemEl = document.getElementById(`ch-item-${idx}`);
                    if (itemEl && !itemEl.classList.contains('active-ch')) {
                        document.querySelectorAll('.chapter-list-item').forEach(el => el.classList.remove('active-ch'));
                        itemEl.classList.add('active-ch');
                    }
                }
            });
        }
    }
    if (playerState.bookmarkKey) {
        localStorage.setItem(playerState.bookmarkKey, JSON.stringify({
            time: audio.currentTime,
            duration: audio.duration,
            track: playerState.currentTrackIndex
        }));
    }
    scheduleBookmarkSync(false);
});

audio.addEventListener('loadedmetadata', () => {
    playerState.duration = toFiniteNumber(audio.duration, 0);
    document.getElementById('timeTotal').innerText = formatTime(playerState.duration);
    if (playerState.mode === 'm4b' && playerState.chapters.length > 0 && hasFiniteDuration(playerState.duration)) {
        document.getElementById('markersContainer').innerHTML = playerState.chapters.map(ch =>
            `<div class="timeline-marker" style="left: ${(ch.start / playerState.duration) * 100}%;" title="${ch.title}"></div>`
        ).join('');
    }
});

audio.addEventListener('ended', () => {
    if (playerState.mode === 'zip' && playerState.currentTrackIndex < playerState.playlist.length - 1) {
        playerState.currentTrackIndex++;
        playCurrentTrack(true);
    } else {
        setPlayButtonState(false);
        syncLibraryPlayIcons();
    }
});

audio.addEventListener('play', () => {
    setPlayButtonState(true);
    syncLibraryPlayIcons();
    updateMediaSession();
});

audio.addEventListener('pause', () => {
    setPlayButtonState(false);
    syncLibraryPlayIcons();
    scheduleBookmarkSync(true);
});

audio.addEventListener('playing', () => {
    if (playerState.source === 'google_drive') {
        const driveFileId = getCurrentDriveStreamFileId();
        setDriveStreamBuffering(driveFileId, !!driveFileId, true, 'playing');
    }
});

audio.addEventListener('loadstart', () => {
    if (playerState.source !== 'google_drive') {
        return;
    }
    const driveFileId = getCurrentDriveStreamFileId();
    if (driveFileId) {
        setDriveStreamBuffering(driveFileId, true, true, 'connecting');
    }
});

['waiting', 'stalled'].forEach((eventName) => {
    audio.addEventListener(eventName, () => {
        if (playerState.source !== 'google_drive') {
            return;
        }
        const driveFileId = getCurrentDriveStreamFileId();
        if (driveFileId) {
            setDriveStreamBuffering(driveFileId, true, true, 'buffering');
        }
    });
});

audio.addEventListener('error', () => {
    if (playerState.source !== 'google_drive') {
        return;
    }
    setDriveStreamBuffering('', false, false);
    setStatusMessage(i18n[appState.currentLang].googleDriveStreamError, 'error');
});

window.addEventListener('beforeunload', () => {
    scheduleBookmarkSync(true);
});

function syncLibraryPlayIcons() {
    const t = i18n[appState.currentLang];
    document.querySelectorAll('.library-quick-play').forEach(el => {
        el.innerText = '▶';
        el.title = 'Play / Pause';
        el.classList.remove('is-active');
        el.setAttribute('aria-pressed', 'false');
    });
    document.querySelectorAll('.library-quick-stream').forEach(el => {
        el.innerText = t.googleDriveStream || 'Stream';
        el.title = t.googleDriveStreamTooltip || t.googleDriveStream || 'Stream';
        el.classList.remove('is-active', 'is-buffering', 'is-connecting');
        el.setAttribute('aria-pressed', 'false');
        el.setAttribute('aria-busy', 'false');
    });
    if (appState.driveStreamBufferingFileId) {
        const bufferingEl = document.getElementById(buildLibraryPlayButtonId('google_drive', appState.driveStreamBufferingFileId));
        if (bufferingEl) {
            if (appState.driveStreamPhase === 'connecting') {
                bufferingEl.innerText = t.googleDriveConnectingShort || 'Connecting...';
                bufferingEl.title = t.googleDriveConnecting || bufferingEl.innerText;
                bufferingEl.classList.add('is-buffering', 'is-connecting');
                bufferingEl.setAttribute('aria-busy', 'true');
            } else if (appState.driveStreamPhase === 'buffering') {
                bufferingEl.innerText = t.googleDriveBufferingShort || 'Buffering...';
                bufferingEl.title = t.googleDriveBuffering || bufferingEl.innerText;
                bufferingEl.classList.add('is-buffering');
                bufferingEl.setAttribute('aria-busy', 'true');
            }
        }
    }
    if (!audio.paused && playerState.fileName) {
        const id = playerState.source === 'google_drive'
            ? buildLibraryPlayButtonId('google_drive', getCurrentDriveStreamFileId())
            : buildLibraryPlayButtonId('local', playerState.fileName);
        const el = document.getElementById(id);
        if (el) {
            if (playerState.source === 'google_drive') {
                el.innerText = t.googleDrivePause || 'Pause';
                el.title = t.googleDrivePause || 'Pause';
                el.classList.add('is-active');
                el.setAttribute('aria-pressed', 'true');
            } else {
                el.innerText = '⏸';
                el.title = 'Play / Pause';
                el.classList.add('is-active');
                el.setAttribute('aria-pressed', 'true');
            }
        }
    }
}

function togglePlay() {
    if (audio.paused) void requestAudioPlayback(playerState.source === 'google_drive');
    else audio.pause();
}

function seekRelative(seconds) {
    audio.currentTime = Math.max(0, Math.min(audio.duration || 0, audio.currentTime + seconds));
}

function seek(event) {
    if (!playerState.duration) return;
    const rect = document.getElementById('timeline').getBoundingClientRect();
    audio.currentTime = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)) * playerState.duration;
}

function toggleChaptersModal() {
    const container = document.getElementById('appContainer');
    setChaptersPanelOpen(!container.classList.contains('panel-open'));
}

function renderPlayerChapterRow({ idx, title, timeText = '', fillPct = 0, isActive = false, action = '', elementId = '', fillId = '', timeId = '' }) {
    const itemIdAttr = elementId ? ` id="${elementId}"` : '';
    const fillIdAttr = fillId ? ` id="${fillId}"` : '';
    const timeIdAttr = timeId ? ` id="${timeId}"` : '';
    const actionAttr = action ? ` data-player-action="${action}" data-index="${idx}"` : '';
    const activeClass = isActive ? 'active-ch' : '';
    const timeMarkup = timeText
        ? `<span class="chapter-time timecode"${timeIdAttr}>${escapeHtml(timeText)}</span>`
        : '';
    return `<div class="chapter-list-item ${activeClass}"${itemIdAttr}${actionAttr}>
        <div class="chapter-bg-fill"${fillIdAttr} style="width: ${fillPct}%"></div>
        <div class="chapter-content">
            <span class="chapter-pill timecode">${String(idx + 1).padStart(2, '0')}</span>
            <span class="chapter-main">
                <span class="chapter-name">${escapeHtml(title)}</span>
            </span>
            ${timeMarkup}
        </div>
    </div>`;
}

function renderPlayerChapters() {
    const listDiv = document.getElementById('playerChaptersList');
    const t = i18n[appState.currentLang];
    if (playerState.mode === 'zip') {
        if (!playerState.playlist.length) {
            setPanelCount(0);
            listDiv.innerHTML = renderPanelEmptyState('≡', t.noChaptersInPanel, t.noChaptersHint);
            return;
        }
        setPanelCount(playerState.playlist.length);
        listDiv.innerHTML = playerState.playlist.map((track, idx) => {
            let fillPct = 0;
            if (idx < playerState.currentTrackIndex) fillPct = 100;
            else if (idx === playerState.currentTrackIndex && audio.duration) {
                fillPct = Math.max(0, Math.min(100, (audio.currentTime / audio.duration) * 100));
            }
            return renderPlayerChapterRow({
                idx,
                title: track.title,
                fillPct,
                isActive: idx === playerState.currentTrackIndex,
                action: 'jump-track'
            });
        }).join('');
    } else {
        if (!playerState.chapters.length) {
            setPanelCount(0);
            listDiv.innerHTML = renderPanelEmptyState('≡', t.noChaptersInPanel, t.noChaptersHint);
            return;
        }
        setPanelCount(playerState.chapters.length);
        const currentChIndex = playerState.chapters.findIndex(c => audio.currentTime >= c.start && audio.currentTime < c.end);
        const safeIndex = currentChIndex !== -1 ? currentChIndex : 0;
        listDiv.innerHTML = playerState.chapters.map((ch, idx) => {
            let fillPct = 0;
            let timeText = formatTime(ch.start);
            if (idx < safeIndex) fillPct = 100;
            else if (idx === safeIndex) {
                const dur = ch.end - ch.start;
                if (dur > 0) {
                    fillPct = ((audio.currentTime - ch.start) / dur) * 100;
                    timeText = `${formatTime(Math.max(0, audio.currentTime - ch.start))} / ${formatTime(dur)}`;
                }
            }
            return renderPlayerChapterRow({
                idx,
                title: ch.title,
                timeText,
                fillPct,
                isActive: idx === safeIndex,
                action: 'seek-chapter',
                elementId: `ch-item-${idx}`,
                fillId: `ch-fill-${idx}`,
                timeId: `ch-time-${idx}`
            });
        }).join('');
    }
    setTimeout(() => {
        const activeEl = listDiv.querySelector('.active-ch');
        if (activeEl) activeEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 100);
}

function handleChapterClick(event, idx, rowEl = null) {
    const ch = playerState.chapters[idx];
    if (!ch) return;
    const targetRow = rowEl || event.currentTarget || event.target.closest('.chapter-list-item');
    if (!targetRow) return;
    const rect = targetRow.getBoundingClientRect();
    const percentage = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    audio.currentTime = ch.start + ((ch.end - ch.start) * percentage);
    if (audio.paused) void requestAudioPlayback(playerState.source === 'google_drive');
}

function jumpToTrack(index) {
    playerState.currentTrackIndex = index;
    playCurrentTrack(true);
    toggleChaptersModal();
}

function initPlayerChapterInteractions() {
    const listDiv = document.getElementById('playerChaptersList');
    if (!listDiv || listDiv.dataset.bound === 'true') {
        return;
    }
    listDiv.dataset.bound = 'true';
    listDiv.addEventListener('click', (event) => {
        const row = event.target.closest('.chapter-list-item[data-player-action]');
        if (!row || !listDiv.contains(row)) {
            return;
        }
        const idx = parseInt(row.dataset.index || '', 10);
        if (Number.isNaN(idx)) {
            return;
        }
        if (row.dataset.playerAction === 'jump-track') {
            jumpToTrack(idx);
            return;
        }
        if (row.dataset.playerAction === 'seek-chapter') {
            handleChapterClick(event, idx, row);
        }
    });
}

function playCurrentTrack(autoplay = false) {
    if (!playerState.playlist.length) return;
    const track = playerState.playlist[playerState.currentTrackIndex];
    const trackUrl = track.url || ('/api/files/' + track.file.split('/').map(p => encodeURIComponent(p)).join('/'));
    audio.src = trackUrl;
    audio.autoplay = autoplay;
    audio.load();
    if (autoplay) setPlayButtonState(true);
    const playerChapterEl = document.getElementById('playerChapter');
    if (playerChapterEl) {
        playerChapterEl.innerText = `${playerState.currentTrackIndex + 1} / ${playerState.playlist.length}: ${track.title}`;
    }
}

async function initPlayer(fileName, autoOpenChapters = false, autoPlay = false) {
    const t = i18n[appState.currentLang];
    setDriveStreamBuffering('', false, false);
    playerState.fileName = fileName;
    playerState.duration = 0;
    playerState.chapters = [];
    playerState.playlist = [];
    playerState.currentTrackIndex = 0;
    playerState.mode = 'single';
    playerState.source = 'local';
    playerState.streamUrl = null;
    playerState.bookmarkKey = 'bookmark_' + fileName;
    playerState.bookId = buildClientBookId(fileName);
    playerState.driveFileId = '';
    playerState.driveMetadataFileId = '';
    playerState.driveCoverFileId = '';
    playerState.driveResourceKey = '';
    playerState.driveMetadataResourceKey = '';
    playerState.driveCoverResourceKey = '';
    playerState.sizeBytes = 0;
    appState.showPlayer = true;
    appState.showPreview = false;
    appState.previewLoading = false;
    document.getElementById('markersContainer').innerHTML = '';
    updateUI();
    const playerTitleEl = document.getElementById('playerTitle');
    const playerChapterEl = document.getElementById('playerChapter');
    if (playerTitleEl) playerTitleEl.innerText = fileName;
    if (playerChapterEl) playerChapterEl.innerText = '';
    setPanelCount(0);
    setPlayButtonState(false);
    document.getElementById('timelineFill').style.width = '0%';
    document.getElementById('timeCurrent').innerText = formatTime(0);
    document.getElementById('timeTotal').innerText = formatTime(0);
    const chaptersListEl = document.getElementById('playerChaptersList');
    if (chaptersListEl && (document.getElementById('appContainer').classList.contains('panel-open') || autoOpenChapters)) {
        chaptersListEl.innerHTML = renderPanelLoadingState(t.chaptersLoadingTitle, t.chaptersLoadingHint, 8, true);
    }
    const coverImg = document.getElementById('playerCover');
    clearPlayerCover();
    coverImg.onload = schedulePlayerLayoutSync;
    audio.autoplay = false;
    const localFileUrl = '/api/files/' + encodeURIComponent(fileName);
    const canStartImmediately = autoPlay && !fileName.toLowerCase().endsWith('.zip');
    if (canStartImmediately) {
        audio.src = localFileUrl;
        audio.load();
        void requestAudioPlayback(false);
    }
    let savedBmk = await loadSavedBookmark(playerState.bookId, playerState.bookmarkKey);

    try {
        const res = await fetch('/api/metadata/' + encodeURIComponent(fileName) + '?t=' + Date.now());
        if (res.ok) {
            const meta = await res.json();
            if (meta.book_id) {
                playerState.bookId = meta.book_id;
                savedBmk = await loadSavedBookmark(playerState.bookId, playerState.bookmarkKey);
            }
            if (meta.title) {
                playerState.bookTitle = meta.title;
                if (playerTitleEl) {
                    playerTitleEl.innerText = meta.title;
                }
            }
            if (meta.local_cover) {
                setPlayerCover('/api/files/' + encodeURIComponent(meta.local_cover));
            } else if (meta.cover_url) {
                setPlayerCover(meta.cover_url);
            }

            if (meta.mode === 'zip' && meta.playlist) {
                playerState.mode = 'zip';
                playerState.playlist = meta.playlist;
                if (savedBmk && (savedBmk.track < 0 || savedBmk.track >= meta.playlist.length)) {
                    savedBmk = { time: 0, track: 0 };
                }
                playerState.currentTrackIndex = (savedBmk && savedBmk.track !== undefined) ? savedBmk.track : 0;
                playCurrentTrack(autoPlay);
                restoreSavedPlaybackPosition(savedBmk);
                syncChaptersPanel(autoOpenChapters);
                schedulePlayerLayoutSync();
                updateMediaSession();
                return;
            } else if (meta.chapters && meta.chapters.length > 0) {
                playerState.mode = 'm4b';
                playerState.chapters = meta.chapters;
            }
        }
    } catch (e) {
        console.log('No metadata found', e);
    }
    syncChaptersPanel(autoOpenChapters);
    schedulePlayerLayoutSync();
    if (!canStartImmediately) {
        audio.src = localFileUrl;
        audio.load();
        if (autoPlay) {
            void requestAudioPlayback(false);
        }
    }
    restoreSavedPlaybackPosition(savedBmk);
    syncSharedActivePlayback();
    updateMediaSession();
    syncMainSurfaceState();
}

async function initDrivePlayer(item, autoPlay = true, autoOpenChapters = false) {
    const t = i18n[appState.currentLang];
    playerState.fileName = item.name;
    playerState.bookTitle = item.name;
    playerState.duration = 0;
    playerState.chapters = [];
    playerState.playlist = [];
    playerState.currentTrackIndex = 0;
    playerState.mode = 'single';
    playerState.source = 'google_drive';
    playerState.streamUrl = buildGoogleDriveStreamUrl(item.drive_file_id, item.resource_key || '');
    playerState.bookmarkKey = `bookmark_drive_${item.drive_file_id}`;
    playerState.bookId = item.book_id || buildClientBookId(item.name, item.size_bytes);
    playerState.driveFileId = item.drive_file_id || '';
    playerState.driveMetadataFileId = item.drive_metadata_file_id || '';
    playerState.driveCoverFileId = item.drive_cover_file_id || '';
    playerState.driveResourceKey = item.resource_key || '';
    playerState.driveMetadataResourceKey = item.drive_metadata_resource_key || '';
    playerState.driveCoverResourceKey = item.drive_cover_resource_key || '';
    playerState.sizeBytes = Number(item.size_bytes) || 0;
    appState.showPlayer = true;
    appState.showPreview = false;
    appState.previewLoading = false;
    document.getElementById('markersContainer').innerHTML = '';
    updateUI();
    clearPlayerCover();
    setPanelCount(0);
    setPlayButtonState(false);
    document.getElementById('timelineFill').style.width = '0%';
    document.getElementById('timeCurrent').innerText = formatTime(0);
    document.getElementById('timeTotal').innerText = formatTime(0);
    const chaptersListEl = document.getElementById('playerChaptersList');
    if (chaptersListEl && (document.getElementById('appContainer').classList.contains('panel-open') || autoOpenChapters)) {
        chaptersListEl.innerHTML = renderPanelLoadingState(t.chaptersLoadingTitle, t.chaptersLoadingHint, 8, true);
    }
    if (autoPlay && playerState.streamUrl) {
        audio.autoplay = false;
        audio.src = playerState.streamUrl;
        audio.load();
        setDriveStreamBuffering(item.drive_file_id, true, true, 'connecting');
        void requestAudioPlayback(true);
    }

    let savedBmk = await loadSavedBookmark(playerState.bookId, playerState.bookmarkKey);

    try {
        const query = new URLSearchParams({
            metadata_file_id: item.drive_metadata_file_id || '',
            cover_file_id: item.drive_cover_file_id || '',
            file_name: item.name || '',
            resource_key: item.resource_key || '',
            metadata_resource_key: item.drive_metadata_resource_key || '',
            cover_resource_key: item.drive_cover_resource_key || '',
        });
        const res = await fetch(`/api/google-drive/metadata/${encodeURIComponent(item.drive_file_id)}?${query.toString()}`);
        if (res.ok) {
            const meta = await res.json();
            if (meta.book_id) {
                playerState.bookId = meta.book_id;
                savedBmk = await loadSavedBookmark(playerState.bookId, playerState.bookmarkKey);
            }
            if (meta.title) {
                playerState.bookTitle = meta.title;
            }
            if (meta.cover_url) {
                setPlayerCover(meta.cover_url);
            }
            if (meta.chapters && meta.chapters.length > 0) {
                playerState.mode = 'm4b';
                playerState.chapters = meta.chapters;
            }
        }
    } catch (e) {
        console.log('No Google Drive metadata found', e);
    }

    syncChaptersPanel(autoOpenChapters);
    schedulePlayerLayoutSync();
    if (!autoPlay) {
        audio.src = playerState.streamUrl;
        audio.autoplay = false;
        audio.load();
        setDriveStreamBuffering(item.drive_file_id, true, true, 'connecting');
    }
    restoreSavedPlaybackPosition(savedBmk);
    syncSharedActivePlayback();
    updateMediaSession();
    syncMainSurfaceState();
}

function updateMediaSession() {
    if ('mediaSession' in navigator) {
        navigator.mediaSession.metadata = new MediaMetadata({
            title: playerState.bookTitle || playerState.fileName,
            artist: 'SonicBook',
            artwork: document.getElementById('playerCover').src
                ? [{ src: document.getElementById('playerCover').src, sizes: '512x512', type: 'image/jpeg' }]
                : []
        });
        navigator.mediaSession.setActionHandler('play', togglePlay);
        navigator.mediaSession.setActionHandler('pause', togglePlay);
        navigator.mediaSession.setActionHandler('seekbackward', () => seekRelative(-15));
        navigator.mediaSession.setActionHandler('seekforward', () => seekRelative(15));
    }
}

window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT') return;
    if (e.code === 'Space') {
        e.preventDefault();
        togglePlay();
    } else if (e.code === 'ArrowLeft') {
        seekRelative(-15);
    } else if (e.code === 'ArrowRight') {
        seekRelative(15);
    }
});

initPlayerChapterInteractions();
initSleepTimer();
