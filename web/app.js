import {buildMotionPlan,keyPlayerIds,replayMinutes,combinationAt} from "./match_clock.mjs";
import {runningPose,playerMotion,coordinatedMotion,formationGeometry} from "./pitch_motion.mjs";
import {summarizeMatch} from "./match_stats.mjs";
const $ = id => document.getElementById(id);
const labels = {Goal:"Goal", "Off T":"Off target", Saved:"Saved"};
const eventLabels = {Pass:"Pass", "Ball Receipt*":"Receipt", Carry:"Carry", Shot:"Shot", "Goal Keeper":"Save", "Kick Off":"Kick-off", Interception:"Interception", Pressure:"Pressure", Tackle:"Tackle", "Full Time":"Full time"};
let data, cursor=0, timer=null, selected=null, pov="striker", prepared=null, busy=false, epoch=0;
let schedule=[],motionPlan=[], playbackMode="idle", highlightResume=false, fallbackTimer=null;
let pitchAnimation=null, lastPitchEvent=null, pitchBall=null;
const pitchPositions=new Map();
let commentaryAudience=null, commentaryCursor=0;
const prefetched=new Map();
const viewedClips=new Set();
const videoWaiters=[];
let activeVideoJobs=0;
function reserveVideoSlot(){
  if(activeVideoJobs<2){activeVideoJobs++;return Promise.resolve();}
  return new Promise(resolve=>videoWaiters.push(resolve));
}
function releaseVideoSlot(){
  const next=videoWaiters.shift();
  if(next)next();else activeVideoJobs--;
}
let insightController=null, insightKey=null;
const insightCache=new Map();
const aiCommentaryCache=new Map();
const aiLineKey=(eventId,side,mode)=>`${eventId}:${side}:${mode}`;
function upgradeCommentaryCard(insight){
  if(insight.generator!=="ai" || insight.facts.event_type!=="Shot")return;
  aiCommentaryCache.set(aiLineKey(insight.event_id,insight.audience,insight.mode),insight.text);
  if($("live-language").value!=="zh" || audience()!==insight.audience || $("mode").value!==insight.mode)return;
  const row=[...$("commentary-history").children].find(item=>item.dataset.eventId===insight.event_id);
  if(row){row.querySelector("p").textContent=insight.text;row.classList.add("ai-commentary");}
}
async function updateLiveInsight(event){
  if(event && !["Shot","Interception","Tackle","Pressure"].includes(event.type.name))return;
  const key=event?`${event.id}:${audience()}:${$("mode").value}:${$("live-language").value}`:null;
  if(key===insightKey)return;
  insightKey=key;
  $("insight-evidence").hidden=true;
  if(!event){
    $("insight").hidden=true;
    $("insight-title").textContent="Why this moment matters";
    $("insight-text").textContent="Insights update as the match unfolds.";
    return;
  }
  $("insight").hidden=false;
  const pending={zh:["正在解读当前动作","结合当前事件与球场位置，整理分析依据…"],
    en:["Reading the current play","Checking the event and pitch position…"],
    es:["Analizando la jugada","Revisando el evento y su posición en el campo…"],
    fr:["Analyse de l'action","Examen de l'événement et de sa position sur le terrain…"]}[$("live-language").value];
  $("insight-title").textContent=`${event.minute}′ · ${pending[0]}`;
  $("insight-text").textContent=pending[1];
  const controller=new AbortController();insightController=controller;
  let baselineShown=false;
  const params={event_id:event.id,audience:audience(),mode:$("mode").value};
  async function fetchInsight(use_ai){
    const response=await fetch("/api/insights",{method:"POST",signal:controller.signal,
      headers:{"Content-Type":"application/json"},body:JSON.stringify({...params,use_ai})});
    const result=await response.json();if(!response.ok)throw Error("Could not load match insight");return result;
  }
  try{
    let insight=insightCache.get(key);
    if(!insight){
      insight=await fetchInsight(false);
      if(key!==insightKey)return;
      displayLiveInsight(insight);baselineShown=true;
      const featured=event.type.name==="Shot";
      if(insight.ai_available && featured && $("live-language").value==="zh")insight=await fetchInsight(true);
      insightCache.set(key,insight);
    }
    upgradeCommentaryCard(insight);
    if(key!==insightKey)return;
    displayLiveInsight(insight);
  }catch(error){
    if(key===insightKey && error.name!=="AbortError"){
      if(baselineShown){$("insight-source").textContent="Event analysis · AI unavailable";}
      else{
        $("insight-title").textContent="Insight temporarily unavailable";
        $("insight-text").textContent="The match will continue. Try switching viewing modes later.";
      }
      insightKey=null;
    }
  }
}
function displayLiveInsight(insight){
    const language=$("live-language").value;
    if(language==="es"||language==="fr"){
      const fact=insight.facts;
      const translations={
        es:{heading:"LECTURA DEL PARTIDO · POR QUÉ IMPORTA",source:"Análisis de los eventos",verdict:"LECTURA DE LA JUGADA",
          goal:["¡Una ocasión que termina en gol!","El marcador cambia; esta acción ya tiene un impacto decisivo."],
          saved:["¡Disparo a puerta y parada!","La jugada creó una ocasión, pero el portero evitó el gol."],
          wide:["Remate sin gol","La jugada terminó en tiro, pero el balón no fue a puerta."],
          win:["Cambio de posesión","La recuperación corta el ataque rival y abre una nueva jugada."],
          pressure:["Presión sobre el balón","El defensor reduce el espacio, aunque la posesión aún no ha cambiado."]},
        fr:{heading:"LECTURE DU MATCH · POURQUOI C'EST IMPORTANT",source:"Analyse des événements",verdict:"LECTURE DE L'ACTION",
          goal:["Une occasion transformée en but !","Le score change : cette action pèse directement sur le match."],
          saved:["Tir cadré et arrêt !","L'action a créé une occasion, mais le gardien a empêché le but."],
          wide:["Un tir sans but","L'action s'achève sur une frappe qui manque le cadre."],
          win:["Changement de possession","La récupération stoppe l'attaque adverse et lance une nouvelle phase."],
          pressure:["Pression sur le ballon","Le défenseur ferme l'espace, sans encore récupérer le ballon."]},
      };
      const words=translations[language];
      const category=fact.event_type==="Shot"?({Goal:"goal",Saved:"saved"}[fact.outcome]||"wide"):
        fact.event_type==="Pressure"?"pressure":"win";
      const [title,explanation]=words[category];
      $("insight-heading-label").textContent=words.heading;
      $("insight-source").textContent=words.source;
      $("insight-title").textContent=`${insight.render.match_minute}′ · ${title}`;
      $("insight-text").hidden=false;$("insight-text").textContent=explanation;
      $("insight-verdict-label").textContent=words.verdict;
      $("insight-verdict").textContent=title;$("insight-why").textContent=explanation;
      $("insight-analyst").hidden=true;$("insight-evidence").hidden=true;
      return;
    }
    const english=$("live-language").value==="en";
    const fact=insight.facts;
    const context=insight.context||{}, analysis=insight.analysis||{};
    let englishTitle="Why this matters", englishText="The next phase will show whether the move develops.";
    if(fact.event_type==="Shot"){
      englishTitle=fact.outcome==="Goal"?"A chance becomes a goal":fact.outcome==="Saved"?"The keeper preserves the score":"The chance goes begging";
      englishText=`A shot from about ${Math.round(fact.goal_distance_m)} metres ${fact.outcome==="Goal"?"changes the score":fact.outcome==="Saved"?"is stopped by the keeper":"goes wide"}. ${fact.nearest_defender_m!=null?`The nearest defender was about ${fact.nearest_defender_m} metres away.`:""}`;
    }else if(fact.event_type==="Pressure"){
      englishTitle="Pressure on the ball";englishText="The defender closes down the carrier, forcing a quicker decision. Pressure alone does not prove a turnover.";
    }else if(["Interception","Tackle"].includes(fact.event_type)){
      englishTitle="Possession changes hands";englishText="This defensive action stops the attack. Watch whether the new ball carrier can move forward quickly.";
    }
    $("insight-title").textContent=english?englishTitle:insight.title;
    $("insight-text").textContent=english?englishText:insight.text;
    $("insight-text").hidden=!english && insight.generator==="ai" && fact.event_type==="Shot";
    $("insight-source").textContent=english?"Rule explanation · synthetic events":insight.generator==="ai"?"AI 解说 · 规则局面判断":insight.generator_label;
    $("insight-heading-label").textContent=english?"MATCH INTELLIGENCE · WHY IT MATTERS":"场边洞察 · 为什么重要";
    $("insight-verdict-label").textContent=english?"READ OF PLAY":"局面判断";
    let englishVerdict="The match state needs more evidence";
    let englishWhy="This event alone does not establish a sustained pattern.";
    let englishWatch="Watch the next sequence before drawing a stronger conclusion.";
    if(fact.event_type==="Shot"){
      englishVerdict=fact.outcome==="Goal"?"The chance changes the score":fact.outcome==="Saved"?"A real chance, held by the keeper":"A shot, without a finish";
      englishWhy=fact.outcome==="Goal"?"This attack has produced a goal, so its impact is already on the scoreboard.":fact.outcome==="Saved"?"The move reached a shot, but the keeper prevented a goal.":"The move created a shot, but the miss leaves the score unchanged.";
      englishWatch="Watch whether the next attack reaches a similar shooting position.";
    }else if(fact.event_type==="Pressure"){
      englishVerdict="Pressure without a confirmed turnover";englishWhy="Closing down the carrier limits space, but one pressure event does not prove possession has changed.";
      englishWatch="Watch for an inaccurate pass, interception or tackle.";
    }else if(["Interception","Tackle"].includes(fact.event_type)){
      englishVerdict="A defensive win changes possession";englishWhy="The action ends the opponent's current move and creates a new starting point.";
      englishWatch="Watch the first pass after the ball is won.";
    }
    $("insight-verdict").textContent=english?englishVerdict:analysis.verdict||"";
    $("insight-why").textContent=english?englishWhy:analysis.why||"";
    $("insight-analyst").hidden=$("mode").value!=="analyst";
    const labelMap={"射门距离":"Shot distance","本方近五分钟射门":"Team shots · last 5 min","最近防守者":"Nearest defender","本次球权成功传球":"Completed passes · this possession","本方近五分钟施压":"Team pressures · last 5 min","本方近五分钟夺回球权":"Ball wins · last 5 min","向前推进":"Forward progress","合成传球难度":"Synthetic pass difficulty"};
    $("insight-signals").replaceChildren(...(analysis.signals||[]).map(signal=>{
      const item=document.createElement("div");item.className="insight-signal";
      const label=document.createElement("span");label.textContent=english?labelMap[signal.label]||signal.label:signal.label;
      const value=document.createElement("strong");value.textContent=signal.value;item.append(label,value);return item;
    }));
    let englishPattern="There is not enough continuous evidence yet to call one side in control.";
    if(context.rhythm==="rising_shot_volume")englishPattern=`Shot rhythm: ${context.recent_shots} team shots in the last five minutes, up from ${context.previous_shots} in the previous five.`;
    else if(context.rhythm==="repeat_shots")englishPattern=`The team has taken ${context.recent_shots} shots in the last five minutes; chances are recurring.`;
    else if(context.rhythm==="pressure_cluster")englishPattern=`The team has recorded ${context.recent_pressures} pressures in five minutes, though that alone does not establish control.`;
    $("insight-pattern").textContent=english?englishPattern:analysis.pattern||"";
    $("insight-watch").textContent=english?`NEXT TO WATCH · ${englishWatch}`:`接下来观察 · ${analysis.watch||""}`;
    $("insight-scope").textContent=english?"Based only on synthetic events so far; local actions are not full tactical tracking.":analysis.scope||"";
    $("insight-measurement").textContent=english?"Distances and angles are estimates from synthetic event positions on a 105 × 68 m pitch.":insight.measurement_note;
    const factNames=english?{pass_distance_m:"Pass distance (m)",forward_progress_m:"Forward progress (m)",
      ball_speed_kmh:"Ball speed (km/h)",shot_speed_kmh:"Shot speed (km/h)",pass_difficulty:"Pass difficulty (0–100)",
      carry_distance_m:"Carry distance (m)",goal_distance_reduction_m:"Closer to goal (m)",
      goal_distance_m:"Distance to goal (m)",nearest_defender_m:"Nearest defender (m)",
      goal_opening_angle_degrees:"Goal opening angle (°)"}:{pass_distance_m:"传球距离（米）",forward_progress_m:"向前推进（米）",
      ball_speed_kmh:"传球球速（公里/小时）",shot_speed_kmh:"射门球速（公里/小时）",pass_difficulty:"传球难度（0–100）",
      carry_distance_m:"带球距离（米）",goal_distance_reduction_m:"距球门缩短（米）",
      goal_distance_m:"距球门中心（米）",nearest_defender_m:"最近防守球员（米）",
      goal_opening_angle_degrees:"两门柱夹角（度）"};
    $("insight-facts").replaceChildren(...Object.entries(factNames).filter(([key])=>insight.facts[key]!=null).map(([key,label])=>{
      const li=document.createElement("li");li.textContent=`${label}：${insight.facts[key]}`;return li;
    }));
    $("insight-events").replaceChildren(...insight.evidence.map(item=>{
      const li=document.createElement("li");
      const event=data.events.find(candidate=>candidate.id===item.event_id);
      li.textContent=english&&event?`${event.minute}′ ${event.player.name} · ${event.type.name}`:item.label;return li;
    }));
    $("insight-evidence").hidden=$("mode").value!=="analyst";
}
const audience=()=>$("audience").value;
function applyAudience(){
  if(selected && audience()!=="neutral"){
    const supported=data.match[audience()==="home"?"home_team":"away_team"].id;
    pov=shotFor(selected).team.id===supported?"striker":"goalkeeper";
  }
  ["striker","goalkeeper"].forEach(id=>{
    $(id).className=id===pov?"selected":"secondary";
    $(id).disabled=audience()!=="neutral";
  });
  $("audience-hint").textContent=audience()==="neutral"
    ?"Neutral viewers can choose the striker or goalkeeper POV."
    :"Your team's POV is selected automatically when a clip is ready.";
}
const seen = () => data.events.slice(0,cursor);
const unlocked = clip => seen().some(e=>e.id===clip.trigger_event_id);
const shotFor = clip => data.events.find(e=>e.id===clip.trigger_event_id);
function clearResult(){
  epoch++;clearTimeout(fallbackTimer);fallbackTimer=null;
  busy=false;prepared=null;highlightResume=false;$("skip-highlight").hidden=true;$("result").hidden=true;
  const video=$("highlight-video");video.onended=null;video.onerror=null;video.onplay=null;video.pause();video.removeAttribute("src");video.load();video.hidden=true;$("pov-stage").hidden=true;
  $("video-status").textContent="Scene selected. Preparing the video request.";
}
function updatePlayback(){
  const finished=data && cursor>=data.events.length;
  $("play").disabled=!!finished || playbackMode==="highlight";
  $("play").textContent=finished?"Full time":playbackMode==="playing"?"Pause":playbackMode==="highlight"?"POV playing":"Resume match";
}
function stop(){clearTimeout(timer);timer=null;updatePlayback();}
function scheduleNext(){
  if(playbackMode!=="playing" || cursor>=data.events.length)return;
  const delay=(schedule[Math.max(0,cursor-1)]||0)/Number($("speed").value);
  timer=setTimeout(()=>{timer=null;tick();},delay);
}
function tick(){
  if(cursor>=data.events.length){stop();playbackMode="finished";updatePlayback();return;}
  const event=data.events[cursor++];
  if(data.clips.some(c=>c.event_ids[0]===event.id)){selected=null;clearResult();}
  const clip=data.clips.find(c=>c.trigger_event_id===event.id);
  if(clip){selected=clip;clearResult();applyAudience();warmHighlight(clip);warmUpcoming();}
  render();
  refreshReadyHighlight();
  if(cursor===data.events.length){stop();playbackMode="finished";updatePlayback();return;}
  if(data.clips.some(c=>c.event_ids.at(-1)===event.id)){
    const entry=prefetched.get(JSON.stringify(highlightProfile(selected)));
    if(entry?.status==="succeeded" && entry.artifacts?.["video_job.json"]?.media_url){
      stop();playbackMode="highlight";prepareHighlight(true,true);return;
    }
    $("video-status").textContent="The moment has happened. Its POV video is still generating while the match continues.";
  }
  if(playbackMode==="playing")scheduleNext();
}
function start(){
  stop();if(!data || cursor>=data.events.length || playbackMode==="highlight")return;
  playbackMode="playing";
  if(cursor===0)tick();else scheduleNext();
  updatePlayback();
}
function renderCommentary(){
  const language=$("live-language").value;
  const tracks={zh:data.commentary,en:data.commentary_en,es:data.commentary_es,fr:data.commentary_fr};
  const lines=tracks[language]?.[audience()]||[];
  const feed=$("commentary-history");
  const trackKey=`${audience()}:${$('live-language').value}:${$("mode").value}`;
  if(commentaryAudience!==trackKey || cursor<commentaryCursor){
    feed.replaceChildren();commentaryCursor=Math.max(0,cursor-28);commentaryAudience=trackKey;
  }
  for(let index=commentaryCursor;index<cursor;index++){
    const line=lines[index];if(!line)continue;
    const addCard=(content,kind="",eventId="")=>{
      const row=document.createElement("div");row.className=`commentary-card ${kind}`.trim();
      if(eventId)row.dataset.eventId=eventId;
      const time=document.createElement("time");
      const sections={zh:["赛前介绍","阶段回顾"],en:["Team news","Match check-in"],
        es:["Alineaciones","Balance del partido"],fr:["Compositions","Bilan du match"]};
      const section=kind==="match-intro"?` · ${sections[language][0]}`
        :kind==="match-summary"?` · ${sections[language][1]}`:"";
      time.textContent=`${Math.floor(line.match_second/60)}′${section}`;
      const text=document.createElement("p");text.textContent=content;
      row.append(time,text);feed.append(row);return row;
    };
    for(const intro of line.intro||[])addCard(intro,"match-intro");
    if(line.text){
      const aiText=$("live-language").value==="zh"?aiCommentaryCache.get(aiLineKey(line.event_id,audience(),$("mode").value)):null;
      const row=addCard(aiText||line.text,data.events[index]?.type.name==="Shot"?"key-moment":"",line.event_id);
      if(aiText)row.classList.add("ai-commentary");
      if($("mode").value==="analyst"){
        const metric=data.events[index]?.kinematics;
        if(metric){const tag=document.createElement("small");tag.className="event-metric";
          const metricLabels={zh:["传球","难度","射门球速","飞行"],en:["Pass","Difficulty","Shot speed","Flight"],
            es:["Pase","Dificultad","Velocidad del tiro","Vuelo"],fr:["Passe","Difficulté","Vitesse du tir","Trajet"]}[language];
          tag.textContent=data.events[index].type.name==="Pass"
            ?`${metricLabels[0]} ${metric.ball_distance_m} m · ${metric.ball_speed_kmh} km/h · ${metricLabels[1]} ${metric.pass_difficulty}/100`
            :`${metricLabels[2]} ${metric.ball_speed_kmh} km/h · ${metricLabels[3]} ${metric.ball_flight_seconds} s`;
          row.append(tag);}
      }
    }
    if(line.summary?.text)addCard(line.summary.text,"match-summary");
  }
  commentaryCursor=cursor;
  while(feed.children.length>50)feed.firstChild.remove();
  feed.scrollTop=feed.scrollHeight;
  const lastSpoken=lines.slice(0,cursor).reverse().map(line=>line.summary?.text||line.text||line.intro?.at(-1)).find(Boolean);
  $("commentary-live-text").textContent=lastSpoken||({zh:"即将开球……",en:"Kick-off coming up…",es:"El partido está por comenzar…",fr:"Le coup d'envoi approche…"}[language]);
}
function renderLineups(){
  const positionNames={GK:"Goalkeeper",LB:"Left back",CB:"Centre back",RB:"Right back",DM:"Defensive midfield",CM:"Central midfield",LW:"Left wing",ST:"Striker",RW:"Right wing"};
  const spots={1:[50,8],2:[14,20],3:[38,20],4:[62,20],5:[86,20],
    6:[50,31],7:[30,36],8:[70,36],9:[18,44],10:[50,44],11:[82,44]};
  const field=$("lineup-players");field.replaceChildren();
  for(const side of ["home","away"]){
    const team=data.match[`${side}_team`];
    $(side==="home"?"lineup-home-name":"lineup-away-name").textContent=team.name;
    $(side==="home"?"data-home-name":"data-away-name").textContent=team.name;
    const players=data.match.players.filter(player=>player.team_id===team.id)
      .sort((a,b)=>a.shirt_number-b.shirt_number);
    for(const player of players){
      const [x,y]=spots[player.shirt_number];
      const node=document.createElement("div");node.className=`lineup-player ${side}`;
      node.style.left=`${side==="home"?100-x:x}%`;
      node.style.top=`${side==="home"?100-y:y}%`;
      node.title=`${player.player.name} · ${positionNames[player.position]||player.position}`;
      const number=document.createElement("span");number.className="lineup-badge";number.textContent=player.shirt_number;
      const name=document.createElement("span");name.className="lineup-player-name";name.textContent=player.player.name;
      const position=document.createElement("span");position.className="lineup-player-role";position.textContent=positionNames[player.position]||player.position;
      node.append(number,name,position);field.append(node);
    }
  }
}
function renderDataBoard(events){
  const [home,away]=summarizeMatch(data.match,events);
  const last=events.at(-1);
  $("data-clock").textContent=`Played ${last?.minute||0}′ · Live statistics`;
  const metrics=[
    ["Goals","goals",value=>String(value)],
    ["Possession","possession",value=>`${Math.round(value*100)}%`],
    ["Shots","shots",value=>String(value)],
    ["Shots on target","shotsOnTarget",value=>String(value)],
    ["Shots inside box","shotsInsideBox",value=>String(value)],
    ["Shots outside box","shotsOutsideBox",value=>String(value)],
    ["Offsides","offsides",value=>String(value)],
    ["Fouls","fouls",value=>String(value)],
    ["Yellow cards","yellowCards",value=>String(value)],
    ["Red cards","redCards",value=>String(value)],
    ["Key passes","keyPasses",value=>String(value)],
    ["Long passes","longPasses",value=>String(value)],
    ["Completed passes","completedPasses",value=>String(value)],
    ["Pass accuracy","passAccuracy",value=>`${Math.round(value*100)}%`],
    ["Avg. pass speed","averagePassSpeed",value=>`${Math.round(value)} km/h`],
    ["Avg. shot speed","averageShotSpeed",value=>`${Math.round(value)} km/h`],
    ["xG estimate","xg",value=>value.toFixed(2)],
  ];
  $("metric-rows").replaceChildren(...metrics.map(([label,key,format])=>{
    const row=document.createElement("div");row.className="metric-row";
    const left=document.createElement("strong");left.className="metric-value";left.textContent=format(home[key]);
    const middle=document.createElement("div");middle.className="metric-middle";
    const title=document.createElement("span");title.className="metric-label";title.textContent=label;
    const bars=document.createElement("div");bars.className="metric-bars";
    const scale=Math.max(home[key],away[key],.01);
    for(const value of [home[key],away[key]]){
      const track=document.createElement("span"),fill=document.createElement("i");
      fill.style.width=`${value/scale*100}%`;track.append(fill);bars.append(track);
    }
    middle.append(title,bars);
    const right=document.createElement("strong");right.className="metric-value";right.textContent=format(away[key]);
    row.append(left,middle,right);return row;
  }));
}
function render(){
  updatePlayback();
  applyAudience();
  $("pitch").classList.toggle("show-formations",$("mode").value==="analyst");
  const events=seen(), shots=events.filter(e=>e.type.name==="Shot"), goals=shots.filter(e=>e.shot.outcome.name==="Goal");
  const last=events.at(-1);
  const homeId=data.match.home_team.id;
  $("score").textContent=`${goals.filter(e=>e.team.id===homeId).length} : ${goals.filter(e=>e.team.id!==homeId).length}`;
  $("clock").textContent=last?`${last.minute}′ ${String(last.second).padStart(2,"0")}″ · Synthetic match`:"Kick-off soon";
  $("progress").textContent=`${cursor} / ${data.events.length}`;
  const onTarget=shots.filter(e=>["Goal","Saved"].includes(e.shot.outcome.name)).length;
  $("stats").replaceChildren(...[[shots.length,"Shots"],[onTarget,"On target"],[events.filter(e=>e.type.name==="Pass").length,"Passes"]].map(([value,label])=>{
    const item=document.createElement("div");item.className="stat";
    const number=document.createElement("b");number.textContent=value;
    const text=document.createElement("span");text.textContent=label;item.append(number,text);return item;
  }));
  const available=data.clips.filter(unlocked);
  $("moments").replaceChildren(...data.clips.map(clip=>{
    const shot=shotFor(clip), button=document.createElement("button");
    button.className="moment"+(selected?.id===clip.id?" active":"");
    button.disabled=!unlocked(clip);
    const title=document.createElement("span");title.textContent=`${shot.minute}′ · ${labels[shot.shot.outcome.name]}`;
    const sub=document.createElement("small");sub.textContent=unlocked(clip)?`${shot.player.name} → View POV`:"Waiting for the moment";
    button.append(title,sub);button.onclick=()=>{stop();playbackMode="paused";selected=clip;clearResult();render();prepareHighlight(true,false);};return button;
  }));
  $("recap").textContent=available.length?available.map(c=>{const e=shotFor(c);return `${e.minute}′: ${e.player.name} — ${labels[e.shot.outcome.name]}.`;}).join(" ")+(cursor===data.events.length?" Full time.":""):"The recap appears as key moments unfold.";
  $("event-log").replaceChildren(...events.slice(-6).reverse().map(e=>{const p=document.createElement("div");p.textContent=`${e.minute}:${String(e.second).padStart(2,"0")} · ${e.player.name} · ${eventLabels[e.type.name]}`;return p;}));
  $("prepare").disabled=busy || highlightResume || !selected || !unlocked(selected);
  $("moment-title").textContent=selected?`${shotFor(selected).minute}′ ${labels[shotFor(selected).shot.outcome.name]} · ${pov==="striker"?"Striker":"Goalkeeper"} POV`:"Waiting for a key moment";
  renderDataBoard(events);
  renderCommentary();
  updateLiveInsight([...events].reverse().find(event=>["Shot","Interception","Tackle","Pressure"].includes(event.type.name))||null);
  renderPitch(last);
}
function pitchState(event){
  const clip=data.clips.find(c=>c.event_ids.includes(event.id));
  if(!clip){
    const active=new Set([event.player.id]);
    if(event.pass)active.add(event.pass.recipient.id);
    if(event.kick_off)active.add(event.kick_off.recipient.id);
    return {points:event.tracking.start.map(p=>({
      player:data.match.players.find(entry=>entry.player.id===p.player_id).player,
      location:p.location,teammate:p.team_id===data.match.home_team.id
    })),active};
  }
  const chain=clip.event_ids.map(id=>data.events.find(e=>e.id===id));
  const shot=shotFor(clip);
  const positions=new Map([
    [shot.player.id,{location:shot.location,player:shot.player,teammate:true}],
    ...shot.shot.freeze_frame.map(p=>[p.player.id,{...p}])
  ]);
  // Seed participants with their first known event position. Other positions are
  // explicitly schematic shot-snapshot fallbacks, never inferred tracking.
  const initialized=new Set();
  for(const item of chain){
    if(item.type.name==="Goal Keeper")continue;
    if(!initialized.has(item.player.id)){
      positions.set(item.player.id,{location:item.location,player:item.player,teammate:item.team.id===data.match.home_team.id});
      initialized.add(item.player.id);
    }
    if(item.pass && !initialized.has(item.pass.recipient.id)){
      positions.set(item.pass.recipient.id,{location:item.pass.end_location,player:item.pass.recipient,teammate:true});
      initialized.add(item.pass.recipient.id);
    }
  }
  for(const item of chain.slice(0,chain.findIndex(e=>e.id===event.id)+1)){
    if(item.shot){
      item.shot.freeze_frame.forEach(p=>positions.set(p.player.id,{...p}));
    }
    positions.set(item.player.id,{
      player:item.player,teammate:item.team.id===data.match.home_team.id,
      location:item.carry?.end_location || item.location
    });
    if(item.pass)positions.set(item.pass.recipient.id,{
      player:item.pass.recipient,teammate:true,location:item.pass.end_location
    });
  }
  const active=new Set([event.player.id]);
  if(event.pass)active.add(event.pass.recipient.id);
  if(event.kick_off)active.add(event.kick_off.recipient.id);
  if(event.shot)shot.shot.freeze_frame.filter(p=>p.position.name==="Goalkeeper").forEach(p=>active.add(p.player.id));
  if(event.tracking){
    return {points:event.tracking.start.map(p=>({
      player:data.match.players.find(entry=>entry.player.id===p.player_id).player,
      location:p.location,teammate:p.team_id===data.match.home_team.id
    })),active};
  }
  return {points:[...positions.values()],active};
}
function renderPitch(event){
  // Commentary and video status can rerender the page mid-event. Keep the
  // existing pitch timeline running instead of freezing it partway through.
  if(event&&lastPitchEvent===event.id&&$("markers").childElementCount)return;
  cancelAnimationFrame(pitchAnimation);
  const group=$("markers");
  const displayPoint=location=>event.team.id===data.match.away_team.id
    ?[120-location[0],80-location[1]]:location;
  const shouldAnimate=!!event&&lastPitchEvent!==event.id;
  group.replaceChildren();
  $("next").disabled=cursor>=data.events.length || playbackMode==="highlight";
  if(!event){lastPitchEvent=null;pitchBall=null;pitchPositions.clear();$("action-caption").textContent="Follow each pass, carry, and shot as the match unfolds.";return;}
  lastPitchEvent=event.id;
  const svg=(tag,attrs,text)=>{
    const node=document.createElementNS("http://www.w3.org/2000/svg",tag);
    Object.entries(attrs).forEach(([key,value])=>node.setAttribute(key,value));
    if(text)node.textContent=text;group.append(node);return node;
  };
  const {points,active}=pitchState(event);
  const formationLayer=svg("g",{class:"formation-overlay","aria-hidden":"true"});
  const formationShapes=[data.match.home_team,data.match.away_team].map(team=>{
    const color=team.id===data.match.home_team.id?"#c4f277":"#f4ae8e";
    const triangle=svg("polygon",{fill:color,"fill-opacity":".11",stroke:color,
      "stroke-opacity":".8","stroke-width":".55","stroke-linejoin":"round"});
    const back=svg("polyline",{fill:"none",stroke:color,"stroke-opacity":".78",
      "stroke-width":".7","stroke-linecap":"round","stroke-linejoin":"round"});
    const front=svg("polyline",{fill:"none",stroke:color,"stroke-opacity":".78",
      "stroke-width":".7","stroke-linecap":"round","stroke-linejoin":"round"});
    formationLayer.append(triangle,back,front);
    return {teamId:team.id,triangle,back,front};
  });
  function updateFormations(){
    for(const shape of formationShapes){
      const geometry=formationGeometry(data.match.players,pitchPositions,shape.teamId);
      const points=band=>geometry[band].map(([x,y])=>`${x},${y}`).join(" ");
      shape.back.setAttribute("points",points("back"));
      shape.front.setAttribute("points",points("front"));
      shape.triangle.setAttribute("points",points("mid"));
    }
  }
  const combination=combinationAt(data.events,cursor-1);
  for(const id of combination.players)active.add(id);
  if(combination.passes.length>=2){
    svg("text",{x:4,y:7,fill:"#ffe99a","font-size":"2.5","font-weight":"700"},
      `${combination.passes.length} consecutive passes · ${combination.players.size} players involved`);
  }
  const end=event.pass?.end_location || event.carry?.end_location || event.shot?.end_location || event.kick_off?.end_location;
  if(event.type.name==="Shot"&&end){
    const from=displayPoint(event.location),to=displayPoint(end);
    svg("line",{x1:from[0],y1:from[1],x2:to[0],y2:to[1],stroke:"#e6ff8c","stroke-width":"1.6",opacity:".15"});
    svg("line",{"data-role":"event-route",x1:from[0],y1:from[1],x2:to[0],y2:to[1],stroke:"#f0ffc0","stroke-width":".55","stroke-dasharray":"2 .8","marker-end":"url(#route-arrow)"});
    svg("circle",{cx:to[0],cy:to[1],r:"1.5",fill:"none",stroke:"#fff9c2","stroke-width":".25"});
  }
  const movingPlayers=[];
  const keyPlayers=keyPlayerIds(event);
  points.forEach(point=>{
    const start=displayPoint(point.location);
    const from=pitchPositions.get(point.player.id)||start;
    point={...point,location:from};
    const firstChild=group.children.length;
    const isActive=active.has(point.player.id);
    const inCombination=combination.passes.length>=2&&combination.players.has(point.player.id);
    if(isActive)svg("circle",{cx:point.location[0],cy:point.location[1],r:inCombination?2.2:2,
      fill:"none",stroke:inCombination?"#ffe99a":point.teammate?"#c4f277":"#f4ae8e",
      "stroke-width":inCombination?".38":".22",opacity:".9"});
    const circle=svg("circle",{"data-player-id":point.player.id,"data-active":isActive,cx:point.location[0],cy:point.location[1],r:1.5,fill:point.teammate?"#c4f277":"#f4ae8e",stroke:"#142219","stroke-width":".25",opacity:isActive?1:.45});
    const title=document.createElementNS(circle.namespaceURI,"title");title.textContent=point.player.name;circle.append(title);
    const entry=data.match.players.find(p=>p.player.id===point.player.id);
    const position=entry?.position||"";
    const labelY=point.location[1]+(position==="GK"?-3:["LB","CB","RB"].includes(position)?-4:position==="ST"?4.5:3.4);
    if(isActive)svg("text",{x:point.location[0],y:labelY,"text-anchor":"middle",fill:"#ffffff","font-size":"2.4","paint-order":"stroke",stroke:"#163025","stroke-width":".6"},`${position} ${point.player.name.split(" ").at(-1)}`.trim());
    else svg("text",{x:point.location[0],y:point.location[1]+.65,"text-anchor":"middle",fill:"#ffffff",opacity:.75,"font-size":"1.9"},String(entry?.shirt_number||""));
    const children=Array.from(group.children).slice(firstChild);
    const wrapper=svg("g",{"data-moving-player":point.player.id});
    children.forEach(child=>wrapper.append(child));
    const target=event.tracking?.end.find(p=>p.player_id===point.player.id)?.location;
    movingPlayers.push({wrapper,id:point.player.id,from,start,to:target?displayPoint(target):start,
      key:keyPlayers.has(point.player.id)});
  });
  const ball=displayPoint(end||event.location);
  const football=svg("g",{"data-role":"football",transform:`translate(${ball[0]} ${ball[1]})`});
  const disc=document.createElementNS(football.namespaceURI,"circle");
  Object.entries({r:1.6,fill:"#fff",stroke:"#101b17","stroke-width":".3"}).forEach(([k,v])=>disc.setAttribute(k,v));football.append(disc);
  const patch=document.createElementNS(football.namespaceURI,"path");patch.setAttribute("d","M0 -.55 .52 -.17 .32 .45 -.32 .45 -.52 -.17Z");patch.setAttribute("fill","#162019");football.append(patch);
  if(event.tracking){
    const began=performance.now();
    const plan=motionPlan[cursor-1]||{durationMs:900,setupShare:.18};
    const nominalDuration=plan.durationMs;
    const duration=shouldAnimate?Math.max(100,nominalDuration/Number($("speed").value)*.97):0;
    const ballStart=displayPoint(event.tracking.ball_start),ballEnd=displayPoint(event.tracking.ball_end);
    const ballFrom=event.type.name==="Kick Off"?ballStart:(pitchBall||ballStart);
    const setupShare=plan.setupShare;
    const flightShare=event.type.name==="Pass"?.55:event.type.name==="Shot"?.45:.9;
    const arrivalAt=setupShare+(1-setupShare)*flightShare;
    function animate(now){
      const t=duration?Math.min((now-began)/duration,1):1;
      movingPlayers.forEach(({wrapper,id,from,start,to,key})=>{
        const current=!shouldAnimate?from:key
          ?runningPose(from,start,to,t,setupShare)
          :playerMotion(from,to,t,nominalDuration,3.8);
        pitchPositions.set(id,current);
        wrapper.setAttribute("transform",`translate(${current[0]-from[0]} ${current[1]-from[1]})`);
      });
      updateFormations();
      pitchBall=coordinatedMotion(ballFrom,ballStart,ballEnd,t,setupShare,arrivalAt);
      football.setAttribute("transform",`translate(${pitchBall[0]} ${pitchBall[1]})`);
      if(t<1)pitchAnimation=requestAnimationFrame(animate);
    }
    animate(began);
  }
  const action=event.type.name==="Pass"?`${event.player.name} → ${event.pass.recipient.name}: ${event.pass.outcome.name==="Complete"?"pass complete":"pass intercepted"}.`
    :event.type.name==="Carry"?`${event.player.name} carries the ball forward.`
    :event.type.name==="Shot"?`${event.player.name} shoots → ${labels[event.shot.outcome.name].toLowerCase()}.`
    :event.type.name==="Goal Keeper"?`${event.player.name} makes the save.`
    :event.type.name==="Kick Off"?event.kick_off?.opening
      ?`${event.player.name} kicks off from the centre circle.`
      :`${event.player.name} restarts from the centre circle after the goal.`
    :event.type.name==="Full Time"?"The 90-minute match is over."
    :event.type.name==="Interception"?`${event.player.name} intercepts the pass.`
    :event.type.name==="Pressure"?`${event.player.name} presses the ball carrier.`
    :event.type.name==="Tackle"?`${event.player.name} wins the tackle.`
    :`${event.player.name} receives the ball.`;
  $("action-caption").textContent=`${event.minute}′ ${eventLabels[event.type.name]} · ${action}`;
}
function highlightProfile(clip){
  const side=audience();
  const supported=side==="neutral"?null:data.match[side==="home"?"home_team":"away_team"].id;
  const viewpoint=side==="neutral"?pov:shotFor(clip).team.id===supported?"striker":"goalkeeper";
  return {clip_id:clip.id,audience:side,pov:viewpoint,language:$("language").value};
}
function warmHighlight(clip,retry=false){
  const profile=highlightProfile(clip);
  const key=JSON.stringify(profile);
  const cached=prefetched.get(key);
  if(cached && !(retry && cached.status==="failed"))return cached;
  const entry={key,profile,status:"waiting",artifacts:null,job_id:null,error:null,ownsSlot:false};
  entry.submitted=(async()=>{
    await reserveVideoSlot();entry.ownsSlot=true;entry.status="submitting";
    const response=await fetch("/api/highlights/prepare",{
      method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(profile)
    });
    const body=await response.json();
    if(!response.ok)throw Error(body.error||"Video job submission failed");
    entry.artifacts=body.artifacts;entry.job_id=body.job_id;
    entry.status=body.artifacts["video_job.json"].status;
    refreshReadyHighlight();
    return entry;
  })();
  entry.ready=(async()=>{
    try{
      await entry.submitted;
      for(let attempt=0;attempt<120 && ["queued","running"].includes(entry.status);attempt++){
        await new Promise(resolve=>setTimeout(resolve,5000));
        const response=await fetch(`/api/highlights/${encodeURIComponent(entry.job_id)}`);
        const body=await response.json();
        if(!response.ok)throw Error(body.error||"Could not check video status");
        entry.artifacts["video_job.json"]=body.video_job;
        entry.status=body.video_job.status;
      }
      if(["queued","running"].includes(entry.status))throw Error("Video generation timed out");
      if(entry.status==="failed")entry.error=entry.artifacts["video_job.json"].error||"Video generation failed";
    }catch(error){entry.status="failed";entry.error=error.message||"Video generation failed";}
    finally{if(entry.ownsSlot){entry.ownsSlot=false;releaseVideoSlot();}}
    if(entry.status==="failed"){
      const status=$("video-generation-status");
      status.textContent=`POV video unavailable: ${entry.error}. The match and commentary continue.`;
      status.hidden=false;
    }
    refreshReadyHighlight();
    return entry;
  })();
  prefetched.set(key,entry);
  return entry;
}
function refreshReadyHighlight(){
  if(!data)return;
  const ready=[...data.clips].reverse().find(clip=>
    !viewedClips.has(clip.id) && seen().some(event=>event.id===clip.event_ids.at(-1)) &&
    prefetched.get(JSON.stringify(highlightProfile(clip)))?.artifacts?.["video_job.json"]?.media_url);
  const button=$("watch-ready");
  button.hidden=!ready;
  if(ready){
    const shot=shotFor(ready);
    button.textContent=`Watch completed POV: ${shot.minute}′ ${labels[shot.shot.outcome.name]}`;
    if(selected?.id===ready.id && playbackMode==="playing")
      $("video-status").textContent="POV video ready. You can watch it at any time.";
    button.onclick=()=>{
      stop();selected=ready;clearResult();playbackMode="highlight";prepareHighlight(true,true);
    };
  }
}
function warmUpcoming(){
  if(!data)return;
  let upcoming=0;
  for(const clip of data.clips){
    const trigger=data.events.findIndex(event=>event.id===clip.trigger_event_id);
    if(trigger>=cursor && upcoming++<2)warmHighlight(clip);
  }
}
$("next").onclick=()=>{stop();playbackMode="paused";tick();updatePlayback();};
$("play").onclick=()=>{if(playbackMode==="playing"){stop();playbackMode="paused";updatePlayback();}else start();};
$("reset").onclick=()=>{stop();playbackMode="paused";cursor=0;selected=null;viewedClips.clear();lastPitchEvent=null;pitchBall=null;pitchPositions.clear();clearResult();render();start();warmUpcoming();};
$("speed").onchange=()=>{if(playbackMode==="playing"){stop();scheduleNext();}};
$("mode").onchange=()=>render();
$("live-mode").onchange=()=>{$("mode").value=$("live-mode").value;insightKey=null;render();};
$("live-language").onchange=()=>{$("language").value=$("live-language").value;insightKey=null;render();};
$("audience").onchange=()=>{
  const resume=highlightResume;clearResult();applyAudience();render();
  warmUpcoming();refreshReadyHighlight();if(resume)prepareHighlight(true,true);
};
$("language").onchange=()=>{
  const resume=highlightResume;clearResult();render();
  warmUpcoming();refreshReadyHighlight();if(resume)prepareHighlight(true,true);
};
["striker","goalkeeper"].forEach(id=>$(id).onclick=()=>{
  pov=id;$(id).className="selected";$(id==="striker"?"goalkeeper":"striker").className="secondary";
  const resume=highlightResume;clearResult();render();warmUpcoming();refreshReadyHighlight();if(resume)prepareHighlight(true,true);
});
function resumeMatch(version){
  if(version!==epoch || !highlightResume)return;
  clearResult();
  playbackMode="paused";start();
}
function resumeAfterDelay(version){
  if(!highlightResume || version!==epoch)return;
  fallbackTimer=setTimeout(()=>resumeMatch(version),2000);
}
async function showVideo(job,version,automatic){
  const video=$("highlight-video");video.src=job.media_url;video.hidden=false;$("pov-stage").hidden=false;
  $("video-status").textContent="POV video ready.";
  if(highlightResume){
    const watched=selected?.id;
    video.onended=()=>{if(watched)viewedClips.add(watched);refreshReadyHighlight();resumeMatch(version);};
    video.onerror=()=>{$("video-status").textContent="Video playback failed. Resuming the match.";resumeAfterDelay(version);};
    video.onplay=()=>{clearTimeout(fallbackTimer);fallbackTimer=null;};
  }
  if(automatic){
    try{await video.play();}
    catch{if(version===epoch){
      $("video-status").textContent="Video ready. Press play, or the match will resume in 15 seconds.";
      if(highlightResume)fallbackTimer=setTimeout(()=>resumeMatch(version),15000);
    }}
  }
}
$("skip-highlight").onclick=()=>resumeMatch(epoch);
async function prepareHighlight(automatic=false,resume=false,retry=false){
  if(!selected||busy)return;stop();if(!resume)playbackMode="paused";busy=true;highlightResume=resume;
  $("skip-highlight").hidden=!resume;const version=++epoch;
  applyAudience();
  $("error").hidden=true;$("video-status").textContent="Checking the video job…";render();
  try{
    const entry=warmHighlight(selected,retry);
    await entry.submitted;
    if(version!==epoch)return;
    prepared=entry.artifacts;
    $("commentary").textContent=prepared["commentary.json"].text;
    $("scene").textContent=JSON.stringify(prepared["scene.json"],null,2);$("result").hidden=false;
    if(["queued","running","submitting"].includes(entry.status))
      $("video-status").textContent="Generating POV video in the background…";
    await entry.ready;
    if(version!==epoch)return;
    const job=entry.artifacts["video_job.json"];
    if(entry.status==="succeeded" && job.media_url)await showVideo(job,version,automatic);
    else if(entry.status==="not_submitted"){
      $("video-status").textContent="OPENROUTER_API_KEY is not configured. Resuming the match.";resumeAfterDelay(version);
    }else{
      $("video-status").textContent=`Video generation failed: ${entry.error||"Unknown error"}. Resuming the match.`;
      resumeAfterDelay(version);
    }
  }catch(error){if(version===epoch && error.name!=="AbortError"){$("error").textContent=error.message;$("error").hidden=false;$("video-status").textContent="Preparation failed. Resuming the match.";resumeAfterDelay(version);}}
  finally{if(version===epoch){busy=false;render();}}
}
$("prepare").onclick=()=>prepareHighlight(false,false,true);
$("download").onclick=()=>{if(!prepared)return;const url=URL.createObjectURL(new Blob([JSON.stringify(prepared["video_request.json"],null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download="video-request.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
async function loadMatch(){
  stop();clearResult();insightController?.abort();insightKey=null;insightCache.clear();
  $("error").hidden=true;
  $("video-generation-status").hidden=true;
  try{
    const response=await fetch("/api/match");
    const body=await response.json();if(!response.ok)throw Error(body.error||"Could not load match data");
    data=body;motionPlan=buildMotionPlan(body.events);schedule=motionPlan.map(item=>item.durationMs);cursor=0;selected=null;viewedClips.clear();lastPitchEvent=null;pitchBall=null;pitchPositions.clear();commentaryAudience=null;commentaryCursor=0;aiCommentaryCache.clear();
    $("speed").options[0].textContent=`Natural pace · about ${replayMinutes(body.events)} min`;
    playbackMode="paused";renderLineups();render();start();warmUpcoming();
    $("video-status").textContent=body.video_available
      ?"The match is underway. POV videos are generating in the background."
      :"The match is underway. Video generation is not configured.";
  }catch(error){$("error").textContent=error.message;$("error").hidden=false;}
}
loadMatch();
