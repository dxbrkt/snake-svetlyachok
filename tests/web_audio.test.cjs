const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function setup() {
    class Target {
        listeners = {};
        addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
        emit(name, event = {}) { for (const fn of this.listeners[name] || []) fn(event); }
    }
    let audio;
    class Audio extends Target {
        paused = true; ended = false; currentTime = 0;
        constructor() { super(); audio = this; }
        play() { this.paused = false; return this.reject ? Promise.reject(this.reject) : Promise.resolve(); }
        pause() { this.paused = true; }
        set src(value) { this.url = value; this.currentTime = 0; }
    }
    const window = new Target(), document = new Target(), timers = [];
    document.hidden = false;
    vm.runInNewContext(fs.readFileSync('web/audio.js', 'utf8'), {
        window, document, Audio, setTimeout: callback => timers.push(callback),
    });
    const radio = window.snakeRadio;
    radio.configure(JSON.stringify({tracks: ['a.ogg', 'b.ogg', 'c.ogg'], volume: .55,
        buttons: {play: [1153, 437, 48, 50]}}));
    return {window, document, radio, audio, timers};
}
test('first canvas gesture plays immediately and uses scaled coordinates', () => {
    const {document, radio} = setup();
    document.emit('pointerdown', {button: 0, clientX: 588, clientY: 230,
        target: {tagName: 'CANVAS', getBoundingClientRect: () => ({left: 0, top: 0, width: 640, height: 360})}});
    assert.equal(radio.playing, true);
});
test('hidden tab pauses, return preserves position, user pause stays paused', () => {
    const {document, window, radio, audio} = setup();
    radio.play(); audio.currentTime = 23;
    document.hidden = true; document.emit('visibilitychange');
    assert.equal(radio.playing, false);
    document.hidden = false; document.emit('visibilitychange'); window.emit('focus');
    assert.equal(radio.playing, true); assert.equal(radio.position, 23);
    radio.pause(); window.emit('blur'); window.emit('focus');
    assert.equal(radio.playing, false);
});
test('close dialog pauses synchronously and cancellation resumes', () => {
    const {window, radio, timers, audio} = setup();
    radio.play(); audio.currentTime = 42;
    window.emit('beforeunload'); assert.equal(radio.playing, false);
    timers.shift()(); assert.equal(radio.playing, true); assert.equal(radio.position, 42);
    window.emit('pagehide'); assert.equal(radio.playing, false);
});
test('playlist advances on ended, wraps, and ignores ended after pause', () => {
    const {radio, audio} = setup();
    radio.play(); audio.emit('ended'); assert.equal(radio.index, 1);
    radio.change(-1); radio.change(-1); assert.equal(radio.index, 2);
    audio.emit('ended'); assert.equal(radio.index, 0);
    radio.pause(); audio.emit('ended'); assert.equal(radio.index, 0);
});
test('blocked playback reports failure, stale rejection cannot override new track', async () => {
    const {radio, audio} = setup();
    audio.reject = {name: 'NotAllowedError'};
    radio.play(); await Promise.resolve(); assert.equal(radio.error, true);
    radio.play(); audio.reject = null; radio.change(1);
    await Promise.resolve(); assert.equal(radio.error, false); assert.equal(radio.playing, true);
});

test('record survives reload, rejects malformed data, tolerates blocked storage', () => {
    const saved = new Map();
    const storage = {getItem: key => saved.get(key) ?? null,
        setItem: (key, value) => saved.set(key, value)};
    const code = fs.readFileSync('web/audio.js', 'utf8').split('// Best score survives reloads;')[1];
    function reload(localStorage) {
        const context = {window: {}, localStorage};
        vm.runInNewContext('// Best score survives reloads;' + code, context);
        return context.window.snakeScores;
    }
    let scores = reload(storage);
    scores.save(23); scores.save(10);
    assert.equal(reload(storage).best, 23);
    saved.set('snake.endless.best', 'oops');
    assert.equal(reload(storage).best, 0);
    scores = reload({getItem() {throw Error('blocked');}, setItem() {throw Error('blocked');}});
    scores.save(12); assert.equal(scores.best, 12);
});
