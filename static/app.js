const i18n = {
    en: {
        placeholder: "Paste link here...",
        btnStart: "Start Download", btnFetch: "Fetch Info", btnConfirm: "Confirm & Download", btnAgain: "Download Another",
        statusInit: "Initializing...", statusStreams: "Downloading...", statusMerging: "Finalizing & Metadata...",
        statusDone: "Ready!", found: "Chapters found:", noChapters: "No chapters found. Will download as single file.",
        modeSingle: "Single File", modeM4B: "M4B (Chapters)", modeZIP: "ZIP (Split)",
        saveTo: "Save to:", changeBtn: "Change", libTitle: "My Library", libEmpty: "Your library is empty.",
        tocTitle: "Table of Contents", noChaptersInPanel: "No chapters available for this book.",
        loadingDialog: "Loading dialog...", assemblingStatus: "⚙️ Assembling M4B... Please wait",
        libTooltip: "Library", themeTooltip: "Theme", langTooltip: "Language",
        resetTooltip: "Reset playback progress",
        confirmReset: "Are you sure you want to reset progress for this book?"
    },
    ru: {
        placeholder: "Вставьте ссылку...",
        btnStart: "Начать загрузку", btnFetch: "Найти главы", btnConfirm: "Подтвердить и скачать", btnAgain: "Загрузить еще одну",
        statusInit: "Инициализация...", statusStreams: "Загрузка...", statusMerging: "Сборка и метаданные...",
        statusDone: "Готово!", found: "Найденные главы:", noChapters: "Главы не найдены. Будет скачано одним файлом.",
        modeSingle: "Одним файлом", modeM4B: "M4B (Главы)", modeZIP: "ZIP (Нарезка)",
        saveTo: "Сохранять в:", changeBtn: "Изменить", libTitle: "Моя Библиотека", libEmpty: "Библиотека пуста.",
        tocTitle: "Оглавление", noChaptersInPanel: "Для этой книги нет списка глав.",
        loadingDialog: "Открытие окна...", assemblingStatus: "⚙️ Сборка M4B... Пожалуйста, подождите",
        libTooltip: "Библиотека", themeTooltip: "Тема", langTooltip: "Язык",
        resetTooltip: "Сбросить прогресс прослушивания",
        confirmReset: "Вы уверены, что хотите сбросить прогресс для этой книги?"
    }
};

let currentLang = localStorage.getItem('lang') || 'en';
let currentMode = localStorage.getItem('mode') || 'm4b';
let step = 'start';
let playerLayoutFrame = null;

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function schedulePlayerLayoutSync() {
    if (playerLayoutFrame !== null) {
        cancelAnimationFrame(playerLayoutFrame);
    }
    playerLayoutFrame = requestAnimationFrame(() => {
        playerLayoutFrame = requestAnimationFrame(() => {
            playerLayoutFrame = null;
            syncPlayerCoverLayout();
        });
    });
}

function syncPlayerCoverLayout() {
    const mainCard = document.querySelector('.main-card');
    const coverFrame = document.getElementById('playerCoverFrame');
    const coverImg = document.getElementById('playerCover');
    if (!mainCard || !coverFrame || !coverImg || coverFrame.style.display === 'none' || coverImg.style.display === 'none' || !coverImg.src) {
        return;
    }

    coverImg.style.maxHeight = 'none';

    const overflow = mainCard.scrollHeight - mainCard.clientHeight;
    if (overflow <= 0) {
        return;
    }

    const currentHeight = coverImg.getBoundingClientRect().height;
    if (currentHeight <= 0) {
        return;
    }

    const targetHeight = Math.max(120, Math.floor(currentHeight - overflow - 4));
    coverImg.style.maxHeight = `${targetHeight}px`;
}

function clearPlayerCover() {
    const coverFrame = document.getElementById('playerCoverFrame');
    const coverBg = document.getElementById('playerCoverBg');
    const coverImg = document.getElementById('playerCover');
    if (!coverFrame || !coverBg || !coverImg) {
        return;
    }
    coverFrame.style.display = 'none';
    coverFrame.classList.remove('is-playing', 'is-paused');
    coverFrame.setAttribute('title', 'Play / Pause');
    coverBg.style.backgroundImage = '';
    coverImg.style.display = 'none';
    coverImg.style.maxHeight = 'none';
    coverImg.removeAttribute('src');
}

function setPlayerCover(src) {
    const coverFrame = document.getElementById('playerCoverFrame');
    const coverBg = document.getElementById('playerCoverBg');
    const coverImg = document.getElementById('playerCover');
    if (!coverFrame || !coverBg || !coverImg || !src) {
        return;
    }
    coverBg.style.backgroundImage = `url("${src.replace(/"/g, '\\"')}")`;
    coverFrame.style.display = 'block';
    coverFrame.classList.add('is-paused');
    coverImg.style.display = 'block';
    coverImg.style.maxHeight = 'none';
    coverImg.src = src;
    schedulePlayerLayoutSync();
}

function setPlayButtonState(isPlaying) {
    const playBtn = document.getElementById('playBtn');
    const playBtnIcon = document.getElementById('playBtnIcon');
    const coverFrame = document.getElementById('playerCoverFrame');
    const coverOverlayIcon = document.getElementById('playerCoverOverlayIcon');
    if (!playBtn || !playBtnIcon) {
        return;
    }
    playBtnIcon.className = `player-icon ${isPlaying ? 'player-icon-pause' : 'player-icon-play'}`;
    playBtn.setAttribute('aria-label', isPlaying ? 'Pause' : 'Play');
    playBtn.setAttribute('title', isPlaying ? 'Pause' : 'Play');
    if (coverOverlayIcon) {
        coverOverlayIcon.className = `player-cover-overlay-icon player-icon ${isPlaying ? 'player-icon-pause' : 'player-icon-play'}`;
    }
    if (coverFrame) {
        coverFrame.classList.toggle('is-playing', isPlaying);
        coverFrame.classList.toggle('is-paused', !isPlaying);
        coverFrame.setAttribute('title', isPlaying ? 'Pause' : 'Play');
    }
}

// Load custom widths
const savedLibWidth = localStorage.getItem('lib-width');
const savedChapWidth = localStorage.getItem('chap-width');
const savedMainWidth = localStorage.getItem('main-width');
if (savedLibWidth) document.documentElement.style.setProperty('--lib-width', savedLibWidth + 'px');
if (savedChapWidth) document.documentElement.style.setProperty('--chap-width', savedChapWidth + 'px');
if (savedMainWidth) document.documentElement.style.setProperty('--main-width', savedMainWidth + 'px');

function setMode(mode) {
    currentMode = mode;
    localStorage.setItem('mode', mode);
    ['m4b', 'mp3', 'zip'].forEach(m => document.getElementById('mode-'+m).classList.toggle('active', m === mode));
    updateUI();
}

// Panel Resizing Logic
let isResizing = false;
let resizeEdge = null;
let startX = 0;
let startMainW = 0;
let startSideW = 0;

function initResize(e, edge) {
    e.preventDefault();
    isResizing = true;
    resizeEdge = edge;
    startX = e.clientX;
    
    const root = document.documentElement;
    startMainW = parseInt(getComputedStyle(root).getPropertyValue('--main-width')) || 450;
    
    if (edge === 'main-left' || edge === 'library') {
        resizeEdge = 'library'; // Boundary between Lib and Main
        startSideW = parseInt(getComputedStyle(root).getPropertyValue('--lib-width')) || 450;
    } else if (edge === 'main-right' || edge === 'chapters') {
        resizeEdge = 'chapters'; // Boundary between Main and Chapters
        startSideW = parseInt(getComputedStyle(root).getPropertyValue('--chap-width')) || 350;
    }
    
    document.body.classList.add('is-resizing');
    document.addEventListener('mousemove', handleResize);
    document.addEventListener('mouseup', stopResize);
}

function handleResize(e) {
    if (!isResizing) return;
    const delta = e.clientX - startX;
    const root = document.documentElement;
    const container = document.getElementById('appContainer');
    
    if (resizeEdge === 'library') {
        let newMainW = startMainW - delta;
        newMainW = Math.max(350, newMainW);
        root.style.setProperty('--main-width', newMainW + 'px');
        
        if (container.classList.contains('library-open')) {
            let newLibW = startSideW + delta;
            newLibW = Math.max(250, newLibW);
            root.style.setProperty('--lib-width', newLibW + 'px');
        }
    } else if (resizeEdge === 'chapters') {
        let newMainW = startMainW + delta;
        newMainW = Math.max(350, newMainW);
        root.style.setProperty('--main-width', newMainW + 'px');
        
        if (container.classList.contains('panel-open')) {
            let newChapW = startSideW - delta;
            newChapW = Math.max(250, newChapW);
            root.style.setProperty('--chap-width', newChapW + 'px');
        }
    }
}

function stopResize() {
    if (!isResizing) return;
    isResizing = false;
    document.body.classList.remove('is-resizing');
    document.removeEventListener('mousemove', handleResize);
    document.removeEventListener('mouseup', stopResize);
    
    const root = document.documentElement;
    localStorage.setItem('main-width', parseInt(getComputedStyle(root).getPropertyValue('--main-width')));
    localStorage.setItem('lib-width', parseInt(getComputedStyle(root).getPropertyValue('--lib-width')));
    localStorage.setItem('chap-width', parseInt(getComputedStyle(root).getPropertyValue('--chap-width')));
    resizeEdge = null;
    schedulePlayerLayoutSync();
}

function updateUI() {
    const t = i18n[currentLang];
    document.getElementById('urlInput').placeholder = t.placeholder;
    document.getElementById('mode-m4b').innerText = t.modeM4B;
    document.getElementById('mode-mp3').innerText = t.modeSingle;
    document.getElementById('mode-zip').innerText = t.modeZIP;
    document.getElementById('langBtn').innerText = currentLang === 'en' ? 'RU' : 'EN';
    document.getElementById('t-found').innerText = t.found;
    document.getElementById('t-save-path').innerText = t.saveTo;
    document.getElementById('btn-change-folder').innerText = t.changeBtn;
    document.getElementById('t-lib-title').innerText = t.libTitle;
    document.getElementById('t-panel-title').innerText = t.tocTitle;
    document.getElementById('btn-player-chapters').innerText = '📑 ' + (currentLang === 'en' ? 'Chapters' : 'Главы');
    
    document.getElementById('libBtn').title = t.libTooltip;
    document.getElementById('themeBtn').title = t.themeTooltip;
    document.getElementById('langBtn').title = t.langTooltip;
    document.getElementById('resetAllBtn').title = "Clear all app data & cache";

    const btn = document.getElementById('mainBtn');
    if (step === 'start') btn.innerText = (currentMode === 'm4b' || currentMode === 'zip') ? t.btnFetch : t.btnStart;
    else if (step === 'confirm') btn.innerText = t.btnConfirm;
    else if (step === 'done') btn.innerText = t.btnAgain;
}

function toggleLang() { currentLang = currentLang === 'en' ? 'ru' : 'en'; localStorage.setItem('lang', currentLang); updateUI(); }
function toggleTheme() {
    const isLight = document.body.classList.toggle('light-theme');
    document.getElementById('themeBtn').innerText = isLight ? '☀️' : '🌙';
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
}

function resetAllData() {
    if(confirm("This will clear all your bookmarks and settings. Continue?")) {
        localStorage.clear();
        location.reload();
    }
}

// Init logic
window.addEventListener('DOMContentLoaded', () => {
    setPlayButtonState(false);
    if (localStorage.getItem('theme') === 'light') {
        document.body.classList.add('light-theme');
        document.getElementById('themeBtn').innerText = '☀️';
    }
    setMode(currentMode);
    if (localStorage.getItem('library-open') === 'true') {
        document.getElementById('appContainer').classList.add('library-open');
        loadLibrary();
    }
    if (localStorage.getItem('panel-open') === 'true') {
        document.getElementById('appContainer').classList.add('panel-open');
    }
    const lastFile = localStorage.getItem('last-played-file');
    if (lastFile) {
        playFromLibrary(lastFile, false, true, false);
    }
    updateUI();
    schedulePlayerLayoutSync();
});

window.addEventListener('resize', schedulePlayerLayoutSync);

async function initFolder() {
    try {
        const res = await fetch('/api/settings/folder');
        const data = await res.json();
        document.getElementById('currentPath').innerText = data.folder;
        document.getElementById('currentPath').title = data.folder;
    } catch(e) {}
}
initFolder();

async function chooseFolder() {
    try {
        document.getElementById('currentPath').innerText = "Loading dialog...";
        const res = await fetch('/api/settings/choose_folder', {method: 'POST'});
        const data = await res.json();
        document.getElementById('currentPath').innerText = data.folder;
        document.getElementById('currentPath').title = data.folder;
    } catch(e) {
        initFolder();
    }
}

function getValidatedBookUrl() {
    const url = document.getElementById('urlInput').value.trim();
    if (!/^https?:\/\/\S+$/i.test(url)) {
        const statusDiv = document.getElementById('status');
        statusDiv.style.display = 'block';
        statusDiv.style.color = 'var(--error)';
        statusDiv.innerText = 'Please enter a valid http(s) URL';
        return null;
    }
    return url;
}

async function handleAction() {
    if (step === 'start') {
        if (currentMode === 'm4b' || currentMode === 'zip') {
            await fetchInfo();
        } else {
            await startDownload();
        }
    } else if (step === 'confirm') {
        await startDownload();
    } else if (step === 'done') {
        resetForm();
    }
}

function resetForm() {
    document.getElementById('urlInput').value = '';
    document.getElementById('pbox').style.display = 'none';
    document.getElementById('status').style.display = 'none';
    document.getElementById('optGroup').style.display = 'flex';
    document.getElementById('playerBox').style.display = 'none';
    clearPlayerCover();
    document.getElementById('appContainer').classList.remove('panel-open');
    localStorage.setItem('panel-open', 'false');
    localStorage.removeItem('last-played-file');
    if (!audio.paused) {
        audio.pause();
    }
    setPlayButtonState(false);
    step = 'start';
    updateUI();
}

function toggleLibrary() {
    const container = document.getElementById('appContainer');
    const isOpen = container.classList.toggle('library-open');
    localStorage.setItem('library-open', isOpen);
    if (isOpen) loadLibrary();
    schedulePlayerLayoutSync();
}

async function loadLibrary() {
    const listDiv = document.getElementById('libraryList');
    const t = i18n[currentLang];
    listDiv.innerHTML = `<div class="empty-lib">${t.statusInit}</div>`;
    try {
        const res = await fetch('/api/library');
        const data = await res.json();
        if (data.files.length === 0) {
            listDiv.innerHTML = `<div class="empty-lib">${t.libEmpty}</div>`;
            return;
        }
        data.files.forEach(f => {
            f.fillPct = 0;
            f.isCompleted = false;
            try {
                const saved = JSON.parse(localStorage.getItem('bookmark_' + f.name));
                if (saved && saved.time && saved.duration) {
                    f.fillPct = (saved.time / saved.duration) * 100;
                    if (f.fillPct >= 99.5) {
                        f.isCompleted = true;
                        f.fillPct = 100;
                    }
                }
            } catch(e) {}
        });
        data.files.sort((a, b) => {
            if (a.isCompleted === b.isCompleted) return b.mtime - a.mtime;
            return a.isCompleted ? 1 : -1;
        });
        listDiv.innerHTML = data.files.map(f => {
            const date = new Date(f.mtime * 1000).toLocaleDateString();
            const isActive = playerState.fileName === f.name ? 'active-lib' : '';
            const completedClass = f.isCompleted ? 'completed-book' : '';
            return `
                <div class="library-item ${isActive} ${completedClass}" onclick="playFromLibrary('${f.name.replace(/'/g, "\\'")}', true, true, true)">
                    <div class="library-bg-fill" style="width: ${f.fillPct}%;"></div>
                    <div class="library-item-info">
                        <div class="library-item-title">${f.name}</div>
                        <div class="library-item-meta">${f.size_mb} MB • ${date} ${f.has_meta ? '• 📑' : ''}</div>
                    </div>
                    <div style="display: flex; gap: 10px; align-items: center; position: relative; z-index: 1;">
                        <button class="btn-icon" style="width: 30px; height: 30px; font-size: 0.8rem;" 
                                onclick="resetBookProgress(event, '${f.name.replace(/'/g, "\\'")}')" 
                                title="${t.resetTooltip}">↺</button>
                        <div class="library-item-play" id="lib-play-${f.name.replace(/'/g, "\\'").replace(/\s+/g, '-')}">▶</div>
                    </div>
                </div>
            `;
        }).join('');
    } catch (e) {
        listDiv.innerHTML = '<div class="empty-lib" style="color: var(--error);">Failed to load library</div>';
    }
}

function hasPlayerChapters() {
    return playerState.playlist.length > 0 || playerState.chapters.length > 0;
}

function syncChaptersPanel(autoOpen = false) {
    const container = document.getElementById('appContainer');
    if (autoOpen && hasPlayerChapters()) {
        container.classList.add('panel-open');
        localStorage.setItem('panel-open', 'true');
    }
    if (container.classList.contains('panel-open')) {
        renderPlayerChapters();
    }
}

function playFromLibrary(fileName, autoPlay = true, keepPanels = false, autoOpenChapters = false) {
    if (playerState.fileName === fileName && autoPlay) {
        if (autoOpenChapters) {
            syncChaptersPanel(true);
        }
        togglePlay();
        return;
    }
    if (!keepPanels) {
        resetForm();
    } else {
        document.getElementById('optGroup').style.display = 'none';
        document.getElementById('chaptersBox').style.display = 'none';
        document.getElementById('status').style.display = 'none';
    }
    localStorage.setItem('last-played-file', fileName);
    step = 'done';
    document.getElementById('mainBtn').innerText = i18n[currentLang].btnAgain;
    initPlayer(fileName, autoOpenChapters);
    if (autoPlay) {
        setTimeout(() => {
            audio.play();
            setPlayButtonState(true);
        }, 500);
    }
}

function resetBookProgress(event, fileName) {
    event.stopPropagation();
    const t = i18n[currentLang];
    if (confirm(t.confirmReset)) {
        localStorage.removeItem('bookmark_' + fileName);
        if (playerState.fileName === fileName) {
            audio.currentTime = 0;
            document.getElementById('timelineFill').style.width = '0%';
        }
        loadLibrary();
    }
}

async function fetchInfo() {
    const url = getValidatedBookUrl();
    if(!url) return;
    const btn = document.getElementById('mainBtn');
    const statusDiv = document.getElementById('status');
    const chaptersBox = document.getElementById('chaptersBox');
    const chaptersList = document.getElementById('chaptersList');
    btn.disabled = true;
    statusDiv.style.display = 'block';
    statusDiv.style.color = '';
    statusDiv.innerText = i18n[currentLang].statusInit;
    chaptersBox.style.display = 'none';
    try {
        const res = await fetch('/api/info', { 
            method: 'POST', 
            headers: {'Content-Type':'application/json'}, 
            body: JSON.stringify({url}) 
        });
        if (!res.ok) throw new Error('Book info fetch failed');
        const data = await res.json();
        if (data.chapters && data.chapters.length > 0) {
            chaptersList.innerHTML = data.chapters.map((c, i) => `
                <div class="chapter-item"><span class="chapter-title">${i + 1}. ${escapeHtml(c.title)}</span></div>
            `).join('');
            chaptersBox.style.display = 'block';
            statusDiv.style.display = 'none';
        } else {
            statusDiv.innerText = i18n[currentLang].noChapters;
        }
        // Save cover URL if found
        if (data.cover) playerState.tempCoverUrl = data.cover;
        step = 'confirm'; 
        updateUI();
    } catch(e) { 
        statusDiv.innerText = 'Error: ' + e.message;
        statusDiv.style.color = 'var(--error)';
    } finally { btn.disabled = false; }
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
}

async function startDownload() {
    const url = getValidatedBookUrl();
    if(!url) return;
    document.getElementById('mainBtn').disabled = true;
    document.getElementById('pbox').style.display = 'block';
    document.getElementById('pbox').classList.remove('merging-mode');
    const statusDiv = document.getElementById('status');
    statusDiv.style.display = 'block';
    statusDiv.style.color = '';
    statusDiv.innerText = i18n[currentLang].statusInit;
    try {
        const res = await fetch('/api/download', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({url, mode: currentMode}) });
        if (!res.ok) {
            let message = 'Download start failed';
            try {
                const payload = await res.json();
                if (payload && payload.detail) {
                    message = payload.detail;
                }
            } catch(e) {}
            throw new Error(message);
        }
        const data = await res.json();
        poll(data.task_id);
    } catch(e) {
        statusDiv.style.color = 'var(--error)';
        statusDiv.innerText = 'Error: ' + e.message;
        document.getElementById('mainBtn').disabled = false;
    }
}

let playerState = {
    mode: 'single', duration: 0, chapters: [], playlist: [], currentTrackIndex: 0, fileName: null, bookTitle: "", tempCoverUrl: null
};

const audio = document.getElementById('audioElement');

audio.addEventListener('timeupdate', () => {
    if(!playerState.duration) return;
    const pct = (audio.currentTime / playerState.duration) * 100;
    document.getElementById('timelineFill').style.width = pct + '%';
    document.getElementById('timeCurrent').innerText = formatTime(audio.currentTime);
    if (playerState.mode === 'zip' && playerState.playlist.length > 0) {
        const track = playerState.playlist[playerState.currentTrackIndex];
        document.getElementById('playerChapter').innerText = `${playerState.currentTrackIndex + 1} / ${playerState.playlist.length}: ${track.title}`;
    } else if(playerState.chapters.length > 0) {
        const currentChIndex = playerState.chapters.findIndex(c => audio.currentTime >= c.start && audio.currentTime < c.end);
        const safeIndex = currentChIndex !== -1 ? currentChIndex : 0;
        document.getElementById('playerChapter').innerText = playerState.chapters[safeIndex].title;
        const container = document.getElementById('appContainer');
        if (container.classList.contains('panel-open')) {
            playerState.chapters.forEach((ch, idx) => {
                const fillEl = document.getElementById(`ch-fill-${idx}`);
                const timeEl = document.getElementById(`ch-time-${idx}`);
                if (fillEl) {
                    if (idx < safeIndex) { fillEl.style.width = '100%'; if(timeEl) timeEl.innerText = formatTime(ch.start); }
                    else if (idx > safeIndex) { fillEl.style.width = '0%'; if(timeEl) timeEl.innerText = formatTime(ch.start); }
                    else {
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
                }
            });
        }
    }
    if(playerState.fileName) {
        localStorage.setItem('bookmark_' + playerState.fileName, JSON.stringify({time: audio.currentTime, duration: audio.duration, track: playerState.currentTrackIndex}));
    }
});

audio.addEventListener('loadedmetadata', () => {
    playerState.duration = audio.duration;
    document.getElementById('timeTotal').innerText = formatTime(audio.duration);
    if (playerState.mode === 'm4b' && playerState.chapters.length > 0) {
        document.getElementById('markersContainer').innerHTML = playerState.chapters.map(ch => `<div class="timeline-marker" style="left: ${(ch.start / audio.duration) * 100}%;" title="${ch.title}"></div>`).join('');
    }
    if(playerState.fileName && !audio.autoplay) {
        try {
            const saved = JSON.parse(localStorage.getItem('bookmark_' + playerState.fileName));
            if(saved && saved.time) audio.currentTime = Math.max(0, Math.min(audio.duration, parseFloat(saved.time)));
        } catch(e) {}
    }
});

audio.addEventListener('ended', () => {
    if (playerState.mode === 'zip' && playerState.currentTrackIndex < playerState.playlist.length - 1) {
        playerState.currentTrackIndex++; playCurrentTrack(true);
    } else {
        setPlayButtonState(false); syncLibraryPlayIcons();
    }
});

audio.addEventListener('play', () => { setPlayButtonState(true); syncLibraryPlayIcons(); updateMediaSession(); });
audio.addEventListener('pause', () => { setPlayButtonState(false); syncLibraryPlayIcons(); });

function syncLibraryPlayIcons() {
    document.querySelectorAll('.library-item-play').forEach(el => el.innerText = '▶');
    if (!audio.paused && playerState.fileName) {
        const id = "lib-play-" + playerState.fileName.replace(/'/g, "\\'").replace(/\s+/g, '-');
        const el = document.getElementById(id);
        if (el) el.innerText = '⏸';
    }
}

function togglePlay() { if (audio.paused) audio.play(); else audio.pause(); }
function seekRelative(seconds) { audio.currentTime = Math.max(0, Math.min(audio.duration || 0, audio.currentTime + seconds)); }
function seek(event) {
    if(!playerState.duration) return;
    const rect = document.getElementById('timeline').getBoundingClientRect();
    audio.currentTime = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)) * playerState.duration;
}
function formatTime(secs) {
    if(isNaN(secs)) return "00:00:00";
    const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), s = Math.floor(secs % 60);
    return [h, m, s].map(v => v.toString().padStart(2, '0')).join(':');
}

function toggleChaptersModal() {
    const container = document.getElementById('appContainer');
    const isOpen = container.classList.toggle('panel-open');
    localStorage.setItem('panel-open', isOpen);
    if (isOpen) renderPlayerChapters();
    schedulePlayerLayoutSync();
}

function renderPlayerChapters() {
    const listDiv = document.getElementById('playerChaptersList'), t = i18n[currentLang];
    if (playerState.mode === 'zip') {
        if (!playerState.playlist.length) { listDiv.innerHTML = `<div class="empty-lib">${t.noChaptersInPanel}</div>`; return; }
        listDiv.innerHTML = playerState.playlist.map((track, idx) => `<div class="chapter-list-item ${idx === playerState.currentTrackIndex ? 'active-ch' : ''}" onclick="jumpToTrack(${idx})"><span>${idx + 1}. ${escapeHtml(track.title)}</span></div>`).join('');
    } else {
        if (!playerState.chapters.length) { listDiv.innerHTML = `<div class="empty-lib">${t.noChaptersInPanel}</div>`; return; }
        const currentChIndex = playerState.chapters.findIndex(c => audio.currentTime >= c.start && audio.currentTime < c.end);
        const safeIndex = currentChIndex !== -1 ? currentChIndex : 0;
        listDiv.innerHTML = playerState.chapters.map((ch, idx) => {
            const isActive = idx === safeIndex ? 'active-ch' : '';
            let fillPct = 0, timeText = formatTime(ch.start);
            if (idx < safeIndex) fillPct = 100;
            else if (idx === safeIndex) {
                const dur = ch.end - ch.start;
                if (dur > 0) { fillPct = ((audio.currentTime - ch.start) / dur) * 100; timeText = `${formatTime(Math.max(0, audio.currentTime - ch.start))} / ${formatTime(dur)}`; }
            }
            return `<div class="chapter-list-item ${isActive}" onclick="handleChapterClick(event, ${idx})" id="ch-item-${idx}"><div class="chapter-bg-fill" id="ch-fill-${idx}" style="width: ${fillPct}%"></div><div class="chapter-content"><span>${idx + 1}. ${escapeHtml(ch.title)}</span><span id="ch-time-${idx}" style="font-family: monospace; font-size: 0.8rem;">${escapeHtml(timeText)}</span></div></div>`;
        }).join('');
    }
    setTimeout(() => { const activeEl = listDiv.querySelector('.active-ch'); if(activeEl) activeEl.scrollIntoView({ behavior: 'smooth', block: 'center' }); }, 100);
}

function handleChapterClick(event, idx) {
    const ch = playerState.chapters[idx]; if (!ch) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const percentage = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    audio.currentTime = ch.start + ((ch.end - ch.start) * percentage);
    if (audio.paused) audio.play();
}

function jumpToTrack(index) { playerState.currentTrackIndex = index; playCurrentTrack(true); toggleChaptersModal(); }

function playCurrentTrack(autoplay = false) {
    if (!playerState.playlist.length) return;
    const track = playerState.playlist[playerState.currentTrackIndex];
    audio.src = '/api/files/' + track.file.split('/').map(p => encodeURIComponent(p)).join('/');
    audio.autoplay = autoplay; audio.load();
    if (autoplay) setPlayButtonState(true);
    document.getElementById('playerChapter').innerText = `${playerState.currentTrackIndex + 1} / ${playerState.playlist.length}: ${track.title}`;
}

async function initPlayer(fileName, autoOpenChapters = false) {
    playerState.fileName = fileName; playerState.chapters = []; playerState.playlist = []; playerState.currentTrackIndex = 0; playerState.mode = 'single';
    document.getElementById('markersContainer').innerHTML = ''; document.getElementById('playerBox').style.display = 'block';
    document.getElementById('playerTitle').innerText = fileName; document.getElementById('playerChapter').innerText = '';
    setPlayButtonState(false);
    const coverImg = document.getElementById('playerCover');
    clearPlayerCover();
    coverImg.onload = schedulePlayerLayoutSync;
    audio.autoplay = false;
    let savedBmk = null;
    try {
        const rawBmk = localStorage.getItem('bookmark_' + fileName);
        if (rawBmk && !rawBmk.startsWith('{')) savedBmk = { time: parseFloat(rawBmk), track: 0 };
        else if (rawBmk) savedBmk = JSON.parse(rawBmk);
    } catch(e) { localStorage.removeItem('bookmark_' + fileName); }

    try {
        const res = await fetch('/api/metadata/' + encodeURIComponent(fileName) + '?t=' + Date.now());
        if(res.ok) {
            const meta = await res.json();
            if(meta.title) { playerState.bookTitle = meta.title; document.getElementById('playerTitle').innerText = meta.title; }
            if (meta.local_cover) {
                setPlayerCover('/api/files/' + encodeURIComponent(meta.local_cover));
            }
            else if (meta.cover_url) {
                setPlayerCover(meta.cover_url);
            }
            
            if (meta.mode === 'zip' && meta.playlist) {
                playerState.mode = 'zip'; playerState.playlist = meta.playlist;
                if (savedBmk && (savedBmk.track < 0 || savedBmk.track >= meta.playlist.length)) savedBmk = {time:0, track:0};
                playerState.currentTrackIndex = (savedBmk && savedBmk.track !== undefined) ? savedBmk.track : 0;
                playCurrentTrack(false);
                if (savedBmk && savedBmk.time) { audio.addEventListener('loadedmetadata', function onMeta() { audio.currentTime = Math.max(0, Math.min(audio.duration || 0, parseFloat(savedBmk.time))); audio.removeEventListener('loadedmetadata', onMeta); }); }
                syncChaptersPanel(autoOpenChapters);
                schedulePlayerLayoutSync();
                updateMediaSession(); return;
            } else if(meta.chapters && meta.chapters.length > 0) {
                playerState.mode = 'm4b'; playerState.chapters = meta.chapters;
            }
        }
    } catch(e) { console.log('No metadata found', e); }
    syncChaptersPanel(autoOpenChapters);
    schedulePlayerLayoutSync();
    audio.src = '/api/files/' + encodeURIComponent(fileName); audio.load();
    if (savedBmk && savedBmk.time) { audio.addEventListener('loadedmetadata', function onMeta() { audio.currentTime = Math.max(0, Math.min(audio.duration, parseFloat(savedBmk.time))); audio.removeEventListener('loadedmetadata', onMeta); }); }
    updateMediaSession();
}

function updateMediaSession() {
    if ('mediaSession' in navigator) {
        navigator.mediaSession.metadata = new MediaMetadata({
            title: playerState.bookTitle || playerState.fileName, artist: 'SonicBook',
            artwork: document.getElementById('playerCover').src ? [{ src: document.getElementById('playerCover').src, sizes: '512x512', type: 'image/jpeg' }] : []
        });
        navigator.mediaSession.setActionHandler('play', togglePlay);
        navigator.mediaSession.setActionHandler('pause', togglePlay);
        navigator.mediaSession.setActionHandler('seekbackward', () => seekRelative(-15));
        navigator.mediaSession.setActionHandler('seekforward', () => seekRelative(15));
    }
}

window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT') return;
    if (e.code === 'Space') { e.preventDefault(); togglePlay(); }
    else if (e.code === 'ArrowLeft') seekRelative(-15);
    else if (e.code === 'ArrowRight') seekRelative(15);
});

function poll(id) {
    const eventSource = new EventSource('/api/progress/stream/' + id);
    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data), t = i18n[currentLang], statusDiv = document.getElementById('status');
        if(data.status === 'processing' || data.status === 'merging') {
            statusDiv.innerText = data.status === 'merging' ? t.statusMerging : t.statusStreams;
            if(data.status === 'merging') document.getElementById('pbox').classList.add('merging-mode');
            document.getElementById('pbox').classList.remove('assembling-mode');
            document.getElementById('bar').style.width = data.percent + '%';
            document.getElementById('perc').innerText = data.percent.toFixed(3) + '%';
            document.getElementById('frag').innerText = `${data.current_frag}/${data.total_frags}`;
        } else if(data.status === 'assembling') {
            statusDiv.innerText = t.assemblingStatus;
            document.getElementById('pbox').classList.add('assembling-mode');
            document.getElementById('bar').style.width = '100%'; document.getElementById('perc').innerText = '100.000%';
        } else if(data.status === 'success') {
            eventSource.close(); statusDiv.innerText = t.statusDone;
            document.getElementById('pbox').classList.remove('assembling-mode');
            document.getElementById('bar').style.width = '100%'; document.getElementById('perc').innerText = '100.000%';
            document.getElementById('mainBtn').disabled = false; document.getElementById('mainBtn').innerText = t.btnAgain;
            step = 'done'; initPlayer(data.file_name);
        } else if(data.status === 'error' || data.status === 'not_found') {
            eventSource.close(); statusDiv.innerText = "Error occurred";
            document.getElementById('mainBtn').disabled = false; document.getElementById('mainBtn').innerText = "Try Again";
        }
    };
    eventSource.onerror = () => eventSource.close();
}
