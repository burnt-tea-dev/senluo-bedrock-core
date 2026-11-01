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

/** Scan bounded slices; native JSON.parse still decodes each scalar exactly. */
export function* parseCookeryGuideJson(text){
 let index=0,budget=0,root,hasRoot=false;
 const stack=[];
 const whitespace=c=>c===' '||c==='\t'||c==='\r'||c==='\n';
 const syntax=()=>{throw new SyntaxError('Invalid guide JSON');};
 function* token(){
  while(index<text.length&&whitespace(text[index])){index++;if(++budget>=256){budget=0;yield;}}
  if(index===text.length)return {kind:'end'};
  const start=index,c=text[index++];
  if(++budget>=256){budget=0;yield;}
  if('{}[]:,'.includes(c))return {kind:c};
  if(c==='"'){
   let escaped=false,closed=false;
   while(index<text.length){
    const next=text[index++];
    if(++budget>=256){budget=0;yield;}
    if(escaped){escaped=false;continue;}
    if(next==='\\'){escaped=true;continue;}
    if(next==='"'){closed=true;break;}
   }
   if(!closed)syntax();
   return {kind:'scalar',value:JSON.parse(text.slice(start,index))};
  }
  while(index<text.length&&!whitespace(text[index])&&!'{}[]:,'.includes(text[index])){
   index++;if(++budget>=256){budget=0;yield;}
  }
  const value=JSON.parse(text.slice(start,index));
  if(value!==null&&typeof value==='object')syntax();
  return {kind:'scalar',value};
 }
 function attach(value){
  if(!stack.length){if(hasRoot)syntax();root=value;hasRoot=true;return;}
  const frame=stack[stack.length-1];
  if(frame.array)frame.value.push(value);
  else Object.defineProperty(frame.value,frame.key,{value,writable:true,enumerable:true,configurable:true});
  frame.state='separator';
 }
 while(true){
  const next=yield* token(),frame=stack[stack.length-1];
  if(!frame&&hasRoot){if(next.kind!=='end')syntax();return root;}
  if(frame?.state==='separator'){
   if(next.kind===(frame.array?']':'}')){stack.pop();continue;}
   if(next.kind!==',')syntax();
   frame.state=frame.array?'value':'key';continue;
  }
  if(frame&&!frame.array&&(frame.state==='first'||frame.state==='key')){
   if(frame.state==='first'&&next.kind==='}'){stack.pop();continue;}
   if(next.kind!=='scalar'||typeof next.value!=='string')syntax();
   frame.key=next.value;frame.state='colon';continue;
  }
  if(frame?.state==='colon'){
   if(next.kind!==':')syntax();frame.state='value';continue;
  }
  if(frame?.array&&frame.state==='first'&&next.kind===']'){stack.pop();continue;}
  if(next.kind==='{'||next.kind==='['){
   const array=next.kind==='[',value=array?[]:{};
   attach(value);stack.push({array,value,state:'first'});continue;
  }
  if(next.kind!=='scalar')syntax();
  attach(next.value);
 }
}

export function createCookeryGuideWorkQueue(system,{normalize,pending,extensions,warn=console.warn}){
 const queue=[];
 let handle,units=0,committed=0,rejected=0,parses=0;
 function* prepare(rec){
  const text=rec.parts.join('');rec.parts.length=0;
  const parsed=yield* parseCookeryGuideJson(text);parses++;
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
