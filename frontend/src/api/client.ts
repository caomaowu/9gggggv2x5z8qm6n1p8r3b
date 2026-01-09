import axios from 'axios';

const envApiUrl = import.meta.env.VITE_API_URL;
const API_URL =
  envApiUrl && envApiUrl.trim().length > 0
    ? envApiUrl
    : import.meta.env.DEV
      ? 'http://localhost:8000/api/v1'
      : '/api/v1';

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});
