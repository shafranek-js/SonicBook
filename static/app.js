const i18n = {
    en: {
        placeholder: "Paste link here...",
        btnStart: "Start Download", btnFetch: "Fetch Info", btnConfirm: "Confirm & Download", btnAgain: "Download Another", btnRetry: "Try Again",
        btnBackToPlayer: "Back to Player",
        statusInit: "Initializing...", statusStreams: "Downloading...", statusMerging: "Finalizing & Metadata...",
        statusDone: "Ready!", found: "Chapters found:", noChapters: "No chapters found. Will download as single file.",
        modeSingle: "Single File", modeM4B: "M4B (Chapters)", modeZIP: "ZIP (Split)",
        saveTo: "Save to:", changeBtn: "Change", libTitle: "My Library", libEmpty: "Your library is empty.",
        librarySourceLocal: "Local", librarySourceDrive: "Drive",
        tocTitle: "Table of Contents", noChaptersInPanel: "No chapters available for this book.",
        groupNowListening: "Now Listening", groupQueue: "In Queue", groupCompleted: "Completed",
        libEmptyHint: "Downloaded books will appear here once they are available locally.",
        libLoadError: "Could not load library",
        libLoadErrorHint: "Check the folder path or reload the app to try again.",
        libraryLoadingTitle: "Loading library",
        libraryLoadingHint: "Preparing your local collection and reading saved progress.",
        chaptersLoadingTitle: "Loading chapters",
        chaptersLoadingHint: "Preparing timeline and chapter navigation for the selected book.",
        noChaptersHint: "This file can still be played, but no structured chapter list is available.",
        idleBadge: "Ready", idleTitle: "Paste a book page link to begin",
        idleSubtitle: "Fetch chapters first for M4B or ZIP, or start an instant single-file download.",
        idlePointOne: "Use the left panel for your current library.",
        idlePointTwo: "Drop a supported page URL directly onto the center panel.",
        dropKicker: "Drop Here", dropLinkTitle: "Drop a link to start", dropLinkSubtitle: "Paste or drop a supported audiobook page URL.",
        dropFilesTitle: "Local file import is not ready", dropFilesSubtitle: "Drop a book page link instead of audio files for now.",
        dropUnsupportedTitle: "Unsupported drop content", dropUnsupportedSubtitle: "Try dropping an http(s) page link.",
        loadingDialog: "Loading dialog...", assemblingStatus: "⚙️ Assembling files... Please wait",
        progressDownloading: "Downloading",
        progressAssembling: "Assembling",
        libTooltip: "Library", themeTooltip: "Theme", langTooltip: "Language", settingsTooltip: "Settings", settingsTitle: "Settings", clearAllDataBtn: "Clear all app data & cache", languageLabel: "Language", downloadAnotherTooltip: "Download another",
        googleDriveLabel: "Google Drive",
        googleDriveFolderPlaceholder: "Drive folder ID",
        googleDriveHint: "Connect your Google account and enter the folder ID that stores your audiobooks.",
        googleDriveConnect: "Connect",
        googleDriveDisconnect: "Disconnect",
        googleDriveSaveFolder: "Save folder",
        googleDriveStatusConnected: "Connected",
        googleDriveStatusDisconnected: "Not connected",
        googleDriveStatusNotConfigured: "Not configured",
        googleDriveStatusConnecting: "Connecting...",
        googleDriveStatusSaving: "Saving...",
        googleDriveFolderSaved: "Google Drive folder saved.",
        googleDriveDisconnected: "Google Drive disconnected.",
        googleDriveImport: "Import",
        googleDriveImporting: "Importing from Google Drive...",
        googleDriveImportingShort: "Importing...",
        googleDriveImported: "Imported into local library.",
        googleDriveImportedShort: "Imported",
        googleDriveStream: "Stream",
        googleDrivePause: "Pause",
        googleDriveBuffering: "Buffering stream...",
        googleDriveBufferingShort: "Buffering...",
        googleDriveStreamError: "Google Drive stream could not start.",
        googleDriveStreamTooltip: "Stream from Google Drive without importing",
        googleDriveRefresh: "Refresh",
        googleDriveRefreshing: "Refreshing Drive library...",
        googleDriveLibraryTitle: "Google Drive Library",
        googleDriveLibraryEmpty: "No supported audiobook files found in the configured Drive folder.",
        googleDriveLibraryHint: "Connect Google Drive and save a folder ID to browse remote books here.",
        googleDriveLibraryError: "Could not load Google Drive library",
        googleDriveLibraryErrorHint: "Check the account connection, folder ID, or Google API configuration.",
        chaptersTooltip: "Show or hide chapter list",
        chapterCountShort: "ch",
        resetTooltip: "Reset playback progress",
        confirmReset: "Are you sure you want to reset progress for this book?"
    },
    ru: {
        placeholder: "Вставьте ссылку...",
        btnStart: "Начать загрузку", btnFetch: "Найти главы", btnConfirm: "Подтвердить и скачать", btnAgain: "Загрузить еще одну", btnRetry: "Попробовать снова",
        btnBackToPlayer: "Вернуться к плееру",
        statusInit: "Инициализация...", statusStreams: "Загрузка...", statusMerging: "Сборка и метаданные...",
        statusDone: "Готово!", found: "Найденные главы:", noChapters: "Главы не найдены. Будет скачано одним файлом.",
        modeSingle: "Одним файлом", modeM4B: "M4B (Главы)", modeZIP: "ZIP (Нарезка)",
        saveTo: "Сохранять в:", changeBtn: "Изменить", libTitle: "Моя Библиотека", libEmpty: "Библиотека пуста.",
        librarySourceLocal: "Локально", librarySourceDrive: "Drive",
        tocTitle: "Оглавление", noChaptersInPanel: "Для этой книги нет списка глав.",
        groupNowListening: "Слушаю сейчас", groupQueue: "В очереди", groupCompleted: "Завершено",
        libEmptyHint: "Скачанные книги появятся здесь, как только будут доступны локально.",
        libLoadError: "Не удалось загрузить библиотеку",
        libLoadErrorHint: "Проверьте путь к папке или обновите приложение и попробуйте снова.",
        libraryLoadingTitle: "Загрузка библиотеки",
        libraryLoadingHint: "Подготавливаю локальную коллекцию и сохраненный прогресс.",
        chaptersLoadingTitle: "Загрузка глав",
        chaptersLoadingHint: "Подготавливаю таймлайн и навигацию по главам для выбранной книги.",
        noChaptersHint: "Файл все равно можно слушать, но структурированный список глав недоступен.",
        idleBadge: "Готово", idleTitle: "Вставьте ссылку на страницу книги",
        idleSubtitle: "Для M4B или ZIP сначала получите главы, либо начните быструю загрузку одним файлом.",
        idlePointOne: "Слева доступна ваша текущая библиотека.",
        idlePointTwo: "Ссылку на страницу книги можно просто перетащить в центр.",
        dropKicker: "Перетащите сюда", dropLinkTitle: "Бросьте ссылку для старта", dropLinkSubtitle: "Вставьте или перетащите URL страницы книги.",
        dropFilesTitle: "Импорт локальных файлов пока не готов", dropFilesSubtitle: "Пока перетаскивайте ссылку на страницу книги, а не аудиофайлы.",
        dropUnsupportedTitle: "Неподдерживаемое содержимое", dropUnsupportedSubtitle: "Попробуйте перетащить http(s)-ссылку.",
        loadingDialog: "Открытие окна...", assemblingStatus: "⚙️ Сборка файлов... Пожалуйста, подождите",
        progressDownloading: "Загрузка",
        progressAssembling: "Сборка",
        libTooltip: "Библиотека", themeTooltip: "Тема", langTooltip: "Язык", settingsTooltip: "Настройки", settingsTitle: "Настройки", clearAllDataBtn: "Очистить все данные приложения и кэш", languageLabel: "Язык", downloadAnotherTooltip: "Загрузить еще одну",
        googleDriveLabel: "Google Drive",
        googleDriveFolderPlaceholder: "ID папки Drive",
        googleDriveHint: "Подключите Google-аккаунт и укажите ID папки, где лежат аудиокниги.",
        googleDriveConnect: "Подключить",
        googleDriveDisconnect: "Отключить",
        googleDriveSaveFolder: "Сохранить папку",
        googleDriveStatusConnected: "Подключено",
        googleDriveStatusDisconnected: "Не подключено",
        googleDriveStatusNotConfigured: "Не настроено",
        googleDriveStatusConnecting: "Подключение...",
        googleDriveStatusSaving: "Сохранение...",
        googleDriveFolderSaved: "Папка Google Drive сохранена.",
        googleDriveDisconnected: "Google Drive отключен.",
        googleDriveImport: "Импорт",
        googleDriveImporting: "Импорт из Google Drive...",
        googleDriveImportingShort: "Импорт...",
        googleDriveImported: "Книга импортирована в локальную библиотеку.",
        googleDriveImportedShort: "Импортирована",
        googleDriveStream: "Стрим",
        googleDrivePause: "Пауза",
        googleDriveBuffering: "Буферизация стрима...",
        googleDriveBufferingShort: "Буферизация...",
        googleDriveStreamError: "Не удалось запустить стрим из Google Drive.",
        googleDriveStreamTooltip: "Слушать из Google Drive без импорта",
        googleDriveRefresh: "Обновить",
        googleDriveRefreshing: "Обновление библиотеки Drive...",
        googleDriveLibraryTitle: "Библиотека Google Drive",
        googleDriveLibraryEmpty: "В выбранной папке Drive не найдено поддерживаемых аудиокниг.",
        googleDriveLibraryHint: "Подключите Google Drive и сохраните ID папки, чтобы видеть удалённые книги здесь.",
        googleDriveLibraryError: "Не удалось загрузить библиотеку Google Drive",
        googleDriveLibraryErrorHint: "Проверьте подключение, ID папки или настройки Google API.",
        chaptersTooltip: "Показать или скрыть список глав",
        chapterCountShort: "гл.",
        resetTooltip: "Сбросить прогресс прослушивания",
        confirmReset: "Вы уверены, что хотите сбросить прогресс для этой книги?"
    }
};

const appState = {
    currentLang: localStorage.getItem('lang') || 'en',
    currentMode: localStorage.getItem('mode') || 'm4b',
    librarySource: localStorage.getItem('library-source') || 'local',
    step: 'start',
    playerReturnState: null,
    activeDownloadTask: null,
    showPlayer: false,
    showPreview: false,
    previewLoading: false,
    showProgress: false,
    mainButtonLabelOverride: '',
    status: {
        visible: false,
        message: '',
        tone: 'info'
    },
    googleDrive: {
        configured: false,
        connected: false,
        folderId: '',
        accountEmail: '',
        accountName: '',
        loading: false,
        refreshingLibrary: false
    },
    driveStreamBufferingFileId: '',
    bookmarks: {}
};
let playerLayoutFrame = null;
let mainDragDepth = 0;

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function renderSkeletonRows(count = 6, compact = false) {
    const rows = Array.from({ length: count }, () => (
        '<div class="skeleton-row' + (compact ? ' compact' : '') + '">' +
            '<div class="skeleton-copy">' +
                '<div class="skeleton-line title"></div>' +
                '<div class="skeleton-line meta"></div>' +
            '</div>' +
            '<div class="skeleton-chip icon"></div>' +
        '</div>'
    )).join('');
    return '<div class="skeleton-stack">' + rows + '</div>';
}

function normalizeBookNameForId(name) {
    const base = String(name || '').replace(/\.[^.]+$/, '').toLowerCase();
    return base.replace(/[^\p{L}\p{N}]+/gu, ' ').trim().replace(/\s+/g, ' ');
}

function buildClientBookId(name, sizeBytes = 0) {
    const normalized = normalizeBookNameForId(name);
    if (!normalized) {
        return '';
    }
    const safeSize = Number(sizeBytes) || 0;
    return safeSize > 0 ? `book:file:${normalized}:${safeSize}` : `book:file:${normalized}`;
}

function buildLegacyClientBookId(name) {
    const normalized = normalizeBookNameForId(name);
    return normalized ? `book:${normalized}` : '';
}

function buildLibraryPlayButtonId(source, identifier) {
    const safeSource = source === 'google_drive' ? 'drive' : 'local';
    const safeIdentifier = encodeURIComponent(String(identifier || ''));
    return `lib-play-${safeSource}-${safeIdentifier}`;
}

async function loadBookmarkSummary() {
    try {
        const res = await fetch('/api/bookmarks');
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'bookmarks');
        }
        appState.bookmarks = data.bookmarks || {};
    } catch (e) {
        appState.bookmarks = {};
    }
    return appState.bookmarks;
}

function getCachedBookmark(bookId) {
    if (!bookId) {
        return null;
    }
    return appState.bookmarks[bookId] || null;
}

function renderPanelEmptyState(icon, title, subtitle = '', tone = '') {
    const toneClass = tone ? ` panel-state-${tone}` : '';
    const subtitleMarkup = subtitle ? `<div class="panel-state-subtitle">${escapeHtml(subtitle)}</div>` : '';
    return `
        <div class="panel-state-shell">
            <div class="panel-state${toneClass}">
                <div class="panel-state-icon" aria-hidden="true">${icon}</div>
                <div class="panel-state-title">${escapeHtml(title)}</div>
                ${subtitleMarkup}
            </div>
        </div>
    `;
}

function renderPanelLoadingState(title, subtitle, count = 6, compact = false) {
    return `
        <div class="panel-state-shell panel-loading-shell">
            <div class="panel-state">
                <div class="panel-state-icon" aria-hidden="true">⋯</div>
                <div class="panel-state-title">${escapeHtml(title)}</div>
                <div class="panel-state-subtitle">${escapeHtml(subtitle)}</div>
            </div>
            ${renderSkeletonRows(count, compact)}
        </div>
    `;
}

function syncMainSurfaceState() {
    const mainCard = document.querySelector('.main-card');
    if (!mainCard) {
        return;
    }
    const hasPlayerSession = appState.showPlayer || appState.step === 'done';
    mainCard.classList.toggle('player-session', hasPlayerSession);
}

function setStatusMessage(message, tone = 'info') {
    appState.status.visible = true;
    appState.status.message = message;
    appState.status.tone = tone;
    updateUI();
}

function clearStatusMessage() {
    appState.status.visible = false;
    appState.status.message = '';
    appState.status.tone = 'info';
    updateUI();
}

function setDropOverlay(kind = 'link') {
    const overlay = document.getElementById('mainDropOverlay');
    const kicker = document.getElementById('mainDropKicker');
    const title = document.getElementById('mainDropTitle');
    const subtitle = document.getElementById('mainDropSubtitle');
    const t = i18n[appState.currentLang];
    if (!overlay || !kicker || !title || !subtitle) {
        return;
    }
    kicker.innerText = t.dropKicker;
    overlay.dataset.kind = kind;
    if (kind === 'files') {
        title.innerText = t.dropFilesTitle;
        subtitle.innerText = t.dropFilesSubtitle;
    } else if (kind === 'unsupported') {
        title.innerText = t.dropUnsupportedTitle;
        subtitle.innerText = t.dropUnsupportedSubtitle;
    } else {
        title.innerText = t.dropLinkTitle;
        subtitle.innerText = t.dropLinkSubtitle;
    }
}

function getDropKind(dataTransfer) {
    if (!dataTransfer) {
        return 'unsupported';
    }
    const types = Array.from(dataTransfer.types || []);
    if (types.includes('Files')) {
        return 'files';
    }
    if (types.includes('text/uri-list') || types.includes('text/plain')) {
        return 'link';
    }
    return 'unsupported';
}

function hideDropOverlay() {
    const overlay = document.getElementById('mainDropOverlay');
    if (!overlay) {
        return;
    }
    overlay.classList.remove('is-visible');
    overlay.dataset.kind = 'link';
}

function handleDroppedPayload(event) {
    const dt = event.dataTransfer;
    const kind = getDropKind(dt);
    const urlInput = document.getElementById('urlInput');
    if (kind === 'link') {
        const raw = (dt.getData('text/uri-list') || dt.getData('text/plain') || '').trim().split('\n')[0].trim();
        if (/^https?:\/\/\S+$/i.test(raw)) {
            urlInput.value = raw;
            urlInput.focus();
            clearStatusMessage();
            return;
        }
    }
    setStatusMessage(kind === 'files' ? i18n[appState.currentLang].dropFilesSubtitle : i18n[appState.currentLang].dropUnsupportedSubtitle, 'error');
}

function initDragAndDrop() {
    const mainCard = document.querySelector('.main-card');
    const overlay = document.getElementById('mainDropOverlay');
    if (!mainCard || !overlay) {
        return;
    }
    ['dragenter', 'dragover'].forEach(type => {
        mainCard.addEventListener(type, (event) => {
            event.preventDefault();
            event.stopPropagation();
            mainDragDepth += type === 'dragenter' ? 1 : 0;
            setDropOverlay(getDropKind(event.dataTransfer));
            overlay.classList.add('is-visible');
            mainCard.classList.add('is-drag-over');
        });
    });
    mainCard.addEventListener('dragleave', (event) => {
        event.preventDefault();
        event.stopPropagation();
        mainDragDepth = Math.max(0, mainDragDepth - 1);
        if (mainDragDepth === 0 || !mainCard.contains(event.relatedTarget)) {
            mainCard.classList.remove('is-drag-over');
            hideDropOverlay();
        }
    });
    mainCard.addEventListener('drop', (event) => {
        event.preventDefault();
        event.stopPropagation();
        mainDragDepth = 0;
        mainCard.classList.remove('is-drag-over');
        hideDropOverlay();
        handleDroppedPayload(event);
    });
    window.addEventListener('dragend', () => {
        mainDragDepth = 0;
        mainCard.classList.remove('is-drag-over');
        hideDropOverlay();
    });
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
    const playerBox = document.getElementById('playerBox');
    const coverFrame = document.getElementById('playerCoverFrame');
    const coverImg = document.getElementById('playerCover');
    if (!mainCard || !playerBox || !coverFrame || !coverImg || coverFrame.style.display === 'none' || coverImg.style.display === 'none' || !coverImg.src) {
        return;
    }

    coverFrame.style.minHeight = '';
    coverImg.style.maxHeight = 'none';

    const overflow = mainCard.scrollHeight - mainCard.clientHeight;
    if (overflow <= 0) {
        const remainingHeight = playerBox.getBoundingClientRect().height
            - (playerBox.scrollHeight - coverFrame.getBoundingClientRect().height);
        if (remainingHeight > 220) {
            coverFrame.style.minHeight = `${Math.floor(remainingHeight)}px`;
        }
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
    coverFrame.style.minHeight = '';
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
    coverFrame.style.display = 'flex';
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

function updateUI() {
    const t = i18n[appState.currentLang];
    const optGroup = document.getElementById('optGroup');
    const toolbarLink = document.querySelector('.toolbar-link');
    const mainToolbar = document.querySelector('.main-toolbar');
    const chaptersBox = document.getElementById('chaptersBox');
    const playerBox = document.getElementById('playerBox');
    const progressBox = document.getElementById('pbox');
    const progressPhase = document.getElementById('progressPhase');
    const statusDiv = document.getElementById('status');
    const idleState = document.getElementById('idleState');
    const secondaryBtn = document.getElementById('secondaryBtn');
    document.getElementById('urlInput').placeholder = t.placeholder;
    document.getElementById('mode-m4b').innerText = t.modeM4B;
    document.getElementById('mode-mp3').innerText = t.modeSingle;
    document.getElementById('mode-zip').innerText = t.modeZIP;
    document.getElementById('settingsLangBtn').innerText = appState.currentLang === 'en' ? 'RU' : 'EN';
    document.getElementById('t-found').innerText = t.found;
    document.getElementById('t-language-label').innerText = t.languageLabel;
    document.getElementById('t-google-drive-label').innerText = t.googleDriveLabel;
    document.getElementById('t-save-path').innerText = t.saveTo;
    document.getElementById('t-settings-title').innerText = t.settingsTitle;
    document.getElementById('btn-change-folder').innerText = t.changeBtn;
    document.getElementById('resetAllDataBtn').innerText = t.clearAllDataBtn;
    document.getElementById('googleDriveFolderInput').placeholder = t.googleDriveFolderPlaceholder;
    document.getElementById('googleDriveHint').innerText = t.googleDriveHint;
    document.getElementById('googleDriveConnectBtn').innerText = t.googleDriveConnect;
    document.getElementById('googleDriveDisconnectBtn').innerText = t.googleDriveDisconnect;
    document.getElementById('googleDriveSaveFolderBtn').innerText = t.googleDriveSaveFolder;
    const libraryRefreshBtn = document.getElementById('libraryRefreshBtn');
    if (libraryRefreshBtn) {
        libraryRefreshBtn.innerText = '↻';
        libraryRefreshBtn.title = t.googleDriveRefresh;
        libraryRefreshBtn.setAttribute('aria-label', t.googleDriveRefresh);
    }
    document.getElementById('t-lib-title').innerText = t.libTitle;
    document.getElementById('t-panel-title').innerText = t.tocTitle;
    document.getElementById('librarySourceLocalBtn').innerText = t.librarySourceLocal;
    document.getElementById('librarySourceDriveBtn').innerText = t.librarySourceDrive;
    const playerChaptersBtn = document.getElementById('btn-player-chapters');
    if (playerChaptersBtn) {
        playerChaptersBtn.innerText = '📑 ' + (appState.currentLang === 'en' ? 'Chapters' : 'Главы');
    }
    document.getElementById('idleBadge').innerText = t.idleBadge;
    document.getElementById('idleTitle').innerText = t.idleTitle;
    document.getElementById('idleSubtitle').innerText = t.idleSubtitle;
    document.getElementById('idlePointOne').innerText = t.idlePointOne;
    document.getElementById('idlePointTwo').innerText = t.idlePointTwo;
    
    document.getElementById('libBtn').title = t.libTooltip;
    document.getElementById('themeBtn').title = t.themeTooltip;
    document.getElementById('downloadAnotherBtn').title = t.downloadAnotherTooltip;
    document.getElementById('downloadAnotherBtn').setAttribute('aria-label', t.downloadAnotherTooltip);
    document.getElementById('settingsBtn').title = t.settingsTooltip;
    document.getElementById('settingsBtn').setAttribute('aria-label', t.settingsTooltip);
    document.getElementById('settingsLangBtn').title = t.langTooltip;
    document.getElementById('settingsLangBtn').setAttribute('aria-label', t.langTooltip);
    syncGoogleDriveSettingsUI();
    syncLibrarySourceUI();

    const btn = document.getElementById('mainBtn');
    const toolbarDownloadBtn = document.getElementById('downloadAnotherBtn');
    const defaultMainButtonText = appState.step === 'done'
        ? {
            text: t.btnAgain
        }
        : appState.step === 'confirm'
            ? {
                text: t.btnConfirm
            }
            : {
                text: (appState.currentMode === 'm4b' || appState.currentMode === 'zip') ? t.btnFetch : t.btnStart
            };
    const stepConfig = appState.step === 'done'
        ? {
            toolbarLinkHidden: true,
            toolbarPlayerMode: true,
            modesVisible: false,
            mainButtonVisible: false,
            mainButtonText: appState.mainButtonLabelOverride || defaultMainButtonText.text,
            toolbarDownloadVisible: true
        }
        : appState.step === 'confirm'
            ? {
                toolbarLinkHidden: false,
                toolbarPlayerMode: false,
                modesVisible: true,
                mainButtonVisible: true,
                mainButtonText: appState.mainButtonLabelOverride || defaultMainButtonText.text,
                toolbarDownloadVisible: false
            }
            : {
                toolbarLinkHidden: false,
                toolbarPlayerMode: false,
                modesVisible: true,
                mainButtonVisible: true,
                mainButtonText: appState.mainButtonLabelOverride || defaultMainButtonText.text,
                toolbarDownloadVisible: false
            };
    if (chaptersBox) {
        chaptersBox.style.display = appState.showPreview ? 'block' : 'none';
        chaptersBox.classList.toggle('is-preview-loading', appState.previewLoading);
    }
    if (playerBox) {
        playerBox.style.display = appState.showPlayer ? 'flex' : 'none';
    }
    if (progressBox) {
        progressBox.style.display = appState.showProgress ? 'block' : 'none';
    }
    if (progressPhase && progressBox) {
        progressPhase.innerText = progressBox.dataset.phase === 'assembling' ? t.progressAssembling : t.progressDownloading;
    }
    if (statusDiv) {
        statusDiv.style.display = appState.status.visible ? 'block' : 'none';
        statusDiv.classList.remove('status-info', 'status-success', 'status-error');
        if (appState.status.visible) {
            statusDiv.classList.add(`status-${appState.status.tone}`);
        }
        statusDiv.innerText = appState.status.message;
    }
    if (idleState) {
        const isIdleVisible =
            !appState.showPlayer &&
            !appState.showPreview &&
            !appState.status.visible &&
            !appState.showProgress &&
            appState.step === 'start';
        idleState.style.display = isIdleVisible ? 'block' : 'none';
    }
    if (toolbarLink) toolbarLink.hidden = stepConfig.toolbarLinkHidden;
    if (mainToolbar) mainToolbar.classList.toggle('toolbar-player-mode', stepConfig.toolbarPlayerMode);
    optGroup.style.display = stepConfig.modesVisible ? 'flex' : 'none';
    btn.innerText = stepConfig.mainButtonText;
    btn.style.display = stepConfig.mainButtonVisible ? 'block' : 'none';
    toolbarDownloadBtn.hidden = !stepConfig.toolbarDownloadVisible;
    if (secondaryBtn) {
        secondaryBtn.innerText = t.btnBackToPlayer;
        secondaryBtn.style.display = hasReturnablePlayer() ? 'block' : 'none';
    }
    syncMainSurfaceState();
}

function syncGoogleDriveSettingsUI() {
    const badge = document.getElementById('googleDriveStatusBadge');
    const folderInput = document.getElementById('googleDriveFolderInput');
    const connectBtn = document.getElementById('googleDriveConnectBtn');
    const disconnectBtn = document.getElementById('googleDriveDisconnectBtn');
    const saveFolderBtn = document.getElementById('googleDriveSaveFolderBtn');
    const t = i18n[appState.currentLang];
    if (!badge || !folderInput || !connectBtn || !disconnectBtn || !saveFolderBtn) {
        return;
    }

    folderInput.value = appState.googleDrive.folderId || '';
    badge.className = 'settings-status-badge';
    let statusText = t.googleDriveStatusDisconnected;
    if (!appState.googleDrive.configured) {
        badge.classList.add('settings-status-warning');
        statusText = t.googleDriveStatusNotConfigured;
    } else if (appState.googleDrive.connected) {
        badge.classList.add('settings-status-success');
        statusText = appState.googleDrive.accountEmail || appState.googleDrive.accountName || t.googleDriveStatusConnected;
    } else if (appState.googleDrive.loading) {
        badge.classList.add('settings-status-pending');
        statusText = t.googleDriveStatusConnecting;
    } else {
        badge.classList.add('settings-status-idle');
        statusText = t.googleDriveStatusDisconnected;
    }
    badge.innerText = statusText;

    connectBtn.hidden = !appState.googleDrive.configured || appState.googleDrive.connected;
    disconnectBtn.hidden = !appState.googleDrive.connected;
    const disableMutations = appState.googleDrive.loading || !appState.googleDrive.configured;
    connectBtn.disabled = disableMutations;
    disconnectBtn.disabled = appState.googleDrive.loading;
    saveFolderBtn.disabled = disableMutations;
    folderInput.disabled = disableMutations;
}

function syncLibrarySourceUI() {
    const localBtn = document.getElementById('librarySourceLocalBtn');
    const driveBtn = document.getElementById('librarySourceDriveBtn');
    const refreshBtn = document.getElementById('libraryRefreshBtn');
    if (!localBtn || !driveBtn) {
        return;
    }
    localBtn.classList.toggle('active', appState.librarySource === 'local');
    driveBtn.classList.toggle('active', appState.librarySource === 'google_drive');
    if (refreshBtn) {
        refreshBtn.hidden = appState.librarySource !== 'google_drive';
        refreshBtn.disabled = !!appState.googleDrive.refreshingLibrary;
        refreshBtn.classList.toggle('is-spinning', !!appState.googleDrive.refreshingLibrary);
    }
}

function setLibrarySource(source) {
    if (!['local', 'google_drive'].includes(source)) {
        return;
    }
    appState.librarySource = source;
    localStorage.setItem('library-source', source);
    syncLibrarySourceUI();
    loadLibrary();
}

function refreshCurrentLibrary() {
    if (appState.librarySource === 'google_drive') {
        loadGoogleDriveLibrary(true);
        return;
    }
    loadLibrary();
}

function hasReturnablePlayer() {
    return !!appState.playerReturnState && !!appState.playerReturnState.fileName && !appState.showPlayer;
}

function toggleLang() { appState.currentLang = appState.currentLang === 'en' ? 'ru' : 'en'; localStorage.setItem('lang', appState.currentLang); updateUI(); }
function toggleTheme() {
    const isLight = document.body.classList.toggle('light-theme');
    document.getElementById('themeBtn').innerText = isLight ? '☀️' : '🌙';
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
}

function resetAllData() {
    if(confirm("This will clear all your bookmarks and settings. Continue?")) {
        closeSettingsMenu();
        localStorage.clear();
        location.reload();
    }
}

function closeSettingsMenu() {
    const wrap = document.getElementById('settingsWrap');
    const menu = document.getElementById('settingsMenu');
    const btn = document.getElementById('settingsBtn');
    if (!wrap || !menu || !btn) {
        return;
    }
    menu.hidden = true;
    wrap.classList.remove('is-open');
    btn.setAttribute('aria-expanded', 'false');
}

function toggleSettingsMenu() {
    const wrap = document.getElementById('settingsWrap');
    const menu = document.getElementById('settingsMenu');
    const btn = document.getElementById('settingsBtn');
    if (!wrap || !menu || !btn) {
        return;
    }
    const willOpen = menu.hidden;
    menu.hidden = !willOpen;
    wrap.classList.toggle('is-open', willOpen);
    btn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
}

function initSettingsMenu() {
    const wrap = document.getElementById('settingsWrap');
    if (!wrap || wrap.dataset.bound === 'true') {
        return;
    }
    wrap.dataset.bound = 'true';
    document.addEventListener('click', (event) => {
        if (!wrap.contains(event.target)) {
            closeSettingsMenu();
        }
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeSettingsMenu();
        }
    });
}

async function loadGoogleDriveStatus() {
    try {
        const res = await fetch('/api/google-drive/status');
        if (!res.ok) {
            throw new Error('status');
        }
        const data = await res.json();
        appState.googleDrive.configured = !!data.configured;
        appState.googleDrive.connected = !!data.connected;
        appState.googleDrive.folderId = data.folder_id || '';
        appState.googleDrive.accountEmail = data.account_email || '';
        appState.googleDrive.accountName = data.account_name || '';
    } catch (e) {
        appState.googleDrive.configured = false;
        appState.googleDrive.connected = false;
        appState.googleDrive.folderId = '';
        appState.googleDrive.accountEmail = '';
        appState.googleDrive.accountName = '';
    } finally {
        appState.googleDrive.loading = false;
        updateUI();
    }
}

async function connectGoogleDrive() {
    const t = i18n[appState.currentLang];
    appState.googleDrive.loading = true;
    updateUI();
    try {
        const res = await fetch('/api/google-drive/auth/url');
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'auth-url');
        }
        window.open(data.auth_url, '_blank', 'noopener,noreferrer');
        setStatusMessage(t.googleDriveStatusConnecting, 'info');
    } catch (e) {
        setStatusMessage(String(e.message || e), 'error');
    } finally {
        appState.googleDrive.loading = false;
        updateUI();
    }
}

async function disconnectGoogleDrive() {
    const t = i18n[appState.currentLang];
    appState.googleDrive.loading = true;
    updateUI();
    try {
        const res = await fetch('/api/google-drive/disconnect', { method: 'POST' });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'disconnect');
        }
        appState.googleDrive.connected = false;
        appState.googleDrive.accountEmail = '';
        appState.googleDrive.accountName = '';
        setStatusMessage(t.googleDriveDisconnected, 'success');
    } catch (e) {
        setStatusMessage(String(e.message || e), 'error');
    } finally {
        appState.googleDrive.loading = false;
        await loadGoogleDriveStatus();
    }
}

async function saveGoogleDriveFolder() {
    const t = i18n[appState.currentLang];
    const folderInput = document.getElementById('googleDriveFolderInput');
    const folderId = (folderInput?.value || '').trim();
    appState.googleDrive.loading = true;
    updateUI();
    try {
        const res = await fetch('/api/google-drive/folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_id: folderId })
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'save-folder');
        }
        appState.googleDrive.folderId = data.folder_id || '';
        setStatusMessage(t.googleDriveFolderSaved, 'success');
    } catch (e) {
        setStatusMessage(String(e.message || e), 'error');
    } finally {
        appState.googleDrive.loading = false;
        updateUI();
    }
}

// Init logic
window.addEventListener('DOMContentLoaded', () => {
    setPlayButtonState(false);
    if (localStorage.getItem('theme') === 'light') {
        document.body.classList.add('light-theme');
        document.getElementById('themeBtn').innerText = '☀️';
    }
    setMode(appState.currentMode);
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
    syncResponsivePanelWidths();
    updateUI();
    initLibraryInteractions();
    initSettingsMenu();
    initDragAndDrop();
    loadGoogleDriveStatus();
    schedulePlayerLayoutSync();
});

window.addEventListener('resize', () => {
    syncResponsivePanelWidths();
    schedulePlayerLayoutSync();
});

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
        closeSettingsMenu();
        document.getElementById('currentPath').innerText = "Loading dialog...";
        const res = await fetch('/api/settings/choose_folder', {method: 'POST'});
        const data = await res.json();
        document.getElementById('currentPath').innerText = data.folder;
        document.getElementById('currentPath').title = data.folder;
    } catch(e) {
        initFolder();
    }
}

function toggleLibrary() {
    const container = document.getElementById('appContainer');
    if (!container) {
        return;
    }

    const chaptersAvailable = hasPlayerChapters();
    const bothPanelsOpen = container.classList.contains('library-open') && (!chaptersAvailable || container.classList.contains('panel-open'));

    if (bothPanelsOpen) {
        container.classList.remove('library-open');
        container.classList.remove('panel-open');
        localStorage.setItem('library-open', 'false');
        localStorage.setItem('panel-open', 'false');
    } else {
        container.classList.add('library-open');
        localStorage.setItem('library-open', 'true');
        loadLibrary();

        if (chaptersAvailable) {
            container.classList.add('panel-open');
            localStorage.setItem('panel-open', 'true');
            renderPlayerChapters();
        } else {
            container.classList.remove('panel-open');
            localStorage.setItem('panel-open', 'false');
        }
    }

    syncResponsivePanelWidths();
    schedulePlayerLayoutSync();
}

function hasPlayerChapters() {
    return playerState.playlist.length > 0 || playerState.chapters.length > 0;
}

function syncChaptersPanel(autoOpen = false) {
    if (autoOpen && hasPlayerChapters()) {
        setChaptersPanelOpen(true);
        return;
    }
    if (document.getElementById('appContainer').classList.contains('panel-open')) {
        renderPlayerChapters();
    }
}

function setChaptersPanelOpen(isOpen) {
    const container = document.getElementById('appContainer');
    if (!container) return;
    if (isOpen && hasPlayerChapters()) {
        container.classList.add('panel-open');
        localStorage.setItem('panel-open', 'true');
        renderPlayerChapters();
    } else {
        container.classList.remove('panel-open');
        localStorage.setItem('panel-open', 'false');
    }
    syncResponsivePanelWidths();
    schedulePlayerLayoutSync();
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
        appState.showPreview = false;
        appState.previewLoading = false;
        syncDownloadProgressVisibility();
        clearStatusMessage();
        updateUI();
    }
    localStorage.setItem('last-played-file', fileName);
    appState.step = 'done';
    appState.mainButtonLabelOverride = '';
    initPlayer(fileName, autoOpenChapters);
    if (autoPlay) {
        setTimeout(() => {
            audio.play();
            setPlayButtonState(true);
        }, 500);
    }
}

function handleLibraryChaptersToggle(event, fileName) {
    event.stopPropagation();
    const isCurrentBook = playerState.fileName === fileName;
    const isPanelOpen = document.getElementById('appContainer').classList.contains('panel-open');
    if (isCurrentBook) {
        setChaptersPanelOpen(!isPanelOpen);
        return;
    }
    playFromLibrary(fileName, false, true, true);
}

function formatTime(secs) {
    if(isNaN(secs)) return "00:00:00";
    const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), s = Math.floor(secs % 60);
    return [h, m, s].map(v => v.toString().padStart(2, '0')).join(':');
}

function formatDurationLabel(secs) {
    if (!secs || isNaN(secs) || secs <= 0) return '';
    const rounded = Math.round(secs);
    const h = Math.floor(rounded / 3600);
    const m = Math.floor((rounded % 3600) / 60);
    const s = Math.floor(rounded % 60);
    if (h > 0) {
        return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function setPanelCount(count) {
    const badge = document.getElementById('panelCountBadge');
    if (!badge) return;
    if (count > 0) {
        badge.innerText = count;
        badge.style.display = 'inline-flex';
    } else {
        badge.innerText = '0';
        badge.style.display = 'none';
    }
}

function setLibraryCount(count) {
    const badge = document.getElementById('libraryCountBadge');
    if (!badge) return;
    if (count > 0) {
        badge.innerText = count;
        badge.style.display = 'inline-flex';
    } else {
        badge.innerText = '0';
        badge.style.display = 'none';
    }
}
