const i18n = {
            en: {
                subtitle: "Advanced Audiobook Downloader", placeholder: "Paste link here...",
                btnStart: "Start Download", btnFetch: "Fetch Info", btnConfirm: "Confirm & Download", btnAgain: "Download Another",
                statusInit: "Initializing...", statusStreams: "Downloading...", statusMerging: "Finalizing & Metadata...",
                statusDone: "Ready!", found: "Chapters found:", noChapters: "No chapters found. Will download as single file.", saveBtn: "📥 Save Result",
                modeSingle: "Single File", modeM4B: "M4B (Chapters)", modeZIP: "ZIP (Split)",
                saveTo: "Save to:", changeBtn: "Change", libTitle: "My Library", libEmpty: "Your library is empty.",
                tocTitle: "Table of Contents", noChaptersInPanel: "No chapters available for this book.",
                loadingDialog: "Loading dialog...", assemblingStatus: "⚙️ Assembling M4B... Please wait",
                libTooltip: "Library", themeTooltip: "Theme", langTooltip: "Language",
                resetTooltip: "Reset playback progress",
                confirmReset: "Are you sure you want to reset progress for this book?"
            },
            ru: {
                subtitle: "Продвинутый загрузчик аудиокниг", placeholder: "Вставьте ссылку...",
                btnStart: "Начать загрузку", btnFetch: "Найти главы", btnConfirm: "Подтвердить и скачать", btnAgain: "Загрузить еще одну",
                statusInit: "Инициализация...", statusStreams: "Загрузка...", statusMerging: "Сборка и метаданные...",
                statusDone: "Готово!", found: "Найденные главы:", noChapters: "Главы не найдены. Будет скачано одним файлом.", saveBtn: "📥 Сохранить результат",
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
                resizeEdge = 'library'; // Treat them the same: the boundary between Lib and Main
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
                // Dragging left boundary: delta > 0 means moving right (Main shrinks, Lib grows)
                let newMainW = startMainW - delta;
                newMainW = Math.max(350, newMainW);
                root.style.setProperty('--main-width', newMainW + 'px');
                
                if (container.classList.contains('library-open')) {
                    let newLibW = startSideW + delta;
                    newLibW = Math.max(250, newLibW);
                    root.style.setProperty('--lib-width', newLibW + 'px');
                }
            } else if (resizeEdge === 'chapters') {
                // Dragging right boundary: delta > 0 means moving right (Main grows, Chap shrinks)
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
        }

        function updateUI() {
            const t = i18n[currentLang];
            // ... (rest of translation logic) ...
            document.getElementById('t-subtitle').innerText = t.subtitle;
            document.getElementById('urlInput').placeholder = t.placeholder;
            document.getElementById('downloadLink').innerText = t.saveBtn;
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
            
            // Tooltips
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

        // Init
        window.addEventListener('DOMContentLoaded', () => {
            // Restore theme
            if (localStorage.getItem('theme') === 'light') {
                document.body.classList.add('light-theme');
                document.getElementById('themeBtn').innerText = '☀️';
            }
            
            // Restore Mode
            setMode(currentMode);
            
            // Restore panels
            if (localStorage.getItem('library-open') === 'true') {
                document.getElementById('appContainer').classList.add('library-open');
                loadLibrary();
            }
            if (localStorage.getItem('panel-open') === 'true') {
                document.getElementById('appContainer').classList.add('panel-open');
            }

            // Restore last played book
            const lastFile = localStorage.getItem('last-played-file');
            if (lastFile) {
                playFromLibrary(lastFile, false, true); // false = don't auto-start audio, true = keep panels open
            }
            
            updateUI();
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
                document.getElementById('currentPath').innerText = "Loading dialog...";
                const res = await fetch('/api/settings/choose_folder', {method: 'POST'});
                const data = await res.json();
                document.getElementById('currentPath').innerText = data.folder;
                document.getElementById('currentPath').title = data.folder;
            } catch(e) {
                initFolder();
            }
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
            document.getElementById('downloadLink').style.display = 'none';
            document.getElementById('status').style.display = 'none';
            document.getElementById('optGroup').style.display = 'flex';
            document.getElementById('playerBox').style.display = 'none';
            document.getElementById('appContainer').classList.remove('panel-open');
            localStorage.setItem('panel-open', 'false');
            localStorage.removeItem('last-played-file');
            if (!audio.paused) {
                audio.pause();
            }
            step = 'start';
            updateUI();
        }

        // Library Logic
        function toggleLibrary() {
            const container = document.getElementById('appContainer');
            const isOpen = container.classList.toggle('library-open');
            localStorage.setItem('library-open', isOpen);
            if (isOpen) loadLibrary();
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

                // Pre-process files to calculate progress and completion status
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

                // Sort: Not completed first (by mtime desc), then completed (by mtime desc)
                data.files.sort((a, b) => {
                    if (a.isCompleted === b.isCompleted) {
                        return b.mtime - a.mtime; // Newest first
                    }
                    return a.isCompleted ? 1 : -1; // Completed goes to bottom
                });

                listDiv.innerHTML = data.files.map(f => {
                    const date = new Date(f.mtime * 1000).toLocaleDateString();
                    const isActive = playerState.fileName === f.name ? 'active-lib' : '';
                    const completedClass = f.isCompleted ? 'completed-book' : '';

                    return `
                        <div class="library-item ${isActive} ${completedClass}" onclick="playFromLibrary('${f.name.replace(/'/g, "\\'")}', true, true)">
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

        function playFromLibrary(fileName, autoPlay = true, keepPanels = false) {
            if (playerState.fileName === fileName && autoPlay) {
                togglePlay();
                return;
            }
            if (!keepPanels) {
                resetForm(); // Hide download UI and potentially close panels if not keeping them
            } else {
                // Just hide the download-specific parts but keep panels
                document.getElementById('optGroup').style.display = 'none';
                document.getElementById('chaptersBox').style.display = 'none';
                document.getElementById('status').style.display = 'none';
            }
            
            // Re-ensure persistence isn't wiped if we want to keep it
            localStorage.setItem('last-played-file', fileName);
            
            step = 'done';
            document.getElementById('mainBtn').innerText = i18n[currentLang].btnAgain;
            initPlayer(fileName);
            
            if (autoPlay) {
                setTimeout(() => {
                    audio.play();
                    document.getElementById('playBtn').innerText = '⏸';
                }, 500);
            }
        }

        function resetBookProgress(event, fileName) {
            event.stopPropagation();
            const t = i18n[currentLang];
            if (confirm(t.confirmReset)) {
                localStorage.removeItem('bookmark_' + fileName);
                // If this is the currently playing book, reset player time
                if (playerState.fileName === fileName) {
                    audio.currentTime = 0;
                    document.getElementById('timelineFill').style.width = '0%';
                }
                loadLibrary(); // Refresh list to show it's done (optional visual feedback)
            }
        }

        async function fetchInfo() {
            const url = document.getElementById('urlInput').value.trim();
            if(!url) return;
            const btn = document.getElementById('mainBtn');
            const statusDiv = document.getElementById('status');
            const chaptersBox = document.getElementById('chaptersBox');
            const chaptersList = document.getElementById('chaptersList');
            
            btn.disabled = true;
            statusDiv.style.display = 'block';
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
                        <div class="chapter-item">
                            <span class="chapter-title">${i+1}. ${c.title}</span>
                        </div>
                    `).join('');
                    chaptersBox.style.display = 'block';
                    statusDiv.style.display = 'none';
                } else {
                    statusDiv.innerText = i18n[currentLang].noChapters;
                }
                step = 'confirm'; 
                updateUI();
            } catch(e) { 
                statusDiv.innerText = 'Error: ' + e.message;
                statusDiv.style.color = 'var(--error)';
            } finally { 
                btn.disabled = false; 
            }
        }

        async function startDownload() {
            const url = document.getElementById('urlInput').value.trim();
            if(!url) return;
            document.getElementById('mainBtn').disabled = true;
            document.getElementById('downloadLink').style.display = 'none';
            document.getElementById('chaptersBox').style.display = 'none';
            document.getElementById('optGroup').style.display = 'none';
            document.getElementById('pbox').style.display = 'block';
            document.getElementById('pbox').classList.remove('merging-mode');
            const statusDiv = document.getElementById('status');
            statusDiv.style.display = 'block';
            statusDiv.innerText = i18n[currentLang].statusInit;
            
            try {
                const res = await fetch('/api/download', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({url, mode: currentMode}) });
                const data = await res.json();
                poll(data.task_id);
            } catch(e) { alert(e); document.getElementById('mainBtn').disabled = false; }
        }

        let playerState = {
            mode: 'single', // 'single', 'm4b', 'zip'
            duration: 0,
            chapters: [], // For m4b/mp3
            playlist: [], // For zip
            currentTrackIndex: 0,
            fileName: null,
            bookTitle: ""
        };

        const audio = document.getElementById('audioElement');

        audio.addEventListener('timeupdate', () => {
            if(!playerState.duration) return;
            const pct = (audio.currentTime / playerState.duration) * 100;
            document.getElementById('timelineFill').style.width = pct + '%';
            document.getElementById('timeCurrent').innerText = formatTime(audio.currentTime);
            
            // Update current chapter text and progress fills
            if (playerState.mode === 'zip' && playerState.playlist.length > 0) {
                const track = playerState.playlist[playerState.currentTrackIndex];
                document.getElementById('playerChapter').innerText = `${playerState.currentTrackIndex + 1} / ${playerState.playlist.length}: ${track.title}`;
            } else if(playerState.chapters.length > 0) {
                const currentChIndex = playerState.chapters.findIndex(c => audio.currentTime >= c.start && audio.currentTime < c.end);
                const safeCurrentChIndex = currentChIndex !== -1 ? currentChIndex : 0;
                
                document.getElementById('playerChapter').innerText = playerState.chapters[safeCurrentChIndex].title;
                
                // Update background fills and times if panel is open
                const container = document.getElementById('appContainer');
                if (container.classList.contains('panel-open')) {
                    playerState.chapters.forEach((ch, idx) => {
                        const fillEl = document.getElementById(`ch-fill-${idx}`);
                        const timeEl = document.getElementById(`ch-time-${idx}`);
                        if (fillEl) {
                            if (idx < safeCurrentChIndex) {
                                fillEl.style.width = '100%';
                                if (timeEl) timeEl.innerText = formatTime(ch.start);
                            } else if (idx > safeCurrentChIndex) {
                                fillEl.style.width = '0%';
                                if (timeEl) timeEl.innerText = formatTime(ch.start);
                            } else {
                                const dur = ch.end - ch.start;
                                const fillPct = dur > 0 ? ((audio.currentTime - ch.start) / dur) * 100 : 0;
                                fillEl.style.width = `${Math.max(0, Math.min(100, fillPct))}%`;
                                
                                if (timeEl) {
                                    const elapsed = Math.max(0, audio.currentTime - ch.start);
                                    timeEl.innerText = `${formatTime(elapsed)} / ${formatTime(dur)}`;
                                }
                                
                                // Active class
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
            
            // Save bookmark with duration for library progress
            if(playerState.fileName) {
                const bmk = {
                    time: audio.currentTime,
                    duration: audio.duration,
                    track: playerState.currentTrackIndex
                };
                localStorage.setItem('bookmark_' + playerState.fileName, JSON.stringify(bmk));
            }
        });

        audio.addEventListener('loadedmetadata', () => {
            playerState.duration = audio.duration;
            document.getElementById('timeTotal').innerText = formatTime(audio.duration);
            
            // Draw chapter markers now that we have accurate duration
            if (playerState.mode === 'm4b' && playerState.chapters.length > 0) {
                const markersHtml = playerState.chapters.map(ch => {
                    const leftPct = (ch.start / audio.duration) * 100;
                    return `<div class="timeline-marker" style="left: ${leftPct}%;" title="${ch.title}"></div>`;
                }).join('');
                document.getElementById('markersContainer').innerHTML = markersHtml;
            }
            
            // Restore bookmark ONLY if we just loaded the file manually (not auto-playing next track)
            if(playerState.fileName && !audio.autoplay) {
                try {
                    const saved = JSON.parse(localStorage.getItem('bookmark_' + playerState.fileName));
                    if(saved && saved.time) audio.currentTime = Math.max(0, Math.min(audio.duration, parseFloat(saved.time)));
                } catch(e) {}
            }
        });

        audio.addEventListener('ended', () => {
            if (playerState.mode === 'zip' && playerState.currentTrackIndex < playerState.playlist.length - 1) {
                // Play next track in ZIP
                playerState.currentTrackIndex++;
                playCurrentTrack(true);
            } else {
                document.getElementById('playBtn').innerText = '▶';
                syncLibraryPlayIcons();
            }
        });

        audio.addEventListener('play', () => {
            document.getElementById('playBtn').innerText = '⏸';
            syncLibraryPlayIcons();
        });

        audio.addEventListener('pause', () => {
            document.getElementById('playBtn').innerText = '▶';
            syncLibraryPlayIcons();
        });

        function syncLibraryPlayIcons() {
            // Reset all icons first
            document.querySelectorAll('.library-item-play').forEach(el => el.innerText = '▶');
            // If playing, find the current one
            if (!audio.paused && playerState.fileName) {
                const id = "lib-play-" + playerState.fileName.replace(/'/g, "\\'").replace(/\s+/g, '-');
                const el = document.getElementById(id);
                if (el) el.innerText = '⏸';
            }
        }

        function togglePlay() {
            if (audio.paused) {
                audio.play();
                document.getElementById('playBtn').innerText = '⏸';
            } else {
                audio.pause();
                document.getElementById('playBtn').innerText = '▶';
            }
        }

        function seekRelative(seconds) {
            audio.currentTime = Math.max(0, Math.min(audio.duration || 0, audio.currentTime + seconds));
        }

        function seek(event) {
            if(!playerState.duration) return;
            const timeline = document.getElementById('timeline');
            const rect = timeline.getBoundingClientRect();
            const pos = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
            audio.currentTime = pos * playerState.duration;
        }

        function formatTime(secs) {
            if(isNaN(secs)) return "00:00:00";
            const h = Math.floor(secs / 3600);
            const m = Math.floor((secs % 3600) / 60);
            const s = Math.floor(secs % 60);
            return [h, m, s].map(v => v.toString().padStart(2, '0')).join(':');
        }

        // Chapters Modal Logic
        function toggleChaptersModal() {
            const container = document.getElementById('appContainer');
            const isOpen = container.classList.toggle('panel-open');
            localStorage.setItem('panel-open', isOpen);
            if (isOpen) renderPlayerChapters();
        }

        function renderPlayerChapters() {
            const listDiv = document.getElementById('playerChaptersList');
            const t = i18n[currentLang];
            
            if (playerState.mode === 'zip') {
                if (!playerState.playlist || playerState.playlist.length === 0) {
                    listDiv.innerHTML = `<div class="empty-lib">${t.noChaptersInPanel}</div>`;
                    return;
                }
                listDiv.innerHTML = playerState.playlist.map((track, idx) => {
                    const isActive = idx === playerState.currentTrackIndex ? 'active-ch' : '';
                    return `
                        <div class="chapter-list-item ${isActive}" onclick="jumpToTrack(${idx})">
                            <span>${idx + 1}. ${track.title}</span>
                        </div>
                    `;
                }).join('');
            } else {
                if (!playerState.chapters || playerState.chapters.length === 0) {
                    listDiv.innerHTML = `<div class="empty-lib">${t.noChaptersInPanel}</div>`;
                    return;
                }
                
                const currentChIndex = playerState.chapters.findIndex(c => audio.currentTime >= c.start && audio.currentTime < c.end);
                const safeCurrentChIndex = currentChIndex !== -1 ? currentChIndex : 0;

                listDiv.innerHTML = playerState.chapters.map((ch, idx) => {
                    const isActive = idx === safeCurrentChIndex ? 'active-ch' : '';
                    let fillPct = 0;
                    let timeText = formatTime(ch.start);
                    
                    if (idx < safeCurrentChIndex) fillPct = 100;
                    else if (idx === safeCurrentChIndex) {
                        const dur = ch.end - ch.start;
                        if (dur > 0) {
                            fillPct = ((audio.currentTime - ch.start) / dur) * 100;
                            const elapsed = Math.max(0, audio.currentTime - ch.start);
                            timeText = `${formatTime(elapsed)} / ${formatTime(dur)}`;
                        }
                    }
                    
                    return `
                        <div class="chapter-list-item ${isActive}" onclick="handleChapterClick(event, ${idx})" id="ch-item-${idx}">
                            <div class="chapter-bg-fill" id="ch-fill-${idx}" style="width: ${fillPct}%"></div>
                            <div class="chapter-content">
                                <span>${idx + 1}. ${ch.title}</span>
                                <span id="ch-time-${idx}" style="font-family: monospace; font-size: 0.8rem;">${timeText}</span>
                            </div>
                        </div>
                    `;
                }).join('');
            }
            
            // Scroll to active chapter
            setTimeout(() => {
                const activeEl = listDiv.querySelector('.active-ch');
                if(activeEl) activeEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 100);
        }

        function jumpToChapter(startTime) {
            audio.currentTime = startTime;
            if (audio.paused) togglePlay();
        }

        function handleChapterClick(event, idx) {
            const ch = playerState.chapters[idx];
            if (!ch) return;

            const rect = event.currentTarget.getBoundingClientRect();
            const clickX = event.clientX - rect.left;
            
            // If the user clicked on the very far right (e.g. on the time text), maybe just start the chapter? 
            // Better yet, just calculate exact position.
            const percentage = Math.max(0, Math.min(1, clickX / rect.width));
            
            const dur = ch.end - ch.start;
            const newTime = ch.start + (dur * percentage);
            
            audio.currentTime = newTime;
            if (audio.paused) togglePlay();
            
            // We don't close the modal automatically here, so they can keep clicking to find the right spot
        }

        function jumpToTrack(index) {
            playerState.currentTrackIndex = index;
            playCurrentTrack(true);
            toggleChaptersModal();
        }

        function playCurrentTrack(autoplay = false) {
            if (playerState.playlist.length === 0) return;
            const track = playerState.playlist[playerState.currentTrackIndex];
            // Fix URI encoding for file paths
            const parts = track.file.split('/');
            const encodedPath = parts.map(p => encodeURIComponent(p)).join('/');
            
            audio.src = '/api/files/' + encodedPath;
            audio.autoplay = autoplay;
            audio.load();
            if (autoplay) {
                document.getElementById('playBtn').innerText = '⏸';
            }
            document.getElementById('playerChapter').innerText = `${playerState.currentTrackIndex + 1} / ${playerState.playlist.length}: ${track.title}`;
        }

        async function initPlayer(fileName) {
            playerState.fileName = fileName;
            playerState.chapters = [];
            playerState.playlist = [];
            playerState.currentTrackIndex = 0;
            playerState.mode = 'single';
            
            document.getElementById('markersContainer').innerHTML = '';
            document.getElementById('playerBox').style.display = 'block';
            document.getElementById('playerTitle').innerText = fileName;
            document.getElementById('playerChapter').innerText = '';
            document.getElementById('playBtn').innerText = '▶';
            audio.autoplay = false;

            // Try loading bookmark
            let savedBmk = null;
            try {
                const rawBmk = localStorage.getItem('bookmark_' + fileName);
                if (rawBmk && !rawBmk.startsWith('{')) {
                    savedBmk = { time: parseFloat(rawBmk), track: 0 };
                } else if (rawBmk) {
                    savedBmk = JSON.parse(rawBmk);
                }
            } catch(e) { 
                console.warn('Invalid bookmark format, clearing...', e);
                localStorage.removeItem('bookmark_' + fileName);
            }

            try {
                const res = await fetch('/api/metadata/' + encodeURIComponent(fileName) + '?t=' + Date.now());
                if(res.ok) {
                    const meta = await res.json();
                    if(meta.title) {
                        playerState.bookTitle = meta.title;
                        document.getElementById('playerTitle').innerText = meta.title;
                    }
                    
                    if (meta.mode === 'zip' && meta.playlist) {
                        playerState.mode = 'zip';
                        playerState.playlist = meta.playlist;
                        
                        // Validate track index from bookmark
                        if (savedBmk && (savedBmk.track < 0 || savedBmk.track >= meta.playlist.length)) {
                            console.warn('Bookmark track index out of bounds, resetting to 0');
                            savedBmk.track = 0;
                            savedBmk.time = 0;
                        }
                        
                        playerState.currentTrackIndex = (savedBmk && savedBmk.track !== undefined) ? savedBmk.track : 0;
                        playCurrentTrack(false);
                        
                        // Apply time bookmark for zip if exists
                        if (savedBmk && savedBmk.time) {
                            audio.addEventListener('loadedmetadata', function onMeta() {
                                // Clamp time just in case
                                audio.currentTime = Math.max(0, Math.min(audio.duration || 0, parseFloat(savedBmk.time)));
                                audio.removeEventListener('loadedmetadata', onMeta);
                            });
                        }
                        // Refresh panel if open
                        if (document.getElementById('appContainer').classList.contains('panel-open')) renderPlayerChapters();
                        return;
                    } else if(meta.chapters && meta.chapters.length > 0) {
                        playerState.mode = 'm4b';
                        playerState.chapters = meta.chapters;
                        // Refresh panel if open
                        if (document.getElementById('appContainer').classList.contains('panel-open')) renderPlayerChapters();
                    }
                }
            } catch(e) { console.log('No metadata found', e); }

            // Default fallback for single/m4b
            audio.src = '/api/files/' + encodeURIComponent(fileName);
            audio.load();
            
            if (savedBmk && savedBmk.time) {
                audio.addEventListener('loadedmetadata', function onMeta() {
                    audio.currentTime = Math.max(0, Math.min(audio.duration || 0, parseFloat(savedBmk.time)));
                    audio.removeEventListener('loadedmetadata', onMeta);
                });
            }
        }

        function poll(id) {
            const eventSource = new EventSource('/api/progress/stream/' + id);

            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                const t = i18n[currentLang];
                const statusDiv = document.getElementById('status');

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
                    document.getElementById('bar').style.width = '100%';
                    document.getElementById('perc').innerText = '100.000%';
                } else if(data.status === 'success') {
                    eventSource.close();
                    statusDiv.innerText = t.statusDone;
                    document.getElementById('pbox').classList.remove('assembling-mode');
                    document.getElementById('bar').style.width = '100%';
                    document.getElementById('perc').innerText = '100.000%';
                    document.getElementById('downloadLink').href = '/api/files/' + data.file_name;
                    document.getElementById('downloadLink').style.display = 'block';
                    document.getElementById('mainBtn').disabled = false;
                    document.getElementById('mainBtn').innerText = t.btnAgain;
                    step = 'done';

                    // Initialize the integrated player
                    initPlayer(data.file_name);
                } else if(data.status === 'error' || data.status === 'not_found') {
                    eventSource.close();
                    statusDiv.innerText = "Error occurred";
                    document.getElementById('mainBtn').disabled = false;
                    document.getElementById('mainBtn').innerText = "Try Again";
                }
            };

            eventSource.onerror = function() {
                eventSource.close();
            };
        }