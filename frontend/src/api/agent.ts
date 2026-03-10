import client from './client';

export interface Agent {
  id: string;
  name: string;
  provider: string;
  model: string;
  base_url?: string;
  usage_example?: string; // In list view this might be empty or full
  custom_code?: string;
  persona?: string;
  long_term_memory?: string[];
  relationships?: string[];
  files?: string[];
}

export interface Relationship {
  id: string;
  source_agent_id: string;
  target_agent_id: string;
  relationship_type: string;
}

export interface SimulationStep {
    id: string;
    type: 'agent' | 'code' | 'loop' | 'dialogue';
    agent_ids?: string[];
    agent_id?: string; // Deprecated
    prompt_template?: string;
    code_snippet?: string;
    output_var?: string;
    output_format?: 'raw' | 'text' | 'image' | 'video';
    execution_mode?: 'serial' | 'parallel';
    use_rag?: boolean;
    loop_condition?: string;
    inner_steps?: SimulationStep[];
    repeat_count?: number | string;
    files?: string[]; // List of filenames attached to this step

    // Dialogue step configuration
    dialogue_max_turns?: number;
    dialogue_auto_partner?: boolean;
    dialogue_partner_id?: string;
    dialogue_end_marker?: string;
}

export interface SimulationHistoryItem {
    step_id: string;
    agent_name: string;
    content: string;
    prompt?: string;
    files?: string[];
    world_state?: any;
}

export interface Simulation {
    id?: string;
    name: string;
    description?: string;
    steps: SimulationStep[];
    variables: { key: string; value: string; description: string }[];
}

export interface SimulationRun {
    id?: string;
    simulation_id?: string;
    timestamp?: number;
    history: SimulationHistoryItem[];
    final_world_state: any;
}

export interface SimulationRepairResponse {
    fixed_simulation: Simulation;
    explanation: string;
}

export const uploadAgentFile = async (agentId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await client.post(`/agents/${agentId}/upload`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    });
    return response.data;
};

export const uploadTempFile = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await client.post<{filename: string, message: string}>(`/simulations/upload_temp`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    });
    return response.data;
};

export const getAgents = async (): Promise<Agent[]> => {
  const response = await client.get<Agent[]>(`/agents`);
  return response.data;
};

export const getAgent = async (id: string) => {
    const response = await client.get<Agent>(`/agents/${id}`);
    return response.data;
}

export const updateAgentMemory = async (id: string, memory: string[]) => {
    await client.put(`/agents/${id}/memory`, memory);
}

export const deleteAgentHistoryBatch = async (id: string, indices: number[]) => {
    await client.post(`/agents/${id}/history/delete_batch`, indices);
}

export const getAgentHistory = async (id: string) => {
    const response = await client.get<any[]>(`/agents/${id}/history`);
    return response.data;
}

export const clearAgentHistory = async (id: string) => {
    await client.delete(`/agents/${id}/history`);
}

export const injectMemory = async (id: string, content: string, importance: number) => {
    const response = await client.post<{status: string, message: string}>(`/agents/${id}/memory/inject`, { content, importance });
    return response.data;
}

export const createAgent = async (agent: Omit<Agent, 'id'>) => {
  const response = await client.post<Agent>(`/agents`, agent);
  return response.data;
};

export const updateAgent = async (id: string, agent: Partial<Agent>) => {
    const response = await client.put<Agent>(`/agents/${id}`, agent);
    return response.data;
};

export const deleteAgent = async (id: string) => {
    await client.delete(`/agents/${id}`);
};

export const duplicateAgent = async (id: string) => {
    const response = await client.post<Agent>(`/agents/${id}/duplicate`);
    return response.data;
};

export const runSimulationStep = async (steps: SimulationStep[], current_step_index: number, history: SimulationHistoryItem[], world_state: any) => {
    const response = await client.post<{content: string, new_history_items: SimulationHistoryItem[], updated_world_state: any}>(`/simulation/run_step`, {
        steps,
        current_step_index,
        history,
        world_state
    });
    return response.data;
}

export const getRelationships = async () => {
  const response = await client.get<Relationship[]>(`/relationships`);
  return response.data;
};

export const createRelationship = async (rel: Omit<Relationship, 'id'>) => {
  const response = await client.post<Relationship>(`/relationships`, rel);
  return response.data;
};

export const deleteRelationship = async (id: string) => {
  await client.delete(`/relationships/${id}`);
};

export const generateAdapter = async (model_name: string, base_url: string, usage_example: string, api_key?: string, input_modality: string = 'text', output_modality: string = 'text') => {
  const response = await client.post<{ generated_code: string; explanation: string }>(`/generate-adapter`, {
    model_name,
    base_url,
        api_key,
    usage_example,
    input_modality,
    output_modality
  });
  return response.data;
};

export const chatWithAgent = async (agentId: string, messages: any[]) => {
    const response = await client.post(`/chat`, {
        agent_id: agentId,
        messages
    });
    return response.data;
}

export const getSimulations = async () => {
    const response = await client.get<Simulation[]>(`/simulations`);
    return response.data;
};

export const createSimulation = async (sim: Simulation) => {
    const response = await client.post<Simulation>(`/simulations`, sim);
    return response.data;
};

export const updateSimulation = async (id: string, sim: Simulation) => {
    const response = await client.put<Simulation>(`/simulations/${id}`, sim);
    return response.data;
};

export const deleteSimulation = async (id: string) => {
    await client.delete(`/simulations/${id}`);
};

export const saveSimulationRun = async (run: SimulationRun) => {
    const response = await client.post<SimulationRun>(`/simulation/runs`, run);
    return response.data;
};

export const getSimulationRuns = async () => {
    const response = await client.get<SimulationRun[]>(`/simulation/runs`);
    return response.data;
};

export const generateSimulation = async (prompt: string, fileContent?: string, fileNames?: string[]) => {
    const response = await client.post<Simulation>(`/simulations/generate`, {
        prompt,
        file_content: fileContent,
        file_names: fileNames
    }, {
        timeout: 600000 // 10 minutes timeout for complex generations
    });
    return response.data;
};

export const fixCodeStep = async (code: string, error: string) => {
    const response = await client.post<{ fixed_code: string; explanation: string }>(`/code/fix`, {
        code,
        error
    });
    return response.data.fixed_code;
};

    export const repairSimulation = async (
        simulation: Simulation,
        current_step_index: number,
        error_message: string,
        history: SimulationHistoryItem[],
        world_state: any
    ) => {
        const response = await client.post<SimulationRepairResponse>(`/simulations/repair`, {
            simulation,
            current_step_index,
            error_message,
            history,
            world_state,
        }, {
            timeout: 600000,
        });
        return response.data;
    };
