#!/usr/bin/env node
/* No dependencies. Checks the shipped inline browser JS and model, then performs
   a chronological holdout comparison against a simple faction-pair mean. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('public/index.html','utf8');
const inline=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(x=>x[1]).filter(Boolean);
for(const source of inline)new vm.Script(source,{filename:'public/index.html:inline'});
const ctx={};vm.runInNewContext(fs.readFileSync('public/prediction-model.js','utf8'),ctx);
const predict=ctx.MatchupModel.predict;
const sample=(fa,fb,sa,da='Take and Hold',db='Disruption',day='2026-09-01')=>({faction_a:fa,faction_b:fb,score_a_20:sa,score_b_20:20-sa,disposition_a:da,disposition_b:db,event_date:day,event_name:'Test'});
const toy=[sample('Aeldari','Adepta Sororitas',14),sample('Aeldari','Orks',12),sample('Orks','Adepta Sororitas',10)];
const a=predict(toy,'Aeldari','Adepta Sororitas','Take and Hold','Disruption',{now:Date.parse('2026-10-01')});
const b=predict(toy,'Adepta Sororitas','Aeldari','Disruption','Take and Hold',{now:Date.parse('2026-10-01')});
assert.ok(a.score>10&&a.score<20,'estimate should favour Aeldari, with shrinkage');
assert.ok(Math.abs(a.score+b.score-20)<1e-8,'inverting factions should invert the score');
assert.equal(predict(toy,'Necrons','Aeldari').score,null,'missing faction evidence must not invent a prediction');
function csv(input){const out=[];let row=[],field='',q=false;for(let i=0;i<input.length;i++){const ch=input[i];if(ch==='"'){if(q&&input[i+1]==='"'){field+='"';i++}else q=!q}else if(ch===','&&!q){row.push(field);field=''}else if((ch==='\n'||ch==='\r')&&!q){if(ch==='\r'&&input[i+1]==='\n')i++;row.push(field);if(row.some(x=>x))out.push(row);row=[];field=''}else field+=ch}if(row.length||field){row.push(field);out.push(row)}const headers=out.shift()||[];return out.map(values=>Object.fromEntries(headers.map((h,i)=>[h,values[i]||''])));}
const paths=fs.readdirSync('public/data').filter(x=>x.endsWith('.csv')).map(x=>'public/data/'+x);
let rows=[];for(const path of paths){const records=csv(fs.readFileSync(path,'utf8'));if(!records.length||!('faction_a' in records[0])||!('score_a_20' in records[0]))continue;rows.push(...records.filter(r=>r.event_date&&Number.isFinite(+r.score_a_20)&&+r.score_a_20>=0&&+r.score_a_20<=20).map(r=>({...r,score_a_20:+r.score_a_20,score_b_20:+r.score_b_20})))}
rows.sort((a,b)=>a.event_date.localeCompare(b.event_date));
const cutoff='2026-09-01',train=rows.filter(r=>r.event_date<cutoff),test=rows.filter(r=>r.event_date>=cutoff);
let baselineError=0,modelError=0,compared=0;
for(const r of test.slice(0,1500)){
 const p=predict(train,r.faction_a,r.faction_b,r.disposition_a,r.disposition_b,{now:Date.parse(r.event_date+'T12:00:00Z')});
 if(p.score==null)continue;
 const direct=train.filter(x=>x.faction_a===r.faction_a&&x.faction_b===r.faction_b||x.faction_b===r.faction_a&&x.faction_a===r.faction_b);
 const baseline=direct.length?direct.reduce((s,x)=>s+(x.faction_a===r.faction_a?x.score_a_20:x.score_b_20),0)/direct.length:10;
 baselineError+=Math.abs(baseline-r.score_a_20);modelError+=Math.abs(p.score-r.score_a_20);compared++;
}
console.log(JSON.stringify({syntax:'passed',unit:'passed',files:paths.length,train:train.length,test:test.length,compared,baselineMAE:compared?baselineError/compared:null,modelMAE:compared?modelError/compared:null},null,2));
if(!compared)throw new Error('No comparable historical holdout games; model not validated');
