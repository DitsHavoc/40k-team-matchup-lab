/* Historical, shrinkage-based 20-point estimate. No fabricated games or win probabilities.
   All data is supplied by the caller; no network requests or hidden external sources. */
(function(root){
 'use strict';
 const clamp=(x,min,max)=>Math.max(min,Math.min(max,x));
 const valid=r=>Number.isFinite(Number(r.score_a_20))&&Number(r.score_a_20)>=0&&Number(r.score_a_20)<=20;
 function weighted(rows,predicate,side,now){
  let sum=0,weight=0,weight2=0,n=0,events=new Set();
  for(const r of rows){
   if(!valid(r))continue;
   const which=predicate(r);if(!which)continue;
   const date=Date.parse(String(r.event_date||'')+'T12:00:00Z');
   const age=Number.isFinite(date)?Math.max(0,(now-date)/86400000):0;
   const w=Math.pow(0.5,age/120);
   const v=side(r,which);
   if(!Number.isFinite(v))continue;
   sum+=v*w;weight+=w;weight2+=w*w;n++;
   if(r.event_name)events.add(r.event_name);
  }
  return {n,avg:weight?sum/weight:null,eff:weight2?weight*weight/weight2:0,events:events.size};
 }
 function predict(rows,a,b,da='',db='',options={}){
  const now=options.now||Date.now();
  const pool=rows.filter(valid);
  const oriented=(r,x,y)=>r.faction_a===x&&r.faction_b===y?1:r.faction_b===x&&r.faction_a===y?-1:0;
  const score=(r,side)=>side===1?Number(r.score_a_20):Number(r.score_b_20);
  const own=weighted(pool,r=>r.faction_a===a?1:r.faction_b===a?-1:0,score,now);
  const opp=weighted(pool,r=>r.faction_a===b?1:r.faction_b===b?-1:0,(r,side)=>20-score(r,side),now);
  const both=weighted(pool,r=>oriented(r,a,b),score,now);
  const ownDisp=da?weighted(pool,r=>(r.faction_a===a&&r.disposition_a===da?1:r.faction_b===a&&r.disposition_b===da?-1:0),score,now):null;
  const oppDisp=db?weighted(pool,r=>(r.faction_a===b&&r.disposition_a===db?1:r.faction_b===b&&r.disposition_b===db?-1:0),(r,side)=>20-score(r,side),now):null;
  const exact=da||db?weighted(pool,r=>{const side=oriented(r,a,b);return side&&(!da||(side===1?r.disposition_a:r.disposition_b)===da)&&(!db||(side===1?r.disposition_b:r.disposition_a)===db)?side:0},score,now):both;
  // Faction skill estimate is shrunk heavily towards 10/20, then refined by direct matchup.
  const nOwn=own.eff/(own.eff+60),nOpp=opp.eff/(opp.eff+60);
  if(own.n===0||opp.n===0)return {score:null,confidence:'Insufficient evidence',reason:'One or both factions have no recorded results',exact:exact.n,headToHead:both.n,own:own.n,opponent:opp.n};
  let estimate=10+(own.avg-10)*nOwn*.65+(opp.avg-10)*nOpp*.65;
  if(both.n)estimate+=(both.avg-estimate)*(both.eff/(both.eff+35));
  // Disposition shifts are differences against the same faction's history, NOT absolute win rates.
  if(ownDisp?.n)estimate+=(ownDisp.avg-own.avg)*(ownDisp.eff/(ownDisp.eff+50))*.6;
  if(oppDisp?.n)estimate+=(oppDisp.avg-opp.avg)*(oppDisp.eff/(oppDisp.eff+50))*.6;
  // The most specific observed evidence is allowed to refine, never dominate, the prior.
  if(da||db){const prior=estimate;estimate+=(exact.avg==null?0:(exact.avg-prior)*(exact.eff/(exact.eff+20)));}
  estimate=clamp(estimate,0,20);
  const confidence=both.n>=30&&exact.n>=10&&Math.min(own.n,opp.n)>=100?'Moderate':both.n>=10&&Math.min(own.n,opp.n)>=40?'Limited':'Low';
  return {score:estimate,confidence,exact:exact.n,headToHead:both.n,own:own.n,opponent:opp.n,exactAverage:exact.avg,headAverage:both.avg,ownDisposition:ownDisp?.n??null,opponentDisposition:oppDisp?.n??null,method:'Shrinkage estimate (120-day recency half-life); experimental, not back-tested'};
 }
 root.MatchupModel={predict,version:'0.1.0'};
})(typeof window!=='undefined'?window:globalThis);
