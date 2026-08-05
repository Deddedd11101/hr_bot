import * as React from "react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Panel,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Bell, CircleDotDashed, Hourglass, Paperclip } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import { layoutScenarioGraph, type ScenarioFlowEdge, type ScenarioFlowNode, type ScenarioGraphNodeData } from "./graph-layout";
import type { WorkspaceGraph } from "./types";

const nodeTypes = {
  scenarioGraphNode: ScenarioGraphNode,
};

export function ScenarioGraphView({
  graph,
  selectedStepId,
  onSelectStep,
}: {
  graph: WorkspaceGraph | null | undefined;
  selectedStepId: number | null;
  onSelectStep: (stepId: number) => void;
}) {
  const [nodes, setNodes] = React.useState<ScenarioFlowNode[]>([]);
  const [edges, setEdges] = React.useState<ScenarioFlowEdge[]>([]);

  const selectedNodeId = React.useMemo(() => {
    if (!graph || !selectedStepId) return null;
    return graph.nodes.find((node) => node.step_id === selectedStepId)?.id || null;
  }, [graph, selectedStepId]);

  React.useEffect(() => {
    let cancelled = false;

    if (!graph?.nodes.length) {
      setNodes([]);
      setEdges([]);
      return;
    }

    layoutScenarioGraph(graph, selectedNodeId).then((layouted) => {
      if (cancelled) return;
      setNodes(layouted.nodes);
      setEdges(layouted.edges);
    });

    return () => {
      cancelled = true;
    };
  }, [graph, selectedNodeId]);

  if (!graph?.nodes.length) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center rounded-lg border border-dashed border-border bg-muted/35 p-6 text-sm font-medium text-muted-foreground">
        Схема появится после добавления шагов.
      </div>
    );
  }

  return (
    <div className="scenario-graph-shell min-h-0 flex-1 overflow-hidden rounded-lg border border-border bg-muted/25">
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.25}
          maxZoom={1.35}
          nodesDraggable={false}
          nodesConnectable={false}
          edgesFocusable={false}
          elementsSelectable={false}
          zoomOnDoubleClick={false}
          proOptions={{ hideAttribution: true }}
          defaultEdgeOptions={{
            markerEnd: { type: MarkerType.ArrowClosed },
          }}
          onNodeClick={(_, node) => {
            const stepId = node.data.step_id;
            if (typeof stepId === "number") {
              onSelectStep(stepId);
            }
          }}
        >
          <Background className="scenario-graph-bg" gap={24} size={1} />
          <Controls showInteractive={false} position="bottom-right" />
          <Panel position="top-left" className="pointer-events-none">
            <div className="rounded-lg border border-border bg-card/90 px-3 py-2 text-xs font-medium text-muted-foreground shadow-sm backdrop-blur">
              {graph.meta.node_count} нод · {graph.meta.edge_count} связей
            </div>
          </Panel>
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}

function ScenarioGraphNode({ data }: NodeProps<ScenarioFlowNode>) {
  const isPlaceholder = data.kind === "branch_slot" || data.is_placeholder;
  const isLaunchTarget = data.kind === "launch_target";

  return (
    <div
      className={cn(
        "scenario-graph-node min-w-[210px] max-w-[238px] rounded-lg border bg-card p-3 text-card-foreground shadow-sm",
        data.selected && "scenario-graph-node-selected",
        isPlaceholder && "scenario-graph-node-placeholder border-dashed bg-muted/45",
        isLaunchTarget && "scenario-graph-node-launch bg-secondary/65",
      )}
    >
      <Handle type="target" position={Position.Left} className="scenario-graph-handle" />
      <div className="flex min-w-0 items-start justify-between gap-2">
        <h4 className="line-clamp-2 text-sm font-semibold leading-5">{data.title || "Без названия"}</h4>
        {data.is_terminal ? <CircleDotDashed className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" /> : null}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <Badge variant={data.waits_for_response ? "default" : "secondary"} className="max-w-full truncate">
          {isPlaceholder ? "Пустая ветка" : isLaunchTarget ? "Внешний сценарий" : data.response_label || compactResponseType(data.response_type)}
        </Badge>
        {data.send_mode ? <Badge variant="outline">{data.send_mode}</Badge> : null}
      </div>
      {data.text_preview ? (
        <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">{data.text_preview}</p>
      ) : null}
      <div className="mt-3 flex items-center gap-2 text-muted-foreground">
        {data.has_attachment ? <Paperclip className="size-3.5" aria-label="Есть вложение" /> : null}
        {data.has_notifications ? <Bell className="size-3.5" aria-label="Есть уведомления" /> : null}
        {data.waits_for_response ? <Hourglass className="size-3.5" aria-label="Ждет ответ" /> : null}
      </div>
      <Handle type="source" position={Position.Right} className="scenario-graph-handle" />
    </div>
  );
}

function compactResponseType(responseType: string) {
  if (responseType === "launch_scenario") return "Переход";
  if (responseType === "branching") return "Ветвление";
  if (responseType === "chain") return "Цепочка";
  if (responseType === "file") return "Файл";
  if (responseType === "text") return "Текст";
  return "Шаг";
}
