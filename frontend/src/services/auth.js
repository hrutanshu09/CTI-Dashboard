import axios from 'axios';

const AUTH_API_BASE_URL =
  process.env.REACT_APP_AUTH_API_BASE_URL ||
  process.env.REACT_APP_LOG_API_BASE_URL ||
  process.env.REACT_APP_API_BASE_URL ||
  'http://127.0.0.1:8001';

const authClient = axios.create({
  baseURL: AUTH_API_BASE_URL,
  withCredentials: true,
});

export const loginUser = async ({ email, password }) => {
  const response = await authClient.post('/auth/login', { email, password });
  return response.data;
};

export const signupUser = async ({ name, email, password }) => {
  const response = await authClient.post('/auth/signup', { name, email, password });
  return response.data;
};

export const getCurrentUser = async () => {
  const response = await authClient.get('/auth/me');
  return response.data;
};

export const logoutUser = async () => {
  const response = await authClient.post('/auth/logout');
  return response.data;
};
