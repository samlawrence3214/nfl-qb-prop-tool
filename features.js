/* Slip builder, paper tracker, and local bet-slip screenshot review. */
let slawsSlip=JSON.parse(localStorage.getItem("slaws_slip")||"[]");
let slawsBets=JSON.parse(localStorage.getItem("slaws_paper_bets")||"[]");
const slawsSave=()=>{localStorage.setItem("slaws_slip",JSON.stringify(slawsSlip));localStorage.setItem("slaws_paper_bets",JSON.stringify(slawsBets))};
const slawsGame=leg=>leg.date+"|"+[leg.team,leg.opponent].sort().join("-");
const americanBreakEven=o=>o<0?-o/(-o+100):100/(o+100);
const decimalPayout=o=>o>0?1+o/100:1+100/-o;
function slawsCandidateLine(p,m){let x=project(p,m),step=CFG[m].step,base=Math.max(m==="receptions"?.5:0,Math.floor(x/step)*step-.5);return{line:Math.max(0,base-step),projection:x}}
function slawsCandidates(){
  let out=[];for(let p of DATA)for(let m of p.markets){let role=p.role||{},s=consistency(p,m);if(p.availability?.status!=="available"||s<7||role.likely_starter===false||(Number.isFinite(role.expected_snap_pct)&&role.expected_snap_pct<.5))continue;let z=slawsCandidateLine(p,m),probability=overProbability(z.projection,z.line,m);if(probability<.64)continue;out.push({p,m,s,...z,probability,score:probability+s*.012})}
  return out.sort((a,b)=>b.score-a.score);
}
function slawsRenderBanner(){
  let root=document.getElementById("modelBanner");if(!root||!DATA.length)return;let a=slawsCandidates(),best=a[0];if(!best){root.innerHTML='<div class="signal warn">No player currently clears the availability and consistency screen.</div>';return}
  let bestGame=slawsGame({date:best.p.upcoming.date,team:best.p.team,opponent:best.p.upcoming.opponent}),second=a.find(x=>x.p.team!==best.p.team&&slawsGame({date:x.p.upcoming.date,team:x.p.team,opponent:x.p.upcoming.opponent})!==bestGame),pair=second?[best,second]:[best],combined=pair.reduce((v,x)=>v*x.probability,1);
  const line=x=>{let price=fairOdds(Math.max(.01,x.probability-.05));return `<div class="pick-line"><b>${x.p.name} over ${x.line.toFixed(1)} ${CFG[x.m].label.toLowerCase()}</b><br><span class="fine">${Math.round(x.probability*100)}% estimate • ${x.s}/10 consistency • minimum acceptable price ${price>0?"+":""}${price} or better</span></div>`};
  root.innerHTML=`<div class="model-pick"><h3>Best model spot</h3><div class="pick-title">${best.p.name}</div>${line(best)}<div class="fine">Not a value bet until the current FanDuel price passes the 5-point edge check.</div><button class="action secondary banner-player" data-id="${best.p.id}" data-market="${best.m}">Open player</button></div><div class="model-pick"><h3>2-leg paper parlay</h3>${pair.map(line).join("")}<div class="fine">${pair.length===2?`Independent combined estimate: ${Math.round(combined*100)}%. Enter both live prices before using.`:"A second independent leg did not clear today's screen."}</div></div>`;
  root.querySelectorAll(".banner-player").forEach(b=>b.onclick=()=>select(b.dataset.id,b.dataset.market));
}
function slawsShow(view){
  ["browseView","consistentView","bearsView","slipView","sgpView","trackerView","reviewView"].forEach(id=>document.getElementById(id)?.classList.toggle("hidden",id!==view));
  UI.marketNav.classList.toggle("hidden",view!=="browseView");
  document.querySelectorAll(".navbtn").forEach(b=>b.classList.toggle("active",b.dataset.slawsView===view||(view==="browseView"&&b.dataset.view==="browse")));
  if(view==="slipView")slawsRenderSlip();if(view==="trackerView")slawsRenderTracker();
}
function slawsLeg(){
  let line=parseFloat(UI.propLine.value),odds=parseInt(UI.propOdds.value,10);
  if(!active||!Number.isFinite(line)||!Number.isFinite(odds)||Math.abs(odds)<100)return null;
  let projection=project(active,market),probability=overProbability(projection,line,market),required=americanBreakEven(odds);
  return{id:Date.now()+"-"+active.id+"-"+market,playerId:active.id,player:active.name,team:active.team,opponent:active.upcoming.opponent,date:active.upcoming.date,market,line,odds,projection,probability,required,edge:probability-required,consistency:consistency(active,market),availability:active.availability?.status||"unverified"};
}
function slawsDecorateEvaluation(){
  document.getElementById("addLeg")?.remove();let leg=slawsLeg();if(!leg)return;
  let b=document.createElement("button");b.id="addLeg";b.className="action";b.textContent="Add to Slip Builder";b.style.marginTop="9px";
  b.onclick=()=>{if(!slawsSlip.some(x=>x.playerId===leg.playerId&&x.market===leg.market&&x.line===leg.line)){slawsSlip.push(leg);slawsSave()}b.textContent="Added to slip";b.disabled=true};
  UI.valueResult.appendChild(b);
}
function slawsCorrelation(){
  let warnings=[];for(let i=0;i<slawsSlip.length;i++)for(let j=i+1;j<slawsSlip.length;j++){
    let a=slawsSlip[i],b=slawsSlip[j];if(slawsGame(a)===slawsGame(b))warnings.push(a.player+" and "+b.player+" share a game");else if(a.team===b.team)warnings.push(a.player+" and "+b.player+" share a team");
  }return [...new Set(warnings)];
}
function slawsCatalogLeg(c){return{id:Date.now()+"-"+c.p.id+"-"+c.m,playerId:c.p.id,player:c.p.name,team:c.p.team,opponent:c.p.upcoming.opponent,date:c.p.upcoming.date,market:c.m,line:c.line,odds:null,projection:c.projection,probability:c.probability,required:null,edge:null,consistency:c.s,availability:c.p.availability?.status||"unverified"}}
function slawsRenderCatalog(){
  let team=document.getElementById("catalogTeam")?.value||"",sort=document.getElementById("catalogSort")?.value||"probability",q=(document.getElementById("catalogSearch")?.value||"").toLowerCase(),a=[];
  for(let p of DATA)for(let m of p.markets){let z=slawsCandidateLine(p,m),s=consistency(p,m),probability=overProbability(z.projection,z.line,m);if((!team||p.team===team)&&(!q||p.name.toLowerCase().includes(q)))a.push({p,m,s,...z,probability})}
  if(sort==="team")a.sort((x,y)=>x.p.team.localeCompare(y.p.team)||y.probability-x.probability);else if(sort==="name")a.sort((x,y)=>x.p.name.localeCompare(y.p.name)||y.probability-x.probability);else a.sort((x,y)=>y.probability-x.probability||(y.s??-1)-(x.s??-1));
  let root=document.getElementById("catalogRows");if(!root)return;root.innerHTML=a.map((x,i)=>`<tr><td><span class="team-code">${x.p.team}</span></td><td><b>${x.p.name}</b></td><td>${CFG[x.m].label}</td><td>O ${x.line.toFixed(1)}</td><td><b>${Math.round(x.probability*100)}%</b></td><td>${x.s==null?"—":x.s+"/10"}</td><td><button class="plus-leg" data-i="${i}" aria-label="Add ${x.p.name} ${CFG[x.m].label}">+</button></td></tr>`).join("");
  root.querySelectorAll(".plus-leg").forEach(b=>b.onclick=()=>{let leg=slawsCatalogLeg(a[+b.dataset.i]);if(!slawsSlip.some(x=>x.playerId===leg.playerId&&x.market===leg.market&&x.line===leg.line)){slawsSlip.push(leg);slawsSave();slawsRenderSlip()}});
  document.getElementById("catalogCount").textContent=a.length+" projected lines";
}
function slawsFeedback(product,warnings){
  let notes=[],missing=slawsSlip.filter(x=>!Number.isFinite(x.odds)),low=slawsSlip.filter(x=>x.consistency<6),thin=slawsSlip.filter(x=>x.probability<.65),bad=slawsSlip.filter(x=>x.availability!=="available"),priced=slawsSlip.filter(x=>Number.isFinite(x.edge)),negative=priced.filter(x=>x.edge<.05);
  if(slawsSlip.length>4)notes.push("This slip has "+slawsSlip.length+" legs; combined hit probability falls quickly as legs are added.");
  if(warnings.length)notes.push("Correlation warning: "+warnings.join("; ")+". Review those legs separately.");
  if(missing.length)notes.push("Enter current FanDuel odds for "+missing.map(x=>x.player).join(", ")+" before judging price value.");
  if(low.length)notes.push("Lower-consistency role: "+low.map(x=>x.player+" "+x.consistency+"/10").join(", ")+".");
  if(thin.length)notes.push("Lower modeled hit probability: "+thin.map(x=>x.player+" "+Math.round(x.probability*100)+"%").join(", ")+".");
  if(bad.length)notes.push("Availability is not fully clear for "+bad.map(x=>x.player).join(", ")+".");
  if(negative.length)notes.push("The current price does not preserve a 5-point model edge for "+negative.map(x=>x.player).join(", ")+".");
  if(!notes.length)notes.push("Every leg clears the current availability, consistency, probability, price, and independence screens. Keep this as a paper test until the tracker has a meaningful sample.");
  let strong=!warnings.length&&!missing.length&&!low.length&&!thin.length&&!bad.length&&!negative.length;
  return`<div class="signal ${strong?"good":"warn"}"><b>${strong?"Stronger slip structure":"Slip needs revision"}</b><ul>${notes.map(x=>"<li>"+x+"</li>").join("")}</ul>${warnings.length?"":"<div>Independent combined estimate: "+Math.round(product*100)+"%.</div>"}</div>`;
}
function slawsGameOptions(){
  let games=new Map();for(let p of DATA){let key=slawsGame({date:p.upcoming.date,team:p.team,opponent:p.upcoming.opponent});if(!games.has(key))games.set(key,{key,date:p.upcoming.date,teams:[p.team,p.upcoming.opponent].sort()})}
  return[...games.values()].sort((a,b)=>String(a.date).localeCompare(String(b.date))||a.teams.join("").localeCompare(b.teams.join("")));
}
function slawsSgpCandidates(key){
  let out=[];for(let p of DATA){if(slawsGame({date:p.upcoming.date,team:p.team,opponent:p.upcoming.opponent})!==key)continue;for(let m of p.markets){let role=p.role||{},s=consistency(p,m),z=slawsCandidateLine(p,m),probability=overProbability(z.projection,z.line,m);if(p.availability?.status!=="available"||s<6||role.likely_starter===false||(Number.isFinite(role.expected_snap_pct)&&role.expected_snap_pct<.45))continue;out.push({p,m,s,...z,probability,score:probability+s*.012})}}
  return out.sort((a,b)=>b.score-a.score);
}
function slawsInvNorm(p){
  let a=[-39.6968302866538,220.946098424521,-275.928510446969,138.357751867269,-30.6647980661472,2.50662827745924],b=[-54.4760987982241,161.585836858041,-155.698979859887,66.8013118877197,-13.2806815528857],c=[-.00778489400243029,-.322396458041136,-2.40075827716184,-2.54973253934373,4.37466414146497,2.93816398269878],d=[.00778469570904146,.32246712907004,2.445134137143,3.75440866190742],q,r;if(p<.02425){q=Math.sqrt(-2*Math.log(p));return(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)}if(p>.97575){q=Math.sqrt(-2*Math.log(1-p));return-(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)}q=p-.5;r=q*q;return(((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
}
function slawsSgpRelation(a,b){if(a.p.id===b.p.id)return"same_player";if(a.p.team===b.p.team){if((a.p.position==="QB"&&["receiving","receptions"].includes(b.m))||(b.p.position==="QB"&&["receiving","receptions"].includes(a.m)))return"qb_receiver";return"same_team"}if(a.m==="passing"&&b.m==="passing")return"opposing_qb";return"opponents"}
function slawsSgpRho(a,b){let markets=[a.m,b.m].sort(),key=slawsSgpRelation(a,b)+"|"+markets.join("|"),model=typeof SGP_CORRELATION_MODEL==="undefined"?null:SGP_CORRELATION_MODEL,row=model?.relationships?.[key];return row&&row.samples>=model.minimum_samples?row:{rho:0,samples:0}}
function slawsCholesky(a){let n=a.length,l=Array.from({length:n},()=>Array(n).fill(0));for(let i=0;i<n;i++)for(let j=0;j<=i;j++){let s=a[i][j];for(let k=0;k<j;k++)s-=l[i][k]*l[j][k];if(i===j){if(s<=1e-8)return null;l[i][j]=Math.sqrt(s)}else l[i][j]=s/l[j][j]}return l}
function slawsJointProbability(legs,trials=16000){
  let n=legs.length,c=Array.from({length:n},(_,i)=>Array.from({length:n},(_,j)=>i===j?1:slawsSgpRho(legs[i],legs[j]).rho)),shrink=1,l;
  while(!(l=slawsCholesky(c))&&shrink>.2){shrink*=.9;for(let i=0;i<n;i++)for(let j=0;j<n;j++)if(i!==j)c[i][j]*=.9}
  if(!l)return null;let thresholds=legs.map(x=>slawsInvNorm(1-x.probability)),seed=2166136261,rand=()=>((seed=Math.imul(seed^seed>>>16,2246822519)>>>0)/4294967296),hits=0;
  for(let t=0;t<trials;t++){let z=[];for(let i=0;i<n;i++){let u=Math.max(1e-10,rand()),v=rand();z.push(Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v))}let all=true;for(let i=0;i<n;i++){let x=0;for(let j=0;j<=i;j++)x+=l[i][j]*z[j];if(x<=thresholds[i]){all=false;break}}if(all)hits++}
  let p=hits/trials,se=Math.sqrt(p*(1-p)/trials),pairs=[];for(let i=0;i<n;i++)for(let j=i+1;j<n;j++){let row=slawsSgpRho(legs[i],legs[j]);pairs.push({label:legs[i].p.name+" ↔ "+legs[j].p.name,rho:row.rho,samples:row.samples})}return{probability:p,se,shrink,pairs};
}
function slawsBuildSgp(){
  let key=document.getElementById("sgpGame").value,count=+document.getElementById("sgpLegCount").value,all=slawsSgpCandidates(key),chosen=[];
  for(let x of all)if(!chosen.some(y=>y.p.id===x.p.id)){chosen.push(x);if(chosen.length===count)break}
  for(let x of all)if(chosen.length<count&&!chosen.includes(x))chosen.push(x);
  let root=document.getElementById("sgpResult");if(!key){root.innerHTML='<div class="signal warn">Choose a game first.</div>';return}if(chosen.length<count){root.innerHTML='<div class="signal warn">This matchup does not have enough available, role-verified props to build that many legs.</div>';return}
  let joint=slawsJointProbability(chosen),jointText=joint?`<div class="signal"><b>Correlation-aware SGP estimate: ${Math.round(joint.probability*100)}%</b><div class="fine">Simulation uncertainty: ±${(1.96*joint.se*100).toFixed(1)} points • historical residual correlations • ${joint.shrink<1?"matrix stabilized":"full estimated matrix"}. This is not a guarantee and still requires live price comparison.</div></div>`:'<div class="signal warn">Not enough relationship data to estimate this SGP jointly.</div>';
  root.innerHTML=`${jointText}<div class="signal warn"><b>Price and lineup gate:</b> Verify every player is active and enter the current FanDuel line and odds after adding these legs. Correlation modeling does not make a bad price valuable.</div><div class="sgp-picks">${chosen.map((x,i)=>`<div class="sgp-pick"><span class="sgp-rank">${i+1}</span><div><b>${x.p.name} over ${x.line.toFixed(1)} ${CFG[x.m].label.toLowerCase()}</b><div class="fine">${x.p.team} • ${Math.round(x.probability*100)}% individual estimate • ${x.s}/10 consistency</div></div></div>`).join("")}</div><button id="addSgp" class="action">Add all ${count} legs to Slip Builder</button>`;
  document.getElementById("addSgp").onclick=()=>{for(let x of chosen){let leg=slawsCatalogLeg(x);if(!slawsSlip.some(y=>y.playerId===leg.playerId&&y.market===leg.market&&y.line===leg.line))slawsSlip.push(leg)}slawsSave();document.getElementById("addSgp").textContent="Added to Slip Builder";document.getElementById("addSgp").disabled=true};
}
function slawsRenderSlip(){
  slawsRenderCatalog();const root=document.getElementById("slipLegs"),summary=document.getElementById("slipSummary");
  root.innerHTML=slawsSlip.length?slawsSlip.map((x,i)=>`<div class="slip-leg"><b>${x.player} — over ${x.line} ${CFG[x.market].label.toLowerCase()}</b><div class="fine">${x.team} vs. ${x.opponent} • model ${Math.round(x.probability*100)}% • ${x.consistency}/10 consistency</div><div class="inline-fields"><label>FanDuel odds<input class="leg-odds" data-i="${i}" type="number" value="${Number.isFinite(x.odds)?x.odds:""}" placeholder="-180"></label><span class="fine">${Number.isFinite(x.edge)?(x.edge>=0?"+":"")+(x.edge*100).toFixed(1)+" point edge":"Price needed"}</span><button class="action danger remove-leg" data-i="${i}">Remove</button></div></div>`).join(""):'<div class="signal">Press a + beside any projected line below to build a slip.</div>';
  root.querySelectorAll(".remove-leg").forEach(b=>b.onclick=()=>{slawsSlip.splice(+b.dataset.i,1);slawsSave();slawsRenderSlip()});
  root.querySelectorAll(".leg-odds").forEach(o=>o.onchange=()=>{let i=+o.dataset.i,v=parseInt(o.value,10),x=slawsSlip[i];x.odds=Number.isFinite(v)&&Math.abs(v)>=100?v:null;x.required=x.odds==null?null:americanBreakEven(x.odds);x.edge=x.required==null?null:x.probability-x.required;slawsSave();slawsRenderSlip()});
  if(!slawsSlip.length){summary.innerHTML="";return}
  let product=slawsSlip.reduce((p,x)=>p*x.probability,1),warnings=slawsCorrelation();
  summary.innerHTML=`<div class="inline-fields"><label>FanDuel parlay odds<input id="parlayOdds" type="number" placeholder="+400 or -120"></label><button id="compareParlay" class="action secondary">Compare price</button><button id="submitFeedback" class="action">Submit Slip for Feedback</button><button id="savePaper" class="action secondary">Save as paper bet</button></div><div id="parlayResult"></div><div id="slipFeedback"></div>`;
  document.getElementById("compareParlay").onclick=()=>{let o=parseInt(document.getElementById("parlayOdds").value,10),out=document.getElementById("parlayResult");if(!Number.isFinite(o)||Math.abs(o)<100){out.className="signal warn";out.textContent="Enter valid American odds.";return}let req=americanBreakEven(o);out.className="signal "+(!warnings.length&&product-req>=.05?"good":"warn");out.innerHTML=warnings.length?"Correlation prevents a dependable combined likelihood. Judge every leg separately.":`Model independence estimate: ${Math.round(product*100)}% • sportsbook break-even: ${Math.round(req*100)}% • difference: ${((product-req)*100).toFixed(1)} points.`};
  document.getElementById("submitFeedback").onclick=()=>document.getElementById("slipFeedback").innerHTML=slawsFeedback(product,warnings);
  document.getElementById("savePaper").onclick=()=>{let o=parseInt(document.getElementById("parlayOdds").value,10);slawsBets.push({id:Date.now(),created:new Date().toISOString(),legs:JSON.parse(JSON.stringify(slawsSlip)),odds:Number.isFinite(o)?o:null,probability:product,correlated:!!warnings.length,status:"pending",stake:1,closingNote:""});slawsSave();document.getElementById("savePaper").textContent="Saved";document.getElementById("savePaper").disabled=true};
}
function slawsMetrics(){
  let settled=slawsBets.filter(x=>x.status!=="pending"),wins=settled.filter(x=>x.status==="win").length,units=0,peak=0,draw=0,maxDraw=0,streak=0,maxStreak=0;
  settled.forEach(x=>{let pnl=x.status==="win"?(x.odds?decimalPayout(x.odds)-1:1):-1;if(x.status==="push")pnl=0;units+=pnl*x.stake;peak=Math.max(peak,units);draw=peak-units;maxDraw=Math.max(maxDraw,draw);streak=x.status==="loss"?streak+1:0;maxStreak=Math.max(maxStreak,streak)});
  return{settled,wins,units,maxDraw,maxStreak};
}
function slawsRenderTracker(){
  let m=slawsMetrics();document.getElementById("trackerStats").innerHTML=`<div class="stat-box">Saved<b>${slawsBets.length}</b></div><div class="stat-box">Settled win rate<b>${m.settled.length?Math.round(m.wins/m.settled.length*100):0}%</b></div><div class="stat-box">Units<b>${m.units.toFixed(2)}</b></div><div class="stat-box">Max drawdown<b>${m.maxDraw.toFixed(2)}</b></div><div class="stat-box">Longest losing streak<b>${m.maxStreak}</b></div>`;
  let body=document.getElementById("trackerRows");body.innerHTML=slawsBets.map((x,i)=>`<tr><td>${new Date(x.created).toLocaleDateString()}</td><td>${x.legs.map(l=>l.player+" O"+l.line).join("<br>")}</td><td>${x.odds==null?"—":(x.odds>0?"+":"")+x.odds}</td><td>${x.correlated?"Correlation warning":Math.round(x.probability*100)+"%"}</td><td><select class="settle" data-i="${i}"><option value="pending">Pending</option><option value="win">Win</option><option value="loss">Loss</option><option value="push">Push</option></select></td><td><input class="close-note" data-i="${i}" value="${x.closingNote||""}" placeholder="Closing line / note"></td><td><button class="action danger delete-bet" data-i="${i}">Delete</button></td></tr>`).join("");
  body.querySelectorAll(".settle").forEach(s=>{s.value=slawsBets[+s.dataset.i].status;s.onchange=()=>{slawsBets[+s.dataset.i].status=s.value;slawsSave();slawsRenderTracker()}});
  body.querySelectorAll(".close-note").forEach(n=>n.onchange=()=>{slawsBets[+n.dataset.i].closingNote=n.value;slawsSave()});
  body.querySelectorAll(".delete-bet").forEach(b=>b.onclick=()=>{if(confirm("Delete this paper-bet record?")){slawsBets.splice(+b.dataset.i,1);slawsSave();slawsRenderTracker()}});
}
async function slawsReviewImage(file){
  let preview=document.getElementById("slipImage"),status=document.getElementById("ocrStatus"),output=document.getElementById("ocrText"),matches=document.getElementById("ocrMatches");
  preview.src=URL.createObjectURL(file);preview.classList.remove("hidden");status.textContent="Reading screenshot locally…";output.textContent="";matches.innerHTML="";
  if(!window.Tesseract){status.textContent="OCR could not load. You can still use the screenshot as a reference and enter the line manually.";return}
  try{let result=await Tesseract.recognize(file,"eng");let text=result.data.text;output.textContent=text;status.textContent="Text extracted locally. Verify every line and price against FanDuel before using it.";let norm=text.toLowerCase(),found=DATA.filter(p=>norm.includes(p.name.toLowerCase())).slice(0,12);matches.innerHTML=found.length?'<h3>Recognized players</h3>'+found.map(p=>`<button class="action secondary ocr-player" data-id="${p.id}">${p.name} — open projections</button>`).join(" "):'<div class="signal warn">No exact player names were matched. OCR can misread stylized sportsbook text.</div>';matches.querySelectorAll(".ocr-player").forEach(b=>b.onclick=()=>{let p=DATA.find(x=>x.id===b.dataset.id);slawsShow("browseView");select(p.id,p.markets[0])})}catch(e){status.textContent="The screenshot could not be read. Use it as a reference and enter the bet details manually."}
}
function slawsSetup(){
  document.title="Slaws Betting Tool";document.querySelector("header h1").textContent="Slaws Betting Tool";
  let top=document.querySelector("nav.nav"),bears=top.querySelector('[data-view="bears"]');
  [{label:"Slip Builder",view:"slipView"},{label:"SGP Builder",view:"sgpView"},{label:"Paper Tracker",view:"trackerView"},{label:"Bet Slip Review",view:"reviewView"}].forEach(x=>{let b=document.createElement("button");b.className="navbtn";b.dataset.slawsView=x.view;b.textContent=x.label;b.onclick=()=>slawsShow(x.view);top.insertBefore(b,bears)});
  bears.textContent="Bears Board";bears.onclick=()=>{setView("bears");slawsShow("bearsView")};top.querySelector('[data-view="browse"]').onclick=()=>{setView("browse");slawsShow("browseView")};top.querySelector('[data-view="consistent"]').onclick=()=>{setView("consistent");slawsShow("consistentView")};
  UI.browseView.insertAdjacentHTML("afterbegin",'<div id="modelBanner" class="model-banner"></div>');
  let main=document.querySelector("main");main.insertAdjacentHTML("beforeend",`<section id="slipView" class="feature-view hidden"><div class="feature-panel"><h2>Slip Builder</h2><div class="local-note">Build directly from the model board, then submit the complete slip for consistency, correlation, availability, probability, and price feedback. Legs stay on this device.</div><div class="slip-section"><h3>Your slip</h3><div id="slipLegs"></div><div id="slipSummary"></div></div><div class="slip-section"><div class="catalog-heading"><div><h3>Add projected lines</h3><div id="catalogCount" class="local-note"></div></div><div class="catalog-toolbar"><input id="catalogSearch" type="search" placeholder="Search player" aria-label="Search player"><select id="catalogTeam" aria-label="Filter by team"><option value="">All teams</option></select><select id="catalogSort" aria-label="Sort projected lines"><option value="probability">Highest probability</option><option value="team">Team</option><option value="name">Player name</option></select></div></div><div class="catalog-table"><table><thead><tr><th>Team</th><th>Player</th><th>Prop</th><th>Suggested line</th><th>Probability</th><th>Consistency</th><th>Add</th></tr></thead><tbody id="catalogRows"></tbody></table></div></div></div></section><section id="trackerView" class="feature-view hidden"><div class="feature-panel"><h2>Paper Tracker</h2><div id="trackerStats" class="stat-row"></div><div class="tracker-table"><table><thead><tr><th>Date</th><th>Legs</th><th>Odds</th><th>Estimate</th><th>Result</th><th>Closing line / note</th><th></th></tr></thead><tbody id="trackerRows"></tbody></table></div></div></section><section id="reviewView" class="feature-view hidden"><div class="feature-panel"><h2>Bet Slip Screenshot Review</h2><div class="signal warn"><b>Privacy:</b> Crop out your name, account number, balance, location, QR codes, and bet identifiers before selecting a screenshot. The image is processed in this browser and is not saved by this site.</div><input id="slipUpload" type="file" accept="image/png,image/jpeg,image/webp"><img id="slipImage" class="screenshot-preview hidden" alt="Selected bet slip"><div id="ocrStatus" class="local-note"></div><div id="ocrMatches"></div><pre id="ocrText" class="ocr-output"></pre><div class="local-note">OCR is only an aid. It may misread names, decimal points, plus/minus signs, or odds. Verify the sportsbook screen manually.</div></div></section>`);
  main.insertAdjacentHTML("beforeend",`<section id="sgpView" class="feature-view hidden"><div class="feature-panel"><h2>SGP Builder</h2><div class="local-note">Choose one matchup and a leg count. The model favors available players with steadier roles and stronger individual over probabilities, while limiting repeated props for the same player when possible.</div><div class="sgp-controls"><label>Game<select id="sgpGame"><option value="">Choose a game</option></select></label><label>Number of legs<select id="sgpLegCount"><option value="2">2 legs</option><option value="3">3 legs</option><option value="4">4 legs</option><option value="5">5 legs</option></select></label><button id="makeSgp" class="action">Build recommended SGP</button></div><div id="sgpResult"></div></div></section>`);
  let originalEvaluate=evaluatePrice;UI.evaluatePrice.onclick=()=>{originalEvaluate();slawsDecorateEvaluation()};document.getElementById("slipUpload").onchange=e=>{if(e.target.files[0])slawsReviewImage(e.target.files[0])};["catalogSearch","catalogTeam","catalogSort"].forEach(id=>document.getElementById(id).oninput=slawsRenderCatalog);document.getElementById("makeSgp").onclick=slawsBuildSgp;
}
slawsSetup();
let slawsBannerTimer=setInterval(()=>{if(DATA.length){clearInterval(slawsBannerTimer);let teams=[...new Set(DATA.map(x=>x.team))].sort(),team=document.getElementById("catalogTeam");team.innerHTML='<option value="">All teams</option>'+teams.map(x=>`<option value="${x}">${x}</option>`).join("");let games=slawsGameOptions(),game=document.getElementById("sgpGame");game.innerHTML='<option value="">Choose a game</option>'+games.map(x=>`<option value="${x.key}">${x.teams.join(" vs. ")} • ${x.date}</option>`).join("");slawsRenderBanner();slawsRenderCatalog()}},100);
