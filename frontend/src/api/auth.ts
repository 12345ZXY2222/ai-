import client from './client';

export const login = async (username: string, password: string) => {
    const params = new URLSearchParams();
    params.append('username', username);
    params.append('password', password);
    const response = await client.post(`/token`, params);
    return response.data;
};

export const register = async (username: string, password: string) => {
    const response = await client.post(`/register`, { username, password });
    return response.data;
};
