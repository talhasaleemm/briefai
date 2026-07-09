import React from 'react';
import type { CustomTemplate } from '../api/templates';

interface TaskOption {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
}

interface TaskGridSelectorProps {
  currentTask: string;
  onChange: (taskId: string) => void;
  customTemplates?: CustomTemplate[];
}

export const TaskGridSelector: React.FC<TaskGridSelectorProps> = ({
  currentTask,
  onChange,
  customTemplates = [],
}) => {
  const options: TaskOption[] = [
    {
      id: 'summarize',
      title: 'Executive Summary',
      description: 'Condense transcript into a high-level summary with key takeaways.',
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="task-card-icon">
          <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <line x1="10" y1="9" x2="8" y2="9" />
        </svg>
      ),
    },
    {
      id: 'action_items',
      title: 'Action Items',
      description: 'Extract operational tasks, owners, and due dates from speech.',
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="task-card-icon">
          <polyline points="9 11 12 14 22 4" />
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
        </svg>
      ),
    },
    {
      id: 'translate',
      title: 'Translation',
      description: 'Translate speech segments into any target language.',
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="task-card-icon">
          <circle cx="12" cy="12" r="10" />
          <line x1="2" y1="12" x2="22" y2="12" />
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
        </svg>
      ),
    },
    {
      id: 'lecture_notes',
      title: 'Study Notes',
      description: 'Format the transcription into structured academic lecture notes.',
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="task-card-icon">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
        </svg>
      ),
    },
    {
      id: 'decisions',
      title: 'Decisions Log',
      description: 'Compile a concise list of all final resolutions and key alignments.',
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="task-card-icon">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
        </svg>
      ),
    },
    {
      id: 'terminology',
      title: 'Definitions',
      description: 'Pinpoint and define complex technical terms and jargon.',
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="task-card-icon">
          <line x1="4" y1="9" x2="20" y2="9" />
          <line x1="4" y1="15" x2="20" y2="15" />
          <line x1="10" y1="3" x2="8" y2="21" />
          <line x1="16" y1="3" x2="14" y2="21" />
        </svg>
      ),
    },
  ];

  const allOptions = [
    ...options,
    ...customTemplates.map((t) => ({
      id: `custom_${t.id}`,
      title: t.name,
      description: 'Custom Template',
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="task-card-icon">
          <path d="M12 20h9" />
          <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
        </svg>
      ),
    })),
  ];

  return (
    <div className="task-grid-selector">
      {allOptions.map((opt) => {
        const isActive = currentTask === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            className={`task-grid-card border-glow ${isActive ? 'active' : ''}`}
            onClick={() => onChange(opt.id)}
          >
            <div className="task-card-header">
              <span className="task-icon-wrapper">{opt.icon}</span>
              <span className="task-card-title">{opt.title}</span>
            </div>
            <p className="task-card-desc">{opt.description}</p>
          </button>
        );
      })}
    </div>
  );
};
