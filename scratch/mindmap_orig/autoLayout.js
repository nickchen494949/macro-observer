/**
 * autoLayout.js — Grid-based layered layout engine for 系统图 App
 *
 * AI provides: nodes with level/lane/group hints (no x/y needed)
 * This engine: calculates x/y coordinates automatically
 *
 * Usage:
 *   autoLayout(nodes, arrows, options)
 *   checkArrowCollisions(nodes, arrows)
 */

(function (root) {
  'use strict';

  var DEFAULT_OPTIONS = {
    colGap: 260,     // horizontal gap between lanes
    rowGap: 200,     // vertical gap between levels
    leftMargin: 40,  // canvas left padding
    topMargin: 40,   // canvas top padding
    nodeGap: 30,     // minimum gap between nodes in same row
    defaultNodeWidth: 180,
    defaultNodeHeight: 100,
  };

  // ─────────────────────────────────────────────
  // 1. LEVEL INFERENCE (when AI didn't provide levels)
  // ─────────────────────────────────────────────

  /**
   * Infer levels from arrow structure using BFS from root nodes.
   * Root = node with zero in-degree.
   * Handles cycles by capping at visited check.
   */
  function inferLevels(nodes, arrows) {
    var nodeMap = {};
    nodes.forEach(function (n) { nodeMap[n.id] = n; });

    // Build adjacency + in-degree
    var children = {};   // id → [target ids]
    var inDegree = {};
    nodes.forEach(function (n) {
      children[n.id] = [];
      inDegree[n.id] = 0;
    });
    arrows.forEach(function (a) {
      if (children[a.from] && nodeMap[a.to]) {
        children[a.from].push(a.to);
        inDegree[a.to] = (inDegree[a.to] || 0) + 1;
      }
    });

    // Find roots (in-degree 0)
    var roots = [];
    nodes.forEach(function (n) {
      if (inDegree[n.id] === 0) roots.push(n.id);
    });

    // If no roots (everything in a cycle), pick first node
    if (roots.length === 0 && nodes.length > 0) {
      roots.push(nodes[0].id);
    }

    // BFS to assign levels — with cycle protection
    var levels = {};
    var visitCount = {};  // prevent infinite loops on cycles
    var queue = [];
    var maxIterations = nodes.length * 3; // safety cap
    var iterations = 0;
    roots.forEach(function (id) {
      levels[id] = 0;
      visitCount[id] = 1;
      queue.push(id);
    });

    while (queue.length > 0 && iterations < maxIterations) {
      iterations++;
      var current = queue.shift();
      var currentLevel = levels[current];
      (children[current] || []).forEach(function (childId) {
        var newLevel = currentLevel + 1;
        // Only update if new level is higher AND we haven't visited too many times
        if ((levels[childId] === undefined || newLevel > levels[childId])
            && (visitCount[childId] || 0) < 2) {
          levels[childId] = newLevel;
          visitCount[childId] = (visitCount[childId] || 0) + 1;
          queue.push(childId);
        }
      });
    }

    // Assign to nodes
    nodes.forEach(function (n) {
      if (n.level === undefined || n.level === null) {
        n.level = levels[n.id] !== undefined ? levels[n.id] : 0;
      }
    });
  }

  // ─────────────────────────────────────────────
  // 2. LANE ASSIGNMENT
  // ─────────────────────────────────────────────

  /**
   * Assign lanes to nodes within each level.
   * Groups nodes by their `group` property, then assigns sequential lanes.
   * Respects existing lane values if provided.
   */
  function assignLanes(nodes, arrows) {
    // Group nodes by level
    var byLevel = {};
    nodes.forEach(function (n) {
      var lvl = n.level || 0;
      if (!byLevel[lvl]) byLevel[lvl] = [];
      byLevel[lvl].push(n);
    });

    // Build parent map for ordering children by parent position
    var parentOf = {};  // childId → [parentIds]
    arrows.forEach(function (a) {
      if (!parentOf[a.to]) parentOf[a.to] = [];
      parentOf[a.to].push(a.from);
    });

    // For each level, assign lanes
    Object.keys(byLevel).forEach(function (lvl) {
      var levelNodes = byLevel[lvl];

      // Separate: nodes with lane already set vs not
      var withLane = levelNodes.filter(function (n) { return n.lane !== undefined && n.lane !== null; });
      var withoutLane = levelNodes.filter(function (n) { return n.lane === undefined || n.lane === null; });

      if (withoutLane.length === 0) return;

      // Sort by group, then by parent's lane (to keep children near parents)
      withoutLane.sort(function (a, b) {
        // First by group
        var ga = a.group || '';
        var gb = b.group || '';
        if (ga !== gb) return ga < gb ? -1 : 1;

        // Then by parent's average x position (if parents have been positioned)
        var aParentLane = getAverageParentLane(a.id, parentOf, nodes);
        var bParentLane = getAverageParentLane(b.id, parentOf, nodes);
        return aParentLane - bParentLane;
      });

      // Find max lane already used
      var maxLane = -1;
      withLane.forEach(function (n) { if (n.lane > maxLane) maxLane = n.lane; });

      // Assign sequential lanes
      withoutLane.forEach(function (n, i) {
        n.lane = maxLane + 1 + i;
      });
    });
  }

  function getAverageParentLane(nodeId, parentOf, nodes) {
    var parents = parentOf[nodeId] || [];
    if (parents.length === 0) return 0;
    var sum = 0;
    var count = 0;
    parents.forEach(function (pid) {
      var pNode = nodes.find(function (n) { return n.id === pid; });
      if (pNode && pNode.lane !== undefined) {
        sum += pNode.lane;
        count++;
      }
    });
    return count > 0 ? sum / count : 0;
  }

  // ─────────────────────────────────────────────
  // 3. COORDINATE CALCULATION
  // ─────────────────────────────────────────────

  function calculateCoordinates(nodes, options) {
    var opts = mergeOptions(options);

    // Group by level for centering
    var byLevel = {};
    nodes.forEach(function (n) {
      var lvl = n.level || 0;
      if (!byLevel[lvl]) byLevel[lvl] = [];
      byLevel[lvl].push(n);
    });

    // Sort each level by lane
    Object.keys(byLevel).forEach(function (lvl) {
      byLevel[lvl].sort(function (a, b) { return (a.lane || 0) - (b.lane || 0); });
    });

    // Calculate positions
    nodes.forEach(function (n) {
      if (n.pinned) return; // skip pinned nodes

      var level = n.level || 0;
      var lane = n.lane || 0;

      // Find the minimum lane in this level for centering
      var levelNodes = byLevel[level] || [];
      var minLane = Infinity;
      levelNodes.forEach(function (ln) {
        if ((ln.lane || 0) < minLane) minLane = ln.lane || 0;
      });

      var adjustedLane = lane - minLane;
      n.x = opts.leftMargin + adjustedLane * opts.colGap;
      n.y = opts.topMargin + level * opts.rowGap;
    });

    // Collision resolution: push overlapping nodes right
    Object.keys(byLevel).forEach(function (lvl) {
      var levelNodes = byLevel[lvl].filter(function (n) { return !n.pinned; });
      levelNodes.sort(function (a, b) { return a.x - b.x; });

      for (var i = 1; i < levelNodes.length; i++) {
        var prev = levelNodes[i - 1];
        var curr = levelNodes[i];
        var prevWidth = prev.nw || opts.defaultNodeWidth;
        var minX = prev.x + prevWidth + opts.nodeGap;
        if (curr.x < minX) {
          curr.x = minX;
        }
      }
    });

    // Center each level horizontally relative to the widest level
    var maxWidth = 0;
    var levelWidths = {};
    Object.keys(byLevel).forEach(function (lvl) {
      var levelNodes = byLevel[lvl];
      if (levelNodes.length === 0) return;
      var minX = Infinity, maxX = 0;
      levelNodes.forEach(function (n) {
        if (n.x < minX) minX = n.x;
        var right = n.x + (n.nw || opts.defaultNodeWidth);
        if (right > maxX) maxX = right;
      });
      levelWidths[lvl] = { min: minX, max: maxX, width: maxX - minX };
      if (maxX - minX > maxWidth) maxWidth = maxX - minX;
    });

    // Shift narrower levels to center
    Object.keys(byLevel).forEach(function (lvl) {
      var lw = levelWidths[lvl];
      if (!lw) return;
      var offset = (maxWidth - lw.width) / 2;
      if (offset > 0) {
        byLevel[lvl].forEach(function (n) {
          if (!n.pinned) n.x += offset;
        });
      }
    });

  }

  // 4. ARROW COLLISION DETECTION
  // ─────────────────────────────────────────────

  /**
   * Check if any arrow's straight-line path passes through a node.
   * Returns array of { arrowId, nodeId } collision pairs.
   */
  function checkArrowCollisions(nodes, arrows) {
    var collisions = [];
    var nodeMap = {};
    nodes.forEach(function (n) { nodeMap[n.id] = n; });

    arrows.forEach(function (a) {
      var fromNode = nodeMap[a.from];
      var toNode = nodeMap[a.to];
      if (!fromNode || !toNode) return;

      // Get arrow start/end points (approximate: center of port)
      var p1 = getPortCenter(fromNode, a.fromPort || 'bottom');
      var p2 = getPortCenter(toNode, a.toPort || 'top');

      // Check against all other nodes
      nodes.forEach(function (n) {
        if (n.id === a.from || n.id === a.to) return;

        var nw = n.nw || 180;
        var nh = n.showDesc ? 100 : 50;
        var padding = 5;

        // Node bounding box
        var nx1 = n.x - padding;
        var ny1 = n.y - padding;
        var nx2 = n.x + nw + padding;
        var ny2 = n.y + nh + padding;

        // Sample points along the line
        for (var t = 0.1; t <= 0.9; t += 0.05) {
          var px = p1.x + (p2.x - p1.x) * t;
          var py = p1.y + (p2.y - p1.y) * t;
          if (px > nx1 && px < nx2 && py > ny1 && py < ny2) {
            collisions.push({ arrowId: a.id, nodeId: n.id });
            return; // one hit is enough per arrow-node pair
          }
        }
      });
    });

    return collisions;
  }

  function getPortCenter(node, port) {
    var nw = node.nw || 180;
    var nh = node.showDesc ? 100 : 50;
    switch (port) {
      case 'top':    return { x: node.x + nw / 2, y: node.y };
      case 'bottom': return { x: node.x + nw / 2, y: node.y + nh };
      case 'left':   return { x: node.x,          y: node.y + nh / 2 };
      case 'right':  return { x: node.x + nw,     y: node.y + nh / 2 };
      default:       return { x: node.x + nw / 2, y: node.y + nh };
    }
  }

  // ─────────────────────────────────────────────
  // 5. MAIN ENTRY POINT
  // ─────────────────────────────────────────────

  /**
   * Run auto-layout on nodes + arrows.
   * Modifies nodes in-place (sets x, y).
   * Skips pinned nodes.
   *
   * @param {Array} nodes - array of node objects
   * @param {Array} arrows - array of arrow objects
   * @param {Object} options - layout options (optional)
   * @returns {Array} nodes (same reference, mutated)
   */
  function autoLayout(nodes, arrows, options) {
    if (!nodes || nodes.length === 0) return nodes;

    // Step 1: Infer levels if not provided
    var needsInference = nodes.some(function (n) {
      return n.level === undefined || n.level === null;
    });
    if (needsInference) {
      inferLevels(nodes, arrows);
    }

    // Step 2: Assign lanes
    assignLanes(nodes, arrows);

    // Step 3: Calculate x/y coordinates
    calculateCoordinates(nodes, options);

    return nodes;
  }

  // ─────────────────────────────────────────────
  // UTILS
  // ─────────────────────────────────────────────

  function mergeOptions(userOpts) {
    var opts = {};
    for (var k in DEFAULT_OPTIONS) {
      opts[k] = DEFAULT_OPTIONS[k];
    }
    if (userOpts) {
      for (var k2 in userOpts) {
        opts[k2] = userOpts[k2];
      }
    }
    return opts;
  }

  // ─────────────────────────────────────────────
  // EXPORT
  // ─────────────────────────────────────────────

  root.autoLayout = autoLayout;
  root.checkArrowCollisions = checkArrowCollisions;

})(typeof window !== 'undefined' ? window : this);
