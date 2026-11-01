import test from 'node:test';
import assert from 'node:assert/strict';
import {createCookeryRecipeOrder,createCookeryReadyBroadcaster,createCookeryGuideWorkQueue,createCookeryDisplayWorkQueue,parseCookeryGuideJson} from '../src/host_api/cookery-guide-decoding.js';

function parseInSlices(text,onYield=()=>{}){
 const parser=parseCookeryGuideJson(text);let step;
 do{step=parser.next();if(!step.done)onYield();}while(!step.done);
 return step.value;
}

test('incremental guide JSON parsing matches native JSON.parse semantics',()=>{
 const valid=[
  'null','true','false','-0','1e400','{"escaped":"\\u4f60\\u597d","pair":"\\uD83D\\uDE80","loneHigh":"\\uD800","loneLow":"\\uDC00"}',
  '[0,-1,1.25,1e-300,"\\n\\t\\\\\\\"",[],{}]',
  '{"same":1,"same":2,"__proto__":{"polluted":true},"constructor":{"prototype":{"polluted":true}}}',
 ];
 for(const text of valid){
  const actual=parseInSlices(text),expected=JSON.parse(text);
  assert.deepEqual(actual,expected,text);
  assert.equal(JSON.stringify(actual),JSON.stringify(expected),text);
 }
 const special=parseInSlices(valid[3]);assert(Object.is(special,-0));
 assert.equal(parseInSlices(valid[4]),JSON.parse(valid[4]));
 const prototypeCase=parseInSlices(valid[7]);
 assert(Object.hasOwn(prototypeCase,'__proto__'));
 assert.equal(Object.getPrototypeOf(prototypeCase),Object.prototype);
 assert.equal({}.polluted,undefined);
});

test('incremental guide JSON parsing rejects malformed JSON like JSON.parse',()=>{
 for(const text of ['', '01', '[1,]', '{"a":1,}', 'true false', '"unterminated', '1e', '{"__proto__":}']){
  assert.throws(()=>JSON.parse(text),SyntaxError,text);
  assert.throws(()=>parseInSlices(text),SyntaxError,text);
 }
});

test('deep guide JSON parses iteratively and a long scalar yields while scanning',()=>{
 const depth=2048,text='['.repeat(depth)+'0'+']'.repeat(depth);
 const parsed=parseInSlices(text);
 assert.equal(JSON.stringify(parsed),JSON.stringify(JSON.parse(text)));
 const longText=JSON.stringify({chapter:'漢🍵'.repeat(10000)});let yields=0;
 const actual=parseInSlices(longText,()=>yields++);
 assert(yields>100,'long guide text must yield repeatedly during scanning');
 assert.deepEqual(actual,JSON.parse(longText));
});

test('same-tick requests coalesce independently, later pings resend, and failures can retry',()=>{
 const tasks=[];let tick=0;
 const system={runTimeout(fn,delay){tasks.push({fn,at:tick+delay});}};
 const runTick=()=>{
  tick++;
  const due=tasks.filter(task=>task.at<=tick);
  for(const task of due){tasks.splice(tasks.indexOf(task),1);task.fn();}
 };
 let recipeSends=0,guideSends=0;
 const recipeReady=createCookeryReadyBroadcaster(system,()=>recipeSends++);
 const guideReady=createCookeryReadyBroadcaster(system,()=>guideSends++);
 for(let i=0;i<15;i++){recipeReady();guideReady();}
 assert.equal(tasks.length,2,'recipe and guide each schedule one deferred send');
 assert.equal(recipeSends,0);assert.equal(guideSends,0);
 runTick();assert.equal(recipeSends,1);assert.equal(guideSends,1);
 recipeReady();guideReady();runTick();
 assert.equal(recipeSends,2,'a later recipe ping can request ready again');
 assert.equal(guideSends,2,'a later guide ping can request ready again');
 let attempts=0;
 const retryReady=createCookeryReadyBroadcaster(system,()=>{if(++attempts===1)throw new Error('send failed');});
 retryReady();assert.throws(runTick,/send failed/);assert.equal(attempts,1);
 retryReady();runTick();assert.equal(attempts,2,'a failed send does not leave the queue latched');
});

test('native guide job yields and publishes only the complete chapter',()=>{
 const jobs=[],extensions=new Map(),rec={source:'fixture',id:'fixture:chapter',parts:[JSON.stringify({id:'fixture:chapter'})]};
 const pending=new Map([['fixture',rec]]);
 const work=createCookeryGuideWorkQueue({runJob(job){jobs.push(job);return jobs.length;}},{
  pending,extensions,*normalize(value){for(let i=0;i<5;i++)yield;return value;},warn(message){throw new Error(message);}
 });
 assert.equal(work.enqueue('fixture',rec),true);
 jobs[0].next();
 assert.equal(work.status().units,1,'each generator step does one original normalization unit');
 assert.equal(extensions.size,0,'partial normalization stays private');
 while(!jobs[0].next().done){}
 assert.equal(work.status().committed,1);assert.equal(work.status().rejected,0);
 assert.deepEqual(extensions.get(rec.id),{id:rec.id});
});

test('native display job preserves order and continues after malformed or rejected messages',()=>{
 const jobs=[],seen=[],warnings=[];
 const work=createCookeryDisplayWorkQueue({runJob(job){jobs.push(job);return jobs.length;}},value=>{
  seen.push(value.id);return {ok:!value.reject,reason:'fixture'};
 },message=>warnings.push(message));
 for(const message of ['{"id":"first"}','{','{"id":"rejected","reject":true}','{"id":"last"}'])work.enqueue(message);
 assert.deepEqual(seen,[],'the incoming callback only enqueues');
 jobs[0].next();assert.deepEqual(seen,['first']);
 while(!jobs[0].next().done){}
 assert.deepEqual(seen,['first','rejected','last']);
 assert.equal(work.status().committed,2);assert.equal(work.status().rejected,2);assert.equal(warnings.length,2);
 work.enqueue('{"id":"late"}');assert.equal(jobs.length,2);
 while(!jobs[1].next().done){}
 assert.equal(seen.at(-1),'late');
});

const nativeOrder=map=>[...map].sort(([a],[b])=>a.localeCompare(b)).map(([,value])=>value);
test('incremental updates preserve native locale ordering, stable equal keys and recipe references',()=>{
 const index=createCookeryRecipeOrder(),map=new Map();index.values(map);
 for(const key of ['wok|Tea:source|food:z','wok|tea-source|food:a','wok|tea_source|food:12','wok|tea:source|food:a','wok|tea:source|food:2']){
  index.set(map,key,Object.freeze({key,metadata:{quality:3}}));assert.deepEqual(index.values(map),nativeOrder(map));
 }
 const key=[...map.keys()][1],replacement={key,metadata:{quality:7}};index.set(map,key,replacement);
 assert.deepEqual(index.values(map),nativeOrder(map));assert(index.values(map).includes(replacement));
 const prefilled=new Map([['b',{id:2}],['a',{id:1}]]);assert.deepEqual(index.values(prefilled),nativeOrder(prefilled));index.set(prefilled,'a',{id:3});assert.deepEqual(index.values(prefilled),nativeOrder(prefilled));
});
test('registration bursts use bounded comparisons and an unchanged index does no sorting',()=>{
 const original=String.prototype.localeCompare;let comparisons=0;String.prototype.localeCompare=function(...args){comparisons++;return original.apply(this,args);};
 try{
  const index=createCookeryRecipeOrder(),map=new Map();index.values(map);
  for(let i=999;i>=0;i--){index.set(map,'wok|fixture|food:'+String(i).padStart(4,'0'),{id:i});index.values(map);}
  assert(comparisons<20000);const before=comparisons;for(let n=0;n<100;n++)index.values(map);assert.equal(comparisons,before);
  assert.equal(index.values(map).length,1000);assert.deepEqual(index.values(map).map(r=>r.id),Array.from({length:1000},(_,n)=>n));
 }finally{String.prototype.localeCompare=original;}
});
