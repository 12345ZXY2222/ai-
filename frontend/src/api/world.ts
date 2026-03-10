import client from './client';

export type WorldLayer = 'wall' | 'color';
export type WorldShape = 'cell' | 'cells' | 'rect' | 'line';
export type WorldColorLabel = 'none' | 'neutral' | 'primary' | 'success' | 'warning' | 'error' | 'info';

export interface WorldAgentPlacement {
  agent_id: string;
  x: number;
  y: number;
}

export type WorldPOIKind = 'custom' | 'cafeteria' | 'dorm' | 'classroom' | 'library' | 'office' | 'sports';

export type WorldPOIShape = 'point' | 'rect' | 'cells';

export interface WorldPOI {
  id: string;
  name: string;
  kind: WorldPOIKind;
  label: WorldColorLabel | null;
  shape?: WorldPOIShape;
  x: number;
  y: number;
  w?: number | null;
  h?: number | null;
  cells?: Array<{ x: number; y: number }> | null;
  description?: string | null;
}

export type WorldIdentityKind = 'student' | 'teacher' | 'custom';

export interface WorldIdentityScheduleItem {
  start_hour: number;
  end_hour: number;
  activity: string;
  poi_kinds: WorldPOIKind[];
}

export interface WorldIdentity {
  id: string;
  name: string;
  kind: WorldIdentityKind;
  description?: string | null;
  schedule: WorldIdentityScheduleItem[];
}

export interface WorldIdentitiesResponse {
  identities: WorldIdentity[];
}

export interface WorldIdentityCreateRequest {
  name: string;
  kind: WorldIdentityKind;
  description?: string | null;
  schedule?: WorldIdentityScheduleItem[];
}

export interface WorldIdentityUpdateRequest {
  name?: string;
  kind?: WorldIdentityKind;
  description?: string | null;
  schedule?: WorldIdentityScheduleItem[] | null;
}

export interface SetWorldAgentIdentityRequest {
  agent_id: string;
  identity_id: string;
}

export interface World {
  id: string;
  name: string;
  width: number;
  height: number;
  walls_count: number;
  colors_count: number;
  agent_placements: WorldAgentPlacement[];
  pois?: WorldPOI[];
  identities?: WorldIdentity[];
  agent_identities?: Record<string, string>;
}

export interface WorldViewResponse {
  x: number;
  y: number;
  width: number;
  height: number;
  walls: boolean[][];
  colors: Array<Array<WorldColorLabel | null>>;
  agent_placements: WorldAgentPlacement[];
}

export interface WorldDrawOp {
  layer: WorldLayer;
  shape: WorldShape;
  x?: number;
  y?: number;
  x2?: number;
  y2?: number;
  cells?: Array<{ x: number; y: number }>;
  wall?: boolean;
  color?: WorldColorLabel;
}

export interface WorldDrawRequest {
  ops: WorldDrawOp[];
  view_x?: number;
  view_y?: number;
  view_w?: number;
  view_h?: number;
}

export interface WorldAIDrawRequest {
  prompt: string;
  x: number;
  y: number;
  w: number;
  h: number;
  max_ops?: number;
}

export interface WorldAIDrawResponse {
  ops: WorldDrawOp[];
  view: WorldViewResponse;
}

export interface WorldAIScriptRequest {
  prompt: string;
  x: number;
  y: number;
  w: number;
  h: number;
  max_commands?: number;
  max_cells?: number;
}

export interface WorldAIScriptResponse {
  commands: any[];
  view: WorldViewResponse;
}

export type WorldAIGenerateMode = 'auto' | 'script' | 'ops';

export interface WorldAIGenerateRequest {
  prompt: string;
  x: number;
  y: number;
  w: number;
  h: number;
  mode?: WorldAIGenerateMode;
  max_commands?: number;
  max_cells?: number;
  max_ops?: number;
}

export interface WorldAIGenerateResponse {
  mode: WorldAIGenerateMode;
  commands: any[];
  ops: WorldDrawOp[];
  view: WorldViewResponse;
}

export interface WorldAIImageRequest {
  prompt: string;
  x: number;
  y: number;
  w: number;
  h: number;
  agent_id?: string | null;
}

export interface WorldAIImageResponse {
  agent_id: string;
  image_url: string;
  ops: WorldDrawOp[];
  view: WorldViewResponse;
}

export interface WorldEncounterDialogueRequest {
  agent_a_id: string;
  agent_b_id: string;
  topic?: string | null;
  max_turns?: number;
}

export interface WorldEncounterDialogueResponse {
  turns: Array<{ agent_id: string; text: string }>;
}

export interface PickPOIPathRequest {
  agent_id: string;
  labels?: WorldColorLabel[];
  strategy?: 'nearest' | 'random';
  max_seed_cells?: number;
  max_attempts?: number;
  max_radius?: number;
}

export interface PickPOIPathResponse {
  label: WorldColorLabel | null;
  poi: { x: number; y: number } | null;
  target: { x: number; y: number };
  path: Array<{ x: number; y: number }>;
}

export interface CreateWorldRequest {
  name: string;
  width: number;
  height: number;
  preset?: string | null;
}

export interface UpdateWorldRequest {
  name?: string;
  agent_placements?: WorldAgentPlacement[];
  pois?: WorldPOI[];
  identities?: WorldIdentity[];
  agent_identities?: Record<string, string>;
}

export interface WorldPOICreateRequest {
  name: string;
  kind?: WorldPOIKind;
  label?: WorldColorLabel | null;
  shape?: WorldPOIShape;
  x: number;
  y: number;
  w?: number | null;
  h?: number | null;
  cells?: Array<{ x: number; y: number }> | null;
  description?: string | null;
}

export interface WorldPOIUpdateRequest {
  name?: string;
  kind?: WorldPOIKind;
  label?: WorldColorLabel | null;
  shape?: WorldPOIShape;
  x?: number;
  y?: number;
  w?: number | null;
  h?: number | null;
  cells?: Array<{ x: number; y: number }> | null;
  description?: string | null;
}

export interface WorldPOIsResponse {
  pois: WorldPOI[];
}

export interface PlanPathToPOIRequest {
  agent_id: string;
  poi_id: string;
  max_radius?: number;
}

export interface PlanPathToPOIResponse {
  poi: WorldPOI;
  target: { x: number; y: number };
  path: Array<{ x: number; y: number }>;
}

export const listWorlds = async (): Promise<World[]> => {
  const res = await client.get<World[]>('/worlds');
  return res.data;
};

export const createWorld = async (payload: CreateWorldRequest): Promise<World> => {
  const res = await client.post<World>('/worlds', payload);
  return res.data;
};

export const getWorld = async (worldId: string): Promise<World> => {
  const res = await client.get<World>(`/worlds/${worldId}`);
  return res.data;
};

export const updateWorld = async (worldId: string, payload: UpdateWorldRequest): Promise<World> => {
  const res = await client.put<World>(`/worlds/${worldId}`, payload);
  return res.data;
};

export const listWorldPOIs = async (worldId: string): Promise<WorldPOI[]> => {
  const res = await client.get<WorldPOIsResponse>(`/worlds/${worldId}/pois`);
  return res.data.pois;
};

export const createWorldPOI = async (worldId: string, payload: WorldPOICreateRequest): Promise<WorldPOI> => {
  const res = await client.post<WorldPOI>(`/worlds/${worldId}/pois`, payload);
  return res.data;
};

export const updateWorldPOI = async (worldId: string, poiId: string, payload: WorldPOIUpdateRequest): Promise<WorldPOI> => {
  const res = await client.put<WorldPOI>(`/worlds/${worldId}/pois/${poiId}`, payload);
  return res.data;
};

export const deleteWorldPOI = async (worldId: string, poiId: string) => {
  await client.delete(`/worlds/${worldId}/pois/${poiId}`);
};

export const planPathToPOI = async (worldId: string, payload: PlanPathToPOIRequest): Promise<PlanPathToPOIResponse> => {
  const res = await client.post<PlanPathToPOIResponse>(`/worlds/${worldId}/plan_path_to_poi`, payload);
  return res.data;
};

export const deleteWorld = async (worldId: string) => {
  await client.delete(`/worlds/${worldId}`);
};

export const getWorldAscii = async (worldId: string): Promise<string> => {
  const res = await client.get<{ ascii: string }>(`/worlds/${worldId}/ascii`);
  return res.data.ascii;
};

export const placeAgentInWorld = async (worldId: string, agentId: string, x: number, y: number): Promise<World> => {
  const res = await client.post<World>(`/worlds/${worldId}/agents/place`, { agent_id: agentId, x, y });
  return res.data;
};

export const moveAgentInWorld = async (worldId: string, agentId: string, toX: number, toY: number): Promise<World> => {
  const res = await client.post<World>(`/worlds/${worldId}/agents/move`, { agent_id: agentId, to_x: toX, to_y: toY });
  return res.data;
};

export const planPath = async (worldId: string, agentId: string, targetX: number, targetY: number): Promise<Array<{ x: number; y: number }>> => {
  const res = await client.post<{ path: Array<{ x: number; y: number }> }>(`/worlds/${worldId}/plan_path`, {
    agent_id: agentId,
    target_x: targetX,
    target_y: targetY,
  });
  return res.data.path;
};

export const pickPOIPath = async (worldId: string, payload: PickPOIPathRequest): Promise<PickPOIPathResponse> => {
  const res = await client.post<PickPOIPathResponse>(`/worlds/${worldId}/pick_poi_path`, payload);
  return res.data;
};

export const getWorldView = async (worldId: string, x: number, y: number, w: number, h: number): Promise<WorldViewResponse> => {
  const res = await client.get<WorldViewResponse>(`/worlds/${worldId}/view`, { params: { x, y, w, h } });
  return res.data;
};

export const drawWorld = async (worldId: string, payload: WorldDrawRequest): Promise<WorldViewResponse> => {
  const res = await client.post<WorldViewResponse>(`/worlds/${worldId}/draw`, payload);
  return res.data;
};

export const aiDrawWorld = async (worldId: string, payload: WorldAIDrawRequest): Promise<WorldAIDrawResponse> => {
  const res = await client.post<WorldAIDrawResponse>(`/worlds/${worldId}/ai_draw`, payload);
  return res.data;
};

export const aiScriptWorld = async (worldId: string, payload: WorldAIScriptRequest): Promise<WorldAIScriptResponse> => {
  const res = await client.post<WorldAIScriptResponse>(`/worlds/${worldId}/ai_script`, payload);
  return res.data;
};

export const aiGenerateWorld = async (worldId: string, payload: WorldAIGenerateRequest): Promise<WorldAIGenerateResponse> => {
  const res = await client.post<WorldAIGenerateResponse>(`/worlds/${worldId}/ai_generate`, payload);
  return res.data;
};

export const aiImageWorld = async (worldId: string, payload: WorldAIImageRequest): Promise<WorldAIImageResponse> => {
  const res = await client.post<WorldAIImageResponse>(`/worlds/${worldId}/ai_image`, payload);
  return res.data;
};

export const worldEncounterDialogue = async (worldId: string, payload: WorldEncounterDialogueRequest): Promise<WorldEncounterDialogueResponse> => {
  const res = await client.post<WorldEncounterDialogueResponse>(`/worlds/${worldId}/encounter_dialogue`, payload);
  return res.data;
};

export const listWorldIdentities = async (worldId: string): Promise<WorldIdentity[]> => {
  const res = await client.get<WorldIdentitiesResponse>(`/worlds/${worldId}/identities`);
  return res.data.identities;
};

export const createWorldIdentity = async (worldId: string, payload: WorldIdentityCreateRequest): Promise<WorldIdentity> => {
  const res = await client.post<WorldIdentity>(`/worlds/${worldId}/identities`, payload);
  return res.data;
};

export const updateWorldIdentity = async (worldId: string, identityId: string, payload: WorldIdentityUpdateRequest): Promise<WorldIdentity> => {
  const res = await client.put<WorldIdentity>(`/worlds/${worldId}/identities/${identityId}`, payload);
  return res.data;
};

export const deleteWorldIdentity = async (worldId: string, identityId: string) => {
  await client.delete(`/worlds/${worldId}/identities/${identityId}`);
};

export const setWorldAgentIdentity = async (worldId: string, payload: SetWorldAgentIdentityRequest) => {
  const res = await client.post(`/worlds/${worldId}/agent_identity`, payload);
  return res.data as { message?: string; agent_id?: string; identity_id?: string };
};
