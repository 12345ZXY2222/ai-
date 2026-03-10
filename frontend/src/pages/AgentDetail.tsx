import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Tabs, List, Input, Button, message, Card, Typography, Upload, Form, Select, Checkbox, Popconfirm } from 'antd';
import { UploadOutlined, SaveOutlined, ReloadOutlined } from '@ant-design/icons';
import { getAgent, updateAgentMemory, uploadAgentFile, updateAgent, generateAdapter, deleteAgentHistoryBatch, getAgentHistory, clearAgentHistory, injectMemory, type Agent } from '../api/agent';

const { TextArea } = Input;
const { Title, Text } = Typography;
const { Option } = Select;

const AgentHistoryViewer: React.FC<{ agentId: string }> = ({ agentId }) => {
    const [history, setHistory] = useState<any[]>([]);
    const [selectedIndices, setSelectedIndices] = useState<number[]>([]);
    const [loading, setLoading] = useState(false);

    const fetchHistory = () => {
        getAgentHistory(agentId).then(data => {
            setHistory(data);
            setSelectedIndices([]);
        });
    };

    useEffect(() => {
        fetchHistory();
    }, [agentId]);

    const handleDeleteSelected = async () => {
        if (selectedIndices.length === 0) return;
        setLoading(true);
        try {
            await deleteAgentHistoryBatch(agentId, selectedIndices);
            message.success("Selected history items deleted");
            fetchHistory();
        } catch (e) {
            message.error("Failed to delete history");
        } finally {
            setLoading(false);
        }
    };

    const handleClearAll = async () => {
        setLoading(true);
        try {
            await clearAgentHistory(agentId);
            message.success("History cleared");
            fetchHistory();
        } catch (e) {
            message.error("Failed to clear history");
        } finally {
            setLoading(false);
        }
    };

    const toggleSelect = (index: number) => {
        if (selectedIndices.includes(index)) {
            setSelectedIndices(selectedIndices.filter(i => i !== index));
        } else {
            setSelectedIndices([...selectedIndices, index]);
        }
    };

    if (!history || history.length === 0) {
        return <div style={{ padding: 20, textAlign: 'center', color: '#999' }}>No history found.</div>;
    }

    return (
        <div>
            <div style={{ marginBottom: 16, display: 'flex', gap: 10 }}>
                <Button 
                    danger 
                    disabled={selectedIndices.length === 0} 
                    onClick={handleDeleteSelected}
                    loading={loading}
                >
                    Delete Selected ({selectedIndices.length})
                </Button>
                <Popconfirm title="Are you sure you want to clear ALL history?" onConfirm={handleClearAll}>
                    <Button danger type="dashed" loading={loading}>Clear All</Button>
                </Popconfirm>
            </div>
            <List
                bordered
                dataSource={history}
                renderItem={(item, index) => (
                    <List.Item>
                        <Checkbox 
                            checked={selectedIndices.includes(index)} 
                            onChange={() => toggleSelect(index)}
                            style={{ marginRight: 15 }}
                        />
                        <List.Item.Meta
                            title={item.role === 'user' ? 'User' : 'Agent'}
                            description={
                                <div>
                                    {item.prompt && (
                                        <div style={{ marginBottom: 8, padding: 8, background: '#f0f2f5', borderRadius: 4 }}>
                                            <Text strong>Prompt/Question:</Text>
                                            <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.9em' }}>{item.prompt}</div>
                                        </div>
                                    )}
                                    {item.memory_context && (
                                        <div style={{ marginBottom: 8, padding: 8, background: '#fffbe6', borderRadius: 4 }}>
                                            <Text strong>Memory Context:</Text>
                                            <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.85em', color: '#666', maxHeight: '100px', overflowY: 'auto' }}>{item.memory_context}</div>
                                        </div>
                                    )}
                                    <div style={{ whiteSpace: 'pre-wrap' }}>{item.content}</div>
                                </div>
                            }
                        />
                        {item.timestamp && <div style={{ fontSize: '0.8em', color: '#999' }}>{new Date(item.timestamp * 1000).toLocaleString()}</div>}
                    </List.Item>
                )}
            />
        </div>
    );
};

const AgentDetail: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const [agent, setAgent] = useState<Agent | null>(null);
    const [memoryInput, setMemoryInput] = useState('');
    const [loading, setLoading] = useState(false);
    
    // Edit Form State
    const [form] = Form.useForm();
    const [provider, setProvider] = useState('');
    
    // Generator State
    const [genLoading, setGenLoading] = useState(false);
    const [inputModality, setInputModality] = useState('text');
    const [outputModality, setOutputModality] = useState('text');
    const [rawUsageExample, setRawUsageExample] = useState('');

    useEffect(() => {
        if (id) loadAgent(id);
    }, [id]);

    const loadAgent = async (agentId: string) => {
        try {
            const data = await getAgent(agentId);
            setAgent(data);
            form.setFieldsValue(data);
            setProvider(data.provider);
        } catch (e) {
            message.error("Failed to load agent");
        }
    };

    const [memoryImportance, setMemoryImportance] = useState(1);

    const addMemory = async () => {
        if (!agent || !memoryInput) return;
        setLoading(true);
        try {
            // Use injectMemory API instead of direct update to support importance/vector DB
            await injectMemory(agent.id, memoryInput, memoryImportance);
            
            // Refresh agent to see new memory list
            loadAgent(agent.id);
            
            setMemoryInput('');
            setMemoryImportance(1);
            message.success("Memory injected successfully");
        } catch (e) {
            message.error("Failed to inject memory");
        } finally {
            setLoading(false);
        }
    };

    const removeMemory = async (index: number) => {
        if (!agent) return;
        const newMemory = [...(agent.long_term_memory || [])];
        newMemory.splice(index, 1);
        try {
            await updateAgentMemory(agent.id, newMemory);
            setAgent({ ...agent, long_term_memory: newMemory });
        } catch (e) {
            message.error("Failed to update memory");
        }
    };

    const handleUpdate = async (values: any) => {
        if (!agent) return;
        // Filter out empty api_key to avoid clearing it if user didn't type anything
        const payload = { ...values };
        if (!payload.api_key) {
            delete payload.api_key;
        }
        try {
            await updateAgent(agent.id, payload);
            message.success("Agent updated");
            loadAgent(agent.id);
        } catch (e) {
            message.error("Failed to update agent");
        }
    };

    const handleGenerate = async () => {
        const values = form.getFieldsValue();
        if(!rawUsageExample) {
            message.error("Please provide a usage example for generation");
            return;
        }
        setGenLoading(true);
        try {
            const res = await generateAdapter(values.model, values.base_url, rawUsageExample, values.api_key, inputModality, outputModality);
            form.setFieldsValue({ usage_example: res.generated_code });
            message.success("Code generated! Don't forget to save.");
        } catch(e) {
            const err: any = e;
            const detail = err?.response?.data?.detail || err?.response?.data?.message;
            message.error(detail || "Generation failed");
        } finally {
            setGenLoading(false);
        }
    }

    if (!agent) return <div>Loading...</div>;

    const items = [
        {
            key: '1',
            label: 'Edit Configuration',
            children: (
                <Card>
                    <Form 
                        form={form} 
                        layout="vertical" 
                        onFinish={handleUpdate}
                        initialValues={agent}
                    >
                        <div style={{ display: 'flex', gap: '20px' }}>
                            <div style={{ flex: 1 }}>
                                <Form.Item name="name" label="Name" rules={[{ required: true }]}>
                                    <Input />
                                </Form.Item>
                                <Form.Item name="provider" label="Provider">
                                    <Select onChange={setProvider}>
                                        <Option value="deepseek">DeepSeek</Option>
                                        <Option value="zhipu">Zhipu AI</Option>
                                        <Option value="custom">Custom</Option>
                                    </Select>
                                </Form.Item>
                                <Form.Item name="model" label="Model">
                                    <Input />
                                </Form.Item>
                                <Form.Item name="base_url" label="Base URL">
                                    <Input />
                                </Form.Item>
                                <Form.Item name="api_key" label="API Key">
                                    <Input.Password placeholder="Leave empty to keep unchanged" />
                                </Form.Item>
                            </div>
                            <div style={{ flex: 1 }}>
                                <Form.Item name="persona" label="Persona / System Prompt">
                                    <TextArea rows={6} />
                                </Form.Item>
                            </div>
                        </div>

                        {provider === 'custom' && (
                            <Card size="small" title="Custom Adapter Configuration" style={{ marginTop: 20, background: '#f9f9f9' }}>
                                <div style={{ display: 'flex', gap: '16px', marginBottom: '10px' }}>
                                    <div style={{ flex: 1 }}>
                                        <label>Input Modality (For Generation)</label>
                                        <Select value={inputModality} onChange={setInputModality} style={{ width: '100%' }}>
                                            <Option value="text">Text Only</Option>
                                            <Option value="text_image">Text + Image</Option>
                                            <Option value="audio">Audio</Option>
                                        </Select>
                                    </div>
                                    <div style={{ flex: 1 }}>
                                        <label>Output Modality (For Generation)</label>
                                        <Select value={outputModality} onChange={setOutputModality} style={{ width: '100%' }}>
                                            <Option value="text">Text</Option>
                                            <Option value="image">Image URL</Option>
                                            <Option value="video">Video</Option>
                                            <Option value="audio">Audio</Option>
                                        </Select>
                                    </div>
                                </div>
                                
                                <div style={{ marginBottom: 10 }}>
                                    <label>Raw Usage Example (for Code Generation):</label>
                                    <TextArea 
                                        rows={4} 
                                        value={rawUsageExample} 
                                        onChange={e => setRawUsageExample(e.target.value)} 
                                        placeholder="Paste cURL or Python example here to regenerate the adapter code..."
                                    />
                                    <Button 
                                        icon={<ReloadOutlined />} 
                                        onClick={handleGenerate} 
                                        loading={genLoading} 
                                        style={{ marginTop: 8 }}
                                    >
                                        Generate Adapter Code
                                    </Button>
                                </div>

                                <Form.Item name="usage_example" label="Adapter Code (Python)">
                                    <TextArea rows={10} style={{ fontFamily: 'monospace' }} />
                                </Form.Item>
                            </Card>
                        )}

                        <Form.Item style={{ marginTop: 20 }}>
                            <Button type="primary" htmlType="submit" icon={<SaveOutlined />}>
                                Save Changes
                            </Button>
                        </Form.Item>
                    </Form>
                </Card>
            ),
        },
        {
            key: '2',
            label: 'Long-term Memory',
            children: (
                <div>
                    <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div style={{ flex: 1 }}>
                            <TextArea 
                                rows={2} 
                                value={memoryInput} 
                                onChange={e => setMemoryInput(e.target.value)} 
                                placeholder="Add a fact (e.g. 'Alice likes apples')" 
                            />
                        </div>
                        <div style={{ width: '100px' }}>
                            <Input 
                                type="number" 
                                min={1} 
                                max={10} 
                                value={memoryImportance} 
                                onChange={e => setMemoryImportance(parseInt(e.target.value))} 
                                addonBefore="Imp"
                                title="Importance (1-10)"
                            />
                        </div>
                        <Button type="primary" onClick={addMemory} loading={loading} style={{ height: 'auto' }}>
                            Inject
                        </Button>
                    </div>
                    {(!agent.long_term_memory || agent.long_term_memory.length === 0) ? (
                        <div style={{ padding: 20, textAlign: 'center', color: '#999' }}>No memories recorded yet.</div>
                    ) : (
                        <List
                            bordered
                            dataSource={agent.long_term_memory || []}
                            renderItem={(item, index) => (
                                <List.Item actions={[<a key="delete" onClick={() => removeMemory(index)}>Delete</a>]}>
                                    {item}
                                </List.Item>
                            )}
                        />
                    )}
                </div>
            ),
        },
        {
            key: '3',
            label: 'Files',
            children: (
                <div>
                    <div style={{ marginBottom: 16 }}>
                        <Upload 
                            customRequest={async (options) => {
                                const { file, onSuccess, onError } = options;
                                try {
                                    await uploadAgentFile(agent.id, file as File);
                                    message.success(`${(file as File).name} uploaded successfully`);
                                    onSuccess?.("ok");
                                    loadAgent(agent.id); // Reload to see new file
                                } catch (err) {
                                    message.error(`${(file as File).name} upload failed.`);
                                    onError?.(err as any);
                                }
                            }}
                            showUploadList={false}
                        >
                            <Button icon={<UploadOutlined />}>Click to Upload</Button>
                        </Upload>
                    </div>
                    <List
                        header={<div>Uploaded Files</div>}
                        bordered
                        dataSource={agent.files || []}
                        renderItem={(item) => (
                            <List.Item>
                                {item}
                            </List.Item>
                        )}
                    />
                </div>
            )
        },
        {
            key: '4',
            label: 'Chat History',
            children: (
                <AgentHistoryViewer agentId={agent.id} />
            )
        }
    ];

    return (
        <div style={{ padding: 24 }}>
            <Title level={2}>{agent.name}</Title>
            <Tabs defaultActiveKey="1" items={items} />
        </div>
    );
};

export default AgentDetail;
