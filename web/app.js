const $ = id => document.getElementById(id);
const labels = {Goal:"进球", "Off T":"射偏", Saved:"扑救"};
const eventLabels = {Pass:"传球", "Ball Receipt*":"接球", Carry:"推进", Shot:"射门", "Goal Keeper":"扑救"};
let data, cursor=0, timer=null, selected=null, pov="striker", prepared=null, busy=false, epoch=0;
let pitchAnimation=null, lastPitchEvent=null;
let requestController=null;
let insightController=null, insightKey=null;
const insightCache=new Map();
async function updateLiveInsight(event){
  const key=event?`${event.id}:${audience()}:${$("mode").value}`:null;
  if(key===insightKey)return;
  insightController?.abort();insightKey=key;
  $("insight-evidence").hidden=true;
  if(!event){
    $("insight-title").textContent="这一步，为什么值得关注？";
    $("insight-text").textContent="播放比赛片段，洞察会随当前动作更新。";
    return;
  }
  $("insight-title").textContent=`${event.minute}′ · 正在解读当前动作`;
  $("insight-text").textContent="结合当前事件与球场位置，整理分析依据…";
  const controller=new AbortController();insightController=controller;
  let baselineShown=false;
  const params={event_id:event.id,audience:audience(),mode:$("mode").value};
  async function fetchInsight(use_ai){
    const response=await fetch("/api/insights",{method:"POST",signal:controller.signal,
      headers:{"Content-Type":"application/json"},body:JSON.stringify({...params,use_ai})});
    const result=await response.json();if(!response.ok)throw Error("无法读取洞察");return result;
  }
  try{
    let insight=insightCache.get(key);
    if(!insight){
      insight=await fetchInsight(false);
      if(key!==insightKey)return;
      displayLiveInsight(insight);baselineShown=true;
      if(insight.ai_available)insight=await fetchInsight(true);
      if(insight.generator==="ai" || !insight.ai_available)insightCache.set(key,insight);
    }
    if(key!==insightKey)return;
    displayLiveInsight(insight);
  }catch(error){
    if(key===insightKey && error.name!=="AbortError"){
      if(baselineShown){$("insight-source").textContent="规则解读 · AI 暂不可用";}
      else{
        $("insight-title").textContent="洞察暂时不可用";
        $("insight-text").textContent="可以继续观看，稍后切换观赛模式重试。";
      }
      insightKey=null;
    }
  }
}
function displayLiveInsight(insight){
    $("insight-title").textContent=insight.title;
    $("insight-text").textContent=insight.text;
    $("insight-source").textContent=insight.generator_label;
    $("insight-measurement").textContent=insight.measurement_note;
    const factNames={pass_distance_m:"传球距离（米）",forward_progress_m:"向前推进（米）",
      carry_distance_m:"带球距离（米）",goal_distance_reduction_m:"距球门缩短（米）",
      goal_distance_m:"距球门中心（米）",nearest_defender_m:"最近防守球员（米）",
      goal_opening_angle_degrees:"两门柱夹角（度）"};
    $("insight-facts").replaceChildren(...Object.entries(factNames).filter(([key])=>insight.facts[key]!=null).map(([key,label])=>{
      const li=document.createElement("li");li.textContent=`${label}：${insight.facts[key]}`;return li;
    }));
    $("insight-events").replaceChildren(...insight.evidence.map(item=>{
      const li=document.createElement("li");li.textContent=item.label;return li;
    }));
    $("insight-evidence").hidden=false;
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
    ?"中立观众：手动选择射手或门将视角，使用客观解说。"
    :"优先体验支持球队的球员视角；片段结束自动准备，视频就绪后尝试播放。";
}
const seen = () => data.events.slice(0,cursor);
const unlocked = clip => seen().some(e=>e.id===clip.trigger_event_id);
const shotFor = clip => data.events.find(e=>e.id===clip.trigger_event_id);
function clearResult(){epoch++;requestController?.abort();busy=false;prepared=null;$("result").hidden=true;const video=$("highlight-video");video.pause();video.removeAttribute("src");video.load();video.hidden=true;$("video-status").textContent="场景已选择，准备生成请求后可预览。";}
function updatePlayback(){
  const finished=data && cursor>=data.events.length;
  const boundary=data && cursor>0 && data.clips.some(c=>c.event_ids.at(-1)===data.events[cursor-1].id);
  $("play").disabled=!!finished;
  $("play").textContent=timer?"暂停":finished?"全部片段已播完":boundary?"播放下一个片段":cursor?"继续当前片段":"播放片段";
}
function stop(){clearInterval(timer);timer=null;updatePlayback();}
function tick(){
  if(cursor>=data.events.length){stop();return;}
  const event=data.events[cursor++];
  if(data.clips.some(c=>c.event_ids[0]===event.id)){selected=null;clearResult();}
  const clip=data.clips.find(c=>c.trigger_event_id===event.id);
  if(clip){selected=clip;clearResult();applyAudience();}
  render();
  if(cursor===data.events.length || data.clips.some(c=>c.event_ids.at(-1)===event.id)){
    stop();
    if(audience()!=="neutral")prepareHighlight(true);
  }
}
function start(){stop();if(!data || cursor>=data.events.length)return;timer=setInterval(tick,Number($("speed").value));updatePlayback();}
function render(){
  updatePlayback();
  applyAudience();
  const events=seen(), shots=events.filter(e=>e.type.name==="Shot"), goals=shots.filter(e=>e.shot.outcome.name==="Goal");
  const last=events.at(-1);
  $("score").textContent=`${goals.length} : 0`;
  $("clock").textContent=last?`${last.minute}′ ${String(last.second).padStart(2,"0")}″ · 片段回放`:"准备开场";
  $("progress").textContent=`${cursor} / ${data.events.length}`;
  const onTarget=shots.filter(e=>["Goal","Saved"].includes(e.shot.outcome.name)).length;
  $("stats").replaceChildren(...[[shots.length,"样例射门"],[onTarget,"样例射正"],[events.filter(e=>e.type.name==="Pass").length,"样例传球"]].map(([value,label])=>{
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
    const sub=document.createElement("small");sub.textContent=unlocked(clip)?`${shot.player.name} → 进入视角`:"等待比赛推进";
    button.append(title,sub);button.onclick=()=>{stop();selected=clip;clearResult();render();if(audience()!=="neutral")prepareHighlight(true);};return button;
  }));
  $("recap").textContent=available.length?available.map(c=>{const e=shotFor(c);return `${e.minute} 分钟，${e.player.name}${({Goal:"射门得分","Off T":"射门偏出",Saved:"射门被扑出"})[e.shot.outcome.name]}。`;}).join(" ")+(cursor===data.events.length?" 三个样例片段已播放完毕。":""):"关键事件发生后，这里会自动整理回顾。";
  $("event-log").replaceChildren(...events.slice(-6).reverse().map(e=>{const p=document.createElement("div");p.textContent=`${e.minute}:${String(e.second).padStart(2,"0")} · ${e.player.name} · ${eventLabels[e.type.name]}`;return p;}));
  $("prepare").disabled=busy || !selected || !unlocked(selected);
  $("moment-title").textContent=selected?`${shotFor(selected).minute}′ ${labels[shotFor(selected).shot.outcome.name]} · ${pov==="striker"?"射手":"门将"}视角`:"等待关键事件";
  updateLiveInsight(last);
  renderPitch(last);
}
function pitchState(event){
  const clip=data.clips.find(c=>c.event_ids.includes(event.id));
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
  cancelAnimationFrame(pitchAnimation);
  const group=$("markers");group.replaceChildren();
  $("next").disabled=cursor>=data.events.length;
  if(!event){lastPitchEvent=null;$("action-caption").textContent="点击播放或“下一步”，按传球 → 接球 → 推进 → 射门查看。";return;}
  const shouldAnimate=lastPitchEvent!==event.id;
  lastPitchEvent=event.id;
  const svg=(tag,attrs,text)=>{
    const node=document.createElementNS("http://www.w3.org/2000/svg",tag);
    Object.entries(attrs).forEach(([key,value])=>node.setAttribute(key,value));
    if(text)node.textContent=text;group.append(node);return node;
  };
  const {points,active}=pitchState(event);
  const end=event.pass?.end_location || event.carry?.end_location || event.shot?.end_location;
  if(end){
    svg("line",{x1:event.location[0],y1:event.location[1],x2:end[0],y2:end[1],stroke:"#e6ff8c","stroke-width":"1.6",opacity:".15"});
    svg("line",{"data-role":"event-route",x1:event.location[0],y1:event.location[1],x2:end[0],y2:end[1],stroke:"#f0ffc0","stroke-width":".55","stroke-dasharray":event.type.name==="Carry"?".6 .7":"2 .8","marker-end":"url(#route-arrow)"});
    svg("circle",{cx:end[0],cy:end[1],r:"1.5",fill:"none",stroke:"#fff9c2","stroke-width":".25"});
  }
  const movingPlayers=[];
  points.forEach(point=>{
    const firstChild=group.children.length;
    const isActive=active.has(point.player.id);
    if(isActive)svg("circle",{cx:point.location[0],cy:point.location[1],r:2,fill:"none",stroke:point.teammate?"#c4f277":"#f4ae8e","stroke-width":".22",opacity:".85"});
    const circle=svg("circle",{"data-player-id":point.player.id,"data-active":isActive,cx:point.location[0],cy:point.location[1],r:1.5,fill:point.teammate?"#c4f277":"#f4ae8e",stroke:"#142219","stroke-width":".25",opacity:isActive?1:.45});
    const title=document.createElementNS(circle.namespaceURI,"title");title.textContent=point.player.name;circle.append(title);
    const role=data.match.players.find(p=>p.player.id===point.player.id)?.role;
    const entry=data.match.players.find(p=>p.player.id===point.player.id);
    const roleName={striker:"射手",goalkeeper:"门将",defender:"后卫",midfielder:"传球者"}[role] || entry?.position || "球员";
    const labelY=point.location[1]+(role==="defender"?-4:role==="striker"?4.5:role==="goalkeeper"?-3:3.4);
    if(isActive)svg("text",{x:point.location[0],y:labelY,"text-anchor":"middle",fill:"#ffffff","font-size":"2.4","paint-order":"stroke",stroke:"#163025","stroke-width":".6"},`${roleName} ${point.player.name.split(" ")[0]}`);
    else svg("text",{x:point.location[0],y:point.location[1]+.65,"text-anchor":"middle",fill:"#ffffff",opacity:.75,"font-size":"1.9"},String(entry?.shirt_number||""));
    const children=Array.from(group.children).slice(firstChild);
    const wrapper=svg("g",{"data-moving-player":point.player.id});
    children.forEach(child=>wrapper.append(child));
    const target=event.tracking?.end.find(p=>p.player_id===point.player.id)?.location || point.location;
    movingPlayers.push({wrapper,from:point.location,to:target});
  });
  const ball=end||event.location;
  const football=svg("g",{"data-role":"football",transform:`translate(${ball[0]} ${ball[1]})`});
  const disc=document.createElementNS(football.namespaceURI,"circle");
  Object.entries({r:1.6,fill:"#fff",stroke:"#101b17","stroke-width":".3"}).forEach(([k,v])=>disc.setAttribute(k,v));football.append(disc);
  const patch=document.createElementNS(football.namespaceURI,"path");patch.setAttribute("d","M0 -.55 .52 -.17 .32 .45 -.32 .45 -.52 -.17Z");patch.setAttribute("fill","#162019");football.append(patch);
  if(event.tracking){
    const began=performance.now(),duration=shouldAnimate?Number($("speed").value)*.85:0;
    function animate(now){
      const t=duration?Math.min((now-began)/duration,1):1;
      movingPlayers.forEach(({wrapper,from,to})=>wrapper.setAttribute("transform",`translate(${(to[0]-from[0])*t} ${(to[1]-from[1])*t})`));
      const a=event.tracking.ball_start,b=event.tracking.ball_end;
      football.setAttribute("transform",`translate(${a[0]+(b[0]-a[0])*t} ${a[1]+(b[1]-a[1])*t})`);
      if(t<1)pitchAnimation=requestAnimationFrame(animate);
    }
    animate(began);
  }
  const action=event.type.name==="Pass"?`${event.player.name} → ${event.pass.recipient.name}：传球。虚线连接传球起点与落点。`
    :event.type.name==="Carry"?`${event.player.name} 带球推进，足球标记在本次推进终点。`
    :event.type.name==="Shot"?`${event.player.name} 起脚射门 → ${labels[event.shot.outcome.name]}。射手与门将高亮，足球沿射门路线移动。`
    :event.type.name==="Goal Keeper"?`${event.player.name} 完成扑救。门将和足球位于扑救位置，其余球员保留模拟站位。`
    :`${event.player.name} 接到传球，准备向球门推进。`;
  $("action-caption").textContent=`${event.minute}′ ${eventLabels[event.type.name]} · ${action}`;
}
$("next").onclick=()=>{stop();tick();};
$("play").onclick=()=>timer?stop():start();
$("reset").onclick=()=>{stop();cursor=0;selected=null;clearResult();$("video-status").textContent="选择已发生的关键事件，准备你的专属片段。";render();};
$("speed").onchange=()=>{if(timer)start();};
$("mode").onchange=()=>render();
$("audience").onchange=()=>{clearResult();applyAudience();render();if(selected&&audience()!=="neutral")prepareHighlight(true);};
$("language").onchange=()=>{clearResult();if(selected&&audience()!=="neutral")prepareHighlight(true);};
["striker","goalkeeper"].forEach(id=>$(id).onclick=()=>{pov=id;$(id).className="selected";$(id==="striker"?"goalkeeper":"striker").className="secondary";clearResult();render();});
async function prepareHighlight(automatic=false){
  if(!selected||busy)return;stop();busy=true;const version=++epoch;
  applyAudience();
  requestController=new AbortController();
  $("error").hidden=true;$("video-status").textContent="正在准备场景和生成请求…";render();
  try{
    const response=await fetch("/api/highlights/prepare",{method:"POST",signal:requestController.signal,headers:{"Content-Type":"application/json"},body:JSON.stringify({clip_id:selected.id,pov,language:$("language").value,audience:audience()})});
    const body=await response.json();if(!response.ok)throw Error(body.error);
    if(version!==epoch)return;
    prepared=body.artifacts;
    $("video-status").textContent="场景已准备 · 等待视频服务接入（尚未生成视频）";
    $("commentary").textContent=prepared["commentary.json"].text;
    $("scene").textContent=JSON.stringify(prepared["scene.json"],null,2);$("result").hidden=false;
    const job=prepared["video_job.json"];
    if(job.status==="queued" || job.status==="running"){
      $("video-status").textContent="AI 视频生成中，请稍候……";
      pollVideo(body.job_id,version,automatic);
    }else if(job.status==="not_submitted"){
      $("video-status").textContent="未配置 OPENROUTER_API_KEY；已准备好视频提示词。";
    }
    if(job.status==="succeeded" && job.media_url){
      const video=$("highlight-video");video.src=job.media_url;video.hidden=false;
      $("video-status").textContent="第一视角视频已就绪。";
      if(automatic){
        try{await video.play();}catch{if(version===epoch)$("video-status").textContent="视频已就绪，点击播放开始观看。";}
      }
    }
  }catch(error){if(version===epoch && error.name!=="AbortError"){$("error").textContent=error.message;$("error").hidden=false;$("video-status").textContent="准备失败，请重试。";}}
  finally{if(version===epoch){busy=false;render();}}
}
async function pollVideo(jobId,version,automatic){
  for(let attempt=0;attempt<120 && version===epoch;attempt++){
    await new Promise(resolve=>setTimeout(resolve,5000));
    if(version!==epoch)return;
    try{
      const response=await fetch(`/api/highlights/${encodeURIComponent(jobId)}`,{signal:requestController?.signal});
      const body=await response.json();if(!response.ok)throw Error(body.error||"视频状态查询失败");
      if(version!==epoch)return;
      const job=body.video_job;
      prepared["video_job.json"]=job;
      if(job.status==="failed"){$("video-status").textContent=`视频生成失败：${job.error||"未知错误"}`;return;}
      if(job.status==="succeeded" && job.media_url){
        const video=$("highlight-video");video.src=job.media_url;video.hidden=false;
        $("video-status").textContent="第一视角视频已就绪。";
        if(automatic){try{await video.play();}catch{if(version===epoch)$("video-status").textContent="视频已就绪，点击播放开始观看。";}}
        return;
      }
      $("video-status").textContent=job.status==="queued"?"视频任务排队中……":"AI 正在生成第一视角视频……";
    }catch(error){if(version===epoch && error.name!=="AbortError")$("video-status").textContent=`视频状态查询失败：${error.message}`;return;}
  }
  if(version===epoch)$("video-status").textContent="生成时间较长，请重新选择片段查看任务进度。";
}
$("prepare").onclick=()=>prepareHighlight(false);
$("download").onclick=()=>{if(!prepared)return;const url=URL.createObjectURL(new Blob([JSON.stringify(prepared["video_request.json"],null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download="video-request.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
fetch("/api/match").then(r=>{if(!r.ok)throw Error("无法读取比赛数据");return r.json();}).then(body=>{
  data=body;render();
}).catch(error=>{$("error").textContent=error.message;$("error").hidden=false;["play","reset","prepare"].forEach(id=>$(id).disabled=true);});
