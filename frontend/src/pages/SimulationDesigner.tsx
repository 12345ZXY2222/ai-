import React, { useState, useEffect, useRef } from 'react';
import { Card, Button, Select, Input, Typography, Space, message, Radio, Collapse, Table, Tag, Tooltip, Modal, List, Drawer, Switch } from 'antd';
import { UploadOutlined, PlusOutlined, PlayCircleOutlined, ReloadOutlined, CodeOutlined, UserOutlined, DeleteOutlined, RetweetOutlined, CopyOutlined, SaveOutlined, FolderOpenOutlined, FastForwardOutlined, PauseCircleOutlined, DownOutlined, RightOutlined, InfoCircleOutlined, RobotOutlined, BugOutlined, HistoryOutlined, FileAddOutlined, MessageOutlined } from '@ant-design/icons';
import { Upload } from 'antd';
import type { UploadFile } from 'antd/es/upload/interface';
import { getAgents, createSimulation, updateSimulation, getSimulations, deleteSimulation, saveSimulationRun, generateSimulation, fixCodeStep, uploadTempFile, injectMemory } from '../api/agent';
import type { Agent, Simulation, SimulationRun, SimulationStep } from '../api/agent';
import { useSimulation } from '../context/SimulationContext';


const { TextArea } = Input;
const { Option } = Select;
const { Title, Text } = Typography;
const { Panel } = Collapse;

interface WorldVariable {
    key: string;
    value: string;
    description: string;
}

// --- Components ---

const VariableManager: React.FC<{
    variables: WorldVariable[];
    onChange: (vars: WorldVariable[]) => void;
}> = ({ variables, onChange }) => {
    const columns = [
        { title: 'Key', dataIndex: 'key', render: (text: string, _: any, i: number) => <Input value={text} onChange={e => updateVar(i, 'key', e.target.value)} placeholder="e.g. inventory" /> },
        { title: 'Initial Value', dataIndex: 'value', render: (text: string, _: any, i: number) => <Input value={text} onChange={e => updateVar(i, 'value', e.target.value)} placeholder="e.g. 100" /> },
        { title: 'Description', dataIndex: 'description', render: (text: string, _: any, i: number) => <Input value={text} onChange={e => updateVar(i, 'description', e.target.value)} placeholder="What is this?" /> },
        { title: 'Action', render: (_: any, __: any, i: number) => <Button danger icon={<DeleteOutlined />} onClick={() => removeVar(i)} /> }
    ];

    const updateVar = (index: number, field: keyof WorldVariable, val: string) => {
        const newVars = [...variables];
        newVars[index][field] = val;
        onChange(newVars);
    };

    const addVar = () => {
        onChange([...variables, { key: '', value: '', description: '' }]);
    };

    const removeVar = (index: number) => {
        const newVars = [...variables];
        newVars.splice(index, 1);
        onChange(newVars);
    };

    return (
        <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                <Text strong>System Variables</Text>
                <Button size="small" icon={<PlusOutlined />} onClick={addVar}>Add Variable</Button>
            </div>
            <Table dataSource={variables} columns={columns} pagination={false} size="small" rowKey={(_, i) => i?.toString() || ''} />
        </div>
    );
};

const StepEditor: React.FC<{
    step: SimulationStep;
    index: number;
    agents: Agent[];
    variables: WorldVariable[];
    onChange: (updatedStep: SimulationStep) => void;
    onRemove: () => void;
    onDuplicate: () => void;
}> = ({ step, index, agents, variables, onChange, onRemove, onDuplicate }) => {
    const [isFixing, setIsFixing] = useState(false);
    const [fixError, setFixError] = useState('');
    const [isFixModalOpen, setIsFixModalOpen] = useState(false);
    const [isVarsOpen, setIsVarsOpen] = useState(false);
    const textAreaRef = useRef<any>(null);

    const updateField = (field: keyof SimulationStep, value: any) => {
        onChange({ ...step, [field]: value });
    };

    const updateType = (newType: SimulationStep['type']) => {
        // Set sensible defaults when switching types
        if (newType === 'dialogue') {
            onChange({
                ...step,
                type: 'dialogue',
                agent_ids: step.agent_ids || [],
                prompt_template: step.prompt_template || '',
                dialogue_auto_partner: step.dialogue_auto_partner ?? true,
                dialogue_max_turns: step.dialogue_max_turns ?? 6,
                dialogue_end_marker: step.dialogue_end_marker || 'END_DIALOGUE'
            });
            return;
        }
        onChange({ ...step, type: newType });
    };

    const handleFixCode = async () => {
        if (!fixError.trim()) {
            message.warning("Please enter the error message");
            return;
        }
        setIsFixing(true);
        try {
            const fixedCode = await fixCodeStep(step.code_snippet || '', fixError);
            updateField('code_snippet', fixedCode);
            message.success("Code fixed successfully!");
            setIsFixModalOpen(false);
            setFixError('');
        } catch (e) {
            message.error("Failed to fix code");
        } finally {
            setIsFixing(false);
        }
    };

    const insertText = (text: string) => {
        const textArea = textAreaRef.current?.resizableTextArea?.textArea;
        if (textArea) {
            const start = textArea.selectionStart;
            const end = textArea.selectionEnd;
            const oldValue = step.prompt_template || '';
            const newValue = oldValue.substring(0, start) + text + oldValue.substring(end);
            updateField('prompt_template', newValue);
            setTimeout(() => {
                textArea.focus();
                textArea.setSelectionRange(start + text.length, start + text.length);
            }, 0);
        } else {
            updateField('prompt_template', (step.prompt_template || '') + text);
        }
    };

    return (
        <Card 
            size="small"
            title={
                <Space>
                    <Tag color={step.type === 'loop' ? 'purple' : step.type === 'code' ? 'blue' : step.type === 'dialogue' ? 'orange' : 'green'}>
                        {step.type.toUpperCase()}
                    </Tag>
                    <span>Step {index + 1}</span>
                </Space>
            }
            extra={
                <Space>
                    <Button type="text" icon={<CopyOutlined />} onClick={onDuplicate} title="Duplicate Step" />
                    <Button danger type="text" icon={<DeleteOutlined />} onClick={onRemove} title="Remove Step" />
                </Space>
            }
            style={{ marginBottom: 10, borderLeft: '4px solid #1890ff' }}
        >
            <Space direction="vertical" style={{ width: '100%' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Radio.Group 
                        value={step.type} 
                        onChange={e => updateType(e.target.value)}
                        optionType="button"
                        buttonStyle="solid"
                        size="small"
                    >
                        <Radio.Button value="agent"><UserOutlined /> Agent</Radio.Button>
                        <Radio.Button value="code"><CodeOutlined /> Code</Radio.Button>
                        <Radio.Button value="loop"><RetweetOutlined /> Loop</Radio.Button>
                        <Radio.Button value="dialogue"><MessageOutlined /> Dialogue</Radio.Button>
                    </Radio.Group>
                    
                    <Input 
                        addonBefore="Repeat" 
                        value={step.repeat_count} 
                        onChange={e => {
                            const val = e.target.value;
                            // Allow empty string (for deleting) or digits
                            if (val === '' || /^\d+$/.test(val)) {
                                updateField('repeat_count', val === '' ? '' : parseInt(val));
                            } else {
                                // Allow variable syntax {{...}}
                                updateField('repeat_count', val);
                            }
                        }}
                        style={{ width: 120 }}
                        size="small"
                    />
                </div>

                {step.type === 'agent' && (
                    <>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                            <Text strong>Select Agents:</Text>
                            <Tooltip title="The step will be executed for each selected agent individually. {{agent.*}} variables will resolve to the specific agent in each execution.">
                                <InfoCircleOutlined style={{ color: '#1890ff', cursor: 'help' }} />
                            </Tooltip>
                        </div>
                        <Select 
                            mode="multiple"
                            value={step.agent_ids || (step.agent_id ? [step.agent_id] : [])} 
                            style={{ width: '100%' }} 
                            onChange={val => updateField('agent_ids', val)}
                            placeholder="Select one or more agents"
                        >
                            {agents.map(a => <Option key={a.id} value={a.id}>{a.name}</Option>)}
                        </Select>
                        
                        <div style={{ marginBottom: 5, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <Text strong>Prompt Template:</Text>
                            <Button 
                                type="link" 
                                size="small" 
                                onClick={() => setIsVarsOpen(!isVarsOpen)}
                                icon={isVarsOpen ? <DownOutlined /> : <RightOutlined />}
                            >
                                {isVarsOpen ? 'Hide Variables' : 'Insert Variables'}
                            </Button>
                        </div>
                        
                        {isVarsOpen && (
                            <div style={{ marginBottom: 8, padding: '8px', background: '#f5f5f5', borderRadius: '4px', border: '1px solid #d9d9d9' }}>
                                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', alignItems: 'center' }}>
                                        <Text type="secondary" style={{ fontSize: '12px', marginRight: 4 }}>World:</Text>
                                        {variables.map(v => (
                                            <Tooltip key={v.key} title={v.description}>
                                                <Tag color="blue" style={{ cursor: 'pointer' }} onClick={() => insertText(`{{state.${v.key}}}`)}>{v.key}</Tag>
                                            </Tooltip>
                                        ))}
                                        {variables.length === 0 && <Text type="secondary" style={{ fontSize: '11px' }}>(No variables)</Text>}
                                    </div>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', alignItems: 'center' }}>
                                        <Text type="secondary" style={{ fontSize: '12px', marginRight: 4 }}>Current Agent:</Text>
                                        <Tooltip title="Name of the agent currently executing this step">
                                            <Tag color="cyan" style={{ cursor: 'pointer' }} onClick={() => insertText('{{agent.name}}')}>Name</Tag>
                                        </Tooltip>
                                        <Tooltip title="Persona of the agent currently executing this step">
                                            <Tag color="cyan" style={{ cursor: 'pointer' }} onClick={() => insertText('{{agent.persona}}')}>Persona</Tag>
                                        </Tooltip>
                                        <Tooltip title="Model of the agent currently executing this step">
                                            <Tag color="cyan" style={{ cursor: 'pointer' }} onClick={() => insertText('{{agent.model}}')}>Model</Tag>
                                        </Tooltip>
                                    </div>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', alignItems: 'center' }}>
                                        <Text type="secondary" style={{ fontSize: '12px', marginRight: 4 }}>Context:</Text>
                                        <Tag color="purple" style={{ cursor: 'pointer' }} onClick={() => insertText('{{memory}}')}>Memory</Tag>
                                        <Tag color="purple" style={{ cursor: 'pointer' }} onClick={() => insertText('{{history}}')}>History</Tag>
                                        <Tag color="purple" style={{ cursor: 'pointer' }} onClick={() => insertText('{{last_output}}')}>Last Output</Tag>
                                    </div>
                                </Space>
                            </div>
                        )}
                        <TextArea 
                            ref={textAreaRef}
                            rows={3} 
                            value={step.prompt_template} 
                            onChange={e => updateField('prompt_template', e.target.value)} 
                            placeholder="Use {{state.var}} to inject variables."
                        />
                        <div style={{ display: 'flex', gap: '10px' }}>
                            <Input 
                                addonBefore="Output Var" 
                                placeholder="Save result to..." 
                                value={step.output_var} 
                                onChange={e => updateField('output_var', e.target.value)} 
                                style={{ flex: 1 }}
                            />
                            <Select
                                value={step.output_format || 'raw'}
                                onChange={val => updateField('output_format', val)}
                                style={{ width: 120 }}
                                options={[
                                    { label: 'Raw (JSON)', value: 'raw' },
                                    { label: 'Text Only', value: 'text' },
                                    { label: 'Image URL', value: 'image' },
                                    { label: 'Video URL', value: 'video' },
                                    { label: 'Audio URL', value: 'audio' },
                                ]}
                                placeholder="Format"
                            />
                            <Select
                                value={step.execution_mode || 'parallel'}
                                onChange={val => updateField('execution_mode', val)}
                                style={{ width: 120 }}
                                options={[
                                    { label: 'Parallel', value: 'parallel' },
                                    { label: 'Serial', value: 'serial' },
                                ]}
                                placeholder="Exec Mode"
                                title="Execution Mode: Parallel (Simultaneous) or Serial (Sequential)"
                            />
                        </div>

                        <div style={{ marginBottom: 10 }}>
                            <Space>
                                <Text strong>Enable RAG Memory:</Text>
                                <Switch 
                                    checked={step.use_rag !== false} // Default true
                                    onChange={val => updateField('use_rag', val)} 
                                />
                                <Tooltip title="If enabled, the agent will retrieve relevant memories from its long-term storage (including past simulation runs) to answer the prompt.">
                                    <InfoCircleOutlined style={{ color: '#1890ff', cursor: 'help' }} />
                                </Tooltip>
                            </Space>
                        </div>
                        
                        <Text strong>Attach Files (from Agent's uploads):</Text>
                        <Select
                            mode="multiple"
                            value={step.files}
                            style={{ width: '100%' }}
                            onChange={val => updateField('files', val)}
                            placeholder="Select files to attach"
                            disabled={(!step.agent_ids || step.agent_ids.length === 0) && !step.agent_id}
                        >
                            {agents
                                .filter(a => (step.agent_ids && step.agent_ids.includes(a.id)) || (step.agent_id === a.id))
                                .flatMap(a => (a.files || []).map((f: string) => ({ agent: a.name, file: f })))
                                .map(item => (
                                    <Option key={`${item.agent}-${item.file}`} value={item.file}>
                                        {item.file} ({item.agent})
                                    </Option>
                                ))
                            }
                        </Select>
                    </>
                )}

                {step.type === 'dialogue' && (
                    <>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                            <Text strong>Initiator Agent(s):</Text>
                            <Tooltip title="Each selected agent will (optionally) choose another agent to talk to, then they will converse until the end marker appears or max turns is reached.">
                                <InfoCircleOutlined style={{ color: '#1890ff', cursor: 'help' }} />
                            </Tooltip>
                        </div>
                        <Select 
                            mode="multiple"
                            value={step.agent_ids || (step.agent_id ? [step.agent_id] : [])}
                            style={{ width: '100%' }}
                            onChange={val => updateField('agent_ids', val)}
                            placeholder="Select one or more initiator agents"
                        >
                            {agents.map(a => <Option key={a.id} value={a.id}>{a.name}</Option>)}
                        </Select>

                        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginTop: 8 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <Text strong>Max Turns:</Text>
                                <Input
                                    value={step.dialogue_max_turns ?? 6}
                                    onChange={e => {
                                        const val = e.target.value;
                                        if (val === '' || /^\d+$/.test(val)) {
                                            updateField('dialogue_max_turns', val === '' ? 6 : parseInt(val));
                                        }
                                    }}
                                    style={{ width: 120 }}
                                    size="small"
                                />
                            </div>

                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <Text strong>Auto Partner:</Text>
                                <Switch
                                    checked={step.dialogue_auto_partner ?? true}
                                    onChange={(checked) => updateField('dialogue_auto_partner', checked)}
                                />
                            </div>

                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <Text strong>End Marker:</Text>
                                <Input
                                    value={step.dialogue_end_marker || 'END_DIALOGUE'}
                                    onChange={e => updateField('dialogue_end_marker', e.target.value)}
                                    style={{ width: 180 }}
                                    size="small"
                                />
                            </div>
                        </div>

                        {(step.dialogue_auto_partner === false) && (
                            <div style={{ marginTop: 8 }}>
                                <Text strong>Fixed Partner:</Text>
                                <Select
                                    value={step.dialogue_partner_id}
                                    style={{ width: '100%', marginTop: 4 }}
                                    onChange={val => updateField('dialogue_partner_id', val)}
                                    placeholder="Select a fixed partner agent"
                                    allowClear
                                >
                                    {agents.map(a => <Option key={a.id} value={a.id}>{a.name}</Option>)}
                                </Select>
                            </div>
                        )}

                        <div style={{ marginBottom: 5, marginTop: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <Text strong>Start Instruction / Goal:</Text>
                            <Button 
                                type="link" 
                                size="small" 
                                onClick={() => setIsVarsOpen(!isVarsOpen)}
                                icon={isVarsOpen ? <DownOutlined /> : <RightOutlined />}
                            >
                                {isVarsOpen ? 'Hide Variables' : 'Insert Variables'}
                            </Button>
                        </div>

                        {isVarsOpen && (
                            <div style={{ marginBottom: 8, padding: '8px', background: '#f5f5f5', borderRadius: '4px', border: '1px solid #d9d9d9' }}>
                                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', alignItems: 'center' }}>
                                        <Text type="secondary" style={{ fontSize: '12px', marginRight: 4 }}>World:</Text>
                                        {variables.map(v => (
                                            <Tooltip key={v.key} title={v.description}>
                                                <Tag color="blue" style={{ cursor: 'pointer' }} onClick={() => insertText(`{{state.${v.key}}}`)}>{v.key}</Tag>
                                            </Tooltip>
                                        ))}
                                        {variables.length === 0 && <Text type="secondary" style={{ fontSize: '11px' }}>(No variables)</Text>}
                                    </div>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', alignItems: 'center' }}>
                                        <Text type="secondary" style={{ fontSize: '12px', marginRight: 4 }}>Current Agent:</Text>
                                        <Tooltip title="Name of the agent currently speaking">
                                            <Tag color="cyan" style={{ cursor: 'pointer' }} onClick={() => insertText('{{agent.name}}')}>Name</Tag>
                                        </Tooltip>
                                        <Tooltip title="Persona of the agent currently speaking">
                                            <Tag color="cyan" style={{ cursor: 'pointer' }} onClick={() => insertText('{{agent.persona}}')}>Persona</Tag>
                                        </Tooltip>
                                    </div>
                                </Space>
                            </div>
                        )}

                        <TextArea
                            rows={5}
                            value={step.prompt_template}
                            onChange={e => updateField('prompt_template', e.target.value)}
                            placeholder="Example: If you are unsure about the plan, pick a relevant teammate and discuss until you reach a decision. End with END_DIALOGUE when done."
                        />
                    </>
                )}

                {step.type === 'code' && (
                    <>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Text strong>Python Code:</Text>
                            <Button 
                                type="link" 
                                size="small" 
                                icon={<BugOutlined />} 
                                onClick={() => setIsFixModalOpen(true)}
                            >
                                AI Fix
                            </Button>
                        </div>
                        <TextArea 
                            rows={3} 
                            value={step.code_snippet} 
                            onChange={e => updateField('code_snippet', e.target.value)} 
                            style={{ fontFamily: 'monospace' }}
                            placeholder="state['inventory'] -= 1"
                        />
                        <Modal
                            title="AI Code Fixer"
                            open={isFixModalOpen}
                            onCancel={() => setIsFixModalOpen(false)}
                            footer={[
                                <Button key="cancel" onClick={() => setIsFixModalOpen(false)}>Cancel</Button>,
                                <Button key="submit" type="primary" loading={isFixing} onClick={handleFixCode}>Fix Code</Button>
                            ]}
                        >
                            <Text>Paste the error message or describe what's wrong:</Text>
                            <TextArea 
                                rows={4} 
                                value={fixError} 
                                onChange={e => setFixError(e.target.value)} 
                                placeholder="e.g. NameError: name 'inventory' is not defined"
                                style={{ marginTop: 10 }}
                            />
                        </Modal>
                    </>
                )}

                {step.type === 'loop' && (
                    <div style={{ background: '#f9f9f9', padding: 10, borderRadius: 4 }}>
                        <Text strong>Loop Condition (Python):</Text>
                        <Input 
                            value={step.loop_condition} 
                            onChange={e => updateField('loop_condition', e.target.value)} 
                            placeholder="e.g. state['inventory'] > 0 (Empty = Always True)"
                            style={{ fontFamily: 'monospace', marginBottom: 10 }}
                        />
                        <Text strong>Inner Steps:</Text>
                        <StepList 
                            steps={step.inner_steps || []} 
                            onChange={newSteps => updateField('inner_steps', newSteps)} 
                            agents={agents}
                            variables={variables}
                        />
                    </div>
                )}
            </Space>
        </Card>
    );
};

const StepList: React.FC<{
    steps: SimulationStep[];
    onChange: (steps: SimulationStep[]) => void;
    agents: Agent[];
    variables: WorldVariable[];
}> = ({ steps, onChange, agents, variables }) => {
    const addStep = () => {
        const newStep: SimulationStep = {
            id: Date.now().toString() + Math.random(),
            type: 'agent',
            agent_ids: [],
            prompt_template: '',
            inner_steps: [],
            repeat_count: 1
        };
        onChange([...steps, newStep]);
    };

    const updateStep = (index: number, updatedStep: SimulationStep) => {
        const newSteps = [...steps];
        newSteps[index] = updatedStep;
        onChange(newSteps);
    };

    const removeStep = (index: number) => {
        const newSteps = [...steps];
        newSteps.splice(index, 1);
        onChange(newSteps);
    };

    const duplicateStep = (index: number) => {
        const newSteps = [...steps];
        const stepToCopy = { ...newSteps[index], id: Date.now().toString() + Math.random() };
        newSteps.splice(index + 1, 0, stepToCopy);
        onChange(newSteps);
    };

    return (
        <div>
            {steps.map((step, i) => (
                <StepEditor 
                    key={step.id} 
                    step={step} 
                    index={i} 
                    agents={agents} 
                    variables={variables}
                    onChange={s => updateStep(i, s)}
                    onRemove={() => removeStep(i)}
                    onDuplicate={() => duplicateStep(i)}
                />
            ))}
            <Button type="dashed" block icon={<PlusOutlined />} onClick={addStep}>Add Step</Button>
        </div>
    );
};

// Helper to render content (text or multimodal)
const renderContent = (content: string) => {
    if (!content) return <Text type="secondary">(Empty)</Text>;
    
    // 1. Try JSON (for structured multimodal responses)
    try {
        if (content.trim().startsWith('[') || content.trim().startsWith('{')) {
            const parsed = JSON.parse(content);

            if (parsed.type === 'state_change') {
                const changes = parsed.changes || {};
                const stdout = parsed.stdout || "";
                const keys = Object.keys(changes);
                
                return (
                    <div style={{ background: '#f0f5ff', padding: '8px', borderRadius: '4px', border: '1px solid #adc6ff' }}>
                        {stdout && (
                            <div style={{ marginBottom: '10px', borderBottom: '1px solid #d9d9d9', paddingBottom: '5px' }}>
                                <Text strong style={{ color: '#555' }}>Console Output:</Text>
                                <pre style={{ margin: '5px 0', padding: '5px', background: '#333', color: '#fff', borderRadius: '4px', fontSize: '11px', whiteSpace: 'pre-wrap' }}>
                                    {stdout}
                                </pre>
                            </div>
                        )}
                        <Text strong style={{ color: '#1d39c4' }}>Variable Updates:</Text>
                        {keys.length === 0 ? (
                            <div style={{ fontStyle: 'italic', color: '#999' }}>No variables changed.</div>
                        ) : (
                            <ul style={{ margin: '5px 0 0 20px', padding: 0 }}>
                                {keys.map(key => (
                                    <li key={key}>
                                        <Text code>{key}</Text>: 
                                        <Text delete type="secondary" style={{ margin: '0 5px' }}>{JSON.stringify(changes[key].old)}</Text> 
                                        <RightOutlined style={{ fontSize: '10px', color: '#999' }} /> 
                                        <Text strong style={{ marginLeft: '5px', color: '#52c41a' }}>{JSON.stringify(changes[key].new)}</Text>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                );
            }

            if (Array.isArray(parsed)) {
                return (
                    <Space direction="vertical" style={{ width: '100%' }}>
                        {parsed.map((part: any, idx: number) => {
                            if (part.type === 'text') return <div key={idx} style={{ whiteSpace: 'pre-wrap' }}>{part.text}</div>;
                            if (part.type === 'image_url') return <img key={idx} src={part.image_url.url} alt="Generated" style={{ maxWidth: '100%', maxHeight: '300px', border: '1px solid #eee', borderRadius: '4px' }} />;
                            if (part.type === 'video_url') return <video key={idx} src={part.video_url.url} controls style={{ maxWidth: '100%', maxHeight: '300px', border: '1px solid #eee', borderRadius: '4px' }} />;
                            if (part.type === 'audio_url') return <audio key={idx} src={part.audio_url.url} controls style={{ width: '100%', marginTop: '8px' }} />;
                            return <Text key={idx} type="secondary">[Unknown Content Type: {part.type}]</Text>;
                        })}
                    </Space>
                );
            } else if (typeof parsed === 'object') {
                 return <pre style={{ fontSize: '11px' }}>{JSON.stringify(parsed, null, 2)}</pre>;
            }
        }
    } catch (e) {
        // Not JSON, continue to Markdown parsing
    }

    // 2. Markdown Image Parsing (e.g. ![alt](url))
    const imageRegex = /!\[([^\]]*)\]\(([^)]+)\)/g;
    if (content.match(imageRegex)) {
        const parts = [];
        let lastIndex = 0;
        let match;
        
        // Reset regex state just in case
        imageRegex.lastIndex = 0;

        while ((match = imageRegex.exec(content)) !== null) {
            // Text before image
            if (match.index > lastIndex) {
                parts.push(<span key={`text-${lastIndex}`}>{content.substring(lastIndex, match.index)}</span>);
            }
            // The Image
            parts.push(
                <div key={`img-${match.index}`} style={{ margin: '8px 0' }}>
                    <img 
                        src={match[2]} 
                        alt={match[1]} 
                        style={{ maxWidth: '100%', maxHeight: '300px', borderRadius: '4px', border: '1px solid #eee' }} 
                    />
                    {match[1] && <div style={{ fontSize: '12px', color: '#999', textAlign: 'center' }}>{match[1]}</div>}
                </div>
            );
            lastIndex = match.index + match[0].length;
        }
        // Remaining text
        if (lastIndex < content.length) {
            parts.push(<span key={`text-${lastIndex}`}>{content.substring(lastIndex)}</span>);
        }
        
        return <div style={{ whiteSpace: 'pre-wrap' }}>{parts}</div>;
    }

    // 3. Plain Text Fallback
    return <div style={{ whiteSpace: 'pre-wrap' }}>{content}</div>;
};

// --- Main Page ---

const SimulationDesigner: React.FC = () => {
    const {
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
    } = useSimulation();

    const [agents, setAgents] = useState<Agent[]>([]);
    
    // Save/Load State
    const [isLoadModalOpen, setIsLoadModalOpen] = useState(false);
    const [savedSims, setSavedSims] = useState<Simulation[]>([]);
    const [isRunHistoryOpen, setIsRunHistoryOpen] = useState(false);
    const [runHistoryList] = useState<SimulationRun[]>([]);

    // AI Generation State
    const [isAiModalOpen, setIsAiModalOpen] = useState(false);
    const [aiPrompt, setAiPrompt] = useState('');
    const [aiFileList, setAiFileList] = useState<UploadFile[]>([]);
    const [isGenerating, setIsGenerating] = useState(false);

    // Memory Injection State
    const [isMemoryModalOpen, setIsMemoryModalOpen] = useState(false);
    const [memoryTargetAgent, setMemoryTargetAgent] = useState<string>('');
    const [memoryContent, setMemoryContent] = useState('');
    const [memoryImportance, setMemoryImportance] = useState(1);

    // --- Persistence Logic ---
    // Persistence handled by SimulationContext

    // Load agents on mount
    useEffect(() => {
        getAgents().then(setAgents).catch(e => {
            console.error("Failed to load agents", e);
            message.error("Failed to load agents list");
        });
    }, []);

    const handleNewSimulation = () => {
        Modal.confirm({
            title: 'Create New Simulation?',
            content: 'This will clear the current simulation draft and execution history. Unsaved progress will be lost.',
            onOk: () => {
                setSteps([]);
                setVariables([]);
                setSimName('New Simulation');
                setCurrentSimId(null);
                setHistory([]);
                setWorldState({});
                setExecStack([]);
                setIsRunning(false);
                setIsAutoRunning(false);
                
                // Clear localStorage
                localStorage.removeItem('simulation_draft');
                localStorage.removeItem('simulation_run_state');
                message.success("New simulation created");
            }
        });
    };

    const handleAiGenerate = async () => {
        if (!aiPrompt.trim()) {
            message.warning("Please enter a description");
            return;
        }
        setIsGenerating(true);
        try {
            let fileContent = undefined;
            let fileNames: string[] = [];

            if (aiFileList.length > 0) {
                const fileObj = aiFileList[0].originFileObj;
                if (fileObj) {
                    // Upload as temp file for attachment support
                    try {
                        const res = await uploadTempFile(fileObj);
                        fileNames.push(res.filename);
                        message.success(`File uploaded: ${res.filename}`);
                    } catch (e) {
                        console.error("Failed to upload temp file", e);
                        message.error("Failed to upload attachment");
                        setIsGenerating(false);
                        return;
                    }
                }
            }

            const sim = await generateSimulation(aiPrompt, fileContent, fileNames);
            
            // Robustly handle missing fields to prevent white screen
            const safeSteps = (sim.steps || []).map((s: any) => ({
                ...s,
                id: s.id || Math.random().toString(),
                type: s.type || 'agent', // Default to agent if missing
                agent_ids: s.agent_ids || [],
                inner_steps: (s.inner_steps || []).map((inner: any) => ({
                    ...inner,
                    id: inner.id || Math.random().toString(),
                    type: inner.type || 'agent',
                    agent_ids: inner.agent_ids || [],
                    repeat_count: inner.repeat_count || 1
                })),
                repeat_count: s.repeat_count || 1
            }));

            setSteps(safeSteps);
            setVariables(sim.variables || []);
            setSimName(sim.name || "Generated Simulation");
            
            if (!sim.steps || sim.steps.length === 0) {
                message.warning("Generated simulation has no steps. The model output might have been truncated.");
            } else {
                // Auto-save the generated simulation
                try {
                    const simDataToSave: Simulation = {
                        name: sim.name || "Generated Simulation",
                        steps: safeSteps,
                        variables: sim.variables || []
                    };
                    const savedSim = await createSimulation(simDataToSave);
                    setCurrentSimId(savedSim.id || null);
                    message.success("Simulation generated and auto-saved successfully!");
                } catch (saveError) {
                    console.error("Auto-save failed", saveError);
                    message.warning("Simulation generated but auto-save failed. Please save manually.");
                }
            }
            
            // Refresh agents list as new agents might have been auto-created
            getAgents().then(setAgents);

            setIsAiModalOpen(false);
            resetSimulation(safeSteps, sim.variables || []);
        } catch (e) {
            const err: any = e;
            const detail = err?.response?.data?.detail || err?.response?.data?.message;
            message.error(detail || "Failed to generate simulation. Please try again.");
            console.error(e);
        } finally {
            setIsGenerating(false);
        }
    };


    // Initialize/Update stack when steps change
    useEffect(() => {
        setExecStack((prev: { steps: SimulationStep[]; index: number }[]) => {
            if (prev.length === 0) {
                return [{ steps: steps, index: 0 }];
            }
            // Update the root frame (index 0) with the new steps list
            // This allows adding steps mid-run and having them be executable
            const newStack = [...prev];
            newStack[0] = { ...newStack[0], steps: steps };
            return newStack;
        });
    }, [steps]);

    const saveSimulation = async () => {
        const simData: Simulation = {
            name: simName,
            steps,
            variables
        };
        try {
            if (currentSimId) {
                await updateSimulation(currentSimId, simData);
                message.success("Simulation updated");
            } else {
                const newSim = await createSimulation(simData);
                setCurrentSimId(newSim.id || null);
                message.success("Simulation saved");
            }
        } catch (e) {
            message.error("Failed to save simulation");
        }
    };

    const loadSimulations = async () => {
        const sims = await getSimulations();
        setSavedSims(sims);
        setIsLoadModalOpen(true);
    };

    const selectSimulation = (sim: Simulation) => {
        setSteps(sim.steps);
        setVariables(sim.variables);
        setSimName(sim.name);
        setCurrentSimId(sim.id || null);
        setIsLoadModalOpen(false);
        resetSimulation();
        message.success("Simulation loaded");
    };

    const handleDeleteSimulation = async (id: string) => {
        try {
            await deleteSimulation(id);
            message.success("Simulation deleted");
            loadSimulations(); // Refresh list
        } catch (e: any) {
            const msg = e.response?.data?.detail || "Failed to delete simulation";
            message.error(msg);
        }
    };

    const saveRun = async () => {
        if (history.length === 0) return;
        try {
            await saveSimulationRun({
                simulation_id: currentSimId || undefined,
                history,
                final_world_state: worldState
            });
            message.success("Run history saved");
        } catch (e) {
            message.error("Failed to save run");
        }
    };

    const downloadHistoryCSV = () => {
        if (history.length === 0) return;

        // 1. Collect all unique variable keys encountered
        const allVarKeys = new Set<string>();
        variables.forEach(v => allVarKeys.add(v.key));
        history.forEach(h => {
            if (h.world_state) {
                Object.keys(h.world_state).forEach(k => allVarKeys.add(k));
            }
        });
        const varColumns = Array.from(allVarKeys).sort();

        // 2. Build Header
        const header = ['Step', 'Agent', 'Prompt', 'Files', 'Response', ...varColumns.map(k => `Var: ${k}`)];
        const rows = [];

        // 3. Initial State Row (Row 0)
        // We try to reconstruct initial state from variables definition
        const initialRow = ['0', 'System', 'Initial State', '', '', ...varColumns.map(k => {
            const v = variables.find(v => v.key === k);
            return v ? `"${v.value.replace(/"/g, '""')}"` : '';
        })];
        rows.push(initialRow.join(','));

        // 4. History Rows
        history.forEach((item, index) => {
            // Handle multimodal content for CSV
            let contentStr = item.content;
            try {
                if (contentStr.trim().startsWith('[') || contentStr.trim().startsWith('{')) {
                    const parsed = JSON.parse(contentStr);
                    if (Array.isArray(parsed)) {
                        // Convert multimodal list to readable string
                        contentStr = parsed.map(p => {
                            if (p.type === 'text') return p.text;
                            if (p.type === 'image_url') return `[Image: ${p.image_url.url}]`;
                            return `[${p.type}]`;
                        }).join('\n');
                    }
                }
            } catch (e) {
                // Keep original if parse fails
            }

            const row = [
                (index + 1).toString(),
                `"${item.agent_name.replace(/"/g, '""')}"`,
                `"${(item.prompt || '').replace(/"/g, '""')}"`,
                `"${(item.files || []).join('; ').replace(/"/g, '""')}"`,
                `"${contentStr.replace(/"/g, '""')}"`,
                ...varColumns.map(k => {
                    const val = item.world_state ? item.world_state[k] : '';
                    return `"${JSON.stringify(val).replace(/"/g, '""')}"`;
                })
            ];
            rows.push(row.join(','));
        });

        // 5. Trigger Download
        const csvContent = "\uFEFF" + header.join(',') + '\n' + rows.join('\n'); // Add BOM for Excel
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `simulation_run_${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    const handleInjectMemory = async () => {
        if (!memoryTargetAgent || !memoryContent) return;
        try {
            await injectMemory(memoryTargetAgent, memoryContent, memoryImportance);
            message.success("Memory injected successfully!");
            setMemoryContent('');
            setIsMemoryModalOpen(false);
            // Refresh agents to reflect new memory in UI
            getAgents().then(setAgents);
        } catch (e) {
            message.error("Failed to inject memory");
        }
    };


    return (
        <div style={{ display: 'flex', height: '85vh', gap: '20px' }}>
            {/* Left: Designer */}
            <div style={{ flex: 3, overflowY: 'auto', paddingRight: '10px', minWidth: 420 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                    <Title level={3} style={{ margin: 0 }}>Simulation Designer</Title>
                    <Space size="small" wrap style={{ justifyContent: 'flex-end' }}>
                        <Button type="primary" icon={<RobotOutlined />} onClick={() => setIsAiModalOpen(true)}>
                            AI Create
                        </Button>
                        
                        <div style={{ width: 1, height: 24, background: '#d9d9d9', margin: '0 8px' }} />
                        
                        <Tooltip title="New Simulation">
                            <Button icon={<FileAddOutlined />} onClick={handleNewSimulation} />
                        </Tooltip>
                        <Tooltip title="Load Simulation">
                            <Button icon={<FolderOpenOutlined />} onClick={loadSimulations} />
                        </Tooltip>
                        <Tooltip title="Save Simulation">
                            <Button icon={<SaveOutlined />} onClick={saveSimulation} />
                        </Tooltip>

                        <div style={{ width: 1, height: 24, background: '#d9d9d9', margin: '0 8px' }} />

                        <Tooltip title="Run History">
                            <Button icon={<HistoryOutlined />} onClick={() => setIsRunHistoryOpen(true)} />
                        </Tooltip>
                    </Space>
                </div>
                
                <Input 
                    addonBefore="Simulation Name" 
                    value={simName} 
                    onChange={e => setSimName(e.target.value)} 
                    style={{ marginBottom: 20 }}
                />

                <Collapse defaultActiveKey={['1']} style={{ marginBottom: 20 }}>
                    <Panel header="World State Variables" key="1">
                        <VariableManager variables={variables} onChange={setVariables} />
                    </Panel>
                    <Panel header="Participating Agents (Context)" key="2">
                        <List
                            size="small"
                            dataSource={agents.filter(a => steps.some(s => s.agent_ids?.includes(a.id) || s.agent_id === a.id))}
                            renderItem={agent => (
                                <List.Item>
                                    <List.Item.Meta
                                        title={agent.name}
                                        description={
                                            <div style={{ fontSize: '0.8em' }}>
                                                <div><strong>Model:</strong> {agent.model}</div>
                                                <div><strong>Persona:</strong> {agent.persona?.substring(0, 50)}...</div>
                                                <div><strong>Memory:</strong> {agent.long_term_memory?.length || 0} items</div>
                                                <div><strong>Relationships:</strong> {agent.relationships?.length || 0} items</div>
                                            </div>
                                        }
                                    />
                                </List.Item>
                            )}
                        />
                    </Panel>
                </Collapse>

                <StepList 
                    steps={steps} 
                    onChange={setSteps} 
                    agents={agents} 
                    variables={variables}
                />
            </div>

            {/* Right: Execution */}
            <div style={{ flex: 2, display: 'flex', flexDirection: 'column', borderLeft: '1px solid #eee', paddingLeft: '20px', minWidth: 420 }}>
                <Title level={3}>Execution</Title>
                <Space wrap style={{ marginBottom: 20 }}>
                    <Button 
                        type="primary" 
                        icon={<PlayCircleOutlined />} 
                        onClick={() => runNextStep()} 
                        loading={isRunning && !isAutoRunning}
                        disabled={execStack.length === 0 || isAutoRunning}
                    >
                        Run Next Step
                    </Button>
                    <Button
                        icon={isAutoRunning ? <PauseCircleOutlined /> : <FastForwardOutlined />}
                        onClick={() => setIsAutoRunning(!isAutoRunning)}
                        disabled={execStack.length === 0 && !isAutoRunning}
                    >
                        {isAutoRunning ? "Pause" : "Run All"}
                    </Button>
                    <Button icon={<ReloadOutlined />} onClick={() => resetSimulation()}>Reset / Start</Button>
                    <Button icon={<SaveOutlined />} onClick={saveRun} disabled={history.length === 0}>Save Run</Button>
                    <Button onClick={downloadHistoryCSV} disabled={history.length === 0}>Download CSV</Button>
                    <Button icon={<InfoCircleOutlined />} onClick={() => setIsMemoryModalOpen(true)}>Inject Memory</Button>
                    <Space>
                        <Text style={{ fontSize: 12 }}>Auto Repair</Text>
                        <Switch checked={autoRepairEnabled} onChange={setAutoRepairEnabled} />
                    </Space>
                </Space>

                <Collapse style={{ marginBottom: 20 }}>
                    <Panel header={<Text strong>Current World State</Text>} key="1" style={{ background: '#fffbe6' }}>
                        <pre style={{ margin: 0, fontSize: 12, maxHeight: '300px', overflow: 'auto' }}>{JSON.stringify(worldState, null, 2)}</pre>
                    </Panel>
                </Collapse>

                <div style={{ flex: 1, overflowY: 'auto', background: '#f5f5f5', padding: '15px', borderRadius: '8px' }}>
                    {history.map((item, i) => (
                        <div key={i} style={{ marginBottom: '15px', background: '#fff', padding: '10px', borderRadius: '4px', border: '1px solid #e8e8e8' }}>
                            <div style={{ fontWeight: 'bold', color: '#1890ff', marginBottom: '5px' }}>
                                {item.agent_name} <span style={{fontSize: '0.8em', color: '#999'}}>(Step {i + 1})</span>
                            </div>
                            
                            {item.prompt && (
                                <div style={{ marginBottom: 8, padding: 8, background: '#f0f2f5', borderRadius: 4, borderLeft: '3px solid #1890ff' }}>
                                    <Text strong style={{ fontSize: '0.9em', color: '#555' }}>Prompt:</Text>
                                    <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.9em', color: '#333' }}>{item.prompt}</div>
                                </div>
                            )}

                            {renderContent(item.content)}
                        </div>
                    ))}
                </div>
            </div>

            <Modal title="Load Simulation" open={isLoadModalOpen} onCancel={() => setIsLoadModalOpen(false)} footer={null}>
                <List
                    dataSource={savedSims}
                    renderItem={item => (
                        <List.Item actions={[
                            <Button onClick={() => selectSimulation(item)}>Load</Button>,
                            <Button danger icon={<DeleteOutlined />} onClick={() => item.id && handleDeleteSimulation(item.id)} />
                        ]}>
                            <List.Item.Meta
                                title={item.name}
                                description={`${item.steps.length} steps, ${item.variables.length} vars`}
                            />
                        </List.Item>
                    )}
                />
            </Modal>

            <Drawer 
                title="Run History" 
                placement="right" 
                onClose={() => setIsRunHistoryOpen(false)} 
                open={isRunHistoryOpen}
                width={500}
            >
                <List
                    dataSource={runHistoryList}
                    renderItem={run => (
                        <List.Item>
                            <List.Item.Meta
                                title={new Date((run.timestamp || 0) * 1000).toLocaleString()}
                                description={`${run.history.length} steps executed`}
                            />
                            <Button onClick={() => {
                                setHistory(run.history as any);
                                setWorldState(run.final_world_state);
                                setIsRunHistoryOpen(false);
                                message.success("Run loaded into view");
                            }}>View</Button>
                        </List.Item>
                    )}
                />
            </Drawer>

            <Modal 
                title={<Space><RobotOutlined /> AI Simulation Creator</Space>}
                open={isAiModalOpen} 
                onCancel={() => setIsAiModalOpen(false)} 
                footer={[
                    <Button key="cancel" onClick={() => setIsAiModalOpen(false)}>Cancel</Button>,
                    <Button key="submit" type="primary" loading={isGenerating} onClick={handleAiGenerate}>Generate</Button>
                ]}
            >
                <Text>Describe the simulation you want to create. Be as specific as possible about the agents, steps, and logic.</Text>
                <TextArea 
                    rows={6} 
                    value={aiPrompt} 
                    onChange={e => setAiPrompt(e.target.value)} 
                    placeholder="Example: Create a debate between two agents about the future of AI. One is optimistic, one is pessimistic. They should take turns speaking 3 times each. Finally, a judge agent decides the winner. Tip: you can also ask for a 'dialogue' step where an agent starts a conversation with another agent until END_DIALOGUE or max turns."
                    style={{ marginTop: 10, marginBottom: 10 }}
                />
                <Upload 
                    fileList={aiFileList}
                    beforeUpload={() => false} // Prevent auto upload
                    onChange={({ fileList }) => setAiFileList(fileList)}
                    maxCount={1}
                >
                    <Button icon={<UploadOutlined />}>Attach Context File</Button>
                </Upload>
            </Modal>

            <Modal
                title="Inject Memory"
                open={isMemoryModalOpen}
                onOk={handleInjectMemory}
                onCancel={() => setIsMemoryModalOpen(false)}
            >
                <div style={{ marginBottom: 16 }}>
                    <Text strong>Target Agent:</Text>
                    <Select 
                        style={{ width: '100%' }} 
                        value={memoryTargetAgent} 
                        onChange={setMemoryTargetAgent}
                        placeholder="Select an agent"
                    >
                        {agents.map(a => (
                            <Option key={a.id} value={a.id}>{a.name}</Option>
                        ))}
                    </Select>
                </div>
                <div style={{ marginBottom: 16 }}>
                    <Text strong>Memory Content:</Text>
                    <TextArea 
                        rows={4} 
                        value={memoryContent} 
                        onChange={e => setMemoryContent(e.target.value)} 
                        placeholder="e.g. You just found 100 dollars on the street."
                    />
                </div>
                <div style={{ marginBottom: 16 }}>
                    <Text strong>Importance (1-10):</Text>
                    <Input 
                        type="number" 
                        value={memoryImportance} 
                        onChange={e => setMemoryImportance(parseInt(e.target.value))} 
                        min={1} 
                        max={10} 
                    />
                </div>
            </Modal>
        </div>
    );
};

export default SimulationDesigner;
