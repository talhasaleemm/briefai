import { api } from "./client";

export interface CustomTemplate {
  id: number;
  user_id: number;
  name: string;
  system_prompt: string | null;
  prompt_template: string;
  created_at: string;
}

export interface CustomTemplateCreate {
  name: string;
  system_prompt?: string | null;
  prompt_template: string;
}

export interface CustomTemplateUpdate {
  name?: string;
  system_prompt?: string | null;
  prompt_template?: string;
}

export const templatesApi = {
  getTemplates: async (): Promise<CustomTemplate[]> => {
    const res = await api.get<CustomTemplate[]>("/templates/");
    return res.data;
  },

  createTemplate: async (data: CustomTemplateCreate): Promise<CustomTemplate> => {
    const res = await api.post<CustomTemplate>("/templates/", data);
    return res.data;
  },

  updateTemplate: async (id: number, data: CustomTemplateUpdate): Promise<CustomTemplate> => {
    const res = await api.put<CustomTemplate>(`/templates/${id}`, data);
    return res.data;
  },

  deleteTemplate: async (id: number): Promise<void> => {
    await api.delete(`/templates/${id}`);
  },
};
