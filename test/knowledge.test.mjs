import test from "node:test";
import assert from "node:assert/strict";
import { articles, retrieveGuidance, buildKnowledgeContext } from "../knowledge.mjs";

test("every article has a unique id and source metadata", () => {
  assert.equal(new Set(articles.map(item => item.id)).size, articles.length);
  for (const article of articles) {
    assert.ok(article.id && article.title && article.guidance);
    assert.ok(article.source.startsWith("https://"));
    // No entry is marked reviewed until a qualified reviewer records a date.
    assert.equal(article.reviewed, null);
  }
});

test("relevant watering query retrieves watering guidance", () => {
  assert.equal(retrieveGuidance("How often should I water a newly planted tree?")[0]?.id, "watering");
});

test("pruning query retrieves pruning guidance", () => {
  assert.equal(retrieveGuidance("Should I prune this branch?")[0]?.id, "pruning");
});

test("unrelated query does not fabricate references", () => {
  assert.deepEqual(retrieveGuidance("zzzxxyy incomprehensible nonsense"), []);
  assert.deepEqual(buildKnowledgeContext("zzzxxyy incomprehensible nonsense").sources, []);
});

test("retrieval has deterministic bounded results", () => {
  const hits = retrieveGuidance("water roots soil pruning insects bark", 100);
  assert.ok(hits.length <= 3);
  assert.deepEqual(hits, retrieveGuidance("water roots soil pruning insects bark", 100));
});

test("chat context returns reference metadata without asserting live verification", () => {
  const result = buildKnowledgeContext("yellow leaves");
  assert.ok(result.context.includes("not a diagnosis"));
  assert.ok(result.sources.length > 0);
  assert.ok(result.sources.every(source => source.url.startsWith("https://")));
});
