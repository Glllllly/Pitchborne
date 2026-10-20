const $ = id => document.getElementById(id);
const labels = {Goal:"进球", "Off T":"射偏", Saved:"扑救"};
const eventLabels = {Pass:"传球", "Ball Receipt*":"接球", Carry:"推进", Shot:"射门", "Goal Keeper":"扑救"};
let data, cursor=0, timer=null, selected=null, pov="striker", prepared=null, busy=false, epoch=0;
const seen = () => data.events.slice(0,cursor);
const unlocked = clip => seen().some(e=>e.id===clip.trigger_event_id);
const shotFor = clip => data.events.find(e=>e.id===clip.trigger_event_id);
function clearResult(){epoch++;prepared=null;$("result").hidden=true;$("video-status").textContent="场景已选择，准备生成请求后可预览。";}
function stop(){clearInterval(timer);timer=null;$("play").textContent="播放片段";}
function tick(){
  if(cursor>=data.events.length){stop();return;}
  const event=data.events[cursor++];
  const clip=data.clips.find(c=>c.trigger_event_id===event.id);
  if(clip){selected=clip;clearResult();}
  render();
  if(cursor===data.events.length)stop();
}
function start(){stop();if(cursor>=data.events.length){cursor=0;selected=null;clearResult();render();}timer=setInterval(tick,Number($("speed").value));$("play").textContent="暂停";}
function render(){
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
  const focus=$("favorite").value;
  $("moments").replaceChildren(...data.clips.map(clip=>{
    const shot=shotFor(clip), button=document.createElement("button");
    button.className="moment"+(selected?.id===clip.id?" active":"");
    const relevant=!focus || clip.event_ids.some(id=>data.events.find(e=>e.id===id).player.id===Number(focus)) || shot.shot.freeze_frame.some(p=>p.player.id===Number(focus));
    button.hidden=!relevant;button.disabled=!unlocked(clip);
    const title=document.createElement("span");title.textContent=`${shot.minute}′ · ${labels[shot.shot.outcome.name]}`;
    const sub=document.createElement("small");sub.textContent=unlocked(clip)?`${shot.player.name} → 进入视角`:"等待比赛推进";
    button.append(title,sub);button.onclick=()=>{selected=clip;clearResult();render();};return button;
  }));
  $("recap").textContent=available.length?available.map(c=>{const e=shotFor(c);return `${e.minute} 分钟，${e.player.name}${({Goal:"射门得分","Off T":"射门偏出",Saved:"射门被扑出"})[e.shot.outcome.name]}。`;}).join(" ")+(cursor===data.events.length?" 三个样例片段已播放完毕。":""):"关键事件发生后，这里会自动整理回顾。";
  $("event-log").replaceChildren(...events.slice(-6).reverse().map(e=>{const p=document.createElement("div");p.textContent=`${e.minute}:${String(e.second).padStart(2,"0")} · ${e.player.name} · ${eventLabels[e.type.name]}`;return p;}));
  $("prepare").disabled=busy || !selected || !unlocked(selected);
  $("moment-title").textContent=selected?`${shotFor(selected).minute}′ ${labels[shotFor(selected).shot.outcome.name]} · ${pov==="striker"?"射手":"门将"}视角`:"等待关键事件";
  if(selected && unlocked(selected)){
    const shot=shotFor(selected), ff=shot.shot.freeze_frame, def=ff.find(p=>p.position.name!=="Goalkeeper"&&!p.teammate);
    const distance=def?Math.hypot(def.location[0]-shot.location[0],def.location[1]-shot.location[1]):null;
    $("insight").textContent=$("mode").value==="analyst"
      ?`射门位置 (${shot.location.join(", ")}) · 最近样例防守者距离 ${distance?.toFixed(1)} 归一化单位。依据：${shot.id}。局部快照不能证明整条防线已被突破。`
      :`接球推进后，射手在附近有防守者的情况下起脚。${shot.shot.outcome.name==="Goal"?"这次射门让主队取得领先。":shot.shot.outcome.name==="Saved"?"门将挡住射门，比分没有改变。":"球偏出球门，这次进攻未能转化为进球。"}`;
  }else $("insight").textContent="播放比赛片段，查看这一刻发生了什么。";
  renderPitch(last);
}
function renderPitch(event){
  const group=$("markers");group.replaceChildren();
  if(!event)return;
  const selectedShot=selected && unlocked(selected)?shotFor(selected):null;
  const snapshot=event.type.name==="Shot"?event:selectedShot && selectedShot.possession===event.possession?selectedShot:null;
  const points=snapshot?[{location:snapshot.location,player:snapshot.player,teammate:true},...snapshot.shot.freeze_frame]:[{location:event.location,player:event.player,teammate:event.team.id===data.match.home_team.id}];
  points.forEach(point=>{
    const circle=document.createElementNS("http://www.w3.org/2000/svg","circle");
    circle.setAttribute("cx",point.location[0]);circle.setAttribute("cy",point.location[1]);circle.setAttribute("r","1.6");circle.setAttribute("fill",point.teammate?"#c4f277":"#f4ae8e");
    const title=document.createElementNS(circle.namespaceURI,"title");title.textContent=point.player.name;circle.append(title);group.append(circle);
  });
}
$("play").onclick=()=>timer?stop():start();
$("reset").onclick=()=>{stop();cursor=0;selected=null;clearResult();$("video-status").textContent="选择已发生的关键事件，准备你的专属片段。";render();};
$("speed").onchange=()=>{if(timer)start();};
["mode","favorite"].forEach(id=>$(id).onchange=()=>render());
$("language").onchange=clearResult;
["striker","goalkeeper"].forEach(id=>$(id).onclick=()=>{pov=id;$(id).className="selected";$(id==="striker"?"goalkeeper":"striker").className="secondary";clearResult();render();});
$("prepare").onclick=async()=>{
  if(!selected||busy)return;stop();busy=true;const version=++epoch;
  $("error").hidden=true;$("video-status").textContent="正在准备场景和生成请求…";render();
  try{
    const response=await fetch("/api/highlights/prepare",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({clip_id:selected.id,pov,language:$("language").value})});
    const body=await response.json();if(!response.ok)throw Error(body.error);
    if(version!==epoch)return;
    prepared=body.artifacts;
    $("video-status").textContent="场景已准备 · 等待视频服务接入（尚未生成视频）";
    $("commentary").textContent=prepared["commentary.json"].text;
    $("scene").textContent=JSON.stringify(prepared["scene.json"],null,2);$("result").hidden=false;
  }catch(error){if(version===epoch){$("error").textContent=error.message;$("error").hidden=false;$("video-status").textContent="准备失败，请重试。";}}
  finally{busy=false;render();}
};
$("download").onclick=()=>{if(!prepared)return;const url=URL.createObjectURL(new Blob([JSON.stringify(prepared["video_request.json"],null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download="video-request.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
fetch("/api/match").then(r=>{if(!r.ok)throw Error("无法读取比赛数据");return r.json();}).then(body=>{
  data=body;data.match.players.forEach(p=>{const option=document.createElement("option");option.value=p.player.id;option.textContent=p.player.name;$("favorite").append(option);});render();
}).catch(error=>{$("error").textContent=error.message;$("error").hidden=false;["play","reset","prepare"].forEach(id=>$(id).disabled=true);});
