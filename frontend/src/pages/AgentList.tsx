import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Modal, Input, message, Form, Select } from 'antd';
import { getAgents, chatWithAgent, deleteAgent, updateAgent, duplicateAgent, type Agent } from '../api/agent';
import { useNavigate } from 'react-router-dom';

const AgentList: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const navigate = useNavigate();
  const [chatModalOpen, setChatModalOpen] = useState(false);
  const [currentAgent, setCurrentAgent] = useState<Agent | null>(null);
  const [chatMessages, setChatMessages] = useState<{role: string, content: string}[]>([]);
  const [inputMsg, setInputMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');

  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    try {
      const data = await getAgents();
      setAgents(data);
    } catch (error) {
      message.error('Failed to load agents');
    }
  };

  const handleChat = (agent: Agent) => {
      setCurrentAgent(agent);
      setChatMessages([]);
      setChatModalOpen(true);
  }

  const handleDelete = (id: string) => {
      Modal.confirm({
          title: 'Are you sure you want to delete this agent?',
          content: 'This action cannot be undone.',
          onOk: async () => {
              try {
                  await deleteAgent(id);
                  message.success('Agent deleted');
                  loadAgents();
              } catch (e) {
                  message.error('Failed to delete agent');
              }
          }
      });
  };

  const handleEdit = (agent: Agent) => {
      setEditingAgent(agent);
      form.setFieldsValue(agent);
      setEditModalOpen(true);
  };

  const handleDuplicate = async (agent: Agent) => {
      try {
          await duplicateAgent(agent.id);
          message.success('Agent duplicated');
          loadAgents();
      } catch (e) {
          message.error('Failed to duplicate agent');
      }
  };

  const saveEdit = async () => {
      try {
          const values = await form.validateFields();
          if (editingAgent) {
              await updateAgent(editingAgent.id, values);
              message.success('Agent updated');
              setEditModalOpen(false);
              loadAgents();
          }
      } catch (e) {
          message.error('Failed to update agent');
      }
  };

  const sendChat = async () => {
      if(!currentAgent || !inputMsg) return;
      const newMsgs = [...chatMessages, {role: 'user', content: inputMsg}];
      setChatMessages(newMsgs);
      setInputMsg('');
      setLoading(true);
      try {
          const res = await chatWithAgent(currentAgent.id, newMsgs);
          const content = res.content || JSON.stringify(res);
          setChatMessages([...newMsgs, {role: 'assistant', content: content}]);
      } catch(e) {
          message.error("Chat failed");
      } finally {
          setLoading(false);
      }
  }

  const columns = [
    { title: 'Name', dataIndex: 'name', key: 'name', sorter: (a: Agent, b: Agent) => a.name.localeCompare(b.name) },
    { title: 'Provider', dataIndex: 'provider', key: 'provider' },
    { title: 'Model', dataIndex: 'model', key: 'model' },
    {
      title: 'Action',
      key: 'action',
      render: (_: any, record: Agent) => (
        <Space size="middle">
          <Button onClick={() => navigate(`/agent/${record.id}`)}>Details</Button>
          <Button onClick={() => handleChat(record)}>Chat</Button>
          <Button onClick={() => handleEdit(record)}>Edit</Button>
          <Button onClick={() => handleDuplicate(record)}>Copy</Button>
          <Button danger onClick={() => handleDelete(record.id)}>Delete</Button>
        </Space>
      ),
    },
  ];

  const filteredAgents = agents.filter(a => 
    a.name.toLowerCase().includes(searchText.toLowerCase()) || 
    (a.model && a.model.toLowerCase().includes(searchText.toLowerCase()))
  );

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
            <h2 style={{ marginRight: 20, marginBottom: 0 }}>Agents ({agents.length})</h2>
            <Input 
                placeholder="Search name or model..." 
                value={searchText} 
                onChange={e => setSearchText(e.target.value)} 
                style={{ width: 250 }} 
                allowClear
            />
        </div>
        <Button type="primary" onClick={() => navigate('/create')}>Create Agent</Button>
      </div>
      <Table 
        columns={columns} 
        dataSource={filteredAgents} 
        rowKey="id" 
        pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'] }}
      />
      
      <Modal 
        title={`Chat with ${currentAgent?.name}`} 
        open={chatModalOpen} 
        onCancel={() => setChatModalOpen(false)}
        footer={null}
        width={800}
      >
          <div style={{height: '400px', overflowY: 'auto', border: '1px solid #eee', padding: '10px', marginBottom: '10px'}}>
              {chatMessages.map((m, i) => (
                  <div key={i} style={{marginBottom: '10px', textAlign: m.role === 'user' ? 'right' : 'left'}}>
                      <div style={{display: 'inline-block', padding: '8px', background: m.role === 'user' ? '#1890ff' : '#f0f0f0', color: m.role === 'user' ? '#fff' : '#000', borderRadius: '4px'}}>
                          {m.content}
                      </div>
                  </div>
              ))}
          </div>
          <div style={{display: 'flex'}}>
              <Input value={inputMsg} onChange={e => setInputMsg(e.target.value)} onPressEnter={sendChat} disabled={loading}/>
              <Button type="primary" onClick={sendChat} loading={loading} style={{marginLeft: '10px'}}>Send</Button>
          </div>
      </Modal>

      <Modal
        title="Edit Agent"
        open={editModalOpen}
        onOk={saveEdit}
        onCancel={() => setEditModalOpen(false)}
      >
          <Form form={form} layout="vertical">
              <Form.Item name="name" label="Name" rules={[{ required: true }]}>
                  <Input />
              </Form.Item>
              <Form.Item name="model" label="Model" rules={[{ required: true }]}>
                  <Input />
              </Form.Item>
              <Form.Item name="provider" label="Provider" rules={[{ required: true }]}>
                  <Select>
                      <Select.Option value="deepseek">DeepSeek</Select.Option>
                      <Select.Option value="zhipu">Zhipu</Select.Option>
                      <Select.Option value="custom">Custom</Select.Option>
                  </Select>
              </Form.Item>
              <Form.Item name="base_url" label="Base URL">
                  <Input />
              </Form.Item>
              <Form.Item name="persona" label="Persona">
                  <Input.TextArea rows={4} />
              </Form.Item>
          </Form>
      </Modal>
    </div>
  );
};

export default AgentList;
