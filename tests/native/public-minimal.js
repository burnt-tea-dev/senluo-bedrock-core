// Isolated observer only. The four production archives are not modified.
import {world, system, BlockPermutation, ItemStack, GameMode, Direction, EnchantmentType} from '@minecraft/server';
import {spawnSimulatedPlayer} from '@minecraft/server-gametest';
import {handleGrill} from './grill/runtime.js';
const KEY='core_public:checkpoint', wait=n=>new Promise(resolve=>system.runTimeout(resolve,n));
const grillPos={x:0,y:5,z:0}, chestPos={x:3,y:5,z:0}, boardPos={x:4,y:5,z:3};
let running=false;
world.beforeEvents.playerInteractWithBlock.subscribe(e=>console.warn('PUBLIC_INPUT_BEFORE '+JSON.stringify({block:e.block.typeId,location:e.block.location,cancel:e.cancel,item:e.itemStack?.typeId,first:e.isFirstEvent})));
world.afterEvents.playerInteractWithBlock.subscribe(e=>console.warn('PUBLIC_INPUT_AFTER '+JSON.stringify({block:e.block.typeId,location:e.block.location,item:e.itemStack?.typeId})));
system.afterEvents.scriptEventReceive.subscribe(e=>{
 if(e.id!=='captain_qa:run'||running)return;
 running=true;run().catch(error=>console.error('CAPTAIN_QA_FATAL '+error+' '+error?.stack));
});
function signature(item){
 if(!item)return null;
 return {type:item.typeId,amount:item.amount,name:item.nameTag,lore:item.getLore(),origin:item.maxAmount===1?item.getDynamicProperty('core_public:origin'):undefined,
  keep:item.keepOnDeath,damage:item.getComponent('minecraft:durability')?.damage,
  enchantments:item.getComponent('minecraft:enchantable')?.getEnchantments().map(x=>[x.type.id,x.level]),
  canPlace:item.getCanPlaceOn(),canDestroy:item.getCanDestroy()};
}
async function run(){
 const d=world.getDimension('overworld'),checks=[],samples=[];
 const check=(name,ok)=>{checks.push({name,passed:!!ok});console.warn('CAPTAIN_QA_CHECK '+JSON.stringify(checks.at(-1)));if(!ok)throw Error(name);};
 const old=world.getDynamicProperty(KEY), saved=old?JSON.parse(old):undefined;
 const phase=saved?({baseline:'first',first:'restart',restart:'rollback'})[saved.phase]:'baseline';
 if(!phase)throw Error('Unexpected checkpoint');
 let player;
 const inventories=()=>d.getEntities({type:'kaleidoscope_grilling:inventory_grill_v1',location:{x:.5,y:5.25,z:.5},maxDistance:1});
 try{
  if(phase==='baseline'){
   d.runCommand('gamerule doMobSpawning false');
   d.runCommand('fill -5 4 -5 8 4 8 stone');d.runCommand('fill -5 5 -5 8 9 8 air');
   d.getBlock(grillPos).setPermutation(BlockPermutation.resolve('kaleidoscope_grilling:grill'));
   d.getBlock(chestPos).setType('minecraft:chest');
  }
  player=spawnSimulatedPlayer({dimension:d,x:1.5,y:5,z:1.5},'PublicCoreQA',GameMode.Survival);
  await wait(5);
  const inventory=player.getComponent('minecraft:inventory').container;
  inventory.clearAll();player.selectedSlotIndex=0;
  const interact=async(pos,item)=>{
   inventory.setItem(0,item);player.lookAtLocation({x:pos.x+.5,y:pos.y+.6,z:pos.z+.5});
   await wait(2);if(pos.x===grillPos.x&&pos.z===grillPos.z)handleGrill(d.getBlock(pos),player,'main');else system.sendScriptEvent('core_public:board',JSON.stringify(pos));await wait(12);
  };
  const grill=d.getBlock(grillPos), chest=d.getBlock(chestPos).getComponent('minecraft:inventory').container;
  if(phase==='baseline'){
   await interact(grillPos,new ItemStack('minecraft:wooden_shovel'));
   await interact(grillPos,new ItemStack('minecraft:flint_and_steel'));
   check('original four-pack baseline ignites grill through its production handler and native inventory',grill.permutation.getState('kaleidoscope_grilling:lit')===true);
   const raw=new ItemStack('kaleidoscope_grilling:raw_beef_skewer',2);
   raw.nameTag='Public upgrade skewer';raw.setLore(['External metadata survives pack upgrade']);raw.keepOnDeath=true;
   await interact(grillPos,raw);
   check('native insertion debits exactly one raw skewer',inventory.getItem(0)?.amount===1);
   check('one original-owner native station inventory exists',inventories().length===1);
   const station=inventories()[0].getComponent('minecraft:inventory').container;
   check('real grill inventory contains exactly the inserted stack',station.getItem(0)?.amount===1&&station.emptySlotsCount===2);
   await interact(grillPos,new ItemStack('minecraft:wooden_shovel'));
   check('normal shovel interaction extinguishes the stored grill',grill.permutation.getState('kaleidoscope_grilling:lit')===false);
   const sword=new ItemStack('minecraft:diamond_sword');sword.nameTag='Original public data';sword.setLore(['Cookery author baseline']);sword.keepOnDeath=true;
   sword.setDynamicProperty('core_public:origin','original');sword.getComponent('minecraft:durability').damage=7;
   sword.getComponent('minecraft:enchantable').addEnchantment({type:new EnchantmentType('unbreaking'),level:2});
   sword.setCanDestroy(['minecraft:stone']);sword.setCanPlaceOn(['minecraft:grass_block']);chest.setItem(0,sword);
   const record={phase,station:signature(station.getItem(0)),chest:signature(chest.getItem(0))};
   check('named raw stack and additional lore were retained in the native grill',record.station.name===raw.nameTag&&record.station.lore.includes('External metadata survives pack upgrade'));
   world.setDynamicProperty(KEY,JSON.stringify(record));samples.push(record);
  }else{
   check(phase+' original grill block survives',grill.typeId==='kaleidoscope_grilling:grill');
   check(phase+' exactly one station owner survives',inventories().length===1);
   const station=inventories()[0].getComponent('minecraft:inventory').container;
   check(phase+' original station ItemStack metadata survives',JSON.stringify(signature(station.getItem(0)))===JSON.stringify(saved.station));
   check(phase+' original chest ItemStack metadata survives',JSON.stringify(signature(chest.getItem(0)))===JSON.stringify(saved.chest));
   check(phase+' extinguished state survives',grill.permutation.getState('kaleidoscope_grilling:lit')===false);
   if(phase==='first'||phase==='restart'){
    player.teleport({x:5.5,y:5,z:4.5});await wait(4);
    if(phase==='first'){
     d.getBlock(boardPos).setType('kaleidoscope_cookery:chopping_board');
     await interact(boardPos,new ItemStack('minecraft:chicken'));
     check('public Cookery accepts chicken through its production board handler',inventory.getItem(0)===undefined);
    }
    const knife=new ItemStack('kaleidoscope_cookery:iron_kitchen_knife');
    inventory.setItem(0,knife);
    for(let i=0;i<2;i++)await interact(boardPos,inventory.getItem(0));
    if(phase==='restart'){
     // The author board cuts four times, then releases on the next interaction.
     await interact(boardPos,inventory.getItem(0));
     const counts={};
     const collect=s=>{if(s)counts[s.typeId]=(counts[s.typeId]??0)+s.amount;};
     for(let i=0;i<inventory.size;i++)collect(inventory.getItem(i));
     for(const item of d.getEntities({type:'minecraft:item',location:{x:4.5,y:5.5,z:3.5},maxDistance:5}))collect(item.getComponent('minecraft:item').itemStack);
     samples.push({boardOutputs:counts});
     check('saved board completes four cuts and releases original three meat outputs after restart',counts['kaleidoscope_cookery:raw_cut_small_meats']===3);
     check('saved board completes original one bone output',counts['minecraft:bone']===1);
     check('Grilling board extension supplies native chicken skin without another addon',counts['kaleidoscope_grilling:chicken_skin']>=1&&counts['kaleidoscope_grilling:chicken_skin']<=3);
    }
   }
   world.setDynamicProperty(KEY,JSON.stringify({...saved,phase}));
  }
 }finally{try{player?.disconnect();}catch{}}
 await wait(3);check('diagnostic player disconnected',world.getAllPlayers().length===0);
 console.warn('CAPTAIN_QA_RESULT '+JSON.stringify({phase,passed:true,checks,samples,playersAfter:0,
  scope:'Four production Grilling/Cookery packs plus a separate QA-only observer. Production handlers with native player/inventory, original-owner station inventories, author chopping-board extension, same-world upgrade/restart/rollback. No client rendering/audio verdict.'}));
}
