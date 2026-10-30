class DataValidationError extends Error {
  constructor(symbol, date, field, message) {
    super(`${symbol} ${date}: ${field} — ${message}`);
    this.name = 'DataValidationError';
    this.symbol = symbol;
    this.date = date;
    this.field = field;
  }
}

const PRICE_FIELD_POLICY = {
  'SPY': 'adjClose_required',
  'QQQ': 'adjClose_required',
  'IWM': 'adjClose_required',
  'IEF': 'adjClose_required',
  'USO': 'adjClose_required',
  'GLD': 'adjClose_required',
  'TLT': 'adjClose_required',
  'SOXX': 'adjClose_required',

  '^VIX': 'close_required',
  '^GSPC': 'close_required',
  '^IXIC': 'close_required',
  '^RUT': 'close_required',

  'CL=F': 'close_required',
  'GC=F': 'close_required',
  'NG=F': 'close_required',
  'HG=F': 'close_required'
};

function getFieldForPurpose(symbol, row, purpose) {
  if (!row || Array.isArray(row)) return null;

  const policy = PRICE_FIELD_POLICY[symbol];
  const v = row.validation || {};

  if (purpose === 'cta_close') {
    if (policy === 'adjClose_required') {
      if (v.closeValid !== false && Number.isFinite(row.adjClose)) return row.adjClose;
      return null;
    }
    if (policy === 'close_required') {
      if (v.closeValid !== false && Number.isFinite(row.close)) return row.close;
      return null;
    }
    return null;
  }

  if (purpose === 'drawdown_low') {
    if (v.lowValid !== false && v.ohlcPathValid !== false) {
      if (policy === 'adjClose_required' && Number.isFinite(row.adjLow)) return row.adjLow;
      if (Number.isFinite(row.low)) return row.low;
    }
    return null;
  }

  return null;
}

module.exports = {
  DataValidationError,
  PRICE_FIELD_POLICY,
  getFieldForPurpose
};
