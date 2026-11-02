import test from 'node:test';
import assert from 'node:assert/strict';
import {createCookeryRecipeWorkQueue} from '../src/host_api/cookery-recipe-ingress.js';
function scheduler(){
 const callbacks=[];
 return {system:{runTimeout(fn,ticks){assert.equal(ticks,1);callbacks.push(fn);return callbacks.length;}},
  tick(){for(const fn of callbacks.splice(0))fn();},pending:()=>callbacks.length};
}
test('recipe bursts preserve every message and metadata while bounding each tick',()=>{
 const s=scheduler(),seen=[];
 const queue=createCookeryRecipeWorkQueue(s.system,v=>{seen.push(v);return {ok:true};});
 const input=Array.from({length:1000},(_,id)=>({id,source:'fixture',amount:3,ingredients:[['a:b','a:c']],metadata:{quality:4}}));
 for(const value of input)queue.enqueue(JSON.stringify(value));
 assert.equal(s.pending(),1);assert.deepEqual(seen,[]);
 let ticks=0;
 while(s.pending()){
  const before=seen.length;s.tick();ticks++;
  assert(seen.length-before<=4,'one callback cannot consume the original hundreds-per-tick burst');
  assert(ticks<5000,'queued work must complete');
 }
 assert(ticks>=250);assert.deepEqual(seen,input);assert.equal(queue.status().queued,0);assert.equal(queue.status().committed,1000);
});
test('FIFO retains replacement order and original registration validation',()=>{
 const s=scheduler(),recipes=new Map(),calls=[],warnings=[];
 const queue=createCookeryRecipeWorkQueue(s.system,v=>{calls.push(v);if(v.amount<1)return {ok:false,reason:'amount'};recipes.set(v.id,v);return {ok:true};},m=>warnings.push(m));
 for(const value of [{id:'same',amount:1},{id:'bad',amount:0},{id:'same',amount:2}])queue.enqueue(JSON.stringify(value));
 while(s.pending())s.tick();assert.deepEqual(calls.map(v=>v.amount),[1,0,2]);assert.equal(recipes.get('same').amount,2);assert(!recipes.has('bad'));assert.equal(queue.status().rejected,1);assert.equal(warnings.length,1);
});
test('malformed input or a throwing registration cannot block subsequent or later messages',()=>{
 const s=scheduler(),seen=[],warnings=[];
 const queue=createCookeryRecipeWorkQueue(s.system,v=>{if(v.id==='throws')throw Error('fixture');seen.push(v.id);return {ok:true};},m=>warnings.push(m));
 for(const value of ['{','{"id":"throws"}','{"id":"good"}'])queue.enqueue(value);
 while(s.pending())s.tick();assert.deepEqual(seen,['good']);assert.equal(queue.status().rejected,2);assert.equal(warnings.length,2);
 queue.enqueue('{"id":"later"}');while(s.pending())s.tick();assert.deepEqual(seen,['good','later']);
});
