import {pitchDistanceMetres,playerMotion} from "./pitch_motion.mjs";

const ACTION_MS={Pass:850,"Ball Receipt*":470,Carry:850,Interception:650,Tackle:680,Pressure:620,Shot:1050,"Goal Keeper":500};
const SPRINT_MPS=10;
const ACTIVE_MPS=5.4;
const FOLLOW_MPS=3.8;

export function keyPlayerIds(event){
  const ids=new Set([event.player?.id]);
  if(event.pass?.recipient?.id)ids.add(event.pass.recipient.id);
  if(event.shot)event.shot.freeze_frame?.filter(point=>point.position?.name==="Goalkeeper")
    .forEach(point=>ids.add(point.player.id));
  return ids;
}

export function buildMotionPlan(events){
  if(!Array.isArray(events)||events.length<2)return [];
  const referenceTeam=events[0].team?.id;
  const positions=new Map();
  const plan=[];
  for(let index=0;index<events.length-1;index++){
    const event=events[index],next=events[index+1];
    const gap=(next.minute*60+next.second)-(event.minute*60+event.second);
    if(gap<0)throw new Error("Match events must be chronological");
    const orient=location=>event.team?.id===referenceTeam?location:[120-location[0],80-location[1]];
    const starts=new Map((event.tracking?.start||[]).map(point=>[point.player_id,orient(point.location)]));
    const ends=new Map((event.tracking?.end||[]).map(point=>[point.player_id,orient(point.location)]));
    const keyIds=keyPlayerIds(event);
    let approach=0,action=0;
    for(const id of keyIds){
      const start=starts.get(id);
      if(!start)continue;
      approach=Math.max(approach,pitchDistanceMetres(positions.get(id)||start,start));
      action=Math.max(action,pitchDistanceMetres(start,ends.get(id)||start));
    }
    // The running curve peaks at 1 / (1 - .12) times its average speed.
    const setupMs=Math.max(120,Math.ceil(approach/SPRINT_MPS/0.88*1000));
    const actionMs=Math.max(ACTION_MS[event.type.name]||600,Math.ceil(action/ACTIVE_MPS*1500));
    const durationMs=setupMs+actionMs;
    plan.push({durationMs,setupShare:setupMs/durationMs});
    for(const [id,end] of ends){
      const start=starts.get(id)||end,from=positions.get(id)||start;
      positions.set(id,keyIds.has(id)?end:playerMotion(from,end,1,durationMs,FOLLOW_MPS));
    }
  }
  return plan;
}

export function buildSchedule(events){
  return buildMotionPlan(events).map(item=>item.durationMs);
}

export function replayMinutes(events){
  return Math.round(buildSchedule(events).reduce((total,value)=>total+value,0)/60000);
}
