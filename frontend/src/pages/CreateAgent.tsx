import React, { useState } from 'react';
import { Form, Input, Button, Select, message, Card } from 'antd';
import { createAgent, generateAdapter } from '../api/agent';
import { useNavigate } from 'react-router-dom';

const { Option } = Select;
const { TextArea } = Input;

const CreateAgent: React.FC = () => {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [provider, setProvider] = useState('deepseek');
  const [generating, setGenerating] = useState(false);
  const [generatedCode, setGeneratedCode] = useState('');
  const [inputModality, setInputModality] = useState('text');
  const [outputModality, setOutputModality] = useState('text');

  const onFinish = async (values: any) => {
    try {
      // If provider is custom, we use the generated code as the "usage_example" (which acts as the script)
      // or we should have a separate field. For now, let's put it in usage_example if custom.
      const payload = { ...values };
      if (provider === 'custom') {
          if (!generatedCode) {
              message.error("Please generate the adapter code first!");
              return;
          }
          payload.usage_example = generatedCode; 
      }
      
      await createAgent(payload);
      message.success('Agent created successfully');
      navigate('/');
    } catch (error) {
      message.error('Failed to create agent');
    }
  };

  const handleGenerate = async () => {
      const values = form.getFieldsValue(['model', 'base_url', 'usage_example', 'api_key']);
      if(!values.usage_example) {
          message.error("Please provide a usage example");
          return;
      }
      setGenerating(true);
      try {
        const res = await generateAdapter(values.model, values.base_url, values.usage_example, values.api_key, inputModality, outputModality);
          setGeneratedCode(res.generated_code);
          message.success("Code generated!");
      } catch(e) {
          const err: any = e;
          const detail = err?.response?.data?.detail || err?.response?.data?.message;
          message.error(detail || "Generation failed");
      } finally {
          setGenerating(false);
      }
  }

  return (
    <Card title="Create New Agent" style={{ maxWidth: 800, margin: '0 auto' }}>
      <Form form={form} layout="vertical" onFinish={onFinish} initialValues={{ provider: 'deepseek' }}>
        <Form.Item name="name" label="Agent Name" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        
        <Form.Item name="provider" label="Provider" rules={[{ required: true }]}>
          <Select onChange={setProvider}>
            <Option value="deepseek">DeepSeek</Option>
            <Option value="zhipu">Zhipu AI</Option>
            <Option value="custom">Custom (Generate Adapter)</Option>
          </Select>
        </Form.Item>

        <Form.Item name="model" label="Model Name" rules={[{ required: true }]}>
          <Input placeholder="e.g. deepseek-chat or my-custom-model" />
        </Form.Item>

        <Form.Item name="persona" label="Persona / System Prompt" help="Define the personality and role of this agent.">
          <TextArea rows={4} placeholder="You are a helpful assistant..." />
        </Form.Item>

        <Form.Item name="base_url" label="Base URL">
          <Input placeholder="Optional for standard providers" />
        </Form.Item>

        <Form.Item name="api_key" label="API Key">
          <Input.Password />
        </Form.Item>

        {provider === 'custom' && (
            <>
                <div style={{ display: 'flex', gap: '16px', marginBottom: '0px' }}>
                    <Form.Item label="Input Modality" style={{ flex: 1 }}>
                        <Select value={inputModality} onChange={setInputModality}>
                            <Option value="text">Text Only</Option>
                            <Option value="text_image">Text + Image (Multimodal)</Option>
                            <Option value="audio">Audio (Speech-to-Text / Audio Analysis)</Option>
                        </Select>
                    </Form.Item>
                    <Form.Item label="Output Modality" style={{ flex: 1 }}>
                        <Select value={outputModality} onChange={setOutputModality}>
                            <Option value="text">Text</Option>
                            <Option value="image">Image URL</Option>
                            <Option value="video">Video (Async Task)</Option>
                            <Option value="audio">Audio (Text-to-Speech)</Option>
                        </Select>
                    </Form.Item>
                </div>

                <Form.Item name="usage_example" label="Usage Example (cURL or Python)" help="Paste an example of how to call this API.">
                    <TextArea rows={6} />
                </Form.Item>
                <Button onClick={handleGenerate} loading={generating} style={{marginBottom: '20px'}}>
                    Generate Adapter Code
                </Button>
                
                {generatedCode && (
                    <Form.Item label="Generated Adapter Code">
                        <TextArea value={generatedCode} rows={10} onChange={e => setGeneratedCode(e.target.value)} />
                    </Form.Item>
                )}
            </>
        )}

        <Form.Item>
          <Button type="primary" htmlType="submit">
            Create Agent
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
};

export default CreateAgent;
