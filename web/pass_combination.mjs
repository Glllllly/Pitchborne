const endsPossession=event=>event.type.name==="Shot" ||
  event.type.name==="Interception" || event.type.name==="Tackle" ||
  event.type.name==="Full Time" ||
  (event.type.name==="Pass" && event.pass?.outcome?.name!=="Complete");

export function combinationAt(events,index){
  const current=events[index];
  if(!current)return {players:new Set(),passes:[]};
  const players=new Set(),passes=[];
  for(let cursor=index;cursor>=0;cursor--){
    const event=events[cursor];
    if(event.team.id!==current.team.id || (cursor<index&&endsPossession(event)))break;
    if(event.type.name==="Pass"){
      players.add(event.player.id);
      if(event.pass?.recipient?.id)players.add(event.pass.recipient.id);
      if(event.pass?.outcome?.name==="Complete")passes.unshift(event);
    }else if(cursor===index && ["Ball Receipt*","Carry","Shot"].includes(event.type.name)){
      players.add(event.player.id);
    }
  }
  return {players,passes};
}
