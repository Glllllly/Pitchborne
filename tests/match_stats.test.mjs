import test from "node:test";
import assert from "node:assert/strict";
import {estimatedShotXg,summarizeMatch} from "../web/match_stats.mjs";

const match={home_team:{id:1,name:"Home"},away_team:{id:2,name:"Away"}};
const pass={id:"pass-1",team:{id:1},type:{name:"Pass"},pass:{outcome:{name:"Complete"}}};
const shot={id:"shot-1",team:{id:1},type:{name:"Shot"},location:[105,40],under_pressure:false,
  shot:{outcome:{name:"Goal"},key_pass_id:"pass-1"},kinematics:{ball_speed_kmh:91}};

test("live statistics count only events already played", () => {
  const before=summarizeMatch(match,[pass]);
  assert.equal(before[0].keyPasses,0);
  assert.equal(before[0].shots,0);
  const after=summarizeMatch(match,[pass,shot]);
  assert.equal(after[0].keyPasses,1);
  assert.equal(after[0].shots,1);
  assert.equal(after[0].shotsOnTarget,1);
  assert.equal(after[0].goals,1);
  assert.ok(after[0].xg>0);
  assert.equal(after[0].averageShotSpeed,91);
  assert.equal(after[1].shots,0);
});

test("synthetic xG uses location and pressure, not shot outcome", () => {
  const close=estimatedShotXg(shot);
  assert.ok(close>estimatedShotXg({...shot,location:[80,40]}));
  assert.ok(close>estimatedShotXg({...shot,under_pressure:true}));
  assert.equal(close,estimatedShotXg({...shot,shot:{...shot.shot,outcome:{name:"Off T"}}}));
});
