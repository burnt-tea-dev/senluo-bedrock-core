// Copyable routing for one native world/system. Separate packs keep separate buses.
const worlds=new WeakMap(),craftWorlds=new WeakMap(),systems=new WeakMap();

function invoke(route,event){
 try{route.handle(event);}catch(error){console.warn('[Grilling event '+route.id+'] '+error);}
}
function broadcast(routes,event){for(const route of routes)invoke(route,event);}
function interact(routes,event){
 const targets=routes.filter(route=>!route.blocks||route.blocks.has(event.block?.typeId));
 for(const route of targets){
  if(route.observe)continue;
  if(event.cancel)break;
  invoke(route,event);
 }
 for(const route of targets)if(route.observe)invoke(route,event);
}
function channel(subscribe,unsubscribe,dispatch=broadcast,exclusive=false){
 const routes=[];
 // A callback may remove its own route; that must not skip the next owner.
 const receive=event=>dispatch([...routes],event);
 return (id,handle,{priority=0,blocks,observe=false}={})=>{
  if(exclusive&&routes.some(route=>route.id===id))throw Error('Duplicate block interaction owner: '+id);
  if(!routes.length)subscribe(receive);
  const route={id,handle,priority,blocks:blocks&&new Set(blocks),observe};
  routes.push(route);routes.sort((a,b)=>a.priority-b.priority);
  return ()=>{
   const index=routes.indexOf(route);if(index<0)return;
   routes.splice(index,1);if(!routes.length)unsubscribe(receive);
  };
 };
}

export function blockEvents(world){
 let router=worlds.get(world);
 if(!router){
  router=Object.freeze({
   interact:channel(fn=>world.beforeEvents.playerInteractWithBlock.subscribe(fn),fn=>world.beforeEvents.playerInteractWithBlock.unsubscribe(fn),interact,true),
   beforeBreak:channel(fn=>world.beforeEvents.playerBreakBlock.subscribe(fn),fn=>world.beforeEvents.playerBreakBlock.unsubscribe(fn)),
   afterBreak:channel(fn=>world.afterEvents.playerBreakBlock.subscribe(fn),fn=>world.afterEvents.playerBreakBlock.unsubscribe(fn)),
   explosion:channel(fn=>world.beforeEvents.explosion.subscribe(fn),fn=>world.beforeEvents.explosion.unsubscribe(fn)),
  });
  worlds.set(world,router);
 }
 return router;
}

export function playerCraftRecipeEvents(world){
 let register=craftWorlds.get(world);
 if(!register){register=channel(fn=>world.afterEvents.playerCraftRecipe.subscribe(fn),fn=>world.afterEvents.playerCraftRecipe.unsubscribe(fn));craftWorlds.set(world,register)}
 return register;
}

export function scriptEvents(system){
 let register=systems.get(system);
 if(!register){
  register=channel(fn=>system.afterEvents.scriptEventReceive.subscribe(fn),fn=>system.afterEvents.scriptEventReceive.unsubscribe(fn));
  systems.set(system,register);
 }
 return register;
}
