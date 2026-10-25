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

test("additional match stats use event ownership and show zero for absent event types", () => {
  const events=[
    {id:"kick",minute:0,second:0,duration:1,type:{name:"Kick Off"},team:{id:1},possession_team:{id:1}},
    {...pass,minute:0,second:10,duration:1,possession_team:{id:1},location:[35,40],
      pass:{...pass.pass,end_location:[75,40]}},
    {...shot,minute:0,second:20,duration:1,possession_team:{id:1},location:[105,40]},
    {id:"away-shot",minute:0,second:30,duration:1,type:{name:"Shot"},team:{id:2},
      possession_team:{id:2},location:[90,40],shot:{outcome:{name:"Off T"}}},
  ];
  const [home,away]=summarizeMatch(match,events);
  assert.equal(home.possession,30/31);
  assert.equal(away.possession,1/31);
  assert.equal(home.longPasses,1);
  assert.equal(home.shotsInsideBox,1);
  assert.equal(away.shotsOutsideBox,1);
  for(const side of [home,away]){
    assert.equal(side.offsides,0);
    assert.equal(side.fouls,0);
    assert.equal(side.yellowCards,0);
    assert.equal(side.redCards,0);
  }
});

test("disciplinary events count for the event team", () => {
  const base={team:{id:1},possession_team:{id:2},minute:4,second:0,duration:1};
  const [home]=summarizeMatch(match,[
    {...base,type:{name:"Offside"}},
    {...base,type:{name:"Foul Committed"},foul_committed:{card:{name:"Yellow Card"}}},
    {...base,type:{name:"Bad Behaviour"},bad_behaviour:{card:{name:"Red Card"}}},
  ]);
  assert.equal(home.offsides,1);
  assert.equal(home.fouls,1);
  assert.equal(home.yellowCards,1);
  assert.equal(home.redCards,1);
});
