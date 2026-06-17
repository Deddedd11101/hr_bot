import type { Edge, Node } from "@xyflow/react";
import ELK from "elkjs/lib/elk.bundled.js";

import type { WorkspaceGraph, WorkspaceGraphEdge, WorkspaceGraphNode } from "./types";

export type ScenarioGraphNodeData = WorkspaceGraphNode & {
  selected: boolean;
};

export type ScenarioGraphEdgeData = WorkspaceGraphEdge;

export type ScenarioFlowNode = Node<ScenarioGraphNodeData, "scenarioGraphNode">;
export type ScenarioFlowEdge = Edge<ScenarioGraphEdgeData>;

const elk = new ELK();

const NODE_WIDTH = 238;
const NODE_HEIGHT = 126;

const elkOptions = {
  "elk.algorithm": "layered",
  "elk.direction": "RIGHT",
  "elk.spacing.nodeNode": "56",
  "elk.layered.spacing.nodeNodeBetweenLayers": "104",
  "elk.layered.spacing.edgeNodeBetweenLayers": "48",
  "elk.edgeRouting": "ORTHOGONAL",
};

export async function layoutScenarioGraph(graph: WorkspaceGraph, selectedNodeId: string | null) {
  const flowNodes: ScenarioFlowNode[] = graph.nodes.map((node) => ({
    id: node.id,
    type: "scenarioGraphNode",
    position: { x: 0, y: 0 },
    data: {
      ...node,
      selected: node.id === selectedNodeId,
    },
    draggable: false,
    selectable: !!node.step_id,
  }));

  const flowEdges: ScenarioFlowEdge[] = graph.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: edge.kind === "launch_scenario" || edge.kind === "return_to_root" ? "smoothstep" : "default",
    label: edge.kind === "branch_option" ? edge.label : undefined,
    data: edge,
    animated: edge.kind === "launch_scenario",
    className: `scenario-graph-edge scenario-graph-edge-${edge.kind}`,
    labelBgPadding: [6, 3],
    labelBgBorderRadius: 8,
  }));

  const layoutGraph = await elk.layout({
    id: "scenario-workspace-graph",
    layoutOptions: elkOptions,
    children: flowNodes.map((node) => ({
      id: node.id,
      width: node.data.kind === "launch_target" ? NODE_WIDTH - 28 : NODE_WIDTH,
      height: node.data.kind === "branch_slot" ? NODE_HEIGHT - 18 : NODE_HEIGHT,
    })),
    edges: flowEdges.map((edge) => ({
      id: edge.id,
      sources: [edge.source],
      targets: [edge.target],
    })),
  });

  const positions = new Map((layoutGraph.children || []).map((node) => [node.id, node]));

  return {
    nodes: flowNodes.map((node) => {
      const layoutNode = positions.get(node.id);
      return {
        ...node,
        position: {
          x: layoutNode?.x || 0,
          y: layoutNode?.y || 0,
        },
      };
    }),
    edges: flowEdges,
  };
}
