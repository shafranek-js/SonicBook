function handleLibraryQuickPlay(event, fileName) {
    event.stopPropagation();
    playFromLibrary(fileName, true, true, true);
}

function handleLibraryAction(action, fileName, event) {
    if (!action || !fileName) {
        return;
    }
    if (action === 'play') {
        handleLibraryQuickPlay(event, fileName);
        return;
    }
    if (action === 'reset') {
        resetBookProgress(event, fileName);
        return;
    }
    if (action === 'chapters') {
        handleLibraryChaptersToggle(event, fileName);
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
            playFromLibrary(rowEl.dataset.file, true, true, true);
        }
    });
}

function renderLibraryItem(file, t) {
    const date = new Date(file.mtime * 1000).toLocaleDateString();
    const isActive = playerState.fileName === file.name ? 'active-lib' : '';
    const completedClass = file.isCompleted ? 'completed-book' : '';
    const safeName = escapeHtml(file.name);
    const playId = `lib-play-${file.name.replace(/\s+/g, '-')}`;
    const durationLabel = formatDurationLabel(file.durationSeconds);
    return `
        <div class="library-item ${isActive} ${completedClass}" data-file="${safeName}">
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
    const listDiv = document.getElementById('libraryList');
    const t = i18n[appState.currentLang];
    listDiv.innerHTML = renderPanelLoadingState(t.libraryLoadingTitle, t.libraryLoadingHint, 7);
    try {
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
            try {
                const saved = JSON.parse(localStorage.getItem('bookmark_' + f.name));
                if (saved && saved.time && saved.duration) {
                    if (!f.durationSeconds) {
                        f.durationSeconds = saved.duration;
                    }
                    f.fillPct = (saved.time / saved.duration) * 100;
                    if (f.fillPct >= 99.5) {
                        f.isCompleted = true;
                        f.fillPct = 100;
                    }
                }
            } catch (e) {}
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

function resetBookProgress(event, fileName) {
    event.stopPropagation();
    const t = i18n[appState.currentLang];
    if (confirm(t.confirmReset)) {
        localStorage.removeItem('bookmark_' + fileName);
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
