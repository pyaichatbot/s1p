#!/usr/bin/env node
// Repository-owned workflow. See docs/engineering/kanban.md.
import { readFileSync, writeFileSync, mkdirSync, renameSync, rmSync, existsSync, realpathSync, statSync } from 'node:fs';
import { resolve, join, relative, isAbsolute, dirname } from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
const statuses=['backlog','ready','in_progress','review','blocked','done'];
const stages=['plan','design','build','test','deploy','observe','maintain'];
const types=['FEAT','BUG','CHORE','SPIKE'];
const transitions={backlog:['ready','blocked'],ready:['in_progress','blocked'],in_progress:['review','blocked'],review:['done','in_progress','blocked'],blocked:['ready'],done:['ready']};
const fail=message=>{throw new Error(message)};
const hash=data=>createHash('sha256').update(data).digest('hex');
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function text(value,name,max=2000) { if(typeof value!=='string'||!value.trim()||value.length>max) fail(`Invalid ${name}`); return value.trim(); }
function evidence(root,path) {
  text(path,'evidence path');
  const absolute=realpathSync(resolve(root,path)); const rel=relative(realpathSync(root),absolute);
  if(!rel||rel.startsWith('..')||isAbsolute(rel)||!statSync(absolute).isFile()||statSync(absolute).size>10*1024*1024) fail('Evidence must be a bounded repository file');
  return {path:rel,sha256:hash(readFileSync(absolute))};
}
function validate(board,root,checkEvidence=true) {
  if(board.schema_version!==1||!Number.isSafeInteger(board.revision)||board.revision<0||!Number.isSafeInteger(board.next_id)||board.next_id<1||!Array.isArray(board.items)||board.items.length>2000) fail('Invalid board');
  const ids=new Set();
  for(const item of board.items) {
    if(!types.includes(item.type)||!new RegExp(`^${item.type}-[0-9]{3,}$`).test(item.id)||ids.has(item.id)||!statuses.includes(item.status)) fail('Invalid item identity/status');
    ids.add(item.id); text(item.title,'title',200);
    if(Number(item.id.split('-')[1])>=board.next_id) fail('Invalid sequence');
    if(!Array.isArray(item.requirements)||!item.requirements.every(x=>typeof x==='string'&&/^[A-Z0-9]+-\d{3}$/.test(x))||!Array.isArray(item.dependencies)||!Array.isArray(item.evidence)||!Array.isArray(item.history)||typeof item.stages!=='object'||item.stages===null) fail('Invalid item fields');
    if(['in_progress','review','done'].includes(item.status)) text(item.owner,'owner',128);
    for(const [stage,note] of Object.entries(item.stages)) {if(!stages.includes(stage)) fail('Invalid stage');text(note,'stage note');}
    if(item.status==='done'&&(!stages.every(s=>item.stages[s])||!item.evidence.length||!item.history.some(h=>h.action==='move:done'&&h.note))) fail('Done requires lifecycle and reviewed evidence');
    if(checkEvidence) for(const e of item.evidence) if(evidence(root,e.path).sha256!==e.sha256) fail(`Evidence changed: ${item.id} ${e.path}`);
  }
  for(const item of board.items) if(item.dependencies.some(id=>id===item.id||!ids.has(id))) fail('Invalid dependency');
}
function render(board) {
  const columns=statuses.map(status=>`<section class="column"><h2>${escape(status.replace('_',' '))}<span>${board.items.filter(i=>i.status===status).length}</span></h2>${board.items.filter(i=>i.status===status).map(i=>`<article class="card"><div class="identity">${escape(i.id)} <span>${escape(i.owner||'Unassigned')}</span></div><h3>${escape(i.title)}</h3><p class="requirements">${escape(i.requirements.join(' · ')||'Scope pending')}</p><details><summary>Work record</summary><p>Dependencies: ${escape(i.dependencies.join(', ')||'None')}</p><ol>${stages.map(s=>`<li><b>${s}</b> ${escape(i.stages[s]||'Pending')}</li>`).join('')}</ol><h4>Evidence</h4>${i.evidence.map(e=>`<p>${escape(e.path)}<br><code>${escape(e.sha256.slice(0,12))}</code></p>`).join('')||'<p>None yet</p>'}<h4>History</h4><ol>${i.history.map(h=>`<li>${escape(h.at)} · ${escape(h.action)} ${escape(h.note||'')}</li>`).join('')}</ol></details></article>`).join('')}</section>`).join('');
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'"><title>S1 · Delivery board</title><style>
:root{font-family:system-ui,sans-serif;color:#202b29;background:#f5f4ef}*{box-sizing:border-box}body{margin:0;padding:32px}header{display:flex;align-items:end;justify-content:space-between;gap:24px;flex-wrap:wrap}h1{font-size:32px;letter-spacing:-1px;margin:8px 0}.eyebrow{font-size:12px;letter-spacing:2px;color:#43685d}header p{color:#58645e;margin:8px 0}label{display:grid;gap:6px;font-size:13px}input{padding:12px;border:1px solid #acb6ac;border-radius:6px;font:inherit;min-width:260px}.board{display:grid;grid-template-columns:repeat(6,minmax(240px,1fr));gap:16px;overflow-x:auto;margin:28px 0;padding-bottom:20px}.column{background:#eaece5;border-radius:8px;padding:12px;min-height:300px}h2{font-size:13px;text-transform:uppercase;letter-spacing:1px;display:flex;justify-content:space-between;margin:4px 0 18px}h2 span{color:#66776c}.card{background:#fff;padding:16px;border:1px solid #d8ddd3;border-radius:6px;margin-bottom:12px;border-top:3px solid #568272;overflow-wrap:anywhere}.identity{font-size:11px;font-weight:650;color:#43685d;display:flex;justify-content:space-between;gap:8px}.identity span{color:#68706b}h3{font-size:17px;line-height:1.4;font-weight:600;margin:12px 0}.requirements{font:11px ui-monospace,monospace;color:#5e6d64}details{font-size:12px;line-height:1.6;border-top:1px solid #e5e7e0;padding-top:10px}summary{cursor:pointer}ol{padding-left:16px}li{margin-bottom:8px}footer{font-size:12px;color:#56645a}code{font-size:11px}input:focus,summary:focus{outline:2px solid #326b57;outline-offset:3px}[hidden]{display:none}@media(max-width:600px){body{padding:16px}h1{font-size:28px}.board{grid-template-columns:repeat(6,270px)}}
</style></head><body><header><div><div class="eyebrow">S1 / ENGINEERING</div><h1>Delivery board</h1><p>Plan → Design → Build → Test → Deploy → Observe → Maintain</p><p>Revision ${board.revision} · ${board.items.length} work items · Local, read-only view</p></div><label>Find work<input id="search" type="search" placeholder="ID, requirement, title or owner"></label></header><main class="board">${columns}</main><footer>Source: kanban/board.json · Update with node scripts/kanban.mjs · Reload after changes. Done is evidence-backed scope completion, not a full-product release claim.</footer><script>document.getElementById('search').addEventListener('input',e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('.card').forEach(c=>c.hidden=!c.textContent.toLowerCase().includes(q));});</script></body></html>\n`;
}
function atomic(path,content) {const temp=`${path}.${process.pid}.tmp`;try{writeFileSync(temp,content,{flag:'wx'});renameSync(temp,path)}finally{rmSync(temp,{force:true})}}
function main() {
  const args=process.argv.slice(2), command=args.shift(); const positional=[],options={};
  const allowed={create:['type','title','requirements','depends'],assign:['owner'],update:['title','requirements','note'],move:['status','note'],stage:['stage','note'],evidence:['path','note','replace'],list:[],validate:[],render:[]};
  if(!Object.hasOwn(allowed,command)) fail('Commands: create, assign, update, move, stage, evidence, list, validate, render');
  while(args.length){const arg=args.shift();if(arg.startsWith('--')){const key=arg.slice(2);if(![...allowed[command],'root','expect-revision'].includes(key)||Object.hasOwn(options,key)||!args.length||args[0].startsWith('--'))fail(`Invalid option ${arg}`);options[key]=args.shift()}else positional.push(arg)}
  if(positional.length!==(['assign','update','move','stage','evidence'].includes(command)?1:0))fail('Invalid item argument');
  const root=resolve(options.root||join(dirname(fileURLToPath(import.meta.url)),'..')),directory=join(root,'kanban');mkdirSync(directory,{recursive:true});
  const lock=join(directory,'.lock');mkdirSync(lock); // Refuse concurrent writes; never steal locks.
  try {
    writeFileSync(join(lock,'owner.json'),JSON.stringify({pid:process.pid,at:new Date().toISOString()}));
    const path=join(directory,'board.json');
    if(existsSync(path)&&statSync(path).size>2*1024*1024)fail('Board exceeds 2 MiB');
    const board=existsSync(path)?JSON.parse(readFileSync(path,'utf8')):{schema_version:1,revision:0,next_id:1,items:[]};
    validate(board,root,command==='validate');
    if(options['expect-revision']!==undefined&&String(board.revision)!==options['expect-revision'])fail('Stale board revision');
    const item=board.items.find(i=>i.id===positional[0]);
    if(positional.length&&!item) fail('Unknown item');
    const at=new Date().toISOString();let action=command;let previousHash;
    if(item?.status==='done' && command!=='move')fail('Reopen done work before editing');
    if(command==='create') {
      if(!types.includes(options.type))fail('Invalid type');
      const title=text(options.title,'title',200),requirements=options.requirements?options.requirements.split(','):[],dependencies=options.depends?options.depends.split(','):[];
      board.items.push({id:`${options.type}-${String(board.next_id++).padStart(3,'0')}`,type:options.type,title,requirements,dependencies,owner:null,status:'backlog',stages:{},evidence:[],history:[{at,action:'create',note:title}]});
    } else if(command==='update') {
      text(options.note,'scope change rationale');
      if(options.title===undefined && options.requirements===undefined)fail('Specify title or requirements');
      if(options.title!==undefined)item.title=text(options.title,'title',200);
      if(options.requirements!==undefined)item.requirements=text(options.requirements,'requirements').split(',');
    } else if(command==='assign') item.owner=text(options.owner,'owner',128);
    else if(command==='stage'){if(!stages.includes(options.stage))fail('Invalid stage');item.stages[options.stage]=text(options.note,'note');action=`stage:${options.stage}`;}
    else if(command==='evidence'){
      const record={...evidence(root,options.path),note:text(options.note,'note')};
      const previous=item.evidence.find(e=>e.path===record.path);
      if(previous && options.replace!=='true')fail('Existing evidence: explicit --replace true and rationale required');
      if(options.replace!==undefined && options.replace!=='true')fail('Invalid replace value');
      if(previous){previousHash=previous.sha256;item.evidence=item.evidence.filter(e=>e.path!==record.path);action='evidence:replace';}
      item.evidence.push(record);
    }
    else if(command==='move') {
      if(!transitions[item.status].includes(options.status))fail('Invalid transition');
      if(options.status==='blocked'||item.status==='done'||options.status==='done')text(options.note,'transition note');
      if(options.status==='in_progress'&&item.dependencies.some(id=>board.items.find(i=>i.id===id).status!=='done'))fail('Unfinished dependency');
      item.status=options.status;action=`move:${options.status}`;
    }
    if(!['list','validate','render'].includes(command)) {
      if(item)item.history.push({at,action,note:options.note||options.owner||'',...(previousHash?{previous_sha256:previousHash}:{})});
      board.revision++;validate(board,root,command==='move'&&options.status==='done');
      const data=JSON.stringify(board,null,2)+'\n';if(Buffer.byteLength(data)>2*1024*1024)fail('Board exceeds 2 MiB');atomic(path,data);
    }
    if(command!=='list')atomic(join(directory,'index.html'),render(board));
    console.log(JSON.stringify(command==='list'?board:{status:'ok',revision:board.revision,id:item?.id||board.items.at(-1)?.id}));
  }finally{rmSync(lock,{recursive:true,force:true})}
}
try{main()}catch(error){console.error(`Kanban: ${error.message}`);process.exitCode=1}
