import React, { useState } from 'react';
import { Form, Input, Button, Card, message, Typography } from 'antd';
import { register as apiRegister, login as apiLogin } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import { useNavigate, Link } from 'react-router-dom';

const { Title } = Typography;

const Register: React.FC = () => {
    const [loading, setLoading] = useState(false);
    const { login } = useAuth();
    const navigate = useNavigate();

    const onFinish = async (values: any) => {
        setLoading(true);
        try {
            await apiRegister(values.username, values.password);
            // Auto login after register
            const data = await apiLogin(values.username, values.password);
            login(data.access_token);
            message.success('Registration successful');
            navigate('/');
        } catch (error: any) {
            console.error("Registration error:", error);
            const errorMsg = error.response?.data?.detail || error.message || 'Registration failed. Username might be taken.';
            message.error(errorMsg);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', background: '#f0f2f5' }}>
            <Card style={{ width: 400 }}>
                <div style={{ textAlign: 'center', marginBottom: 20 }}>
                    <Title level={3}>Register</Title>
                </div>
                <Form
                    name="register"
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
                            Register
                        </Button>
                    </Form.Item>
                    <div style={{ textAlign: 'center' }}>
                        Already have an account? <Link to="/login">Log in</Link>
                    </div>
                </Form>
            </Card>
        </div>
    );
};

export default Register;
