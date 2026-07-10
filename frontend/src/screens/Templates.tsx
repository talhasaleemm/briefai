import { useState, useEffect } from 'react';
import { templatesApi } from '../api/templates';
import type { CustomTemplate } from '../api/templates';

export function Templates() {
  const [templates, setTemplates] = useState<CustomTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isEditing, setIsEditing] = useState(false);
  const [currentId, setCurrentId] = useState<number | null>(null);
  
  const [name, setName] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [promptTemplate, setPromptTemplate] = useState('');

  const [formError, setFormError] = useState<string | null>(null);

  const loadTemplates = async () => {
    try {
      setLoading(true);
      const data = await templatesApi.getTemplates();
      setTemplates(data);
    } catch (err: any) {
      setError(err.message || "Failed to load templates.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTemplates();
  }, []);

  const handleEdit = (tmpl: CustomTemplate) => {
    setCurrentId(tmpl.id);
    setName(tmpl.name);
    setSystemPrompt(tmpl.system_prompt || '');
    setPromptTemplate(tmpl.prompt_template);
    setIsEditing(true);
    setFormError(null);
  };

  const handleCreateNew = () => {
    setCurrentId(null);
    setName('');
    setSystemPrompt('');
    setPromptTemplate('{transcript}\n\n');
    setIsEditing(true);
    setFormError(null);
  };

  const handleCancel = () => {
    setIsEditing(false);
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm("Are you sure you want to delete this template?")) return;
    try {
      await templatesApi.deleteTemplate(id);
      loadTemplates();
    } catch (err: any) {
      alert(err.message || "Failed to delete.");
    }
  };

  const handleSave = async () => {
    setFormError(null);
    
    if (!promptTemplate.includes('{transcript}')) {
      setFormError("The Prompt Template must contain the {transcript} placeholder.");
      return;
    }
    if (promptTemplate.length > 4000 || systemPrompt.length > 4000) {
      setFormError("Prompts cannot exceed 4000 characters.");
      return;
    }

    try {
      if (currentId) {
        await templatesApi.updateTemplate(currentId, {
          name,
          system_prompt: systemPrompt || null,
          prompt_template: promptTemplate
        });
      } else {
        await templatesApi.createTemplate({
          name,
          system_prompt: systemPrompt || null,
          prompt_template: promptTemplate
        });
      }
      setIsEditing(false);
      loadTemplates();
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message;
      setFormError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  };

  if (loading && !templates.length) {
    return <div style={{ color: 'var(--text-muted)' }}>Loading templates...</div>;
  }

  return (
    <div className="templates-container" style={{ maxWidth: '800px', margin: '0 auto', color: 'var(--text-primary)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h2>Custom Template Builder</h2>
        {!isEditing && (
          <button className="btn btn-primary" onClick={handleCreateNew}>
            + New Template
          </button>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {isEditing ? (
        <div className="template-editor border-glow" style={{ padding: '2rem', backgroundColor: 'var(--panel-bg)', borderRadius: '12px' }}>
          <h3 style={{ marginTop: 0, marginBottom: '1.5rem' }}>
            {currentId ? 'Edit Template' : 'Create Template'}
          </h3>

          {formError && <div className="alert alert-error" style={{ marginBottom: '1rem' }}>{formError}</div>}

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>Template Name</label>
            <input 
              className="config-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Weekly Standup Notes"
              style={{ width: '100%' }}
            />
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>System Prompt (Optional)</label>
            <textarea 
              className="config-input"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="e.g. You are a precise scrum master..."
              style={{ width: '100%', minHeight: '80px', resize: 'vertical' }}
            />
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>Prompt Template (Required)</label>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
              Define instructions for the LLM. You MUST include the <code>{'{transcript}'}</code> placeholder exactly as shown so the system knows where to inject the meeting text.
            </p>
            <textarea 
              className="config-input"
              value={promptTemplate}
              onChange={(e) => setPromptTemplate(e.target.value)}
              style={{ width: '100%', minHeight: '200px', resize: 'vertical', fontFamily: 'monospace' }}
            />
          </div>

          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
            <button className="btn btn-secondary" onClick={handleCancel}>Cancel</button>
            <button className="btn btn-success" onClick={handleSave} disabled={!name || !promptTemplate}>Save Template</button>
          </div>
        </div>
      ) : (
        <div className="template-list" style={{ display: 'grid', gap: '1rem' }}>
          {templates.length === 0 ? (
            <div style={{ padding: '3rem', textAlign: 'center', backgroundColor: 'var(--panel-bg)', borderRadius: '12px', color: 'var(--text-muted)' }}>
              No custom templates found. Create one to get started!
            </div>
          ) : (
            templates.map(tmpl => (
              <div key={tmpl.id} className="template-card border-glow" style={{ padding: '1.5rem', backgroundColor: 'var(--panel-bg)', borderRadius: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ margin: 0, marginBottom: '0.5rem' }}>{tmpl.name}</h3>
                  <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-muted)' }}>
                    Created: {new Date(tmpl.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button className="btn btn-secondary btn-sm" onClick={() => handleEdit(tmpl)}>Edit</button>
                  <button className="btn btn-secondary btn-sm" style={{ color: '#ff6b6b' }} onClick={() => handleDelete(tmpl.id)}>Delete</button>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
