/** Cooperative guide registration, preserving the author's normalization.
 * Completed transfers enter a FIFO; one complete chapter becomes visible only
 * after the original normalizer has finished. No world or player state is used.
 */
/** Coalesce same-tick readiness pings without suppressing later requests. */
export function createCookeryReadyBroadcaster(system,sendNow){
 let pending=false;
 return function requestReady(){
  if(pending)return;
  pending=true;
  system.runTimeout(()=>{
   pending=false;
   sendNow();
  },1);
 };
}

export function createCookeryGuideWorkQueue(system,{normalize,pending,extensions,warn=console.warn}){
 const queue=[];
 let handle,units=0,committed=0,rejected=0,parses=0;
 function* prepare(rec){
  // JSON.parse remains one intrinsic operation, once per completed transfer.
  // Release the packet array before traversing the resulting structured data.
  const parsed=JSON.parse(rec.parts.join(''));parses++;rec.parts.length=0;
  const value=yield* normalize(parsed,rec.source);
  if(!value||value.id!==rec.id)throw new Error('schema');
  return value;
 }
 function schedule(){if(handle===undefined&&queue.length)handle=system.runJob(drain());}
 function* drain(){
  try{
   while(queue.length){
    const current=queue[0];units++;
    try{
     const step=current.job.next();
     if(step.done){extensions.set(current.rec.id,step.value);committed++;queue.shift();}
    }catch(error){
     warn(`[Kaleidoscope Cookery] Rejected guidebook extension ${current.rec.id}: ${error}`);
     current.rec.parts.length=0;rejected++;queue.shift();
    }
    yield;
   }
  }finally{handle=undefined;}
 }
 return Object.freeze({
  enqueue(key,rec){
   // A completed END was accepted already. A later BEGIN must not erase it;
   // FIFO completion preserves the author's order even across source IDs.
   if(pending.get(key)!==rec)return false;
   pending.delete(key);queue.push({rec,job:prepare(rec)});schedule();return true;
  },
  status:()=>({queued:queue.length,units,committed,rejected,parses,scheduler:"native-job"})
 });
}

/** Display rules have no synchronous reply; register them under the engine job budget. */
export function createCookeryDisplayWorkQueue(system,register,warn=console.warn){
 const queue=[];let handle,committed=0,rejected=0;
 function* drain(){
  try{
   while(queue.length){
    const message=queue.shift();
    try{
     const result=register(JSON.parse(message));
     if(!result.ok){rejected++;warn(`[Kaleidoscope Cookery] Rejected extension display rule (${result.reason}).`);}
     else committed++;
    }catch(error){rejected++;warn(`[Kaleidoscope Cookery] Invalid extension recipe message: ${error}`);}
    yield;
   }
  }finally{handle=undefined;}
 }
 return Object.freeze({
  enqueue(message){queue.push(String(message??""));if(handle===undefined)handle=system.runJob(drain());},
  status:()=>({queued:queue.length,committed,rejected,scheduler:"native-job"})
 });
}
