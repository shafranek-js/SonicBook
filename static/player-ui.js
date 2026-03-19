let playerState = {
    mode: 'single', duration: 0, chapters: [], playlist: [], currentTrackIndex: 0, fileName: null, bookTitle: "", tempCoverUrl: null
};

const audio = document.getElementById('audioElement');

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
    if (playerState.fileName) {
        localStorage.setItem('bookmark_' + playerState.fileName, JSON.stringify({
            time: audio.currentTime,
            duration: audio.duration,
            track: playerState.currentTrackIndex
        }));
    }
});

audio.addEventListener('loadedmetadata', () => {
    playerState.duration = audio.duration;
    document.getElementById('timeTotal').innerText = formatTime(audio.duration);
    if (playerState.mode === 'm4b' && playerState.chapters.length > 0) {
        document.getElementById('markersContainer').innerHTML = playerState.chapters.map(ch =>
            `<div class="timeline-marker" style="left: ${(ch.start / audio.duration) * 100}%;" title="${ch.title}"></div>`
        ).join('');
    }
    if (playerState.fileName && !audio.autoplay) {
        try {
            const saved = JSON.parse(localStorage.getItem('bookmark_' + playerState.fileName));
            if (saved && saved.time) {
                audio.currentTime = Math.max(0, Math.min(audio.duration, parseFloat(saved.time)));
            }
        } catch (e) {}
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
});

function syncLibraryPlayIcons() {
    document.querySelectorAll('.library-quick-play').forEach(el => el.innerText = '▶');
    if (!audio.paused && playerState.fileName) {
        const id = "lib-play-" + playerState.fileName.replace(/'/g, "\\'").replace(/\s+/g, '-');
        const el = document.getElementById(id);
        if (el) el.innerText = '⏸';
    }
}

function togglePlay() {
    if (audio.paused) audio.play();
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
    if (audio.paused) audio.play();
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
    audio.src = '/api/files/' + track.file.split('/').map(p => encodeURIComponent(p)).join('/');
    audio.autoplay = autoplay;
    audio.load();
    if (autoplay) setPlayButtonState(true);
    const playerChapterEl = document.getElementById('playerChapter');
    if (playerChapterEl) {
        playerChapterEl.innerText = `${playerState.currentTrackIndex + 1} / ${playerState.playlist.length}: ${track.title}`;
    }
}

async function initPlayer(fileName, autoOpenChapters = false) {
    const t = i18n[appState.currentLang];
    playerState.fileName = fileName;
    playerState.chapters = [];
    playerState.playlist = [];
    playerState.currentTrackIndex = 0;
    playerState.mode = 'single';
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
    const chaptersListEl = document.getElementById('playerChaptersList');
    if (chaptersListEl && (document.getElementById('appContainer').classList.contains('panel-open') || autoOpenChapters)) {
        chaptersListEl.innerHTML = renderPanelLoadingState(t.chaptersLoadingTitle, t.chaptersLoadingHint, 8, true);
    }
    const coverImg = document.getElementById('playerCover');
    clearPlayerCover();
    coverImg.onload = schedulePlayerLayoutSync;
    audio.autoplay = false;
    let savedBmk = null;
    try {
        const rawBmk = localStorage.getItem('bookmark_' + fileName);
        if (rawBmk && !rawBmk.startsWith('{')) savedBmk = { time: parseFloat(rawBmk), track: 0 };
        else if (rawBmk) savedBmk = JSON.parse(rawBmk);
    } catch (e) {
        localStorage.removeItem('bookmark_' + fileName);
    }

    try {
        const res = await fetch('/api/metadata/' + encodeURIComponent(fileName) + '?t=' + Date.now());
        if (res.ok) {
            const meta = await res.json();
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
                playCurrentTrack(false);
                if (savedBmk && savedBmk.time) {
                    audio.addEventListener('loadedmetadata', function onMeta() {
                        audio.currentTime = Math.max(0, Math.min(audio.duration || 0, parseFloat(savedBmk.time)));
                        audio.removeEventListener('loadedmetadata', onMeta);
                    });
                }
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
    audio.src = '/api/files/' + encodeURIComponent(fileName);
    audio.load();
    if (savedBmk && savedBmk.time) {
        audio.addEventListener('loadedmetadata', function onMeta() {
            audio.currentTime = Math.max(0, Math.min(audio.duration, parseFloat(savedBmk.time)));
            audio.removeEventListener('loadedmetadata', onMeta);
        });
    }
    updateMediaSession();
    syncMainSurfaceState();
    syncIdleState();
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
