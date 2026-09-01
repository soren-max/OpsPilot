import type { ReactNode } from "react";
import type { StatusTone } from "./Status";

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        <p className="page-header__description">{description}</p>
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </header>
  );
}

export function PageSection({
  id,
  title,
  description,
  actions,
  children,
  className = "",
}: {
  id?: string;
  title?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section id={id} className={`page-section section-card ${className}`.trim()}>
      {(title || actions) && (
        <header className="section-card__header">
          <div>
            {title && <h2>{title}</h2>}
            {description && <p>{description}</p>}
          </div>
          {actions && <div className="section-card__actions">{actions}</div>}
        </header>
      )}
      <div className="section-card__body">{children}</div>
    </section>
  );
}

/** @deprecated Use PageSection. Kept temporarily for compatibility during CSS convergence. */
export const SectionCard = PageSection;

export function MetricTile({
  label,
  value,
  detail,
  tone = "neutral",
  icon,
}: {
  label: string;
  value: string | number;
  detail: string;
  tone?: StatusTone;
  icon: ReactNode;
}) {
  return (
    <article className={`metric-tile metric-tile--${tone}`}>
      <span className="metric-tile__icon">{icon}</span>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </article>
  );
}
