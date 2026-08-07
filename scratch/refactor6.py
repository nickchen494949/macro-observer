import re

with open('server.js', 'r') as f:
    content = f.read()

# 1. Add V3 Validator setup
old_setup = """const flowApiSchemaStr = fs.readFileSync(path.join(__dirname, 'config/schemas/flow_api_v2.schema.json'), 'utf-8');
const validateFlowSnapshot = ajv.compile(JSON.parse(flowApiSchemaStr));

let flowApiSchemaV3Str = '';
try {
  flowApiSchemaV3Str = fs.readFileSync(path.join(__dirname, 'config/schemas/flow_api_v3.schema.json'), 'utf-8');
} catch (err) {}
"""
new_setup = """const flowApiSchemaStr = fs.readFileSync(path.join(__dirname, 'config/schemas/flow_api_v2.schema.json'), 'utf-8');
const validateFlowSnapshot = ajv.compile(JSON.parse(flowApiSchemaStr));

let flowApiSchemaV3Str = '';
let validateFlowSnapshotV3 = null;
try {
  flowApiSchemaV3Str = fs.readFileSync(path.join(__dirname, 'config/schemas/flow_api_v3.schema.json'), 'utf-8');
  validateFlowSnapshotV3 = ajv.compile(JSON.parse(flowApiSchemaV3Str));
} catch (err) {}
"""
content = content.replace(old_setup, new_setup)

# 2. Update routing logic
old_route = """  } else if (p === '/api/flows') {
    try {
      const { runProductionFlows } = require('./lib/flow_wrappers');
      const flows = runProductionFlows(store);
      
      const isValid = validateFlowSnapshot(flows);
      if (!isValid) {
        console.error('Flow engine generated invalid snapshot schema:', validateFlowSnapshot.errors);
        res.writeHead(500);
        res.end(JSON.stringify({ status: 'error', error: 'Internal API Schema Violation' }));
        return;
      }
      
      res.end(JSON.stringify(flows));
    } catch (e) {
      console.error('Flow engine error:', e);
      res.end(JSON.stringify({ status: 'error', error: e.message }));
    }
  } else if (p === '/api/schema/flow_v1' || p === '/api/schema/flow_v2') {
    res.end(flowApiSchemaStr);
  } else if (p === '/api/schema/flow_v3') {
    res.end(flowApiSchemaV3Str);
  } else if (p === '/api/data') {"""

new_route = """  } else if (p === '/api/flows' || p === '/api/flows/v3') {
    try {
      const { runProductionFlows } = require('./lib/flow_wrappers');
      const flows = runProductionFlows(store);
      
      const isValid = validateFlowSnapshotV3 ? validateFlowSnapshotV3(flows) : false;
      if (!isValid) {
        console.error('Flow engine generated invalid snapshot schema:', validateFlowSnapshotV3 ? validateFlowSnapshotV3.errors : 'V3 schema missing');
        res.writeHead(500);
        res.end(JSON.stringify({ status: 'error', error: 'Internal API Schema Violation (V3)' }));
        return;
      }
      
      res.end(JSON.stringify(flows));
    } catch (e) {
      console.error('Flow engine error:', e);
      res.end(JSON.stringify({ status: 'error', error: e.message }));
    }
  } else if (p === '/api/flows/v2') {
    // V2 is frozen, returns 410 Gone or mock
    res.writeHead(410);
    res.end(JSON.stringify({ error: 'V2 engine is frozen and no longer supported.' }));
  } else if (p === '/api/schema/flow_v1' || p === '/api/schema/flow_v2') {
    res.end(flowApiSchemaStr);
  } else if (p === '/api/schema/flow_v3') {
    res.end(flowApiSchemaV3Str);
  } else if (p === '/api/data') {"""

content = content.replace(old_route, new_route)

with open('server.js', 'w') as f:
    f.write(content)
