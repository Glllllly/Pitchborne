import test from "node:test";
import assert from "node:assert/strict";
import {combinationAt} from "../web/match_clock.mjs";

const event=(id,team,type,player,recipient,outcome="Complete")=>({
  id,team:{id:team},type:{name:type},player:{id:player},
  ...(type==="Pass"?{pass:{recipient:{id:recipient},outcome:{name:outcome}}}:{})
});

test("continuous team passes retain every participant and stop at possession boundaries",()=>{
  const events=[
    event(1,1,"Pass",10,11),event(2,1,"Ball Receipt*",11),
    event(3,1,"Carry",11),event(4,1,"Pass",11,12),
    event(5,1,"Shot",12),event(6,1,"Pass",13,14),
    event(7,2,"Interception",20),event(8,1,"Pass",15,16,"Incomplete"),
    event(9,1,"Pass",17,18)
  ];
  assert.deepEqual([...combinationAt(events,3).players].sort((a,b)=>a-b),[10,11,12]);
  assert.deepEqual(combinationAt(events,3).passes.map(pass=>pass.id),[1,4]);
  assert.deepEqual(combinationAt(events,4).passes.map(pass=>pass.id),[1,4]);
  assert.deepEqual(combinationAt(events,5).passes.map(pass=>pass.id),[6]);
  assert.deepEqual(combinationAt(events,8).passes.map(pass=>pass.id),[9]);
});
