function clean(value) {
  return value === undefined || value === null ? "" : String(value);
}

function scoreLevel(score) {
  const value = Number(score || 0);
  if (value >= 90) return "excellent";
  if (value >= 80) return "high";
  if (value >= 70) return "medium";
  return "low";
}

function scoreLabel(score) {
  const value = Number(score || 0);
  if (value >= 90) return "高度匹配";
  if (value >= 80) return "较高匹配";
  if (value >= 70) return "可继续看";
  return "待人工判断";
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
    { name: "技术领域", value: Number(dims["技术领域"] || 0) },
    { name: "应用场景", value: Number(dims["应用场景"] || 0) },
    { name: "产业方向", value: Number(dims["产业方向"] || 0) },
    { name: "成熟度", value: Number(dims["成熟度"] || 0) }
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
