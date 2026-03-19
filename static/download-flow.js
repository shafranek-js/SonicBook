function getValidatedBookUrl() {
    const url = document.getElementById('urlInput').value.trim();
    if (!/^https?:\/\/\S+$/i.test(url)) {
        setStatusMessage('Please enter a valid http(s) URL', 'error');
        return null;
    }
    return url;
}

async function handleAction() {
    if (appState.step === 'start') {
        if (appState.currentMode === 'm4b' || appState.currentMode === 'zip') {
            await fetchInfo();
        } else {
            await startDownload();
        }
    } else if (appState.step === 'confirm') {
        await startDownload();
    } else if (appState.step === 'done') {
        resetForm({ preservePlayer: true });
    }
}

function handleSecondaryAction() {
    if (!appState.playerReturnState) {
        return;
    }
    appState.showPlayer = true;
    appState.showPreview = false;
    appState.previewLoading = false;
    appState.showProgress = false;
    setChaptersPanelOpen(!!appState.playerReturnState.panelOpen);
    appState.playerReturnState = null;
    appState.step = 'done';
    updateUI();
    schedulePlayerLayoutSync();
}

function resetForm({ preservePlayer = false } = {}) {
    document.getElementById('urlInput').value = '';
    appState.showProgress = false;
    appState.showPreview = false;
    appState.previewLoading = false;
    clearStatusMessage();
    const container = document.getElementById('appContainer');
    const canPreservePlayer = preservePlayer && playerState.fileName && appState.showPlayer;
    if (canPreservePlayer) {
        appState.playerReturnState = {
            fileName: playerState.fileName,
            panelOpen: container.classList.contains('panel-open')
        };
        appState.showPlayer = false;
        container.classList.remove('panel-open');
        localStorage.setItem('panel-open', 'false');
    } else {
        appState.showPlayer = false;
        clearPlayerCover();
        container.classList.remove('panel-open');
        localStorage.setItem('panel-open', 'false');
        localStorage.removeItem('last-played-file');
        appState.playerReturnState = null;
    }
    if (!audio.paused) {
        audio.pause();
    }
    setPlayButtonState(false);
    appState.step = 'start';
    updateUI();
    syncResponsivePanelWidths();
    schedulePlayerLayoutSync();
}

async function fetchInfo() {
    const url = getValidatedBookUrl();
    if (!url) return;
    const btn = document.getElementById('mainBtn');
    const chaptersList = document.getElementById('chaptersList');
    btn.disabled = true;
    setStatusMessage(i18n[appState.currentLang].statusInit, 'info');
    chaptersList.innerHTML = renderSkeletonRows(5, true);
    appState.showPreview = true;
    appState.previewLoading = true;
    updateUI();
    try {
        const res = await fetch('/api/info', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({url})
        });
        if (!res.ok) throw new Error('Book info fetch failed');
        const data = await res.json();
        appState.previewLoading = false;
        if (data.chapters && data.chapters.length > 0) {
            chaptersList.innerHTML = data.chapters.map((c, i) => `
                <div class="chapter-item">
                    <span class="chapter-index timecode">${String(i + 1).padStart(2, '0')}</span>
                    <span class="chapter-title">${escapeHtml(c.title)}</span>
                </div>
            `).join('');
            appState.showPreview = true;
            clearStatusMessage();
        } else {
            appState.showPreview = false;
            setStatusMessage(i18n[appState.currentLang].noChapters, 'info');
        }
        if (data.cover) playerState.tempCoverUrl = data.cover;
        appState.step = 'confirm';
        updateUI();
    } catch (e) {
        appState.previewLoading = false;
        appState.showPreview = false;
        updateUI();
        setStatusMessage('Error: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

async function startDownload() {
    const url = getValidatedBookUrl();
    if (!url) return;
    document.getElementById('mainBtn').disabled = true;
    appState.showProgress = true;
    document.getElementById('pbox').classList.remove('merging-mode');
    updateUI();
    setStatusMessage(i18n[appState.currentLang].statusInit, 'info');
    try {
        const res = await fetch('/api/download', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({url, mode: appState.currentMode})
        });
        if (!res.ok) {
            let message = 'Download start failed';
            try {
                const payload = await res.json();
                if (payload && payload.detail) {
                    message = payload.detail;
                }
            } catch (e) {}
            throw new Error(message);
        }
        const data = await res.json();
        poll(data.task_id);
    } catch (e) {
        appState.showProgress = false;
        setStatusMessage('Error: ' + e.message, 'error');
        document.getElementById('mainBtn').disabled = false;
        updateUI();
    }
}

function poll(id) {
    const eventSource = new EventSource('/api/progress/stream/' + id);
    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data), t = i18n[appState.currentLang];
        if (data.status === 'processing' || data.status === 'merging') {
            setStatusMessage(data.status === 'merging' ? t.statusMerging : t.statusStreams, 'info');
            if (data.status === 'merging') document.getElementById('pbox').classList.add('merging-mode');
            document.getElementById('pbox').classList.remove('assembling-mode');
            document.getElementById('bar').style.width = data.percent + '%';
            document.getElementById('perc').innerText = data.percent.toFixed(3) + '%';
            document.getElementById('frag').innerText = `${data.current_frag}/${data.total_frags}`;
        } else if (data.status === 'assembling') {
            setStatusMessage(t.assemblingStatus, 'info');
            document.getElementById('pbox').classList.add('assembling-mode');
            document.getElementById('bar').style.width = '100%';
            document.getElementById('perc').innerText = '100.000%';
        } else if (data.status === 'success') {
            eventSource.close();
            setStatusMessage(t.statusDone, 'success');
            appState.showProgress = false;
            document.getElementById('pbox').classList.remove('assembling-mode');
            document.getElementById('bar').style.width = '100%';
            document.getElementById('perc').innerText = '100.000%';
            document.getElementById('mainBtn').disabled = false;
            document.getElementById('mainBtn').innerText = t.btnAgain;
            appState.step = 'done';
            updateUI();
            initPlayer(data.file_name);
        } else if (data.status === 'error' || data.status === 'not_found') {
            eventSource.close();
            appState.showProgress = false;
            setStatusMessage('Error occurred', 'error');
            document.getElementById('mainBtn').disabled = false;
            document.getElementById('mainBtn').innerText = 'Try Again';
            updateUI();
        }
    };
    eventSource.onerror = () => eventSource.close();
}
