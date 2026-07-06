import React from 'react';

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  description: string;
  icon: React.ReactNode;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  unit = '',
  description,
  icon,
}) => {
  return (
    <div className="metric-card">
      <div className="metric-card-header">
        <span className="metric-card-title">{title}</span>
        <div className="metric-card-icon">{icon}</div>
      </div>
      <div className="metric-card-body">
        <span className="metric-card-value">{value}</span>
        {unit && <span className="metric-card-unit">{unit}</span>}
      </div>
      <p className="metric-card-description">{description}</p>
    </div>
  );
};
