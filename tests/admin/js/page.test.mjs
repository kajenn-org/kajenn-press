import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';
import {webcrypto} from 'node:crypto';
const text = await readFile(new URL('../../../src/kajenn_press/admin/pages/page.js', import.meta.url), 'utf8');
const {Logic} = await import('data:text/javascript;base64,' + Buffer.from(text).toString('base64'));
globalThis.crypto ??= webcrypto;
globalThis.window = {addEventListener() {}, removeEventListener() {}};
window.parent = window;
const published = [];
globalThis.gramlot = {publish: (target, payload) => published.push({target, payload})};

function fixture(call) {
    const values = new Map(Object.entries({
        'page.declarations': JSON.stringify({intro: {format: 'html', required: true},
            notes: {format: 'markdown', required: false}}),
        'page.variant_id': 'v', 'page.variant_generation': 1, 'page.variant_revision': 'vr1',
        'page.template_revision': 'tr', 'page.template_id': 't', 'page.content_id': 'c',
        'page.busy': false, 'page.load_revision': '', 'page.new_language': 'en',
        'draft.blocks.intro': '<p>Saved</p>', 'draft.blocks.notes': '# Saved'
    }));
    // Like the Gramlot renderer, only the rendered pane accepts dispose callbacks.
    const pane = {};
    const node = {GET: key => values.get(key), SET: (key, value) => values.set(key, value), parentNode: pane};
    const logic = new Logic();
    logic.page = {rpc: {call}, src: {renderer: {onDispose: (target, _fn) => {
        if (target !== pane) throw new Error('Source node is not mounted');
    }}}};
    return {logic, node};
}
const rendered = html => ({ok: true, result: {status: 'succeeded', html, diagnostics: []}});

test('save sends every block with its format and the variant generation', async () => {
    const calls = [];
    const {logic, node} = fixture(async (_type, _name, args) => {
        calls.push(structuredClone(args));
        if (args.operation === 'render_draft') return rendered('initial');
        return {ok: true, result: {records: [{record_id: 'v', revision_id: 'vr2', generation: 2}]}};
    });
    logic.initialize(node, {});
    node.SET('draft.blocks.notes', '# Edited');
    logic.changed(node, {});
    assert.equal(node.GET('page.dirty'), true);
    await logic.save(node, {});
    const save = calls.find(c => c.operation === 'draft_save').arguments;
    assert.equal(save.expected_generation, 1);
    assert.deepEqual(save.blocks, {intro: {format: 'html', source: '<p>Saved</p>'},
        notes: {format: 'markdown', source: '# Edited'}});
    assert.equal(node.GET('page.variant_generation'), 2);
    assert.equal(node.GET('page.variant_revision'), 'vr2');
    assert.equal(node.GET('page.dirty'), false);
});

test('a conflict keeps the draft; revert restores the saved revision', async () => {
    const {logic, node} = fixture(async (_type, _name, args) => {
        if (args.operation === 'render_draft') return rendered('initial');
        return {ok: false, error: {code: 'conflict', message: 'Newer revision exists.'}};
    });
    logic.initialize(node, {});
    node.SET('draft.blocks.intro', '<p>Mine</p>');
    await logic.save(node, {});
    assert.equal(node.GET('draft.blocks.intro'), '<p>Mine</p>');
    assert.match(node.GET('page.message'), /Newer revision exists\. Your draft is preserved\./);
    assert.equal(logic.pageState.pending, null);
    logic.revert(node, {});
    assert.equal(node.GET('draft.blocks.intro'), '<p>Saved</p>');
    assert.equal(node.GET('page.dirty'), false);
});

test('live preview renders all unsaved blocks and keeps only the latest reply', async () => {
    const calls = [], replies = [];
    const {logic, node} = fixture((_type, _name, args) => {
        calls.push(structuredClone(args));
        return new Promise(resolve => replies.push(resolve));
    });
    logic.initialize(node, {});
    node.SET('draft.blocks.intro', '<p>Later</p>');
    const latest = logic.livePreview(node, {});
    assert.deepEqual(calls[1].arguments, {variant_id: 'v', revision_id: 'vr1',
        blocks: {intro: '<p>Later</p>', notes: '# Saved'}, resources: {}});
    replies[1](rendered('latest'));
    await latest;
    replies[0](rendered('initial'));
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(node.GET('page.preview'), 'latest');
});

test('loading a revision fills the draft; open template asks the shell; add language translates', async () => {
    const calls = [];
    const {logic, node} = fixture(async (_type, name, args) => {
        calls.push({name, args: structuredClone(args)});
        if (name === 'read') return {generation: 1, sources: {'block.intro': {text: '<p>Old</p>'}}};
        if (args.operation === 'render_draft') return rendered('initial');
        return {ok: true, result: {records: [{record_id: 'v2'}]}};
    });
    logic.initialize(node, {});
    node.SET('page.load_revision', 'vr0');
    await logic.loadRevision(node, {});
    assert.equal(node.GET('draft.blocks.intro'), '<p>Old</p>');
    assert.equal(node.GET('draft.blocks.notes'), '');
    assert.equal(node.GET('page.dirty'), true);
    logic.openTemplate(node, {});
    assert.deepEqual(published.at(-1), {target: {topic: 'open_object', parent: true},
        payload: {kind: 'template', record_id: 't'}});
    await logic.addLanguage(node, {});
    const created = calls.find(c => c.args.operation === 'variant_create').args.arguments;
    assert.equal(created.language, 'en');
    assert.equal(created.translated_from, 'vr1');
    assert.equal(node.GET('page.language'), 'en');
});

test('use latest template keeps matching blocks and reloads the editor', async () => {
    const calls = [];
    const {logic, node} = fixture(async (_type, _name, args) => {
        calls.push(structuredClone(args));
        if (args.operation === 'render_draft') return rendered('initial');
        return {ok: true, result: {records: [{record_id: 'v', revision_id: 'vr2', generation: 2}]}};
    });
    // The latest template keeps intro, turns notes into HTML and adds an aside.
    node.SET('page.latest_template', 'tr2');
    node.SET('page.latest_declarations', JSON.stringify({intro: {format: 'html', required: true},
        notes: {format: 'html', required: false}, aside: {format: 'markdown', required: false}}));
    node.SET('page.version', 0);
    logic.initialize(node, {});
    await logic.useLatestTemplate(node, {});
    const save = calls.find(c => c.operation === 'draft_save').arguments;
    assert.equal(save.template_revision, 'tr2');
    assert.deepEqual(save.blocks, {intro: {format: 'html', source: '<p>Saved</p>'}});
    assert.equal(node.GET('page.version'), 1);
});
