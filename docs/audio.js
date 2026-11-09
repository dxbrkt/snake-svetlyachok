/* Native media decoding keeps audio independent of the WebAssembly game loop. */
(() => {
    const audio = new Audio();
    audio.preload = 'auto';
    let tracks = [], buttons = {}, wanted = false, suspended = false, revision = 0;
    const radio = window.snakeRadio = {
        index: 0,
        error: false,
        get playing() { return !audio.paused && !audio.ended; },
        get position() { return audio.currentTime || 0; },
        configure(config) {
            const data = JSON.parse(config);
            tracks = data.tracks;
            buttons = data.buttons;
            audio.volume = data.volume;
            audio.src = tracks[0];
        },
        play() {
            wanted = true;
            if (suspended || document.hidden) return;
            const request = ++revision;
            radio.error = false;
            audio.play().catch(error => {
                if (request !== revision || error.name === 'AbortError') return;
                radio.error = true;
                wanted = false;
            });
        },
        pause() {
            wanted = false;
            ++revision;
            audio.pause();
        },
        toggle() { wanted ? radio.pause() : radio.play(); },
        change(step) {
            ++revision;
            audio.pause();
            radio.index = (radio.index + step + tracks.length) % tracks.length;
            audio.src = tracks[radio.index];
            radio.play();
        },
        setVolume(value) { audio.volume = Math.max(0, Math.min(1, value)); },
    };
    function suspend() {
        suspended = true;
        ++revision;
        audio.pause();
    }
    function resume() {
        if (document.hidden) return;
        suspended = false;
        if (wanted) radio.play();
    }
    audio.addEventListener('ended', () => { if (wanted) radio.change(1); });
    audio.addEventListener('error', () => { radio.error = true; });
    document.addEventListener('visibilitychange', () => document.hidden ? suspend() : resume());
    window.addEventListener('blur', suspend);
    window.addEventListener('focus', resume);
    window.addEventListener('pagehide', suspend);
    window.addEventListener('pageshow', resume);
    // The timeout runs only after a blocking close confirmation is dismissed.
    window.addEventListener('beforeunload', () => {
        suspend();
        setTimeout(resume, 0);
    }, {capture: true});
    // Run playback in the actual browser gesture, before Python receives input.
    document.addEventListener('pointerdown', event => {
        if (event.button !== 0 || event.target.tagName !== 'CANVAS' || !tracks.length) return;
        const rect = event.target.getBoundingClientRect();
        const x = (event.clientX - rect.left) * 1280 / rect.width;
        const y = (event.clientY - rect.top) * 720 / rect.height;
        for (const [name, [bx, by, bw, bh]] of Object.entries(buttons)) {
            if (x >= bx && x < bx + bw && y >= by && y < by + bh) {
                suspended = false;
                if (name === 'play') radio.toggle();
                else radio.change(name === 'previous' ? -1 : 1);
                break;
            }
        }
    }, {capture: true});
    document.addEventListener('keydown', event => {
        if (!tracks.length || event.repeat || event.ctrlKey || event.metaKey || event.altKey) return;
        if (['INPUT', 'TEXTAREA'].includes(event.target.tagName) || event.target.isContentEditable) return;
        if (event.code === 'KeyM') radio.toggle();
        else if (event.code === 'BracketLeft') radio.change(-1);
        else if (event.code === 'BracketRight') radio.change(1);
    }, {capture: true});
})();

// Best score survives reloads; disabled storage must never prevent playing.
(() => {
    let best = 0;
    try {
        const stored = Number(localStorage.getItem('snake.endless.best'));
        if (Number.isSafeInteger(stored) && stored >= 0) best = stored;
    } catch (_) {}
    window.snakeScores = {
        get best() { return best; },
        save(score) {
            if (!Number.isSafeInteger(score) || score <= best) return;
            best = score;
            try { localStorage.setItem('snake.endless.best', String(best)); } catch (_) {}
        },
    };
})();

// Cosmetic choices and the village achievement are independent of audio.
(() => {
    let villageWon = false, selected = 'classic';
    try {
        const stored = JSON.parse(localStorage.getItem('snake.wardrobe') || '{}');
        villageWon = stored?.villageWon === true;
        selected = typeof stored?.selected === 'string' ? stored.selected : 'classic';
    } catch (_) {}
    function unlocked(skin) {
        return ['classic', 'berry'].includes(skin) ||
            (skin === 'firefly' && villageWon) ||
            (skin === 'dragon' && window.snakeScores.best >= 24);
    }
    if (!unlocked(selected)) selected = 'classic';
    function persist() {
        try { localStorage.setItem('snake.wardrobe', JSON.stringify({villageWon, selected})); } catch (_) {}
    }
    window.snakeWardrobe = {
        get selected() { return selected; },
        get villageWon() { return villageWon; },
        select(skin) { if (unlocked(skin)) { selected = skin; persist(); } },
        winVillage() { villageWon = true; persist(); },
    };
})();
