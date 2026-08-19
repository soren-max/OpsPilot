export interface RouteMeta {
  path: string;
  label: string;
}

export const routeMeta: RouteMeta[] = [
  { path: "/", label: "运维总览" },
  { path: "/services", label: "服务管理" },
  { path: "/hosts", label: "主机管理" },
  { path: "/tasks", label: "任务中心" },
  { path: "/audits", label: "操作审计" },
  { path: "/access", label: "权限管理" },
  { path: "/operations-integration", label: "运维接入配置" },
  { path: "/settings", label: "系统配置" },
];

export function matchRouteMeta(pathname: string): RouteMeta {
  return (
    routeMeta.find((item) =>
      item.path === "/" ? pathname === "/" : pathname.startsWith(item.path),
    ) ?? routeMeta[0]!
  );
}
