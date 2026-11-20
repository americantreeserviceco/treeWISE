// Curated, version-controlled guidance. Not a diagnosis or a substitute for an arborist.
// Content is advisory; source pages should be reviewed periodically for updates.
export const articles = [
  {
    id: "watering",
    title: "Watering trees in Colorado",
    keywords: ["water", "watering", "drought", "dry", "brown leaves", "newly planted", "winter watering", "irrigation"],
    guidance: "Watering depends on species, tree age, weather, soil drainage, and recent precipitation. Check soil moisture in the root zone before adding water. Newly planted trees require closer monitoring while roots establish. Avoid keeping roots continuously saturated. In dry Colorado winters, ask whether the ground is unfrozen and conditions are appropriate before recommending winter watering.",
    source: "https://extension.colostate.edu/",
    reviewed: "2026-11-20"
  },
  {
    id: "leaf-symptoms",
    title: "Brown, yellow, or wilting foliage",
    keywords: ["brown", "yellow", "wilting", "leaves", "leaf", "scorch", "chlorosis", "spots", "needles"],
    guidance: "Leaf discoloration can be associated with inconsistent watering, heat, salt exposure, root damage, pests, diseases, or natural seasonal change. Ask for species, affected branches, when symptoms started, and nearby construction or soil disturbance. A photo can show symptoms but does not establish the underlying cause.",
    source: "https://extension.colostate.edu/",
    reviewed: "2026-11-20"
  },
  {
    id: "pruning",
    title: "Pruning and tree preservation",
    keywords: ["prune", "pruning", "trim", "trimming", "deadwood", "branch", "limb", "canopy"],
    guidance: "Pruning decisions depend on tree species, season, branch condition, and goals. Avoid unnecessary topping and indiscriminate removal of healthy canopy. Large limbs, high work, compromised trees, and work near utilities should be assessed by qualified professionals; do not provide risky DIY cutting instructions.",
    source: "https://www.treesaregood.org/",
    reviewed: "2026-11-20"
  },
  {
    id: "pests",
    title: "Possible insect and disease concerns",
    keywords: ["bug", "beetle", "borer", "insect", "pest", "fungus", "disease", "holes", "sap", "bark"],
    guidance: "Pests and diseases vary by host species and season. Ask for species, location of symptoms, timing, and clear photographs of both affected and unaffected areas. Do not identify a pathogen with certainty or recommend pesticides, injections, or treatment solely from a photo. Suggest local extension diagnostics or an in-person arborist when warranted.",
    source: "https://extension.colostate.edu/",
    reviewed: "2026-11-20"
  },
  {
    id: "roots",
    title: "Root zones, soil, and construction damage",
    keywords: ["root", "roots", "soil", "compaction", "construction", "excavation", "mulch", "grade", "trunk"],
    guidance: "Soil compaction, trenching, grade changes, excess mulch against the trunk, and altered drainage can stress trees. Ask about recent landscape or construction work and the extent of soil disturbance. Avoid declaring a tree stable or unstable from remote observations. Visible root-plate movement or sudden leaning requires keeping people clear and seeking qualified on-site assessment.",
    source: "https://www.treesaregood.org/",
    reviewed: "2026-11-20"
  },
  {
    id: "planting",
    title: "Planting trees along Colorado's Front Range",
    keywords: ["plant", "planting", "species", "select", "choose", "new tree", "transplant", "site"],
    guidance: "Tree selection should consider local climate, available rooting space, sun, soil, water, mature size, and utility clearance. Recommend site-specific guidance and diverse, climate-appropriate species rather than promising any species will thrive. Avoid making utility-clearance or municipal-permit claims without local verification.",
    source: "https://extension.colostate.edu/",
    reviewed: "2026-11-20"
  }
];

const stopwords = new Set(["about","after","again","also","are","can","could","does","for","from","have","how","into","just","more","much","need","our","that","the","their","there","these","this","tree","trees","what","when","where","which","will","with","would","your"]);
function terms(value) {
  return [...new Set(String(value).toLowerCase().match(/[a-z]{3,}/g)?.filter(w => !stopwords.has(w)) ?? [])];
}
export function retrieveGuidance(query, limit = 3) {
  const queryTerms = terms(query);
  if (!queryTerms.length) return [];
  return articles.map(article => {
    const keywordTerms = new Set(terms(article.keywords.join(" ")));
    const titleTerms = new Set(terms(article.title));
    const guidanceTerms = new Set(terms(article.guidance));
    const score = queryTerms.reduce((total, term) =>
      total + (keywordTerms.has(term) ? 5 : 0) +
      (titleTerms.has(term) ? 3 : 0) +
      (guidanceTerms.has(term) ? 1 : 0), 0);
    return { article, score };
  }).filter(hit => hit.score >= 3).sort((a,b) => b.score - a.score || a.article.id.localeCompare(b.article.id))
    .slice(0, Math.max(0, Math.min(3, limit)))
    .map(({article}) => article);
}
export function buildKnowledgeContext(query) {
  const hits = retrieveGuidance(query);
  if (!hits.length) return { context: "", sources: [] };
  const context = hits.map(({id,title,guidance}) => `[${id}] ${title}: ${guidance}`).join("\n");
  return {
    context: "Curated tree-care reference notes (not a diagnosis). Use only where relevant, and do not claim any source was consulted live:\n" + context,
    sources: hits.map(({id,title,source,reviewed}) => ({ id, title, url: source, reviewed }))
  };
}
