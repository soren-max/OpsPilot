import { ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import type { Service, Task } from "../types";
import { StatusBadge } from "./OpsUI";

export function ResourceList({ services }: { services: Service[] }) {
  return (
    <ul className="dashboard-resource-list">
      {services.map((service) => (
        <li key={service.id}>
          <Link to={`/services?search=${encodeURIComponent(service.name)}`}>
            <span className={`resource-status-dot is-${service.current_status.toLowerCase()}`} />
            <span className="dashboard-row__copy">
              <strong>{service.name}</strong>
              <small>
                {service.service_type} · {service.host_count} 台主机
              </small>
            </span>
            <StatusBadge status={service.current_status} domain="service" compact />
            <ChevronRight size={16} aria-hidden="true" />
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function TaskList({ tasks }: { tasks: Task[] }) {
  return (
    <ul className="dashboard-resource-list dashboard-task-list">
      {tasks.map((task) => (
        <li key={task.id}>
          <Link to={`/tasks?task=${task.id}`}>
            <span className={`resource-status-dot is-${task.status.toLowerCase()}`} />
            <span className="dashboard-row__copy">
              <strong className="mono">{task.id.slice(0, 8)}</strong>
              <small>
                {task.targets.length} 个目标 · {formatDate(task.created_at)}
              </small>
            </span>
            <StatusBadge status={task.status} domain="task" compact />
            <ChevronRight size={16} aria-hidden="true" />
          </Link>
        </li>
      ))}
    </ul>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}
