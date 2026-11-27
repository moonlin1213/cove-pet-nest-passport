import test from 'node:test';
import assert from 'node:assert/strict';
import {openLocalRoom} from './pairing.mjs';

function browser({release = async () => {}, popup = true} = {}) {
  const events = [];
  const tab = {
    opener: 'installer',
    location: {replace: url => events.push(['navigate', url])},
    close: () => events.push(['close'])
  };
  return {events, tab, io: {
    openTab() { events.push(['open']); return popup ? tab : null; },
    async release() { events.push(['release']); await release(); },
    navigate: url => events.push(['same-tab', url])
  }};
}

test('opens the local pairing page only after the installer releases USB', async () => {
  let allow;
  const release = new Promise(resolve => {allow = resolve;});
  const {events, tab, io} = browser({release: () => release});
  const result = openLocalRoom('8767', io);
  assert.deepEqual(events, [['open'], ['release']]);
  assert.equal(tab.opener, null);
  allow();
  await result;
  assert.deepEqual(events.at(-1), ['navigate', 'http://127.0.0.1:8767/passport']);
});

test('supports a custom local port and a blocked new tab', async () => {
  const {events, io} = browser({popup: false});
  await openLocalRoom(' 18767 ', io);
  assert.deepEqual(events, [['open'], ['release'], ['same-tab', 'http://127.0.0.1:18767/passport']]);
});

test('rejects addresses, credentials, and invalid ports before touching the device', async () => {
  for (const value of ['0', '65536', '-1', '1.5', ' ', '8767#key=abc', '80@example.org']) {
    const {events, io} = browser();
    await assert.rejects(openLocalRoom(value, io), /端口/);
    assert.deepEqual(events, []);
  }
});

test('on USB release failure, stays on the installer for recovery', async () => {
  const {events, io} = browser({release: async () => {throw Error('串口仍被占用');}});
  await assert.rejects(openLocalRoom('8767', io), /串口/);
  assert.deepEqual(events, [['open'], ['release'], ['close']]);
});
