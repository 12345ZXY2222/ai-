import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { message } from 'antd';
import { runSimulationStep, repairSimulation, type SimulationStep, type SimulationHistoryItem } from '../api/agent';

interface WorldVariable {
    key: string;
    value: string;
    description: string;
}

interface SimulationContextType {
    // State
    steps: SimulationStep[];
    setSteps: (steps: SimulationStep[]) => void;
    variables: WorldVariable[];
    setVariables: (vars: WorldVariable[]) => void;
    history: SimulationHistoryItem[];
    setHistory: (history: SimulationHistoryItem[] | ((prev: SimulationHistoryItem[]) => SimulationHistoryItem[])) => void;
    worldState: any;
    setWorldState: (state: any) => void;
    execStack: { steps: SimulationStep[], index: number }[];
    setExecStack: (stack: { steps: SimulationStep[], index: number }[] | ((prev: { steps: SimulationStep[], index: number }[]) => { steps: SimulationStep[], index: number }[])) => void;
    isRunning: boolean;
    setIsRunning: (isRunning: boolean) => void;
    isAutoRunning: boolean;
    setIsAutoRunning: (isAuto: boolean) => void;
    autoRepairEnabled: boolean;
    setAutoRepairEnabled: (enabled: boolean) => void;
    simName: string;
    setSimName: (name: string) => void;
    currentSimId: string | null;
    setCurrentSimId: (id: string | null) => void;
    
    // Actions
    runNextStep: () => Promise<void>;
    resetSimulation: (newSteps?: SimulationStep[], newVariables?: WorldVariable[]) => void;
}

const SimulationContext = createContext<SimulationContextType | undefined>(undefined);

export const SimulationProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [steps, setSteps] = useState<SimulationStep[]>([]);
    const [variables, setVariables] = useState<WorldVariable[]>([]);
    const [history, setHistory] = useState<SimulationHistoryItem[]>([]);
    const [worldState, setWorldState] = useState<any>({});
    const [execStack, setExecStack] = useState<{ steps: SimulationStep[], index: number }[]>([]);
    const [isRunning, setIsRunning] = useState(false);
    const [isAutoRunning, setIsAutoRunning] = useState(false);
    const [autoRepairEnabled, setAutoRepairEnabled] = useState(true);
    const [simName, setSimName] = useState('New Simulation');
    const [currentSimId, setCurrentSimId] = useState<string | null>(null);
    const [isLoaded, setIsLoaded] = useState(false);

    // --- Persistence Logic ---
    useEffect(() => {
        const savedState = localStorage.getItem('simulation_run_state');
        if (savedState) {
            try {
                const parsed = JSON.parse(savedState);
                if (parsed.history) setHistory(parsed.history);
                if (parsed.worldState) setWorldState(parsed.worldState);
                if (parsed.execStack) setExecStack(parsed.execStack);
                if (parsed.currentSimId) setCurrentSimId(parsed.currentSimId);
                if (parsed.steps) setSteps(parsed.steps);
                if (parsed.variables) setVariables(parsed.variables);
                if (parsed.simName) setSimName(parsed.simName);
            } catch (e) {
                console.error("Failed to restore simulation state", e);
            }
        }
        setIsLoaded(true);
    }, []);

    useEffect(() => {
        if (!isLoaded) return;
        const runState = { history, worldState, execStack, currentSimId, steps, variables, simName };
        localStorage.setItem('simulation_run_state', JSON.stringify(runState));
    }, [history, worldState, execStack, currentSimId, steps, variables, simName, isLoaded]);
    // -------------------------

    // --- Auto-Run Logic ---
    useEffect(() => {
        if (isAutoRunning && !isRunning) {
            if (execStack.length > 0) {
                const timer = setTimeout(() => {
                    runNextStep();
                }, 500);
                return () => clearTimeout(timer);
            } else {
                setIsAutoRunning(false);
                if (history.length > 0) { // Only show if we actually ran something
                    message.success("Simulation finished");
                }
            }
        }
    }, [isAutoRunning, isRunning, execStack]);
    // ----------------------

    const resetSimulation = (newSteps?: SimulationStep[], newVariables?: WorldVariable[]) => {
        setIsAutoRunning(false);
        setHistory([]);
        const initialState: any = {};
        const varsToUse = newVariables || variables;
        varsToUse.forEach(v => {
            try {
                initialState[v.key] = JSON.parse(v.value);
            } catch {
                initialState[v.key] = v.value;
            }
        });
        setWorldState(initialState);
        setExecStack([{ steps: newSteps || steps, index: 0 }]);
    };

    const runNextStep = async () => {
        if (execStack.length === 0) {
            message.info("Simulation finished.");
            return;
        }

        setIsRunning(true);
        try {
            let stack = [...execStack];
            let currentFrame = stack[stack.length - 1];
            let currentState = worldState; // Use current state
            const rootIndex = stack.length > 0 ? stack[0].index : 0;

            const tryAutoRepair = async (errorMessage: string) => {
                if (!autoRepairEnabled) return false;
                try {
                    const repaired = await repairSimulation(
                        {
                            name: simName,
                            steps,
                            variables,
                        },
                        rootIndex,
                        errorMessage,
                        history,
                        currentState,
                    );

                    const fixed = repaired?.fixed_simulation;
                    if (fixed && Array.isArray(fixed.steps) && fixed.steps.length > 0) {
                        setSteps(fixed.steps as SimulationStep[]);
                        const fixedVars = Array.isArray((fixed as any).variables) ? (fixed as any).variables : variables;
                        setVariables(fixedVars);
                        setExecStack([{ steps: fixed.steps as SimulationStep[], index: Math.min(rootIndex, fixed.steps.length) }]);
                        message.success(`Auto repair applied: ${repaired.explanation || 'simulation fixed'}`);
                        return true;
                    }
                } catch (repairErr) {
                    console.error('Auto repair failed', repairErr);
                }
                return false;
            };

            // Check if frame finished
            if (currentFrame.index >= currentFrame.steps.length) {
                stack.pop();
                if (stack.length === 0) {
                    setExecStack([]);
                    message.success("Simulation Complete");
                    setIsRunning(false);
                    return;
                }
                setExecStack(stack);
                setIsRunning(false);
                return;
            }

            const step = currentFrame.steps[currentFrame.index];

            // Resolve Repeat Count
            let repeatCount = 1;
            if (step.repeat_count !== undefined) {
                if (typeof step.repeat_count === 'number') {
                    repeatCount = step.repeat_count;
                } else if (typeof step.repeat_count === 'string') {
                    let valStr = step.repeat_count;
                    if (valStr.startsWith('{{state.') && valStr.endsWith('}}')) {
                        const key = valStr.slice(8, -2);
                        if (currentState[key] !== undefined) {
                            repeatCount = parseInt(currentState[key]);
                        }
                    } else {
                        repeatCount = parseInt(valStr);
                    }
                }
            }
            if (isNaN(repeatCount) || repeatCount < 0) repeatCount = 1;

            if (repeatCount === 0) {
                currentFrame.index++;
                setExecStack(stack);
                setIsRunning(false);
                return;
            }

            if (repeatCount > 1) {
                const repeatedSteps = Array(repeatCount).fill(null).map(() => ({
                    ...step,
                    repeat_count: 1
                }));
                currentFrame.index++;
                stack.push({ steps: repeatedSteps, index: 0 });
                setExecStack(stack);
                setIsRunning(false);
                return;
            }

            if (step.type === 'loop') {
                let isTrue = true;
                if (step.loop_condition && step.loop_condition.trim() !== '') {
                    const conditionCode = `state['__loop_result'] = ${step.loop_condition}`;
                    const res = await runSimulationStep([{
                        id: 'temp-eval',
                        type: 'code',
                        code_snippet: conditionCode
                    }], 0, [], currentState);
                    
                    const evalLog = res.new_history_items[0]?.content || "";
                    if (evalLog.startsWith("Error")) {
                        const repaired = await tryAutoRepair(`Loop condition error: ${evalLog}`);
                        if (!repaired) {
                            message.error(`Loop condition error: ${evalLog}`);
                        }
                        setIsRunning(false);
                        return;
                    }
                    isTrue = res.updated_world_state['__loop_result'];
                    if (res.updated_world_state.hasOwnProperty('__loop_result')) {
                        delete res.updated_world_state['__loop_result'];
                    }
                    setWorldState(res.updated_world_state);
                    currentState = res.updated_world_state; 
                }

                if (isTrue) {
                    message.success("Loop condition TRUE: Entering loop");
                    stack.push({ steps: step.inner_steps || [], index: 0 });
                    setExecStack(stack);
                } else {
                    message.info("Loop condition FALSE: Skipping loop");
                    currentFrame.index++;
                    setExecStack(stack);
                }
                setIsRunning(false);
                return;
            }

            // Normal Step
            const res = await runSimulationStep([step], 0, history, currentState);

            const stepErrorText = (res.new_history_items || [])
                .map(item => item?.content || '')
                .find(content => typeof content === 'string' && (content.startsWith('Error') || content.includes('Error executing code')));

            if (stepErrorText) {
                const repaired = await tryAutoRepair(stepErrorText);
                if (!repaired) {
                    message.error(stepErrorText);
                }
                setIsRunning(false);
                return;
            }
            
            setHistory(prev => [...prev, ...res.new_history_items]);
            setWorldState(res.updated_world_state);
            
            currentFrame.index++;
            setExecStack(stack);

        } catch (e) {
            console.error(e);
            const detail = (e as any)?.response?.data?.detail || (e as any)?.message || "Step execution failed";
            if (autoRepairEnabled) {
                try {
                    const repaired = await repairSimulation(
                        {
                            name: simName,
                            steps,
                            variables,
                        },
                        execStack.length > 0 ? execStack[0].index : 0,
                        detail,
                        history,
                        worldState,
                    );
                    const fixed = repaired?.fixed_simulation;
                    if (fixed && Array.isArray(fixed.steps) && fixed.steps.length > 0) {
                        setSteps(fixed.steps as SimulationStep[]);
                        const fixedVars = Array.isArray((fixed as any).variables) ? (fixed as any).variables : variables;
                        setVariables(fixedVars);
                        setExecStack([{ steps: fixed.steps as SimulationStep[], index: Math.min(execStack.length > 0 ? execStack[0].index : 0, fixed.steps.length) }]);
                        message.success(`Auto repair applied: ${repaired.explanation || 'simulation fixed'}`);
                        return;
                    }
                } catch (repairErr) {
                    console.error('Auto repair failed after exception', repairErr);
                }
            }
            message.error(`Step execution failed: ${detail}`);
        } finally {
            setIsRunning(false);
        }
    };

    return (
        <SimulationContext.Provider value={{
            steps, setSteps,
            variables, setVariables,
            history, setHistory,
            worldState, setWorldState,
            execStack, setExecStack,
            isRunning, setIsRunning,
            isAutoRunning, setIsAutoRunning,
            autoRepairEnabled, setAutoRepairEnabled,
            simName, setSimName,
            currentSimId, setCurrentSimId,
            runNextStep,
            resetSimulation
        }}>
            {children}
        </SimulationContext.Provider>
    );
};

export const useSimulation = () => {
    const context = useContext(SimulationContext);
    if (context === undefined) {
        throw new Error('useSimulation must be used within a SimulationProvider');
    }
    return context;
};
