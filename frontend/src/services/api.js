const TOKEN_KEY = "docuguard_token";

export const getStoredToken = () => localStorage.getItem(TOKEN_KEY);
export const setStoredToken = (token) => {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
};

const getHeaders = (isFormData = false) => {
  const headers = {};
  if (!isFormData) {
    headers["Content-Type"] = "application/json";
  }
  const token = getStoredToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
};

async function handleResponse(response) {
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const errorMsg = data?.detail || data?.message || "An unexpected error occurred.";
    throw new Error(errorMsg);
  }
  return data;
}

export const api = {
  // Auth
  async register(fullName, email, password, confirmPassword) {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({
        full_name: fullName,
        email,
        password,
        confirm_password: confirmPassword,
      }),
    });
    return handleResponse(res);
  },

  async login(email, password) {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ email, password }),
    });
    return handleResponse(res);
  },

  async getMe() {
    const token = getStoredToken();
    if (!token) return null;
    const res = await fetch("/api/auth/me", {
      method: "GET",
      headers: getHeaders(),
    });
    return handleResponse(res);
  },

  async logout() {
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        headers: getHeaders(),
      });
    } catch {
      // Ignored if network fails on logout
    } finally {
      setStoredToken(null);
    }
  },

  // Document Upload
  async uploadDocument(file) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch("/api/documents/upload", {
      method: "POST",
      headers: getHeaders(true),
      body: formData,
    });
    return handleResponse(res);
  },

  // Documents
  async listDocuments(search = "", docType = "") {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (docType) params.append("doc_type", docType);
    const res = await fetch(`/api/documents?${params.toString()}`, {
      method: "GET",
      headers: getHeaders(),
    });
    return handleResponse(res);
  },

  async getDocument(documentId) {
    const res = await fetch(`/api/documents/${documentId}`, {
      method: "GET",
      headers: getHeaders(),
    });
    return handleResponse(res);
  },

  async deleteDocument(documentId) {
    const res = await fetch(`/api/documents/${documentId}`, {
      method: "DELETE",
      headers: getHeaders(),
    });
    return handleResponse(res);
  },

  // Dashboard Stats
  async getDashboardStats() {
    const res = await fetch("/api/dashboard/stats", {
      method: "GET",
      headers: getHeaders(),
    });
    return handleResponse(res);
  },

  // Tasks
  async listTasks(status = "", priority = "", category = "") {
    const params = new URLSearchParams();
    if (status) params.append("status_filter", status);
    if (priority) params.append("priority", priority);
    if (category) params.append("category", category);
    const res = await fetch(`/api/tasks?${params.toString()}`, {
      method: "GET",
      headers: getHeaders(),
    });
    return handleResponse(res);
  },

  async toggleTask(taskId) {
    const res = await fetch(`/api/tasks/${taskId}/toggle`, {
      method: "PATCH",
      headers: getHeaders(),
    });
    return handleResponse(res);
  },

  // Deadlines
  async listDeadlines(status = "") {
    const params = new URLSearchParams();
    if (status) params.append("status_filter", status);
    const res = await fetch(`/api/deadlines?${params.toString()}`, {
      method: "GET",
      headers: getHeaders(),
    });
    return handleResponse(res);
  },

  async toggleDeadline(deadlineId) {
    const res = await fetch(`/api/deadlines/${deadlineId}/toggle`, {
      method: "PATCH",
      headers: getHeaders(),
    });
    return handleResponse(res);
  },

  // Rules
  async listRules(ruleType = "") {
    const params = new URLSearchParams();
    if (ruleType) params.append("rule_type", ruleType);
    const res = await fetch(`/api/rules?${params.toString()}`, {
      method: "GET",
      headers: getHeaders(),
    });
    return handleResponse(res);
  },
};
