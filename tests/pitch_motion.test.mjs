import test from "node:test";
import assert from "node:assert/strict";
import {interpolatePose} from "../web/pitch_motion.mjs";

test("players enter the next event continuously before its action", () => {
  const previous=[12, 20], start=[30, 40], end=[35, 44];
  assert.deepEqual(interpolatePose(previous,start,end,0,0.28),previous);
  assert.deepEqual(interpolatePose(previous,start,end,0.28,0.28),start);
  assert.deepEqual(interpolatePose(previous,start,end,1,0.28),end);
  const before=interpolatePose(previous,start,end,0.279,0.28);
  const after=interpolatePose(previous,start,end,0.281,0.28);
  assert.ok(Math.hypot(after[0]-before[0],after[1]-before[1])<0.01);
  assert.deepEqual(interpolatePose(previous,start,end,1),end);
  assert.ok(interpolatePose(previous,start,end,0.5)[0]<start[0]);
});
