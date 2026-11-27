import test from 'node:test';
import assert from 'node:assert/strict';
import {install, restore} from './flow.mjs';
import {createHash} from 'node:crypto';
const sha = (b) => createHash('sha256').update(b).digest('hex');
const size = 8 * 1024 * 1024;
const original = new Uint8Array(size).fill(2);
const app = new Uint8Array(size).fill(3);
const info = {size,sha256:sha(app)};
function setup(overrides={}) {
  const writes=[];
  const io={board:'test',read:async()=>original,write:async b=>writes.push(b),save:async b=>b,...overrides};
  return {io,writes};
}
test('only flash after the backup file matches the board', async()=>{
  for(const save of [async()=>new Uint8Array(size),async()=>{throw Error('cancelled')}]) {
    const {io,writes}=setup({save});
    await assert.rejects(install(io,app,info));assert.equal(writes.length,0);
  }
  const {io,writes}=setup();await install(io,app,info);assert.deepEqual(writes,[app]);
});
test('reject damaged release and backup from another board',async()=>{
  const {io,writes}=setup();
  await assert.rejects(install(io,original,info));
  await assert.rejects(restore(io,original,'passport-other-'+sha(original)+'.bin'));
  assert.equal(writes.length,0);
});

test('restore writes exactly the saved bytes for this board',async()=>{
  const {io,writes}=setup();
  await restore(io,original,'passport-test-'+sha(original)+'.bin');
  assert.deepEqual(writes,[original]);
});
