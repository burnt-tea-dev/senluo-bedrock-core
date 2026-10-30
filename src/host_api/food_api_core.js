/** Explicit cross-pack output metadata; the empty translated carrier is not display lore. */
// Java FoodState.bucket: quantize new absolute deadlines, never stored reads.
export function bucketHotUntil(until){
 if(!Number.isSafeInteger(until)||until<0)throw Error('invalid heat deadline');
 return Math.floor(until/100)*100;
}
export const FOOD_PAYLOAD_KEY='senluo.public.food.v1';
const ID=/^[a-z0-9_.-]+:[a-z0-9_./-]+$/;
export function normalizePublicFood(raw){
 if(!raw||raw.v!==1||!Number.isSafeInteger(raw.hotUntil)||raw.hotUntil<0||!Array.isArray(raw.seasoning)||raw.seasoning.length>8||raw.seasoning.some(x=>typeof x!=='string'||!ID.test(x)))return undefined;
 if(raw.nativeVariant!==undefined&&(!Number.isInteger(raw.nativeVariant)||raw.nativeVariant<0||raw.nativeVariant>32767))return undefined;
 if(raw.quality!==undefined&&(!Number.isInteger(raw.quality)||raw.quality<0||raw.quality>3))return undefined;
 return {v:1,hotUntil:raw.hotUntil,seasoning:[...raw.seasoning],...(raw.nativeVariant===undefined?{}:{nativeVariant:raw.nativeVariant}),...(raw.quality===undefined?{}:{quality:raw.quality})};
}
export function isFoodPayloadLine(row){return row&&typeof row==='object'&&row.translate===FOOD_PAYLOAD_KEY;}
export function readPublicFoodLore(rawLore){
 if(!Array.isArray(rawLore))return {present:true,valid:false};
 const lines=rawLore.filter(isFoodPayloadLine);
 if(!lines.length)return {present:false,valid:false};
 if(lines.length!==1||!Array.isArray(lines[0].with)||lines[0].with.length!==1||typeof lines[0].with[0]!=='string')return {present:true,valid:false};
 try{const state=normalizePublicFood(JSON.parse(lines[0].with[0]));return {present:true,valid:!!state,state}}catch{return {present:true,valid:false}}
}
export function readPublicFood(stack){
 try{return readPublicFoodLore(stack?.getRawLore()??[])}catch{return {present:true,valid:false}}
}
const QUALITY_NAMES=['superb','excellent','standard','poor'],QUALITY_COLORS=['6','a','f','8'];
export function cuisineQualityLore(quality){
 if(!Number.isInteger(quality)||quality<0||quality>3)return undefined;
 return {rawtext:[{text:'§r§'+QUALITY_COLORS[quality]},{translate:'tooltip.kaleidoscope_grilling.cuisine_quality.'+QUALITY_NAMES[quality]},{text:'§r'}]};
}
export function isCuisineQualityLore(row){
 const parts=row?.rawtext;if(!Array.isArray(parts)||parts.length!==3||parts[2]?.text!=='§r')return false;
 const quality=QUALITY_NAMES.findIndex(name=>parts[1]?.translate==='tooltip.kaleidoscope_grilling.cuisine_quality.'+name);
 return quality>=0&&parts[0]?.text==='§r§'+QUALITY_COLORS[quality];
}
export function publicFoodLoreRows(rawLore,raw){
 const state=normalizePublicFood(raw);if(!state)throw Error('public food schema');
 if(!Array.isArray(rawLore))throw Error('public food lore unreadable');
 const rows=rawLore.filter(x=>!isFoodPayloadLine(x)&&!isCuisineQualityLore(x));if(rows.length>=20)throw Error('public food metadata has no space');
 // The source quality tooltip is optional presentation; the persisted payload
 // always takes priority when a user's custom lore leaves only one free line.
 const qualityLore=cuisineQualityLore(state.quality);if(qualityLore&&rows.length<19)rows.push(qualityLore);
 rows.push({translate:FOOD_PAYLOAD_KEY,with:[JSON.stringify(state)]});return rows;
}
export function writePublicFood(stack,raw){
 const state=normalizePublicFood(raw);if(!state)throw Error('public food schema');
 stack.setLore(publicFoodLoreRows(stack.getRawLore(),state));
 const actual=readPublicFood(stack);if(!actual.valid||JSON.stringify(actual.state)!==JSON.stringify(state))throw Error('public food readback');return stack;
}
