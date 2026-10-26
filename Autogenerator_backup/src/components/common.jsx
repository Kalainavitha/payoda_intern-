import { Check, CircleAlert, ChevronRight } from 'lucide-react'
import { dateLabel } from '../utils/date'

export function Alert({ kind, message, onClose }) {
  return (
    <div className={`alert alert-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      {kind === 'error' ? <CircleAlert size={17} /> : <Check size={17} />}
      <span>{message}</span>
      <button className="alert-dismiss" aria-label="Dismiss message" onClick={onClose}>
        <span aria-hidden="true">×</span>
      </button>
    </div>
  )
}

export function Heading({ eyebrow, title, description, action }) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action && <div className="heading-action">{action}</div>}
    </div>
  )
}

export function Metric({ label, value, note, icon: Icon, tone }) {
  return (
    <article className="metric-card">
      <div className={`metric-icon ${tone}`}><Icon size={18} /></div>
      <div className="metric-label">{label}</div>
      <strong className="metric-value">{value}</strong>
      <div className="metric-note">{note}</div>
    </article>
  )
}

export function ProjectRow({ item, index, onClick }) {
  const type = item.project_type === 'Other' ? item.custom_project_type : item.project_type

  return (
    <button className="project-row" onClick={onClick}>
      <div className={`project-index project-color-${index % 4}`}>{String(index + 1).padStart(2, '0')}</div>
      <div className="project-row-main">
        <strong>{item.name}</strong>
        <span>{type} <i /> {item.tasks?.length || 0} tasks reviewed</span>
      </div>
      <div className="project-row-date">
        <small>DEADLINE</small>
        <span>{dateLabel(item.deadline, { month: 'short', day: 'numeric' })}</span>
      </div>
      <span className={`status-pill ${item.tasks?.length ? 'status-ready' : ''}`}>
        {item.tasks?.length ? 'In review' : 'Needs tasks'}
      </span>
      <ChevronRight size={17} className="row-arrow" />
    </button>
  )
}
