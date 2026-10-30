function canonicalize(obj) {
  if (obj === null || typeof obj !== 'object') {
    return obj;
  }
  if (Array.isArray(obj)) {
    return obj.map(canonicalize);
  }
  const sortedKeys = Object.keys(obj).sort();
  const result = {};
  for (const key of sortedKeys) {
    if (key === 'snapshotGeneratedAt' || key === 'downloadedAt') continue; // strip runtime timestamps
    result[key] = canonicalize(obj[key]);
  }
  return result;
}

module.exports = { canonicalize };
