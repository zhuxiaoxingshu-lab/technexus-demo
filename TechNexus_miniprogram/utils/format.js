function clean(value) {
  return value === undefined || value === null ? "" : String(value);
}

function scoreLevel(score) {
  const value = Number(score || 0);
  if (value >= 80) return "excellent";
  if (value >= 65) return "high";
  if (value >= 45) return "medium";
  return "low";
}

function scoreLabel(score) {
  const value = Number(score || 0);
  if (value >= 80) return "建议优先对接";
  if (value >= 65) return "建议补充材料";
  if (value >= 45) return "建议进一步核验";
  return "暂不推荐";
}

function tagsForResult(item) {
  return [
    clean(item.tech_field),
    clean(item.demand_type),
    clean(item.region),
    item.intended_price ? `意向投入 ${item.intended_price}` : "",
    clean(item.cooperation_mode),
    clean(item.scoring_source)
  ].filter(Boolean);
}

function dimensionsForResult(item) {
  const dims = item.dimensions || {};
  return [
    { name: "核心问题", value: Number(dims["核心问题"] || 0) },
    { name: "技术标的", value: Number(dims["技术标的"] || 0) },
    { name: "技术路线", value: Number(dims["技术路线"] || 0) },
    { name: "指标约束", value: Number(dims["指标约束"] || 0) },
    { name: "交付成熟度", value: Number(dims["交付成熟度"] || 0) }
  ];
}

function prepareResult(item, index) {
  const score = Number(item.score || 0);
  const detailText = clean(item.demand_detail || item.detail_summary).trim();
  return {
    ...item,
    index,
    score,
    level: scoreLevel(score),
    score_label: scoreLabel(score),
    tags: tagsForResult(item),
    dimensions_list: dimensionsForResult(item),
    confidence: Number(item.confidence || 0),
    verified_items: Array.isArray(item.verified_items) ? item.verified_items : [],
    unverified_items: Array.isArray(item.unverified_items) ? item.unverified_items : [],
    hard_conflicts: Array.isArray(item.hard_conflicts) ? item.hard_conflicts : [],
    detail_text: detailText,
    has_long_detail: detailText.length > 220,
    detail_expanded: false
  };
}

module.exports = {
  prepareResult,
  scoreLabel,
  scoreLevel
};
