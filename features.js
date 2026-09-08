/* Slip builder, paper tracker, and local bet-slip screenshot review. */
let slawsSlip=JSON.parse(localStorage.getItem("slaws_slip")||"[]");
let slawsBets=JSON.parse(localStorage.getItem("slaws_paper_bets")||"[]");
const slawsSave=()=>{localStorage.setItem("slaws_slip",JSON.stringify(slawsSlip));localStorage.setItem("slaws_paper_bets",JSON.stringify(slawsBets))};
const slawsGame=leg=>leg.date+"|"+[leg.team,leg.opponent].sort().join("-");
const americanBreakEven=o=>o<0?-o/(-o+100):100/(o+100);
const decimalPayout=o=>o>0?1+o/100:1+100/-o;
function slawsShow(view){
  ["browseView","consistentView","bearsView","slipView","trackerView","reviewView"].forEach(id=>document.getElementById(id)?.classList.toggle("hidden",id!==view));
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
function slawsRenderSlip(){
  const root=document.getElementById("slipLegs"),summary=document.getElementById("slipSummary");
  root.innerHTML=slawsSlip.length?slawsSlip.map((x,i)=>`<div class="slip-leg"><b>${x.player} — over ${x.line} ${CFG[x.market].label.toLowerCase()}</b><div class="fine">${x.team} vs. ${x.opponent} • ${x.odds>0?"+":""}${x.odds} • model ${Math.round(x.probability*100)}% • edge ${x.edge>=0?"+":""}${(x.edge*100).toFixed(1)} pts</div><button class="action danger remove-leg" data-i="${i}">Remove</button></div>`).join(""):'<div class="signal">No legs yet. Evaluate a player price, then choose “Add to Slip Builder.”</div>';
  root.querySelectorAll(".remove-leg").forEach(b=>b.onclick=()=>{slawsSlip.splice(+b.dataset.i,1);slawsSave();slawsRenderSlip()});
  if(!slawsSlip.length){summary.innerHTML="";return}
  let product=slawsSlip.reduce((p,x)=>p*x.probability,1),warnings=slawsCorrelation(),minEdge=Math.min(...slawsSlip.map(x=>x.edge)),weak=slawsSlip.some(x=>x.consistency<5||x.availability!=="available");
  let strength=!warnings.length&&!weak&&minEdge>=.05?"Stronger paper-test candidate":weak||minEdge<0?"Weak — pass":"Uncertain — paper test only";
  summary.innerHTML=`<div class="signal ${strength.startsWith("Strong")?"good":"warn"}"><b>${strength}</b><br>${warnings.length?"Combined probability is not reliable because: "+warnings.join("; "):"Independence estimate: "+Math.round(product*100)+"%"}.</div><div class="inline-fields"><label>FanDuel parlay odds<input id="parlayOdds" type="number" placeholder="+400 or -120"></label><button id="compareParlay" class="action">Compare price</button><button id="savePaper" class="action secondary">Save as paper bet</button></div><div id="parlayResult"></div>`;
  document.getElementById("compareParlay").onclick=()=>{let o=parseInt(document.getElementById("parlayOdds").value,10),out=document.getElementById("parlayResult");if(!Number.isFinite(o)||Math.abs(o)<100){out.className="signal warn";out.textContent="Enter valid American odds.";return}let req=americanBreakEven(o);out.className="signal "+(!warnings.length&&product-req>=.05?"good":"warn");out.innerHTML=warnings.length?"Correlation prevents a dependable combined likelihood. Judge every leg separately.":`Model independence estimate: ${Math.round(product*100)}% • sportsbook break-even: ${Math.round(req*100)}% • difference: ${((product-req)*100).toFixed(1)} points.`};
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
  [{label:"Slip Builder",view:"slipView"},{label:"Paper Tracker",view:"trackerView"},{label:"Bet Slip Review",view:"reviewView"}].forEach(x=>{let b=document.createElement("button");b.className="navbtn";b.dataset.slawsView=x.view;b.textContent=x.label;b.onclick=()=>slawsShow(x.view);top.insertBefore(b,bears)});
  bears.textContent="Bears Board";bears.onclick=()=>{setView("bears");slawsShow("bearsView")};top.querySelector('[data-view="browse"]').onclick=()=>{setView("browse");slawsShow("browseView")};top.querySelector('[data-view="consistent"]').onclick=()=>{setView("consistent");slawsShow("consistentView")};
  let main=document.querySelector("main");main.insertAdjacentHTML("beforeend",`<section id="slipView" class="feature-view hidden"><div class="feature-panel"><h2>Slip Builder</h2><div class="local-note">Legs stay on this device. Same-game and same-team combinations are flagged because their outcomes may be correlated.</div><div id="slipLegs"></div><div id="slipSummary"></div></div></section><section id="trackerView" class="feature-view hidden"><div class="feature-panel"><h2>Paper Tracker</h2><div id="trackerStats" class="stat-row"></div><div class="tracker-table"><table><thead><tr><th>Date</th><th>Legs</th><th>Odds</th><th>Estimate</th><th>Result</th><th>Closing line / note</th><th></th></tr></thead><tbody id="trackerRows"></tbody></table></div></div></section><section id="reviewView" class="feature-view hidden"><div class="feature-panel"><h2>Bet Slip Screenshot Review</h2><div class="signal warn"><b>Privacy:</b> Crop out your name, account number, balance, location, QR codes, and bet identifiers before selecting a screenshot. The image is processed in this browser and is not saved by this site.</div><input id="slipUpload" type="file" accept="image/png,image/jpeg,image/webp"><img id="slipImage" class="screenshot-preview hidden" alt="Selected bet slip"><div id="ocrStatus" class="local-note"></div><div id="ocrMatches"></div><pre id="ocrText" class="ocr-output"></pre><div class="local-note">OCR is only an aid. It may misread names, decimal points, plus/minus signs, or odds. Verify the sportsbook screen manually.</div></div></section>`);
  let originalEvaluate=evaluatePrice;UI.evaluatePrice.onclick=()=>{originalEvaluate();slawsDecorateEvaluation()};document.getElementById("slipUpload").onchange=e=>{if(e.target.files[0])slawsReviewImage(e.target.files[0])};
}
slawsSetup();
