import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
const script = resolve('scripts/kanban.mjs');
function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 's1-kanban-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const run = (...args) => spawnSync(process.execPath, [script, ...args, '--root', root], {encoding:'utf8'});
  return {root,run, board:()=>JSON.parse(readFileSync(join(root,'kanban/board.json')))};
}
test('create, assign, transitions, evidence and complete lifecycle', t => {
  const {root,run,board}=fixture(t);
  assert.equal(run('create','--type','FEAT','--title','First','--requirements','L1-001').status,0);
  assert.equal(run('move','FEAT-001','--status','done').status,1);
  assert.equal(run('move','FEAT-001','--status','ready').status,0);
  assert.equal(run('move','FEAT-001','--status','in_progress').status,1);
  assert.equal(run('assign','FEAT-001','--owner','worker').status,0);
  assert.equal(run('move','FEAT-001','--status','in_progress').status,0);
  assert.equal(run('move','FEAT-001','--status','review').status,0);
  assert.equal(run('move','FEAT-001','--status','done','--note','reviewed').status,1);
  for(const stage of ['plan','design','build','test','deploy','observe','maintain']) assert.equal(run('stage','FEAT-001','--stage',stage,'--note','Evidence reviewed or N/A: documentation scope').status,0);
  writeFileSync(join(root,'proof.txt'),'actual evidence');
  assert.equal(run('evidence','FEAT-001','--path','proof.txt','--note','test result').status,0);
  assert.equal(run('move','FEAT-001','--status','done','--note','Reviewed').status,0);
  assert.equal(board().items[0].status,'done');
  writeFileSync(join(root,'proof.txt'),'changed');
  assert.equal(run('validate').status,1);
});
test('stale writes, lock contention, malformed input and HTML injection',t=>{
  const {root,run,board}=fixture(t);
  assert.equal(run('create','--type','BUG','--title','<script>alert(1)</script>').status,0);
  const original=JSON.stringify(board());
  assert.equal(run('assign','BUG-001','--owner','x','--expect-revision','0').status,1);
  assert.equal(run('create','--type','BAD','--title','x').status,1);
  assert.equal(run('create','--type','FEAT','--title','x','--typo','x').status,1);
  mkdirSync(join(root,'kanban/.lock'));
  assert.equal(run('assign','BUG-001','--owner','x').status,1);
  assert.equal(JSON.stringify(board()),original);
  const html=readFileSync(join(root,'kanban/index.html'),'utf8');
  assert.ok(html.includes('&lt;script&gt;'));
  assert.ok(!html.includes('<script>alert'));
});
test('dependency, blocked and reopen rules',t=>{
  const {run}=fixture(t);
  run('create','--type','CHORE','--title','dependency');
  run('create','--type','FEAT','--title','dependent','--depends','CHORE-001');
  run('assign','FEAT-002','--owner','a'); run('move','FEAT-002','--status','ready');
  assert.equal(run('move','FEAT-002','--status','in_progress').status,1);
  assert.equal(run('move','FEAT-002','--status','blocked').status,1);
  assert.equal(run('move','FEAT-002','--status','blocked','--note','waiting').status,0);
  assert.equal(run('move','FEAT-002','--status','ready').status,0);
  assert.equal(run('evidence','FEAT-002','--path','../escape','--note','bad').status,1);
});
test('evidence drift needs explicit replacement with history',t=>{
  const {root,run,board}=fixture(t);
  run('create','--type','CHORE','--title','evidence');
  writeFileSync(join(root,'proof.txt'),'v1');
  assert.equal(run('evidence','CHORE-001','--path','proof.txt','--note','first').status,0);
  writeFileSync(join(root,'proof.txt'),'v2');
  assert.equal(run('validate').status,1);
  assert.equal(run('evidence','CHORE-001','--path','proof.txt','--note','new').status,1);
  assert.equal(run('evidence','CHORE-001','--path','proof.txt','--note','Rerun after reviewed fix','--replace','true').status,0);
  assert.equal(run('validate').status,0);
  assert.equal(board().items[0].evidence.length,1);
  assert.ok(board().items[0].history.at(-1).previous_sha256);
});
test('read and validation boundaries refuse malformed boards and commands',t=>{
  const {root,run,board}=fixture(t);
  assert.equal(run('list').status,0);
  for(const args of [[],['unknown'],['create','--type','FEAT','--title',''],['create','--type','FEAT','--title','a','--title','b'],['create','extra'],['assign','missing','--owner','x']]) assert.equal(run(...args).status,1);
  assert.equal(run('create','--type','SPIKE','--title','Boundaries').status,0);
  assert.equal(run('render').status,0);
  assert.equal(run('stage','SPIKE-001','--stage','oops','--note','x').status,1);
  assert.equal(run('assign','SPIKE-001','--owner','').status,1);
  assert.equal(run('create','--type','BUG','--title','bad requirement','--requirements','bogus').status,1);
  assert.equal(run('create','--type','BUG','--title','bad dependency','--depends','BUG-999').status,1);
  writeFileSync(join(root,'proof.txt'),'data');
  assert.equal(run('evidence','SPIKE-001','--path','proof.txt','--note','x','--replace','false').status,1);
  const original=board(),path=join(root,'kanban/board.json');
  const variants=[{...original,schema_version:2},{...original,next_id:1},{...original,items:[{...original.items[0],type:'BAD'}]},{...original,items:[{...original.items[0],requirements:null}]},{...original,items:[{...original.items[0],stages:{oops:'x'}}]}];
  for(const variant of variants){writeFileSync(path,JSON.stringify(variant));assert.equal(run('validate').status,1)}
  writeFileSync(path,'x'.repeat(2*1024*1024+1)); assert.equal(run('list').status,1);
});
test('reviewed scope updates preserve history and reject unknown fields',t=>{
  const {run,board}=fixture(t);
  run('create','--type','CHORE','--title','Initial');
  assert.equal(run('update','CHORE-001','--requirements','CQ-001,CQ-002').status,1);
  assert.equal(run('update','CHORE-001','--title','Reviewed scope','--requirements','CQ-001,CQ-002','--note','Owner directed code constraints').status,0);
  assert.deepEqual(board().items[0].requirements,['CQ-001','CQ-002']);
  assert.equal(board().items[0].history.at(-1).action,'update');
  assert.equal(run('update','CHORE-001','--note','no change').status,1);
  assert.equal(run('update','CHORE-001','--requirements','bad','--note','bad scope').status,1);
});
