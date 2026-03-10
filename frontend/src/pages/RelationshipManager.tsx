import React, { useEffect, useState, useCallback } from 'react';
import { ReactFlow, Background, Controls, MiniMap, useNodesState, useEdgesState, type Connection, type Edge, type Node, MarkerType } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Select, Button, Card, message, Form, Input } from 'antd';
import { getAgents, getRelationships, createRelationship, deleteRelationship, type Agent, type Relationship } from '../api/agent';

const { Option } = Select;

const RelationshipManager: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  
  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const [form] = Form.useForm();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [agentsData, relsData] = await Promise.all([getAgents(), getRelationships()]);
      setAgents(agentsData);
      updateGraph(agentsData, relsData);
    } catch (error) {
      message.error("Failed to load data");
    }
  };

  const updateGraph = (agentsList: Agent[], relsList: Relationship[]) => {
    // Layout nodes in a circle or grid
    const newNodes: Node[] = agentsList.map((agent, index) => ({
      id: agent.id,
      data: { label: agent.name },
      position: { x: 250 + Math.cos(index) * 200, y: 250 + Math.sin(index) * 200 }, // Simple circular layout
      style: { background: '#fff', border: '1px solid #777', padding: 10, borderRadius: 5, width: 150, textAlign: 'center' }
    }));

    const newEdges: Edge[] = relsList.map(rel => ({
      id: rel.id,
      source: rel.source_agent_id,
      target: rel.target_agent_id,
      label: rel.relationship_type,
      type: 'smoothstep',
      markerEnd: { type: MarkerType.ArrowClosed },
      animated: true,
    }));

    setNodes(newNodes);
    setEdges(newEdges);
  };

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const onConnect = useCallback(async (_params: Connection) => {
      // This is for drag-and-drop connections, but we'll use the form for explicit typing
      message.info("Please use the form to add typed relationships.");
  }, []);

  const handleAddRelationship = async (values: any) => {
      try {
          await createRelationship(values);
          message.success("Relationship added");
          form.resetFields();
          fetchData();
      } catch(e) {
          message.error("Failed to add relationship");
      }
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const onEdgeClick = async (_event: React.MouseEvent, edge: Edge) => {
      if(window.confirm(`Delete relationship '${edge.label}'?`)) {
          try {
              await deleteRelationship(edge.id);
              message.success("Deleted");
              fetchData();
          } catch(e) {
              message.error("Failed to delete");
          }
      }
  }

  return (
    <div style={{ height: '80vh', display: 'flex', flexDirection: 'column' }}>
      <Card title="Relationship Manager" style={{ marginBottom: 20 }}>
        <Form layout="inline" form={form} onFinish={handleAddRelationship}>
            <Form.Item name="source_agent_id" rules={[{required: true, message: 'Select source'}]}>
                <Select placeholder="Source Agent" style={{width: 200}}>
                    {agents.map(a => <Option key={a.id} value={a.id}>{a.name}</Option>)}
                </Select>
            </Form.Item>
            <Form.Item name="relationship_type" rules={[{required: true, message: 'Enter type'}]}>
                <Input placeholder="Type (e.g. Teacher, Parent)" />
            </Form.Item>
            <Form.Item name="target_agent_id" rules={[{required: true, message: 'Select target'}]}>
                <Select placeholder="Target Agent" style={{width: 200}}>
                    {agents.map(a => <Option key={a.id} value={a.id}>{a.name}</Option>)}
                </Select>
            </Form.Item>
            <Form.Item>
                <Button type="primary" htmlType="submit">Add Relationship</Button>
            </Form.Item>
        </Form>
      </Card>
      
      <div style={{ flex: 1, border: '1px solid #ddd', borderRadius: '8px' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onEdgeClick={onEdgeClick}
          fitView
        >
          <Controls />
          <MiniMap />
          <Background gap={12} size={1} />
        </ReactFlow>
      </div>
      <div style={{marginTop: 10, color: '#666'}}>
          * Click on a connection line to delete it.
      </div>
    </div>
  );
};

export default RelationshipManager;
