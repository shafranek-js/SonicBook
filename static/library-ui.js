const driveImportState = new Map();
const importedDriveBookIds = new Set();
const DRIVE_IMPORT_RESET_DELAY_MS = 5000;

function getDriveImportState(fileId) {
    return driveImportState.get(fileId) || 'idle';
}

function setDriveImportState(fileId, state) {
    if (!fileId) {
        return;
    }
    if (!state || state === 'idle') {
        driveImportState.delete(fileId);
        return;
    }
    driveImportState.set(fileId, state);
}

function scheduleDriveImportReset(fileId) {
    if (!fileId) {
        return;
    }
    window.setTimeout(() => {
        const row = document.querySelector(`.drive-library-item[data-drive-file-id="${CSS.escape(fileId)}"]`);
        const bookId = row?.dataset.bookId || '';
        if (bookId && importedDriveBookIds.has(bookId)) {
            syncDriveImportRow(fileId);
            return;
        }
        if (getDriveImportState(fileId) !== 'imported') {
            return;
        }
        setDriveImportState(fileId, 'idle');
        syncDriveImportRow(fileId);
    }, DRIVE_IMPORT_RESET_DELAY_MS);
}

function syncDriveImportRow(fileId) {
    if (!fileId) {
        return;
    }
    const row = document.querySelector(`.drive-library-item[data-drive-file-id="${CSS.escape(fileId)}"]`);
    if (!row) {
        return;
    }
    const button = row.querySelector('[data-library-action="import"]');
    if (!button) {
        return;
    }
    const t = i18n[appState.currentLang];
    const importState = getDriveImportState(fileId);
    const isImporting = importState === 'importing';
    const isPersistedImported = !!row.dataset.bookId && importedDriveBookIds.has(row.dataset.bookId);
    const isImported = isPersistedImported || importState === 'imported';
    row.classList.toggle('is-importing', isImporting);
    row.classList.toggle('is-imported', isImported);
    button.disabled = isImporting || isPersistedImported;
    button.classList.toggle('is-busy', isImporting);
    button.classList.toggle('is-done', isImported);
    button.setAttribute('aria-busy', isImporting ? 'true' : 'false');
    button.textContent = isImporting
        ? (t.googleDriveImportingShort || t.googleDriveImporting)
        : isImported
            ? (t.googleDriveImportedShort || t.googleDriveImport)
            : t.googleDriveImport;
    button.title = isImporting
        ? t.googleDriveImporting
        : isImported
            ? t.googleDriveImported
            : t.googleDriveImport;
}

async function loadImportedDriveBookIds() {
    importedDriveBookIds.clear();
    const res = await fetch('/api/library/imported-book-ids');
    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.detail || 'library-import-state');
    }
    (data.book_ids || []).forEach((bookId) => {
        if (bookId) {
            importedDriveBookIds.add(bookId);
        }
    });
}

function getLegacyBookmark(legacyKey) {
    if (!legacyKey) {
        return null;
    }
    try {
        return JSON.parse(localStorage.getItem(legacyKey));
    } catch (e) {
        return null;
    }
}

function applyBookmarkToLibraryItem(file, bookmark, fallbackDuration = 0) {
    file.fillPct = 0;
    file.isCompleted = false;
    if (!bookmark || !bookmark.time || !bookmark.duration) {
        return;
    }
    if (!file.durationSeconds && (bookmark.duration || fallbackDuration)) {
        file.durationSeconds = bookmark.duration || fallbackDuration;
    }
    file.fillPct = (bookmark.time / bookmark.duration) * 100;
    if (file.fillPct >= 99.5) {
        file.isCompleted = true;
        file.fillPct = 100;
    }
}

function handleLibraryQuickPlay(event, fileName) {
    event.stopPropagation();
    playFromLibrary(fileName, true, true, true);
}

function handleLibraryAction(action, fileName, event) {
    if (!action || !fileName) {
        return;
    }
    if (action === 'play') {
        const row = event.target.closest('.library-item');
        if (row?.dataset.source === 'google_drive') {
            playDriveLibraryItem(row, true);
            return;
        }
        handleLibraryQuickPlay(event, fileName);
        return;
    }
    if (action === 'reset') {
        resetBookProgress(event, fileName);
        return;
    }
    if (action === 'chapters') {
        handleLibraryChaptersToggle(event, fileName);
        return;
    }
    if (action === 'import') {
        importDriveBook(event, fileName);
    }
}

function initLibraryInteractions() {
    const listDiv = document.getElementById('libraryList');
    if (!listDiv || listDiv.dataset.bound === 'true') {
        return;
    }
    listDiv.dataset.bound = 'true';
    listDiv.addEventListener('click', (event) => {
        const actionEl = event.target.closest('[data-library-action]');
        if (actionEl) {
            handleLibraryAction(actionEl.dataset.libraryAction, actionEl.dataset.file, event);
            return;
        }

        const rowEl = event.target.closest('.library-item[data-file]');
        if (rowEl) {
            if (rowEl.dataset.source === 'google_drive') {
                return;
            }
            playFromLibrary(rowEl.dataset.file, true, true, true);
        }
    });
}

function renderLibraryItem(file, t) {
    if (file.source === 'google_drive') {
        return renderDriveLibraryItem(file, t);
    }
    const date = new Date(file.mtime * 1000).toLocaleDateString();
    const isActive = playerState.fileName === file.name ? 'active-lib' : '';
    const completedClass = file.isCompleted ? 'completed-book' : '';
    const safeName = escapeHtml(file.name);
    const playId = buildLibraryPlayButtonId('local', file.name);
    const durationLabel = formatDurationLabel(file.durationSeconds);
    return `
        <div class="library-item ${isActive} ${completedClass}" data-file="${safeName}" data-book-id="${escapeHtml(file.book_id || '')}">
            <div class="library-bg-fill" style="width: ${file.fillPct}%;"></div>
            <div class="library-item-info">
                <div class="library-item-title">${escapeHtml(file.name)}</div>
                <div class="library-item-meta">
                    ${durationLabel ? `<span class="library-meta-pill timecode">${durationLabel}</span>` : ''}
                    ${file.chapterCount ? `<span class="library-meta-pill timecode">${file.chapterCount} ${t.chapterCountShort}</span>` : ''}
                    <span class="library-meta-pill timecode">${file.size_mb} MB</span>
                    <span class="library-meta-pill timecode">${date}</span>
                    ${file.has_meta ? `<button class="library-meta-pill library-meta-flag" type="button" data-library-action="chapters" data-file="${safeName}" title="${escapeHtml(t.chaptersTooltip)}" aria-label="${escapeHtml(t.chaptersTooltip)}">📑</button>` : ''}
                </div>
            </div>
            <div class="library-item-actions">
                <button class="library-quick-btn library-quick-play" id="${playId}"
                        type="button"
                        data-library-action="play"
                        data-file="${safeName}"
                        title="Play / Pause">▶</button>
                <button class="library-quick-btn"
                        type="button"
                        data-library-action="reset"
                        data-file="${safeName}"
                        title="${escapeHtml(t.resetTooltip)}">↺</button>
            </div>
        </div>
    `;
}

function renderDriveLibraryItem(file, t) {
    const date = file.mtime ? new Date(file.mtime * 1000).toLocaleDateString() : '';
    const safeName = escapeHtml(file.name);
    const durationLabel = formatDurationLabel(file.durationSeconds);
    const playId = buildLibraryPlayButtonId('google_drive', file.drive_file_id);
    const isActive = playerState.source === 'google_drive' && playerState.streamUrl?.includes(`/${file.drive_file_id}/stream`) ? 'active-lib' : '';
    const completedClass = file.isCompleted ? 'completed-book' : '';
    const importState = getDriveImportState(file.drive_file_id);
    const isImporting = importState === 'importing';
    const isPersistedImported = !!file.book_id && importedDriveBookIds.has(file.book_id);
    const isImported = isPersistedImported || importState === 'imported';
    const importLabel = isImporting
        ? (t.googleDriveImportingShort || t.googleDriveImporting)
        : isImported
            ? (t.googleDriveImportedShort || t.googleDriveImport)
            : t.googleDriveImport;
    return `
        <div class="library-item drive-library-item ${isActive} ${completedClass} ${isImporting ? 'is-importing' : ''} ${isImported ? 'is-imported' : ''}"
             data-file="${safeName}"
             data-source="google_drive"
             data-drive-file-id="${escapeHtml(file.drive_file_id || '')}"
             data-book-id="${escapeHtml(file.book_id || '')}"
             data-metadata-file-id="${escapeHtml(file.drive_metadata_file_id || '')}"
             data-cover-file-id="${escapeHtml(file.drive_cover_file_id || '')}">
            <div class="library-bg-fill" style="width: ${file.fillPct || 0}%;"></div>
            <div class="library-item-info">
                <div class="library-item-title">${escapeHtml(file.name)}</div>
                <div class="library-item-meta">
                    ${durationLabel ? `<span class="library-meta-pill timecode">${durationLabel}</span>` : ''}
                    ${file.chapterCount ? `<span class="library-meta-pill timecode">${file.chapterCount} ${t.chapterCountShort}</span>` : ''}
                    <span class="library-meta-pill timecode">${file.size_mb} MB</span>
                    ${date ? `<span class="library-meta-pill timecode">${date}</span>` : ''}
                </div>
            </div>
            <div class="library-item-actions">
                ${file.streamable ? `<button class="library-quick-btn library-quick-stream" id="${playId}"
                        type="button"
                        data-library-action="play"
                        data-file="${safeName}"
                        title="${escapeHtml(t.googleDriveStreamTooltip || t.googleDriveStream)}">${escapeHtml(t.googleDriveStream)}</button>` : ''}
                <button class="library-quick-btn"
                        type="button"
                        data-library-action="reset"
                        data-file="${safeName}"
                        title="${escapeHtml(t.resetTooltip)}">↺</button>
                <button class="library-quick-btn library-quick-import ${isImporting ? 'is-busy' : ''} ${isImported ? 'is-done' : ''}"
                        type="button"
                        data-library-action="import"
                        data-file="${safeName}"
                        aria-busy="${isImporting ? 'true' : 'false'}"
                        ${isImporting || isPersistedImported ? 'disabled' : ''}
                        title="${escapeHtml(isImporting ? t.googleDriveImporting : isImported ? t.googleDriveImported : t.googleDriveImport)}">${escapeHtml(importLabel)}</button>
            </div>
        </div>
    `;
}

function renderLibraryGroup(title, files, t) {
    if (!files.length) {
        return '';
    }
    return `
        <section class="library-group">
            <div class="library-group-title">
                <span>${title}</span>
                <span class="library-group-count timecode">${files.length}</span>
            </div>
            <div class="library-group-items">
                ${files.map(file => renderLibraryItem(file, t)).join('')}
            </div>
        </section>
    `;
}

async function loadLibrary() {
    if (appState.librarySource === 'google_drive') {
        await loadGoogleDriveLibrary();
        return;
    }
    const listDiv = document.getElementById('libraryList');
    const t = i18n[appState.currentLang];
    listDiv.innerHTML = renderPanelLoadingState(t.libraryLoadingTitle, t.libraryLoadingHint, 7);
    try {
        await loadBookmarkSummary();
        const res = await fetch('/api/library');
        const data = await res.json();
        if (data.files.length === 0) {
            setLibraryCount(0);
            listDiv.innerHTML = renderPanelEmptyState('◦', t.libEmpty, t.libEmptyHint);
            return;
        }
        setLibraryCount(data.files.length);
        data.files.forEach(f => {
            f.fillPct = 0;
            f.isCompleted = false;
            if (typeof f.duration_seconds === 'number') {
                f.durationSeconds = f.duration_seconds;
            }
            if (typeof f.chapter_count === 'number') {
                f.chapterCount = f.chapter_count;
            }
            const saved = getCachedBookmark(f.book_id)
                || getCachedBookmark(buildClientBookId(f.name))
                || getCachedBookmark(buildLegacyClientBookId(f.name))
                || getLegacyBookmark('bookmark_' + f.name);
            applyBookmarkToLibraryItem(f, saved, f.durationSeconds || 0);
        });
        const sortByRecent = (a, b) => b.mtime - a.mtime;
        const nowListening = data.files
            .filter(f => !f.isCompleted && (playerState.fileName === f.name || f.fillPct > 0))
            .sort((a, b) => {
                if (playerState.fileName === a.name) return -1;
                if (playerState.fileName === b.name) return 1;
                return sortByRecent(a, b);
            });
        const inQueue = data.files
            .filter(f => !f.isCompleted && f.fillPct === 0 && playerState.fileName !== f.name)
            .sort(sortByRecent);
        const completed = data.files
            .filter(f => f.isCompleted)
            .sort(sortByRecent);
        listDiv.innerHTML =
            renderLibraryGroup(t.groupNowListening, nowListening, t) +
            renderLibraryGroup(t.groupQueue, inQueue, t) +
            renderLibraryGroup(t.groupCompleted, completed, t);
        syncLibraryPlayIcons();
    } catch (e) {
        setLibraryCount(0);
        listDiv.innerHTML = renderPanelEmptyState('!', t.libLoadError, t.libLoadErrorHint, 'error');
    }
}

async function loadGoogleDriveLibrary(forceRefresh = false) {
    const listDiv = document.getElementById('libraryList');
    const t = i18n[appState.currentLang];
    listDiv.innerHTML = renderPanelLoadingState(t.googleDriveLibraryTitle, t.googleDriveLibraryHint, 5, true);
    appState.googleDrive.refreshingLibrary = true;
    syncLibrarySourceUI();
    try {
        await loadBookmarkSummary();
        await loadImportedDriveBookIds();
        const suffix = forceRefresh ? '?refresh=1' : '';
        const res = await fetch(`/api/google-drive/library${suffix}`);
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'google-drive-library');
        }
        if (!Array.isArray(data.files) || data.files.length === 0) {
            setLibraryCount(0);
            listDiv.innerHTML = renderPanelEmptyState('☁', t.googleDriveLibraryEmpty, t.googleDriveLibraryHint);
            return;
        }
        setLibraryCount(data.files.length);
        data.files.forEach(f => {
            f.fillPct = 0;
            f.isCompleted = false;
            if (typeof f.duration_seconds === 'number') {
                f.durationSeconds = f.duration_seconds;
            }
            if (typeof f.chapter_count === 'number') {
                f.chapterCount = f.chapter_count;
            }
            const saved = getCachedBookmark(f.book_id)
                || getCachedBookmark(buildClientBookId(f.name))
                || getCachedBookmark(buildLegacyClientBookId(f.name))
                || getLegacyBookmark(`bookmark_drive_${f.drive_file_id}`);
            applyBookmarkToLibraryItem(f, saved, f.durationSeconds || 0);
        });
        const sortByRecent = (a, b) => (b.mtime || 0) - (a.mtime || 0);
        const nowListening = data.files
            .filter(f => !f.isCompleted && (
                (playerState.source === 'google_drive' && playerState.streamUrl?.includes(`/${f.drive_file_id}/stream`)) ||
                f.fillPct > 0
            ))
            .sort((a, b) => {
                const aIsCurrent = playerState.source === 'google_drive' && playerState.streamUrl?.includes(`/${a.drive_file_id}/stream`);
                const bIsCurrent = playerState.source === 'google_drive' && playerState.streamUrl?.includes(`/${b.drive_file_id}/stream`);
                if (aIsCurrent) return -1;
                if (bIsCurrent) return 1;
                return sortByRecent(a, b);
            });
        const inQueue = data.files
            .filter(f => !f.isCompleted && f.fillPct === 0 && !(playerState.source === 'google_drive' && playerState.streamUrl?.includes(`/${f.drive_file_id}/stream`)))
            .sort(sortByRecent);
        const completed = data.files
            .filter(f => f.isCompleted)
            .sort(sortByRecent);
        listDiv.innerHTML =
            renderLibraryGroup(t.groupNowListening, nowListening, t) +
            renderLibraryGroup(t.groupQueue, inQueue, t) +
            renderLibraryGroup(t.groupCompleted, completed, t);
        syncLibraryPlayIcons();
    } catch (e) {
        setLibraryCount(0);
        listDiv.innerHTML = renderPanelEmptyState('!', t.googleDriveLibraryError, t.googleDriveLibraryErrorHint, 'error');
    } finally {
        appState.googleDrive.refreshingLibrary = false;
        syncLibrarySourceUI();
    }
}

async function importDriveBook(event, fileName) {
    event.stopPropagation();
    const t = i18n[appState.currentLang];
    const row = event.target.closest('.library-item');
    if (!row) {
        return;
    }
    const metadataFileId = row.dataset.metadataFileId || '';
    const coverFileId = row.dataset.coverFileId || '';
    const driveFileId = row.dataset.driveFileId || '';
    if (!driveFileId) {
        setStatusMessage(t.googleDriveLibraryError, 'error');
        return;
    }
    if (getDriveImportState(driveFileId) === 'importing') {
        return;
    }

    setDriveImportState(driveFileId, 'importing');
    syncDriveImportRow(driveFileId);
    setStatusMessage(t.googleDriveImporting, 'info');
    try {
        const res = await fetch('/api/google-drive/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_id: driveFileId,
                metadata_file_id: metadataFileId,
                cover_file_id: coverFileId
            })
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'google-drive-import');
        }
        const bookId = row.dataset.bookId || buildClientBookId(data.file_name || fileName);
        if (bookId) {
            importedDriveBookIds.add(bookId);
        }
        setDriveImportState(driveFileId, 'imported');
        syncDriveImportRow(driveFileId);
        scheduleDriveImportReset(driveFileId);
        setStatusMessage(`${t.googleDriveImported} ${data.file_name}`, 'success');
    } catch (e) {
        setDriveImportState(driveFileId, 'idle');
        syncDriveImportRow(driveFileId);
        setStatusMessage(String(e.message || e), 'error');
    }
}

function buildDriveItemFromRow(row) {
    if (!row) {
        return null;
    }
    return {
        name: row.dataset.file || '',
        book_id: row.dataset.bookId || '',
        drive_file_id: row.dataset.driveFileId || '',
        drive_metadata_file_id: row.dataset.metadataFileId || '',
        drive_cover_file_id: row.dataset.coverFileId || '',
        source: 'google_drive',
        streamable: true
    };
}

function playDriveLibraryItem(row, autoPlay = true) {
    const item = buildDriveItemFromRow(row);
    if (!item || !item.drive_file_id) {
        return;
    }
    const currentDriveFileId = getCurrentDriveStreamFileId();
    const isCurrentDriveBook = playerState.source === 'google_drive' && currentDriveFileId === item.drive_file_id;

    if (isCurrentDriveBook) {
        if (appState.driveStreamBufferingFileId === item.drive_file_id) {
            audio.pause();
            audio.removeAttribute('src');
            audio.load();
            setDriveStreamBuffering('', false, false);
            setPlayButtonState(false);
            clearStatusMessage();
            syncLibraryPlayIcons();
            return;
        }
        if (!audio.paused) {
            audio.pause();
            return;
        }
        audio.play().catch(() => {
            setStatusMessage(i18n[appState.currentLang].googleDriveStreamError, 'error');
        });
        return;
    }

    setDriveStreamBuffering(item.drive_file_id, true, true);
    resetForm();
    appState.step = 'done';
    appState.mainButtonLabelOverride = '';
    initDrivePlayer(item, autoPlay, true);
}

async function resetBookProgress(event, fileName) {
    event.stopPropagation();
    const t = i18n[appState.currentLang];
    if (confirm(t.confirmReset)) {
        const row = event.target.closest('.library-item');
        const isDrive = row?.dataset.source === 'google_drive';
        localStorage.removeItem('bookmark_' + fileName);
        if (isDrive && row?.dataset.driveFileId) {
            localStorage.removeItem(`bookmark_drive_${row.dataset.driveFileId}`);
        }
        const bookId = row?.dataset.bookId || buildClientBookId(fileName);
        if (bookId) {
            delete appState.bookmarks[bookId];
            delete appState.bookmarks[buildLegacyClientBookId(fileName)];
            delete appState.bookmarks[buildClientBookId(fileName)];
            try {
                await fetch(`/api/bookmarks/${encodeURIComponent(bookId)}`, { method: 'DELETE' });
            } catch (e) {}
        }
        if (playerState.fileName === fileName) {
            audio.currentTime = 0;
            document.getElementById('timelineFill').style.width = '0%';
        }
        loadLibrary();
    }
}

function filterLibrary() {
    const input = document.getElementById('libSearchInput');
    const filter = input.value.toLowerCase();
    const listDiv = document.getElementById('libraryList');
    const items = listDiv.getElementsByClassName('library-item');
    for (let i = 0; i < items.length; i++) {
        const titleEl = items[i].querySelector('.library-item-title');
        if (titleEl) {
            const txtValue = titleEl.textContent || titleEl.innerText;
            items[i].style.display = txtValue.toLowerCase().indexOf(filter) > -1 ? "" : "none";
        }
    }
    listDiv.querySelectorAll('.library-group').forEach(group => {
        const hasVisibleItems = Array.from(group.querySelectorAll('.library-item')).some(item => item.style.display !== 'none');
        group.style.display = hasVisibleItems ? '' : 'none';
    });
}
