import test from "node:test";
import assert from "node:assert/strict";
import {interpolatePose,runningPose,coordinatedMotion,setupShareFor,playerMotion,pitchDistanceMetres} from "../web/pitch_motion.mjs";

test("key player runs through the start of the action without a scene cut",()=>{
  const previous=[10,40],start=[75,40],end=[80,42],setup=.85;
  assert.deepEqual(runningPose(previous,start,end,0,setup),previous);
  assert.deepEqual(runningPose(previous,start,end,setup,setup),start);
  assert.deepEqual(runningPose(previous,start,end,1,setup),end);
  assert.ok(runningPose(previous,start,end,.4,setup)[0]>previous[0]);
});

test("player motion respects a running-speed ceiling across near and distant targets",()=>{
  const from=[10,40],near=[13,40],far=[110,40],duration=1200,speed=4;
  assert.deepEqual(playerMotion(from,far,0,duration,speed),from);
  const nearEnd=playerMotion(from,near,1,duration,speed);
  const farEnd=playerMotion(from,far,1,duration,speed);
  assert.deepEqual(nearEnd,near);
  assert.ok(pitchDistanceMetres(from,farEnd)<pitchDistanceMetres(from,far));
  assert.ok(pitchDistanceMetres(from,farEnd)<=speed*duration/1000/1.5+1e-9);
  const midpoint=playerMotion(from,far,.5,duration,speed);
  assert.ok(pitchDistanceMetres(from,midpoint)<pitchDistanceMetres(from,farEnd));
});

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

test("ball flight finishes before player follow-through on one shared timeline",()=>{
  const setup=setupShareFor(30);
  const ballStart=[20,40],ballEnd=[60,40];
  assert.deepEqual(coordinatedMotion([18,40],ballStart,ballEnd,setup,setup,.82),ballStart);
  assert.deepEqual(coordinatedMotion([18,40],ballStart,ballEnd,.82,setup,.82),ballEnd);
  assert.deepEqual(coordinatedMotion([18,40],ballStart,ballEnd,1,setup,.82),ballEnd);
  const player=interpolatePose([20,40],[20,40],[24,40],.82,setup);
  assert.ok(player[0]<24);
});
