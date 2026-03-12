export type EventType =
	| 'SessionStart'
	| 'SessionEnd'
	| 'SubagentStart'
	| 'SubagentEnd'
	| 'PreToolUse'
	| 'PostToolUse'
	| 'PostToolUseFailure'
	| 'SkillLoaded';

export type AgentStatus = 'running' | 'complete' | 'failed';
export type ConnectionStatus = 'connected' | 'reconnecting' | 'disconnected';

export interface ObserverEvent {
	event_id: string;
	event_type: EventType;
	session_id: string;
	agent_id?: string;
	agent_type?: string;
	tool_use_id?: string;
	tool_name?: string;
	cwd?: string;
	received_at: string;
	payload: Record<string, unknown>;
}

export interface SessionInfo {
	session_id: string;
	cwd: string;
	start_time: string;
	end_time?: string;
	agent_count: number;
	event_count: number;
	is_active: boolean;
}

export interface GraphNode {
	data: {
		id: string;
		label: string;
		agent_type: string;
		status: AgentStatus;
		tool_count: number;
		started_at?: string;
		prompt?: string;
		spawned_by?: string;
		skills?: string[];
		tools?: Record<string, number>;
	};
}

export interface GraphEdge {
	data: {
		id: string;
		source: string;
		target: string;
		prompt?: string;
	};
}

export interface SessionGraph {
	nodes: GraphNode[];
	edges: GraphEdge[];
}

export interface TimelineAgent {
	agent_id: string;
	agent_type: string;
	status: AgentStatus;
	start_time: number;
	end_time?: number;
	depth: number;
	tool_calls: TimelineToolCall[];
	prompt?: string;
}

export interface TimelineToolCall {
	tool_name: string;
	timestamp: number;
	duration?: number;
	success: boolean;
	input_summary?: string;
}

export interface QueryResult {
	cypher?: string;
	explanation?: string;
	columns: string[];
	rows: Record<string, unknown>[];
	is_graph?: boolean;
	graph?: SessionGraph;
}

export type MessageRole = 'user' | 'assistant' | 'system';

export interface AgentMessage {
	message_id: string;
	session_id: string;
	agent_id: string;
	role: MessageRole;
	content: string;
	sequence: number;
	timestamp: string;
}

export interface ToolStats {
	tool_name: string;
	call_count: number;
	success_count: number;
	fail_count: number;
	p50_ms: number;
	p95_ms: number;
}
