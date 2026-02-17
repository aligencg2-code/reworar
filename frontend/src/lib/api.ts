// API service — Backend ile iletişim katmanı
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

class ApiService {
  private token: string | null = null;

  constructor() {
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('demet_token');
    }
  }

  setToken(token: string) {
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('demet_token', token);
    }
  }

  clearToken() {
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('demet_token');
    }
  }

  async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    // Don't set Content-Type for FormData
    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      this.clearToken();
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      throw new Error('Oturum süresi doldu');
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Sunucu hatası' }));
      throw new Error(error.detail || 'İstek başarısız');
    }

    return response.json();
  }

  // Auth
  async login(username: string, password: string) {
    const data = await this.request<any>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    this.setToken(data.access_token);
    return data;
  }

  async register(username: string, email: string, password: string) {
    const data = await this.request<any>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, email, password }),
    });
    this.setToken(data.access_token);
    return data;
  }

  getInstagramConnectUrl() {
    return `${API_BASE}/auth/instagram/connect`;
  }

  // Dashboard
  async getDashboardStats() {
    return this.request<any>('/dashboard/stats');
  }

  async getRecentActivity(limit = 20) {
    return this.request<any>(`/dashboard/activity?limit=${limit}`);
  }

  // Accounts
  async getAccounts() {
    return this.request<any[]>('/accounts');
  }

  async getAccount(id: number) {
    return this.request<any>(`/accounts/${id}`);
  }

  async updateAccount(id: number, data: any) {
    return this.request<any>(`/accounts/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteAccount(id: number) {
    return this.request<any>(`/accounts/${id}`, { method: 'DELETE' });
  }

  // Posts
  async getPosts(params?: Record<string, any>) {
    const query = params ? '?' + new URLSearchParams(params).toString() : '';
    return this.request<any>(`/posts${query}`);
  }

  async getCalendar(month: number, year: number, accountId?: number) {
    const params = new URLSearchParams({ month: String(month), year: String(year) });
    if (accountId) params.set('account_id', String(accountId));
    return this.request<any>(`/posts/calendar?${params}`);
  }

  async createPost(data: any) {
    return this.request<any>('/posts', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updatePost(id: number, data: any) {
    return this.request<any>(`/posts/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deletePost(id: number) {
    return this.request<any>(`/posts/${id}`, { method: 'DELETE' });
  }

  async publishPost(id: number) {
    return this.request<any>(`/posts/${id}/publish`, { method: 'POST' });
  }

  // Media
  async getMedia(params?: Record<string, any>) {
    const query = params ? '?' + new URLSearchParams(params).toString() : '';
    return this.request<any>(`/media${query}`);
  }

  async uploadMedia(files: File[], mediaType = 'photo', folder = 'default', accountId?: number) {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    formData.append('media_type', mediaType);
    formData.append('folder', folder);
    if (accountId) formData.append('account_id', String(accountId));

    const headers: Record<string, string> = {};
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;

    const response = await fetch(`${API_BASE}/media/upload`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) throw new Error('Yükleme başarısız');
    return response.json();
  }

  async resizeMedia(id: number, aspectRatio: string) {
    return this.request<any>(`/media/${id}/resize?aspect_ratio=${aspectRatio}`, {
      method: 'POST',
    });
  }

  async deleteMedia(id: number) {
    return this.request<any>(`/media/${id}`, { method: 'DELETE' });
  }

  // Messages
  async getConversations(accountId: number) {
    return this.request<any>(`/messages/conversations/${accountId}`);
  }

  async getMessageHistory(accountId: number, conversationId?: string, limit = 50) {
    const params = new URLSearchParams({ limit: String(limit) });
    if (conversationId) params.set('conversation_id', conversationId);
    return this.request<any>(`/messages/history/${accountId}?${params}`);
  }

  async getTemplates() {
    return this.request<any>('/messages/templates');
  }

  async createTemplate(data: any) {
    return this.request<any>('/messages/templates', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteTemplate(id: number) {
    return this.request<any>(`/messages/templates/${id}`, { method: 'DELETE' });
  }

  async getAutoReplyRules() {
    return this.request<any>('/messages/auto-reply');
  }

  async createAutoReplyRule(data: any) {
    return this.request<any>('/messages/auto-reply', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteAutoReplyRule(id: number) {
    return this.request<any>(`/messages/auto-reply/${id}`, { method: 'DELETE' });
  }

  // Downloads
  async startDownload(data: any) {
    return this.request<any>('/downloads/start', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getDownloadStatus(jobId: string) {
    return this.request<any>(`/downloads/status/${jobId}`);
  }

  async stopDownload(jobId: string) {
    return this.request<any>(`/downloads/stop/${jobId}`, { method: 'POST' });
  }

  // Hashtags
  async getHashtagGroups(accountId?: number) {
    const params = accountId ? `?account_id=${accountId}` : '';
    return this.request<any>(`/hashtags${params}`);
  }

  async createHashtagGroup(data: any) {
    return this.request<any>('/hashtags', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateHashtagGroup(id: number, data: any) {
    return this.request<any>(`/hashtags/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteHashtagGroup(id: number) {
    return this.request<any>(`/hashtags/${id}`, { method: 'DELETE' });
  }

  // Settings
  async getSettings() {
    return this.request<any>('/settings');
  }

  async updateSettings(settings: { key: string; value: string }[]) {
    return this.request<any>('/settings', {
      method: 'POST',
      body: JSON.stringify({ settings }),
    });
  }

  // Backups
  async getBackups() {
    return this.request<any>('/dashboard/backups');
  }

  async createBackup() {
    return this.request<any>('/dashboard/backups/create', { method: 'POST' });
  }
}

export const api = new ApiService();
