const savedLibWidth = localStorage.getItem('lib-width');
const savedChapWidth = localStorage.getItem('chap-width');
const savedMainWidth = localStorage.getItem('main-width');
const panelPrefs = {
    lib: parseInt(savedLibWidth, 10) || 450,
    chap: parseInt(savedChapWidth, 10) || 350,
    main: parseInt(savedMainWidth, 10) || 450
};

function getContainerInnerWidth(container) {
    const styles = getComputedStyle(container);
    const paddingX = (parseFloat(styles.paddingLeft) || 0) + (parseFloat(styles.paddingRight) || 0);
    return Math.max(0, container.clientWidth - paddingX);
}

function syncResponsivePanelWidths() {
    const root = document.documentElement;
    const container = document.getElementById('appContainer');
    if (!container) {
        root.style.setProperty('--lib-width', panelPrefs.lib + 'px');
        root.style.setProperty('--chap-width', panelPrefs.chap + 'px');
        root.style.setProperty('--main-width', panelPrefs.main + 'px');
        return;
    }

    const visibleWidths = [];
    if (container.classList.contains('library-open')) {
        visibleWidths.push(['lib', panelPrefs.lib]);
    }
    visibleWidths.push(['main', panelPrefs.main]);
    if (container.classList.contains('panel-open')) {
        visibleWidths.push(['chap', panelPrefs.chap]);
    }

    const gap = parseFloat(getComputedStyle(container).gap) || 0;
    const availableWidth = getContainerInnerWidth(container) - Math.max(0, visibleWidths.length - 1) * gap;
    const preferredTotal = visibleWidths.reduce((sum, [, width]) => sum + width, 0);
    const scale = preferredTotal > 0 && availableWidth > 0 && preferredTotal > availableWidth
        ? availableWidth / preferredTotal
        : 1;

    root.style.setProperty('--lib-width', Math.round(panelPrefs.lib * scale) + 'px');
    root.style.setProperty('--chap-width', Math.round(panelPrefs.chap * scale) + 'px');
    root.style.setProperty('--main-width', Math.round(panelPrefs.main * scale) + 'px');
}

syncResponsivePanelWidths();

function setMode(mode) {
    appState.currentMode = mode;
    localStorage.setItem('mode', mode);
    ['m4b', 'mp3', 'zip'].forEach(m => document.getElementById('mode-' + m).classList.toggle('active', m === mode));
    updateUI();
}

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

    startMainW = panelPrefs.main;

    if (edge === 'main-left' || edge === 'library') {
        resizeEdge = 'library';
        startSideW = panelPrefs.lib;
    } else if (edge === 'main-right' || edge === 'chapters') {
        resizeEdge = 'chapters';
        startSideW = panelPrefs.chap;
    }

    document.body.classList.add('is-resizing');
    document.addEventListener('mousemove', handleResize);
    document.addEventListener('mouseup', stopResize);
}

function handleResize(e) {
    if (!isResizing) return;
    const delta = e.clientX - startX;
    const container = document.getElementById('appContainer');

    if (resizeEdge === 'library') {
        let newMainW = startMainW - delta;
        newMainW = Math.max(280, newMainW);
        panelPrefs.main = newMainW;

        if (container.classList.contains('library-open')) {
            let newLibW = startSideW + delta;
            newLibW = Math.max(220, newLibW);
            panelPrefs.lib = newLibW;
        }
    } else if (resizeEdge === 'chapters') {
        let newMainW = startMainW + delta;
        newMainW = Math.max(280, newMainW);
        panelPrefs.main = newMainW;

        if (container.classList.contains('panel-open')) {
            let newChapW = startSideW - delta;
            newChapW = Math.max(220, newChapW);
            panelPrefs.chap = newChapW;
        }
    }

    syncResponsivePanelWidths();
}

function stopResize() {
    if (!isResizing) return;
    isResizing = false;
    document.body.classList.remove('is-resizing');
    document.removeEventListener('mousemove', handleResize);
    document.removeEventListener('mouseup', stopResize);

    localStorage.setItem('main-width', Math.round(panelPrefs.main));
    localStorage.setItem('lib-width', Math.round(panelPrefs.lib));
    localStorage.setItem('chap-width', Math.round(panelPrefs.chap));
    resizeEdge = null;
    syncResponsivePanelWidths();
    schedulePlayerLayoutSync();
}
