import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Divider,
  Empty,
  Input,
  List,
  message,
  Row,
  Radio,
  Select,
  Space,
  Spin,
  Steps,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  Upload,
} from 'antd';
import {
  BugOutlined,
  CodeOutlined,
  CopyOutlined,
  DeleteOutlined,
  DownOutlined,
  PlayCircleOutlined,
  RobotOutlined,
  UploadOutlined,
  ReloadOutlined,
  FastForwardOutlined,
  InfoCircleOutlined,
  MessageOutlined,
  PauseCircleOutlined,
  PlusOutlined,
  RightOutlined,
  RetweetOutlined,
  LineChartOutlined,
  SaveOutlined,
  HistoryOutlined,
  ExperimentOutlined,
  FileSearchOutlined,
  UserOutlined,
} from '@ant-design/icons';
import type { UploadProps } from 'antd';
import type { Agent, Simulation, SimulationHistoryItem, SimulationStep } from '../api/agent';
import { fixCodeStep, getAgents, repairSimulation, runSimulationStep, saveSimulationRun } from '../api/agent';
import {
  analyzeExperimentRun,
  generateComparisonReport,
  listExperimentPapers,
  listExperimentSessions,
  solveExperimentPipeline,
  uploadAnalysisDataFile,
  uploadExperimentPaper,
  type LLMExperimentAnalysisFileRecord,
  type LLMExperimentAnalyzeRunResponse,
  type LLMExperimentBuildResponse,
  type LLMExperimentComparisonReportResponse,
  type LLMExperimentPaperRecord,
  type LLMExperimentSessionRecord,
} from '../api/llmExperiment';

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;
const { Option } = Select;

interface WorldVariable {
  key: string;
  value: string;
  description: string;
}

const normalizeStepShape = (raw: any): SimulationStep => {
  const t = raw?.type;
  const type: SimulationStep['type'] = t === 'agent' || t === 'code' || t === 'loop' || t === 'dialogue' ? t : 'agent';
  return {
    id: String(raw?.id || `${Date.now()}-${Math.random()}`),
    type,
    agent_ids: Array.isArray(raw?.agent_ids) ? raw.agent_ids : (raw?.agent_id ? [raw.agent_id] : []),
    prompt_template: String(raw?.prompt_template || ''),
    code_snippet: String(raw?.code_snippet || ''),
    output_var: raw?.output_var,
    output_format: raw?.output_format,
    execution_mode: raw?.execution_mode,
    use_rag: raw?.use_rag,
    loop_condition: raw?.loop_condition,
    inner_steps: Array.isArray(raw?.inner_steps) ? raw.inner_steps.map((s: any) => normalizeStepShape(s)) : [],
    repeat_count: raw?.repeat_count ?? 1,
    files: Array.isArray(raw?.files) ? raw.files : [],
    dialogue_max_turns: raw?.dialogue_max_turns,
    dialogue_auto_partner: raw?.dialogue_auto_partner,
    dialogue_partner_id: raw?.dialogue_partner_id,
    dialogue_end_marker: raw?.dialogue_end_marker,
  };
};

const parseValue = (raw: string): any => {
  if (raw === '') return '';
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
};

const buildInitialWorldState = (simulation?: Record<string, any>): Record<string, any> => {
  const variables = (simulation?.variables || []) as Array<{ key?: string; value?: string }>;
  const state: Record<string, any> = {};
  variables.forEach((item) => {
    if (!item?.key) return;
    state[item.key] = parseValue(String(item.value ?? ''));
  });
  return state;
};

const pretty = (value: any) => {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value ?? '');
  }
};

const pickExecutionError = (items: SimulationHistoryItem[] = []): string | null => {
  const matched = items
    .filter((item) => (item?.agent_name || '') === 'System')
    .map((item) => item?.content || '')
    .find((content) => {
      if (typeof content !== 'string') return false;
      return (
        content.includes('Error executing code') ||
        content.startsWith('Error evaluating loop condition') ||
        content.startsWith('Error: loop exceeded max iterations')
      );
    });
  return matched || null;
};

const renderExecutionContent = (content: string) => {
  if (!content) return <Text type="secondary">(Empty)</Text>;

  try {
    if (content.trim().startsWith('[') || content.trim().startsWith('{')) {
      const parsed = JSON.parse(content);

      if (parsed?.type === 'state_change') {
        const changes = parsed.changes || {};
        const stdout = parsed.stdout || '';
        const keys = Object.keys(changes);

        return (
          <div style={{ background: '#f0f5ff', padding: 8, borderRadius: 4, border: '1px solid #adc6ff' }}>
            {stdout && (
              <div style={{ marginBottom: 10, borderBottom: '1px solid #d9d9d9', paddingBottom: 6 }}>
                <Text strong style={{ color: '#555' }}>Console Output:</Text>
                <pre style={{ margin: '6px 0 0 0', padding: 8, background: '#333', color: '#fff', borderRadius: 4, fontSize: 11, whiteSpace: 'pre-wrap' }}>
                  {stdout}
                </pre>
              </div>
            )}
            <Text strong style={{ color: '#1d39c4' }}>Variable Updates:</Text>
            {keys.length === 0 ? (
              <div style={{ fontStyle: 'italic', color: '#999' }}>No variables changed.</div>
            ) : (
              <ul style={{ margin: '6px 0 0 20px', padding: 0 }}>
                {keys.map((key) => (
                  <li key={key}>
                    <Text code>{key}</Text>
                    <Text delete type="secondary" style={{ margin: '0 6px' }}>
                      {JSON.stringify(changes[key]?.old)}
                    </Text>
                    <RightOutlined style={{ fontSize: 10, color: '#999' }} />
                    <Text strong style={{ marginLeft: 6, color: '#52c41a' }}>
                      {JSON.stringify(changes[key]?.new)}
                    </Text>
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
              if (part?.type === 'text') return <div key={idx} style={{ whiteSpace: 'pre-wrap' }}>{part.text}</div>;
              if (part?.type === 'image_url') return <img key={idx} src={part.image_url?.url} alt="Generated" style={{ maxWidth: '100%', maxHeight: 300, border: '1px solid #eee', borderRadius: 4 }} />;
              if (part?.type === 'video_url') return <video key={idx} src={part.video_url?.url} controls style={{ maxWidth: '100%', maxHeight: 300, border: '1px solid #eee', borderRadius: 4 }} />;
              if (part?.type === 'audio_url') return <audio key={idx} src={part.audio_url?.url} controls style={{ width: '100%', marginTop: 8 }} />;
              return <Text key={idx} type="secondary">[Unknown Content Type: {part?.type}]</Text>;
            })}
          </Space>
        );
      }

      if (typeof parsed === 'object') {
        return <pre style={{ fontSize: 11, margin: 0 }}>{JSON.stringify(parsed, null, 2)}</pre>;
      }
    }
  } catch {
    // Fallback to plain text rendering.
  }

  const imageRegex = /!\[([^\]]*)\]\(([^)]+)\)/g;
  if (content.match(imageRegex)) {
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;
    imageRegex.lastIndex = 0;

    while ((match = imageRegex.exec(content)) !== null) {
      if (match.index > lastIndex) {
        parts.push(<span key={`text-${lastIndex}`}>{content.substring(lastIndex, match.index)}</span>);
      }
      parts.push(
        <div key={`img-${match.index}`} style={{ margin: '8px 0' }}>
          <img src={match[2]} alt={match[1]} style={{ maxWidth: '100%', maxHeight: 300, borderRadius: 4, border: '1px solid #eee' }} />
          {match[1] && <div style={{ fontSize: 12, color: '#999', textAlign: 'center' }}>{match[1]}</div>}
        </div>,
      );
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < content.length) {
      parts.push(<span key={`text-${lastIndex}`}>{content.substring(lastIndex)}</span>);
    }

    return <div style={{ whiteSpace: 'pre-wrap' }}>{parts}</div>;
  }

  return <div style={{ whiteSpace: 'pre-wrap' }}>{content}</div>;
};

const VariableManager: React.FC<{
  variables: WorldVariable[];
  onChange: (vars: WorldVariable[]) => void;
}> = ({ variables, onChange }) => {
  const updateVar = (index: number, field: keyof WorldVariable, val: string) => {
    const next = [...variables];
    next[index] = { ...next[index], [field]: val };
    onChange(next);
  };

  const addVar = () => onChange([...variables, { key: '', value: '', description: '' }]);
  const removeVar = (index: number) => onChange(variables.filter((_, i) => i !== index));

  const columns = [
    {
      title: 'Key',
      dataIndex: 'key',
      render: (text: string, _: unknown, i: number) => (
        <Input value={text} onChange={(e) => updateVar(i, 'key', e.target.value)} placeholder="e.g. inventory" />
      ),
    },
    {
      title: 'Initial Value',
      dataIndex: 'value',
      render: (text: string, _: unknown, i: number) => (
        <Input value={text} onChange={(e) => updateVar(i, 'value', e.target.value)} placeholder="e.g. 100" />
      ),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      render: (text: string, _: unknown, i: number) => (
        <Input value={text} onChange={(e) => updateVar(i, 'description', e.target.value)} placeholder="What is this?" />
      ),
    },
    {
      title: 'Action',
      render: (_: unknown, __: unknown, i: number) => (
        <Button danger icon={<DeleteOutlined />} onClick={() => removeVar(i)} />
      ),
    },
  ];

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
        <Text strong>System Variables</Text>
        <Button size="small" icon={<PlusOutlined />} onClick={addVar}>Add Variable</Button>
      </div>
      <Table
        dataSource={variables}
        columns={columns}
        pagination={false}
        size="small"
        rowKey={(_, i) => String(i)}
      />
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
  const [isVarsOpen, setIsVarsOpen] = useState(false);
  const stepSafe = normalizeStepShape(step);
  const stepType = stepSafe.type;

  const updateField = (field: keyof SimulationStep, value: any) => {
    onChange({ ...stepSafe, [field]: value });
  };

  const updateType = (newType: SimulationStep['type']) => {
    if (newType === 'dialogue') {
      onChange({
        ...stepSafe,
        type: 'dialogue',
        agent_ids: stepSafe.agent_ids || [],
        prompt_template: stepSafe.prompt_template || '',
        dialogue_auto_partner: stepSafe.dialogue_auto_partner ?? true,
        dialogue_max_turns: stepSafe.dialogue_max_turns ?? 6,
        dialogue_end_marker: stepSafe.dialogue_end_marker || 'END_DIALOGUE',
      });
      return;
    }
    onChange({ ...stepSafe, type: newType });
  };

  const insertText = (text: string) => {
    updateField('prompt_template', `${stepSafe.prompt_template || ''}${text}`);
  };

  return (
    <Card
      size="small"
      title={(
        <Space>
          <Tag color={step.type === 'loop' ? 'purple' : step.type === 'code' ? 'blue' : step.type === 'dialogue' ? 'orange' : 'green'}>
            {stepType.toUpperCase()}
          </Tag>
          <span>Step {index + 1}</span>
        </Space>
      )}
      extra={(
        <Space>
          <Button type="text" icon={<CopyOutlined />} onClick={onDuplicate} title="Duplicate Step" />
          <Button danger type="text" icon={<DeleteOutlined />} onClick={onRemove} title="Remove Step" />
        </Space>
      )}
      style={{ marginBottom: 10, borderLeft: '4px solid #1890ff' }}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
          <Radio.Group
            value={stepType}
            onChange={(e) => updateType(e.target.value)}
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
            value={stepSafe.repeat_count}
            onChange={(e) => {
              const val = e.target.value;
              if (val === '' || /^\d+$/.test(val)) {
                updateField('repeat_count', val === '' ? '' : parseInt(val, 10));
              } else {
                updateField('repeat_count', val);
              }
            }}
            style={{ width: 130 }}
            size="small"
          />
        </div>

        {(stepType === 'agent' || stepType === 'dialogue') && (
          <>
            <Select
              mode="multiple"
              value={stepSafe.agent_ids || (stepSafe.agent_id ? [stepSafe.agent_id] : [])}
              style={{ width: '100%' }}
              onChange={(val) => updateField('agent_ids', val)}
              placeholder="Select one or more agents"
            >
              {agents.map((a) => <Option key={a.id} value={a.id}>{a.name}</Option>)}
            </Select>

            <div style={{ marginBottom: 4, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Text strong>{stepType === 'dialogue' ? 'Start Instruction / Goal:' : 'Prompt Template:'}</Text>
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
              <div style={{ marginBottom: 8, padding: 8, background: '#f5f5f5', borderRadius: 4, border: '1px solid #d9d9d9' }}>
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
                    <Text type="secondary" style={{ fontSize: 12, marginRight: 4 }}>World:</Text>
                    {variables.map((v) => (
                      <Tooltip key={v.key} title={v.description}>
                        <Tag color="blue" style={{ cursor: 'pointer' }} onClick={() => insertText(`{{state.${v.key}}}`)}>{v.key}</Tag>
                      </Tooltip>
                    ))}
                    {variables.length === 0 && <Text type="secondary" style={{ fontSize: 11 }}>(No variables)</Text>}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
                    <Text type="secondary" style={{ fontSize: 12, marginRight: 4 }}>Context:</Text>
                    <Tag color="purple" style={{ cursor: 'pointer' }} onClick={() => insertText('{{memory}}')}>Memory</Tag>
                    <Tag color="purple" style={{ cursor: 'pointer' }} onClick={() => insertText('{{history}}')}>History</Tag>
                    <Tag color="purple" style={{ cursor: 'pointer' }} onClick={() => insertText('{{last_output}}')}>Last Output</Tag>
                  </div>
                </Space>
              </div>
            )}

            <TextArea
              rows={stepType === 'dialogue' ? 5 : 3}
              value={stepSafe.prompt_template}
              onChange={(e) => updateField('prompt_template', e.target.value)}
              placeholder="Use {{state.var}} to inject variables."
            />
          </>
        )}

        {stepType === 'agent' && (
          <>
            <div style={{ display: 'flex', gap: 10 }}>
              <Input
                addonBefore="Output Var"
                placeholder="Save result to..."
                value={stepSafe.output_var}
                onChange={(e) => updateField('output_var', e.target.value)}
                style={{ flex: 1 }}
              />
              <Select
                value={stepSafe.output_format || 'raw'}
                onChange={(val) => updateField('output_format', val)}
                style={{ width: 130 }}
                options={[
                  { label: 'Raw (JSON)', value: 'raw' },
                  { label: 'Text Only', value: 'text' },
                  { label: 'Image URL', value: 'image' },
                  { label: 'Video URL', value: 'video' },
                ]}
              />
              <Select
                value={stepSafe.execution_mode || 'parallel'}
                onChange={(val) => updateField('execution_mode', val)}
                style={{ width: 120 }}
                options={[
                  { label: 'Parallel', value: 'parallel' },
                  { label: 'Serial', value: 'serial' },
                ]}
              />
            </div>

            <Space>
              <Text strong>Enable RAG Memory</Text>
              <Switch checked={stepSafe.use_rag !== false} onChange={(val) => updateField('use_rag', val)} />
              <Tooltip title="Enable retrieval from long-term memory during this agent call.">
                <InfoCircleOutlined style={{ color: '#1890ff' }} />
              </Tooltip>
            </Space>
          </>
        )}

        {stepType === 'dialogue' && (
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Text strong>Max Turns:</Text>
              <Input
                value={stepSafe.dialogue_max_turns ?? 6}
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === '' || /^\d+$/.test(val)) {
                    updateField('dialogue_max_turns', val === '' ? 6 : parseInt(val, 10));
                  }
                }}
                style={{ width: 120 }}
                size="small"
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Text strong>Auto Partner:</Text>
              <Switch
                checked={stepSafe.dialogue_auto_partner ?? true}
                onChange={(checked) => updateField('dialogue_auto_partner', checked)}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Text strong>End Marker:</Text>
              <Input
                value={stepSafe.dialogue_end_marker || 'END_DIALOGUE'}
                onChange={(e) => updateField('dialogue_end_marker', e.target.value)}
                style={{ width: 160 }}
                size="small"
              />
            </div>
          </div>
        )}

        {stepType === 'code' && (
          <>
            <Text strong>Python Code:</Text>
            <TextArea
              rows={4}
              value={stepSafe.code_snippet}
              onChange={(e) => updateField('code_snippet', e.target.value)}
              style={{ fontFamily: 'monospace' }}
              placeholder="state['inventory'] -= 1"
            />
            <Button
              icon={<BugOutlined />}
              onClick={async () => {
                try {
                  const fixedCode = await fixCodeStep(stepSafe.code_snippet || '', 'Please review and fix possible runtime issues.');
                  updateField('code_snippet', fixedCode);
                  message.success('Code snippet auto-fixed');
                } catch {
                  message.error('AI fix failed');
                }
              }}
            >
              AI Fix
            </Button>
          </>
        )}

        {stepType === 'loop' && (
          <div style={{ background: '#f9f9f9', padding: 10, borderRadius: 4 }}>
            <Text strong>Loop Condition (Python):</Text>
            <Input
              value={stepSafe.loop_condition}
              onChange={(e) => updateField('loop_condition', e.target.value)}
              placeholder="e.g. state['inventory'] > 0 (Empty = Always True)"
              style={{ fontFamily: 'monospace', marginBottom: 10 }}
            />
            <Text strong>Inner Steps:</Text>
            <StepList
              steps={stepSafe.inner_steps || []}
              onChange={(newSteps) => updateField('inner_steps', newSteps)}
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
      id: `${Date.now()}-${Math.random()}`,
      type: 'agent',
      agent_ids: [],
      prompt_template: '',
      inner_steps: [],
      repeat_count: 1,
    };
    onChange([...steps, newStep]);
  };

  const updateStep = (index: number, updatedStep: SimulationStep) => {
    const next = [...steps];
    next[index] = updatedStep;
    onChange(next);
  };

  const removeStep = (index: number) => onChange(steps.filter((_, i) => i !== index));

  const duplicateStep = (index: number) => {
    const next = [...steps];
    const copied = { ...next[index], id: `${Date.now()}-${Math.random()}` };
    next.splice(index + 1, 0, copied);
    onChange(next);
  };

  return (
    <div>
      {steps.map((step, i) => (
        <StepEditor
          key={step.id || `${i}-${step.type}`}
          step={step}
          index={i}
          agents={agents}
          variables={variables}
          onChange={(s) => updateStep(i, s)}
          onRemove={() => removeStep(i)}
          onDuplicate={() => duplicateStep(i)}
        />
      ))}
      <Button type="dashed" block icon={<PlusOutlined />} onClick={addStep}>Add Step</Button>
    </div>
  );
};

const buildRunHistoryCsv = (simulation: Simulation, history: SimulationHistoryItem[]): string => {
  const allVarKeys = new Set<string>();
  (simulation.variables || []).forEach((item) => {
    if (item?.key) allVarKeys.add(item.key);
  });
  history.forEach((item) => {
    if (!item?.world_state) return;
    Object.keys(item.world_state).forEach((key) => allVarKeys.add(key));
  });
  const varColumns = Array.from(allVarKeys).sort();

  const header = ['Step', 'Agent', 'Prompt', 'Files', 'Response', ...varColumns.map((key) => `Var: ${key}`)];
  const rows: string[] = [];

  const initialRow = [
    '0',
    'System',
    'Initial State',
    '',
    '',
    ...varColumns.map((key) => {
      const matched = (simulation.variables || []).find((item) => item.key === key);
      return matched ? `"${String(matched.value ?? '').replace(/"/g, '""')}"` : '';
    }),
  ];
  rows.push(initialRow.join(','));

  history.forEach((item, index) => {
    let contentText = item.content || '';
    try {
      if (contentText.trim().startsWith('[') || contentText.trim().startsWith('{')) {
        const parsed = JSON.parse(contentText);
        if (Array.isArray(parsed)) {
          contentText = parsed
            .map((part) => {
              if (part.type === 'text') return part.text;
              if (part.type === 'image_url') return `[Image: ${part.image_url?.url}]`;
              return `[${part.type}]`;
            })
            .join('\n');
        }
      }
    } catch {
      // keep original content when not JSON
    }

    const row = [
      String(index + 1),
      `"${String(item.agent_name || '').replace(/"/g, '""')}"`,
      `"${String(item.prompt || '').replace(/"/g, '""')}"`,
      `"${(item.files || []).join('; ').replace(/"/g, '""')}"`,
      `"${String(contentText).replace(/"/g, '""')}"`,
      ...varColumns.map((key) => {
        const value = item.world_state ? item.world_state[key] : '';
        const serialized = JSON.stringify(value);
        return `"${String(serialized ?? '').replace(/"/g, '""')}"`;
      }),
    ];
    rows.push(row.join(','));
  });

  return `\uFEFF${header.join(',')}\n${rows.join('\n')}`;
};

const normalizeRepairedSimulation = (base: Simulation, repaired?: Partial<Simulation> | null): Simulation => {
  const fixed = repaired || {};
  const fixedSteps = Array.isArray(fixed.steps) ? fixed.steps : base.steps;
  const fixedVariables = Array.isArray(fixed.variables) ? fixed.variables : base.variables;

  return {
    ...base,
    steps: fixedSteps,
    variables: fixedVariables,
    id: base.id,
    name: base.name,
    description: base.description,
  };
};

const toEditableSimulation = (raw?: Partial<Simulation> | null): Simulation | null => {
  if (!raw) return null;
  return {
    id: raw.id,
    name: raw.name || 'LLM Experiment Simulation',
    description: raw.description || '',
    steps: Array.isArray(raw.steps) ? raw.steps : [],
    variables: Array.isArray(raw.variables)
      ? raw.variables.map((v) => ({
          key: String(v?.key ?? ''),
          value: String(v?.value ?? ''),
          description: String(v?.description ?? ''),
        }))
      : [],
  };
};

const LLMReplacementExperiment: React.FC = () => {
  const [papers, setPapers] = useState<LLMExperimentPaperRecord[]>([]);
  const [sessions, setSessions] = useState<LLMExperimentSessionRecord[]>([]);

  const [selectedPaperId, setSelectedPaperId] = useState<string | undefined>(undefined);
  const [requirements, setRequirements] = useState('');
  const [goal, setGoal] = useState('');
  const [constraints, setConstraints] = useState('');

  const [loadingPapers, setLoadingPapers] = useState(false);
  const [solving, setSolving] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [runningOneStep, setRunningOneStep] = useState(false);
  const [autoRunning, setAutoRunning] = useState(false);

  const [latestBuild, setLatestBuild] = useState<LLMExperimentBuildResponse | null>(null);
  const [analysisOutput, setAnalysisOutput] = useState<LLMExperimentAnalyzeRunResponse | null>(null);
  const [analysisDataFile, setAnalysisDataFile] = useState<LLMExperimentAnalysisFileRecord | null>(null);
  const [analysisInjectedRequirements, setAnalysisInjectedRequirements] = useState('');
  const [comparisonRequirements, setComparisonRequirements] = useState('');
  const [comparisonReport, setComparisonReport] = useState<LLMExperimentComparisonReportResponse | null>(null);
  const [uploadingAnalysisData, setUploadingAnalysisData] = useState(false);
  const [generatingComparison, setGeneratingComparison] = useState(false);
  const [autoRepairEnabled] = useState(true);

  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [runHistory, setRunHistory] = useState<SimulationHistoryItem[]>([]);
  const [worldState, setWorldState] = useState<Record<string, any>>({});
  const [availableAgents, setAvailableAgents] = useState<Agent[]>([]);
  const [editableSimulation, setEditableSimulation] = useState<Simulation | null>(null);

  const refreshPapers = useCallback(async () => {
    setLoadingPapers(true);
    try {
      const rows = await listExperimentPapers();
      setPapers(rows);
      if (!selectedPaperId && rows.length > 0) {
        setSelectedPaperId(rows[0].id);
      }
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载论文失败');
    } finally {
      setLoadingPapers(false);
    }
  }, [selectedPaperId]);

  const refreshSessions = useCallback(async () => {
    try {
      const rows = await listExperimentSessions(30);
      setSessions(rows);
    } catch {
      setSessions([]);
    }
  }, []);

  useEffect(() => {
    refreshPapers();
    refreshSessions();
  }, [refreshPapers, refreshSessions]);

  useEffect(() => {
    getAgents().then(setAvailableAgents).catch(() => setAvailableAgents([]));
  }, []);

  const resetRunnerBySimulation = useCallback((simulation?: Record<string, any>) => {
    setCurrentStepIndex(0);
    setRunHistory([]);
    setWorldState(buildInitialWorldState(simulation));
    setAutoRunning(false);
  }, []);

  const handleSolve = async () => {
    if (!requirements.trim()) {
      message.warning('请先填写实验要求');
      return;
    }
    setSolving(true);
    try {
      const response = await solveExperimentPipeline({
        paper_id: selectedPaperId,
        requirements,
        experiment_goal: goal || undefined,
        constraints: constraints || undefined,
        save_simulation: true,
      });
      setLatestBuild(response);
      setEditableSimulation(toEditableSimulation(response.simulation_reviewed));
      setAnalysisOutput(null);
      setComparisonReport(null);
      resetRunnerBySimulation(response.simulation_reviewed);
      await refreshSessions();
      message.success('四模块实验流程已完成，可开始运行模拟');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '生成失败');
    } finally {
      setSolving(false);
    }
  };

  const handleRunOneStep = async () => {
    if (!editableSimulation || !editableSimulation.steps?.length) {
      message.warning('请先生成 simulation');
      return;
    }
    if (currentStepIndex >= editableSimulation.steps.length) {
      message.info('已执行完所有步骤');
      setAutoRunning(false);
      return;
    }

    setRunningOneStep(true);
    const activeSessionId = latestBuild?.session_id;
    try {
      const runOnce = async (simulationToRun: Simulation, repairedOnce = false): Promise<{
        mergedHistory: SimulationHistoryItem[];
        updatedWorldState: Record<string, any>;
        simulationUsed: Simulation;
      }> => {
        try {
          const result = await runSimulationStep(
            simulationToRun.steps,
            currentStepIndex,
            runHistory,
            worldState,
          );

          const stepError = pickExecutionError(result.new_history_items || []);
          if (stepError && autoRepairEnabled && !repairedOnce) {
            const repaired = await repairSimulation(
              simulationToRun,
              currentStepIndex,
              stepError,
              runHistory,
              worldState,
            );
            const fixed = normalizeRepairedSimulation(simulationToRun, repaired?.fixed_simulation as Partial<Simulation>);
            if (fixed?.steps?.length) {
              setLatestBuild((prev) => {
                if (!prev) return prev;
                if (activeSessionId && prev.session_id !== activeSessionId) return prev;
                return {
                  ...prev,
                  simulation_reviewed: fixed,
                };
              });
              setEditableSimulation(fixed);
              message.success(`自动修复成功：${repaired.explanation || '已修复并重试'}`);
              return runOnce(fixed, true);
            }
          }

          if (stepError) {
            throw new Error(stepError);
          }

          const mergedHistory = [...runHistory, ...(result.new_history_items || [])];
          const updatedWorldState = (result.updated_world_state || {}) as Record<string, any>;
          return { mergedHistory, updatedWorldState, simulationUsed: simulationToRun };
        } catch (innerError: any) {
          const detail = innerError?.response?.data?.detail || innerError?.message || '运行步骤失败';
          if (autoRepairEnabled && !repairedOnce) {
            const repaired = await repairSimulation(
              simulationToRun,
              currentStepIndex,
              detail,
              runHistory,
              worldState,
            );
            const fixed = normalizeRepairedSimulation(simulationToRun, repaired?.fixed_simulation as Partial<Simulation>);
            if (fixed?.steps?.length) {
              setLatestBuild((prev) => {
                if (!prev) return prev;
                if (activeSessionId && prev.session_id !== activeSessionId) return prev;
                return {
                  ...prev,
                  simulation_reviewed: fixed,
                };
              });
              setEditableSimulation(fixed);
              message.success(`自动修复成功：${repaired.explanation || '已修复并重试'}`);
              return runOnce(fixed, true);
            }
          }
          throw innerError;
        }
      };

      const { mergedHistory, updatedWorldState, simulationUsed } = await runOnce(editableSimulation, false);
      const nextIndex = currentStepIndex + 1;

      setRunHistory(mergedHistory);
      setWorldState(updatedWorldState);
      setCurrentStepIndex(nextIndex);

      const finished = nextIndex >= simulationUsed.steps.length;
      if (finished) {
        setAutoRunning(false);
        const csvContent = buildRunHistoryCsv(simulationUsed, mergedHistory);
        const file = new File(
          [csvContent],
          `llm_experiment_run_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.csv`,
          { type: 'text/csv;charset=utf-8;' },
        );
        try {
          const uploaded = await uploadAnalysisDataFile(file);
          setAnalysisDataFile(uploaded.file);
          message.success(`模拟完成，已自动生成并绑定CSV：${uploaded.file.file_name}`);
        } catch (uploadError: any) {
          message.warning(uploadError?.response?.data?.detail || '模拟已完成，但自动上传CSV失败，可手动上传');
        }
      }
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '运行步骤失败');
      setAutoRunning(false);
    } finally {
      setRunningOneStep(false);
    }
  };

  useEffect(() => {
    if (!autoRunning) return;
    if (!editableSimulation?.steps?.length) {
      setAutoRunning(false);
      return;
    }
    if (runningOneStep || currentStepIndex >= editableSimulation.steps.length) {
      if (currentStepIndex >= editableSimulation.steps.length) {
        setAutoRunning(false);
        message.success('自动运行完成');
      }
      return;
    }

    const timer = window.setTimeout(() => {
      handleRunOneStep();
    }, 800);

    return () => window.clearTimeout(timer);
  }, [autoRunning, currentStepIndex, editableSimulation, runningOneStep]);

  const handleSaveRun = async () => {
    if (!editableSimulation) {
      message.warning('没有可保存的 simulation');
      return;
    }
    try {
      await saveSimulationRun({
        simulation_id: editableSimulation.id,
        history: runHistory,
        final_world_state: worldState,
      });
      message.success('运行结果已保存到 simulation runs');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存运行结果失败');
    }
  };

  const handleAnalyze = async () => {
    if (!latestBuild) {
      message.warning('请先完成实验生成');
      return;
    }
    setAnalyzing(true);
    try {
      const result = await analyzeExperimentRun({
        session_id: latestBuild.session_id,
        paper_id: latestBuild.paper_id,
        requirements,
        experiment_goal: goal || undefined,
        analysis_thinking: latestBuild.analysis_thinking,
        analysis_injected_requirements: analysisInjectedRequirements || undefined,
        analysis_file_id: analysisDataFile?.id,
        run_history: runHistory,
        final_world_state: worldState,
      });
      setAnalysisOutput(result);
      setComparisonReport(null);
      message.success('分析完成');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '分析失败');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleLoadSession = (session: LLMExperimentSessionRecord) => {
    setLatestBuild({
      session_id: session.id,
      paper_id: session.paper_id,
      experiment_design: session.experiment_design,
      analysis_thinking: session.analysis_thinking,
      simulation_draft: session.simulation_reviewed,
      simulation_reviewed: session.simulation_reviewed,
      checker_notes: session.checker_notes,
      analysis_code_seed: session.analysis_code_seed,
      created_agent_ids: session.created_agent_ids || [],
      created_at: session.created_at,
    });
    setRequirements(session.requirements || '');
    setGoal(session.experiment_goal || '');
    if (session.paper_id) {
      setSelectedPaperId(session.paper_id);
    }
    setEditableSimulation(toEditableSimulation(session.simulation_reviewed));
    setAnalysisOutput(session.latest_analysis || null);
    setComparisonReport(session.latest_comparison_report ? { report: session.latest_comparison_report } : null);
    setAnalysisInjectedRequirements(session.latest_analysis_injected_requirements || '');
    setComparisonRequirements(session.latest_compare_requirements || '');
    resetRunnerBySimulation(session.simulation_reviewed);
    message.success('会话已加载');
  };

  const handleGenerateComparisonReport = async () => {
    if (!latestBuild || !analysisOutput) {
      message.warning('请先完成分析，再生成比较报告');
      return;
    }
    setGeneratingComparison(true);
    try {
      const report = await generateComparisonReport({
        session_id: latestBuild.session_id,
        paper_id: latestBuild.paper_id,
        requirements,
        compare_requirements: comparisonRequirements || undefined,
        analysis_result: analysisOutput.analysis_result,
        analysis_conclusion: analysisOutput.conclusion,
      });
      setComparisonReport(report);
      message.success('比较报告生成完成');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '比较报告生成失败');
    } finally {
      setGeneratingComparison(false);
    }
  };

  const uploadProps: UploadProps = {
    showUploadList: false,
    accept: '.pdf,.txt,.md,.docx,.csv,.json',
    customRequest: async (options) => {
      const f = options.file as File;
      setUploading(true);
      try {
        const res = await uploadExperimentPaper(f);
        message.success(`上传成功：${res.paper.title}`);
        await refreshPapers();
        setSelectedPaperId(res.paper.id);
        options.onSuccess?.(res);
      } catch (e: any) {
        message.error(e?.response?.data?.detail || '上传失败');
        options.onError?.(e);
      } finally {
        setUploading(false);
      }
    },
  };

  const analysisDataUploadProps: UploadProps = {
    showUploadList: false,
    accept: '.csv,.txt,.json',
    customRequest: async (options) => {
      const f = options.file as File;
      setUploadingAnalysisData(true);
      try {
        const res = await uploadAnalysisDataFile(f);
        setAnalysisDataFile(res.file);
        message.success(`分析数据上传成功：${res.file.file_name}`);
        options.onSuccess?.(res);
      } catch (e: any) {
        message.error(e?.response?.data?.detail || '分析数据上传失败');
        options.onError?.(e);
      } finally {
        setUploadingAnalysisData(false);
      }
    },
  };

  const updateEditableSimulation = useCallback((updater: (prev: Simulation) => Simulation) => {
    setEditableSimulation((prev) => {
      if (!prev) return prev;
      return updater(prev);
    });
  }, []);

  const syncLatestBuildSimulation = useCallback((nextSimulation: Simulation) => {
    setLatestBuild((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        simulation_reviewed: nextSimulation,
      };
    });
  }, []);

  const handleSimulationNameChange = (value: string) => {
    updateEditableSimulation((prev) => {
      const next = { ...prev, name: value };
      syncLatestBuildSimulation(next);
      return next;
    });
  };

  const handleSimulationDescriptionChange = (value: string) => {
    updateEditableSimulation((prev) => {
      const next = { ...prev, description: value };
      syncLatestBuildSimulation(next);
      return next;
    });
  };

  const handleSimulationVariablesChange = (variables: WorldVariable[]) => {
    updateEditableSimulation((prev) => {
      const next = { ...prev, variables };
      syncLatestBuildSimulation(next);
      return next;
    });
  };

  const handleSimulationStepsChange = (steps: SimulationStep[]) => {
    updateEditableSimulation((prev) => {
      const next = { ...prev, steps };
      syncLatestBuildSimulation(next);
      return next;
    });
  };

  const stepsTotal = editableSimulation?.steps?.length || 0;
  const stepIndexById = useMemo(() => {
    const map = new Map<string, number>();
    (editableSimulation?.steps || []).forEach((step, idx) => {
      if (step?.id) map.set(step.id, idx + 1);
    });
    return map;
  }, [editableSimulation]);

  const paperTitleMap = useMemo(() => {
    const map = new Map<string, string>();
    papers.forEach((p) => map.set(p.id, p.title));
    return map;
  }, [papers]);

  const historicalPaperOptions = useMemo(() => {
    const seen = new Set<string>();
    const out: Array<{ value: string; label: string }> = [];
    sessions.forEach((s) => {
      const pid = s.paper_id;
      if (!pid || seen.has(pid)) return;
      seen.add(pid);
      out.push({
        value: pid,
        label: `${s.paper_title || paperTitleMap.get(pid) || pid}（来自历史会话）`,
      });
    });
    return out;
  }, [sessions, paperTitleMap]);

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Space align="center">
            <ExperimentOutlined style={{ fontSize: 24 }} />
            <div>
              <Title level={3} style={{ margin: 0 }}>LLM 实验工作台</Title>
              <Text type="secondary">四模块流水线：设计AI → 创作Agent组 → 检查AI → 结果分析</Text>
            </div>
          </Space>
        </Col>
        <Col>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={refreshPapers} loading={loadingPapers}>刷新论文</Button>
            <Button icon={<HistoryOutlined />} onClick={refreshSessions}>刷新会话</Button>
          </Space>
        </Col>
      </Row>

      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col xs={24} lg={16}>
            <Steps
              current={latestBuild ? 4 : 0}
              items={[
                { title: '模拟创作AI', description: '生成完整实验设计+分析思路' },
                { title: '创作Agent组', description: '生成 simulation 结构' },
                { title: '检查AI', description: '审查并改进 simulation' },
                { title: '分析模块', description: '根据运行结果生成分析' },
                { title: '比较报告AI', description: '对照原文与分析结果输出比较报告' },
              ]}
            />
          </Col>
          <Col xs={24} lg={8}>
            <Alert
              type="info"
              showIcon
              message="你可以先上传论文，再输入要求，一键生成完整实验。"
              style={{ marginTop: 4 }}
            />
          </Col>
        </Row>
      </Card>

      <Row gutter={16}>
        <Col xs={24} xl={16}>
          <Card title="1) 实验输入" style={{ marginBottom: 16 }}>
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <Space wrap>
                <Upload {...uploadProps}>
                  <Button icon={<UploadOutlined />} loading={uploading}>上传论文</Button>
                </Upload>
                <Select
                  value={selectedPaperId}
                  onChange={setSelectedPaperId}
                  placeholder="选择已上传论文"
                  style={{ minWidth: 280 }}
                  options={papers.map((paper) => ({
                    value: paper.id,
                    label: `${paper.title} (${new Date(paper.created_at * 1000).toLocaleString()})`,
                  }))}
                />
                <Select
                  value={selectedPaperId}
                  onChange={setSelectedPaperId}
                  placeholder="或从历史会话选论文"
                  style={{ minWidth: 280 }}
                  options={historicalPaperOptions}
                  allowClear
                />
                <Tag color="blue">论文数: {papers.length}</Tag>
              </Space>

              <Input
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                placeholder="实验目标（可选）"
              />
              <TextArea
                value={requirements}
                onChange={(e) => setRequirements(e.target.value)}
                autoSize={{ minRows: 4, maxRows: 8 }}
                placeholder="请输入你的实验要求（建议详细描述：对象、变量、评价指标、期望结论）"
              />
              <TextArea
                value={constraints}
                onChange={(e) => setConstraints(e.target.value)}
                autoSize={{ minRows: 2, maxRows: 6 }}
                placeholder="约束条件（可选）：如固定参数范围、必须包含对照组等"
              />

              <Button
                type="primary"
                icon={<RobotOutlined />}
                loading={solving}
                onClick={handleSolve}
                size="large"
              >
                运行四模块生成实验
              </Button>
            </Space>
          </Card>

          <Card title="2) 生成结果" style={{ marginBottom: 16 }}>
            {!latestBuild ? (
              <Empty description="尚未生成实验" />
            ) : (
              <Collapse
                defaultActiveKey={['design', 'sim', 'checker']}
                items={[
                  {
                    key: 'design',
                    label: '实验设计与分析思路（模块1）',
                    children: (
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{latestBuild.experiment_design}</Paragraph>
                        <Divider style={{ margin: '8px 0' }} />
                        <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{latestBuild.analysis_thinking}</Paragraph>
                      </Space>
                    ),
                  },
                  {
                    key: 'sim',
                    label: 'Simulation 配置（模块2+3）',
                    children: (
                      <Space direction="vertical" style={{ width: '100%' }} size="middle">
                        <Alert
                          type="info"
                          showIcon
                          message="此处可直接按 Simulation 页面方式编辑变量和步骤；修改后点击下方重置即可按新配置重新运行。"
                        />
                        <Input
                          addonBefore="Simulation Name"
                          value={editableSimulation?.name}
                          onChange={(e) => handleSimulationNameChange(e.target.value)}
                          placeholder="Simulation Name"
                        />
                        <TextArea
                          value={editableSimulation?.description}
                          onChange={(e) => handleSimulationDescriptionChange(e.target.value)}
                          autoSize={{ minRows: 2, maxRows: 6 }}
                          placeholder="Simulation Description"
                        />

                        <Collapse
                          defaultActiveKey={['vars', 'steps']}
                          items={[
                            {
                              key: 'vars',
                              label: 'World State Variables',
                              children: (
                                <VariableManager
                                  variables={(editableSimulation?.variables || []) as WorldVariable[]}
                                  onChange={handleSimulationVariablesChange}
                                />
                              ),
                            },
                            {
                              key: 'steps',
                              label: 'Simulation Steps',
                              children: (
                                <StepList
                                  steps={editableSimulation?.steps || []}
                                  onChange={handleSimulationStepsChange}
                                  agents={availableAgents}
                                  variables={(editableSimulation?.variables || []) as WorldVariable[]}
                                />
                              ),
                            },
                          ]}
                        />
                      </Space>
                    ),
                  },
                  {
                    key: 'checker',
                    label: '检查AI改进说明（模块3）',
                    children: <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{latestBuild.checker_notes}</Paragraph>,
                  },
                ]}
              />
            )}
          </Card>

          <Card title="3) Simulation 运行（Simulation 风格执行面板）" style={{ marginBottom: 16 }}>
            {!editableSimulation ? (
              <Empty description="请先生成 simulation" />
            ) : (
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                <Alert
                  type="success"
                  showIcon
                  message={`${editableSimulation.name} · 步骤进度 ${Math.min(currentStepIndex, stepsTotal)}/${stepsTotal}`}
                />

                <Row gutter={16}>
                  <Col xs={24} lg={9}>
                    <Card size="small" title="Execution" style={{ height: '100%' }}>
                      <Space direction="vertical" style={{ width: '100%' }} size="middle">
                        <Space wrap>
                          <Button
                            type="primary"
                            icon={<PlayCircleOutlined />}
                            onClick={handleRunOneStep}
                            loading={runningOneStep}
                            disabled={currentStepIndex >= stepsTotal || autoRunning}
                          >
                            Run Next Step
                          </Button>
                          {!autoRunning ? (
                            <Button icon={<FastForwardOutlined />} onClick={() => setAutoRunning(true)} disabled={currentStepIndex >= stepsTotal}>
                              Run All
                            </Button>
                          ) : (
                            <Button icon={<PauseCircleOutlined />} danger onClick={() => setAutoRunning(false)}>
                              Pause
                            </Button>
                          )}
                          <Button icon={<ReloadOutlined />} onClick={() => resetRunnerBySimulation(editableSimulation)}>
                            Reset / Start
                          </Button>
                          <Button icon={<SaveOutlined />} onClick={handleSaveRun}>
                            Save Run
                          </Button>
                        </Space>

                        <Collapse
                          defaultActiveKey={['state']}
                          items={[
                            {
                              key: 'state',
                              label: <Text strong>Current World State</Text>,
                              children: (
                                <pre style={{ margin: 0, fontSize: 12, maxHeight: 300, overflow: 'auto' }}>
                                  {JSON.stringify(worldState, null, 2)}
                                </pre>
                              ),
                            },
                          ]}
                        />
                      </Space>
                    </Card>
                  </Col>

                  <Col xs={24} lg={15}>
                    <Card size="small" title="Run History Stream">
                      <div style={{ maxHeight: 520, overflowY: 'auto', background: '#f5f5f5', padding: 12, borderRadius: 8 }}>
                        {runHistory.length === 0 ? (
                          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚无运行历史" />
                        ) : (
                          runHistory.map((item, i) => {
                            const resolvedStep = item.step_id ? stepIndexById.get(item.step_id) : undefined;
                            const stepLabel = resolvedStep || i + 1;
                            return (
                              <div
                                key={`${item.step_id || 'step'}-${i}`}
                                style={{ marginBottom: 14, background: '#fff', padding: 10, borderRadius: 6, border: '1px solid #e8e8e8' }}
                              >
                                <div style={{ fontWeight: 'bold', color: '#1890ff', marginBottom: 6 }}>
                                  {item.agent_name || 'Unknown Agent'}{' '}
                                  <span style={{ fontSize: '0.8em', color: '#999' }}>(Step {stepLabel})</span>
                                </div>

                                {item.prompt && (
                                  <div style={{ marginBottom: 8, padding: 8, background: '#f0f2f5', borderRadius: 4, borderLeft: '3px solid #1890ff' }}>
                                    <Text strong style={{ fontSize: '0.9em', color: '#555' }}>Prompt:</Text>
                                    <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.9em', color: '#333' }}>{item.prompt}</div>
                                  </div>
                                )}

                                {renderExecutionContent(item.content || '')}
                              </div>
                            );
                          })
                        )}
                      </div>
                    </Card>
                  </Col>
                </Row>
              </Space>
            )}
          </Card>

          <Card title="4) 实验后续分析（模块4）">
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <Alert
                type="info"
                showIcon
                message="分析AI将读取：论文原文 + 模拟运行历史 + 世界变量 + 自动生成并绑定的CSV（可手动覆盖）+ 你注入的额外要求。"
              />

              <Space wrap>
                <Upload {...analysisDataUploadProps}>
                  <Button icon={<UploadOutlined />} loading={uploadingAnalysisData}>上传模拟导出CSV</Button>
                </Upload>
                <Tag color={autoRepairEnabled ? 'blue' : 'default'}>
                  自动修复：{autoRepairEnabled ? '开启' : '关闭'}
                </Tag>
                {analysisDataFile ? (
                  <Tag color="green">已绑定分析数据：{analysisDataFile.file_name}</Tag>
                ) : (
                  <Tag>未上传分析数据文件</Tag>
                )}
              </Space>

              <TextArea
                value={analysisInjectedRequirements}
                onChange={(e) => setAnalysisInjectedRequirements(e.target.value)}
                autoSize={{ minRows: 2, maxRows: 6 }}
                placeholder="分析阶段注入要求（可选），例如：优先比较缺货成本变化并给出可落地阈值建议。"
              />

              <Button
                type="primary"
                icon={<LineChartOutlined />}
                loading={analyzing}
                onClick={handleAnalyze}
                disabled={!latestBuild}
              >
                生成分析代码并执行分析
              </Button>

              {!analysisOutput ? (
                <Empty description="尚未执行分析" />
              ) : (
                <Collapse
                  defaultActiveKey={['code', 'result', 'conclusion']}
                  items={[
                    {
                      key: 'code',
                      label: '分析代码',
                      children: <TextArea readOnly autoSize={{ minRows: 8, maxRows: 20 }} value={analysisOutput.analysis_code} />,
                    },
                    {
                      key: 'result',
                      label: '分析输出',
                      children: (
                        <Space direction="vertical" style={{ width: '100%' }}>
                          <Text strong>stdout</Text>
                          <TextArea readOnly autoSize={{ minRows: 4, maxRows: 12 }} value={analysisOutput.analysis_stdout} />
                          <Text strong>analysis_result</Text>
                          <TextArea readOnly autoSize={{ minRows: 6, maxRows: 14 }} value={pretty(analysisOutput.analysis_result)} />
                        </Space>
                      ),
                    },
                    {
                      key: 'conclusion',
                      label: '结论',
                      children: <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{analysisOutput.conclusion}</Paragraph>,
                    },
                  ]}
                />
              )}
            </Space>
          </Card>

          <Card title="5) 比较报告AI（读取原文+分析结果）" style={{ marginTop: 16 }}>
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <TextArea
                value={comparisonRequirements}
                onChange={(e) => setComparisonRequirements(e.target.value)}
                autoSize={{ minRows: 2, maxRows: 6 }}
                placeholder="比较报告附加要求（可选），例如：重点比较论文结论与本次实验在库存波动上的差异。"
              />
              <Button
                icon={<FileSearchOutlined />}
                type="primary"
                loading={generatingComparison}
                onClick={handleGenerateComparisonReport}
                disabled={!analysisOutput || !latestBuild}
              >
                生成比较报告
              </Button>

              {!comparisonReport ? (
                <Empty description="尚未生成比较报告" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{comparisonReport.report}</Paragraph>
              )}
            </Space>
          </Card>
        </Col>

        <Col xs={24} xl={8}>
          <Card
            title="已保存会话"
            extra={<Button size="small" icon={<ReloadOutlined />} onClick={refreshSessions}>刷新</Button>}
          >
            {sessions.length === 0 ? (
              <Empty description="暂无会话" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <List
                dataSource={sessions}
                renderItem={(item) => (
                  <List.Item
                    actions={[
                      <Button
                        size="small"
                        onClick={() => item.paper_id && setSelectedPaperId(item.paper_id)}
                        disabled={!item.paper_id}
                      >
                        选论文
                      </Button>,
                      <Button size="small" onClick={() => handleLoadSession(item)}>
                        加载
                      </Button>,
                    ]}
                  >
                    <List.Item.Meta
                      title={<Text strong>{item.experiment_goal || '未命名实验目标'}</Text>}
                      description={
                        <Space direction="vertical" size={2}>
                          <Text type="secondary">{new Date(item.created_at * 1000).toLocaleString()}</Text>
                          <Tag color="geekblue" style={{ width: 'fit-content' }}>
                            论文: {item.paper_title || (item.paper_id ? (paperTitleMap.get(item.paper_id) || item.paper_id) : '未绑定')}
                          </Tag>
                          <Text ellipsis style={{ maxWidth: 260 }}>{item.requirements}</Text>
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>

          <Card title="运行状态" style={{ marginTop: 16 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text>论文加载：{loadingPapers ? <Spin size="small" /> : '就绪'}</Text>
              <Text>实验生成：{solving ? <Spin size="small" /> : '就绪'}</Text>
              <Text>模拟运行：{runningOneStep || autoRunning ? <Spin size="small" /> : '就绪'}</Text>
              <Text>结果分析：{analyzing ? <Spin size="small" /> : '就绪'}</Text>
              <Text>分析数据上传：{uploadingAnalysisData ? <Spin size="small" /> : '就绪'}</Text>
              <Text>比较报告生成：{generatingComparison ? <Spin size="small" /> : '就绪'}</Text>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default LLMReplacementExperiment;
