import React, { useState } from 'react';
import { Form, Input, Button, Card, message, Typography } from 'antd';
import { login as apiLogin } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import { useNavigate, Link } from 'react-router-dom';
import type { AxiosError } from 'axios';

const { Title } = Typography;

const Login: React.FC = () => {
    const [loading, setLoading] = useState(false);
    const { login } = useAuth();
    const navigate = useNavigate();

    const onFinish = async (values: any) => {
        setLoading(true);
        try {
            const data = await apiLogin(values.username, values.password);
            login(data.access_token);
            message.success('Login successful');
            navigate('/');
        } catch (error) {
            const err = error as AxiosError<any>;
            const detail = (err.response?.data as any)?.detail;
            message.error(detail || 'Login failed. Please check your credentials.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', background: '#f0f2f5' }}>
            <Card style={{ width: 400 }}>
                <div style={{ textAlign: 'center', marginBottom: 20 }}>
                    <Title level={3}>AI Platform Login</Title>
                </div>
                <Form
                    name="login"
                    onFinish={onFinish}
                    layout="vertical"
                >
                    <Form.Item
                        label="Username"
                        name="username"
                        rules={[{ required: true, message: 'Please input your username!' }]}
                    >
                        <Input />
                    </Form.Item>

                    <Form.Item
                        label="Password"
                        name="password"
                        rules={[{ required: true, message: 'Please input your password!' }]}
                    >
                        <Input.Password />
                    </Form.Item>

                    <Form.Item>
                        <Button type="primary" htmlType="submit" block loading={loading}>
                            Log in
                        </Button>
                    </Form.Item>
                    <div style={{ textAlign: 'center' }}>
                        Or <Link to="/register">register now!</Link>
                    </div>
                </Form>
            </Card>
        </div>
    );
};

export default Login;
