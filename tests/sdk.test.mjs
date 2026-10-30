import {test} from 'node:test';
import assert from 'node:assert/strict';
import {blockEvents, playerCraftRecipeEvents, scriptEvents} from '../src/host_api/event_router.js';
import {readPublicFoodLore, publicFoodLoreRows, bucketHotUntil} from '../src/host_api/food_api_core.js';

// A signal is the external API boundary. These tests execute the exported SDK.
function signal(){
 const handlers=new Set();
 return {handlers,subscribe(fn){handlers.add(fn)},unsubscribe(fn){handlers.delete(fn)},emit(event){for(const fn of [...handlers])fn(event)}};
}
function world(){return {beforeEvents:{playerInteractWithBlock:signal(),playerBreakBlock:signal(),explosion:signal()},afterEvents:{playerBreakBlock:signal(),playerCraftRecipe:signal()}}}

test('one native subscription, priority, cancellation and observers',()=>{
 const w=world(),router=blockEvents(w),calls=[];
 assert.equal(router,blockEvents(w));
 const stopObserve=router.interact('observe',()=>calls.push('observe'),{observe:true});
 const stopSecond=router.interact('second',()=>calls.push('second'),{priority:2});
 const stopFirst=router.interact('first',e=>{calls.push('first');e.cancel=true},{priority:1,blocks:['test:board']});
 assert.equal(w.beforeEvents.playerInteractWithBlock.handlers.size,1);
 assert.throws(()=>router.interact('first',()=>{}),/Duplicate/);
 w.beforeEvents.playerInteractWithBlock.emit({block:{typeId:'test:board'},cancel:false});
 assert.deepEqual(calls,['first','observe']);
 calls.length=0;w.beforeEvents.playerInteractWithBlock.emit({block:{typeId:'test:other'},cancel:false});
 assert.deepEqual(calls,['second','observe']);
 stopObserve();stopSecond();stopFirst();stopFirst();
 assert.equal(w.beforeEvents.playerInteractWithBlock.handlers.size,0);
});

test('self removal does not skip another route and pack buses stay separate',()=>{
 const a=world(),b=world(),calls=[];
 const off=blockEvents(a).afterBreak('first',()=>{calls.push('first');off()});
 const stop=blockEvents(a).afterBreak('second',()=>calls.push('second'));
 const stopOther=blockEvents(b).afterBreak('other',()=>calls.push('other'));
 a.afterEvents.playerBreakBlock.emit({});a.afterEvents.playerBreakBlock.emit({});
 assert.deepEqual(calls,['first','second','second']);stop();stopOther();
});

test('craft route stays lazy on engines without that optional API',()=>{
 const w=world();delete w.afterEvents.playerCraftRecipe;
 assert.ok(blockEvents(w));
 const supported=world(),calls=[];
 const off=playerCraftRecipeEvents(supported)('craft',e=>calls.push(e.recipeId));
 supported.afterEvents.playerCraftRecipe.emit({recipeId:'test:oil'});
 assert.deepEqual(calls,['test:oil']);off();
 assert.equal(supported.afterEvents.playerCraftRecipe.handlers.size,0);
 const s={afterEvents:{scriptEventReceive:signal()}};
 const close=scriptEvents(s)('client',e=>calls.push(e.id));s.afterEvents.scriptEventReceive.emit({id:'test:reply'});close();
 assert.equal(calls.at(-1),'test:reply');assert.equal(s.afterEvents.scriptEventReceive.handlers.size,0);
});

test('public food carrier preserves player lore and exact legacy deadlines',()=>{
 const custom={text:'Player note'},legacy={v:1,hotUntil:1201,seasoning:['test:salt'],nativeVariant:7,quality:2};
 const rows=publicFoodLoreRows([custom],legacy);
 assert.deepEqual(rows[0],custom);
 assert.deepEqual(readPublicFoodLore(rows),{present:true,valid:true,state:legacy});
 assert.equal(bucketHotUntil(1201),1200);
 assert.deepEqual(readPublicFoodLore([...rows,rows.at(-1)]),{present:true,valid:false});
 assert.throws(()=>publicFoodLoreRows(Array.from({length:20},()=>({text:'full'})),legacy),/space/);
});
