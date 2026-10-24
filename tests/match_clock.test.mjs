import assert from "node:assert/strict";
import {test} from "node:test";
import {buildSchedule, MATCH_REPLAY_MS} from "../web/match_clock.mjs";

test("full match schedule totals nine minutes and holds shots", () => {
  const events = [
    {minute:0, second:0, type:{name:"Pass"}},
    {minute:1, second:0, type:{name:"Shot"}},
    {minute:2, second:0, type:{name:"Pass"}},
    {minute:90, second:0, type:{name:"Full Time"}},
  ];
  const delays = buildSchedule(events);
  assert.equal(delays.length, 3);
  assert.ok(Math.abs(delays.reduce((a,b)=>a+b,0)-MATCH_REPLAY_MS)<.001);
  assert.ok(delays[1]>delays[0]);
});
