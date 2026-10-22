import test from "node:test";
import assert from "node:assert/strict";
import { OpenRouter } from "@openrouter/sdk";
import { HTTPClient } from "@openrouter/sdk/lib/http.js";
import { generateInsight, configuration, DEFAULT_MODEL } from "../adapters/openrouter.mjs";

const request = { instructions: "Use facts only.", facts: { outcome: "Goal" }, evidence: [{ event_id: "event-1" }] };
const config = { model: DEFAULT_MODEL, timeoutMs: 1000 };
const base = { id: "test-gen", created: 1, model: DEFAULT_MODEL, object: "chat.completion.chunk" };
function clientWith(chunks, inspect = () => {}) {
  return new OpenRouter({ apiKey: "test-only", retryConfig: { strategy: "none" },
    httpClient: new HTTPClient({fetcher: async (req) => {
      inspect(await req.json());
      return new Response(chunks.map(c=>`data: ${JSON.stringify({...base,...c})}\n\n`).join("")+"data: [DONE]\n\n", {headers:{"Content-Type":"text/event-stream"}});
    }}),
  });
}
test("official SDK streams content and maps final usage including reasoning", async () => {
  const body = JSON.stringify({title:"Goal",text:"Our team scored.",evidence_event_ids:["event-1"]});
  const client = clientWith([
    { choices:[{index:0,delta:{role:"assistant",content:body.slice(0,20)},finish_reason:null}] },
    { choices:[{index:0,delta:{content:body.slice(20)},finish_reason:"stop"}] },
    { choices:[], usage:{prompt_tokens:100,completion_tokens:40,total_tokens:140,completion_tokens_details:{reasoning_tokens:7}} },
  ], sent=>{
    assert.equal(sent.model,DEFAULT_MODEL); assert.equal(sent.stream,true);
    assert.equal(sent.response_format.type,"json_object");
    assert.deepEqual(JSON.parse(sent.messages[1].content).facts,request.facts);
  });
  const result=await generateInsight(request,{client,config});
  assert.equal(result.text,"Our team scored.");
  assert.equal(result.generation.usage.reasoning_tokens,7);
  assert.equal(result.generation.usage.total_tokens,140);
});
test("truncated streams are rejected",async()=>{
  const client=clientWith([{choices:[{index:0,delta:{content:'{}'},finish_reason:"length"}]}]);
  await assert.rejects(generateInsight(request,{client,config}),/incomplete_response/);
});
test("malformed JSON is rejected",async()=>{
  const client=clientWith([{choices:[{index:0,delta:{content:'not JSON'},finish_reason:"stop"}]}]);
  await assert.rejects(generateInsight(request,{client,config}),SyntaxError);
});
test("configuration contains no secret",()=>{
  const value=configuration({OPENROUTER_API_KEY:"secret-for-test",OPENROUTER_TIMEOUT_MS:"bad"});
  assert.equal(value.configured,true);assert.equal(value.timeoutMs,45000);
  assert.ok(!JSON.stringify(value).includes("secret-for-test"));
});
test("upstream error chunks cannot be mistaken for completed output",async()=>{
  const client=clientWith([{choices:[],error:{code:503,message:"unavailable"}}]);
  await assert.rejects(generateInsight(request,{client,config}),/upstream_stream_error/);
});
test("deadline aborts a stalled SDK request",async()=>{
  const client={chat:{send:async(_,{signal})=>new Promise((resolve,reject)=>{
    signal.addEventListener("abort",()=>reject(new DOMException("Aborted","AbortError")),{once:true});
  })}};
  await assert.rejects(generateInsight(request,{client,config:{...config,timeoutMs:20}}),{name:"AbortError"});
});
