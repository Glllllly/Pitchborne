import assert from "node:assert/strict";
import {test} from "node:test";
import {buildSchedule,buildMotionPlan,replayMinutes} from "../web/match_clock.mjs";

test("event pacing gives passes and shots readable action time", () => {
  const events = [
    {minute:0, second:0, type:{name:"Pass"}},
    {minute:1, second:0, type:{name:"Shot"}},
    {minute:2, second:0, type:{name:"Pass"}},
    {minute:90, second:0, type:{name:"Full Time"}},
  ];
  const delays = buildSchedule(events);
  assert.equal(delays.length, 3);
  assert.ok(delays[0]>=970);
  assert.ok(delays[1]>delays[0]);
  assert.ok(delays[2]>=970);
  assert.equal(replayMinutes(events),Math.round(delays.reduce((a,b)=>a+b,0)/60000));
});

test("a distant receiver gets running time before the next ball action",()=>{
  const tracking=(receiverX)=>({
    start:[{player_id:1,location:[10,40]},{player_id:2,location:[receiverX,40]}],
    end:[{player_id:1,location:[10,40]},{player_id:2,location:[receiverX,40]}]
  });
  const first={minute:0,second:0,team:{id:1},type:{name:"Pass"},player:{id:1},tracking:tracking(15)};
  const next={minute:0,second:2,team:{id:1},type:{name:"Pass"},player:{id:1},
    pass:{recipient:{id:2}},tracking:tracking(85)};
  const end={minute:0,second:4,team:{id:1},type:{name:"Full Time"},player:{id:1}};
  const plan=buildMotionPlan([first,next,end]);
  assert.ok(plan[1].durationMs>7000);
  assert.ok(plan[1].setupShare>.8);
});
