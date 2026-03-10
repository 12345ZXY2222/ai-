import axios from 'axios';

const client = axios.create({
    baseURL: '/api',
});

client.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

client.interceptors.response.use(
    (response) => response,
    (error) => {
        // Only redirect to login if it's a 401 AND we are not already on the login or register page
        // And avoid redirecting if the 401 is from the login endpoint itself (invalid credentials)
        if (error.response && error.response.status === 401) {
             const isAuthPage = window.location.pathname === '/login' || window.location.pathname === '/register';
             const isAuthEndpoint = error.config.url.includes('/token') || error.config.url.includes('/register');
             
             if (!isAuthPage && !isAuthEndpoint) {
                localStorage.removeItem('token');
                window.location.href = '/login';
             }
        }
        return Promise.reject(error);
    }
);

export default client;
