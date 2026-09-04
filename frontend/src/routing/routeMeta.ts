export interface RouteMeta {
  path: string;
  label: string;
}

export const routeMeta: RouteMeta[] = [
  { path: "/", label: "Overview" },
  { path: "/services", label: "Services" },
  { path: "/hosts", label: "Hosts" },
  { path: "/incidents", label: "Incidents" },
  { path: "/tasks", label: "Executions" },
  { path: "/audits", label: "Audit" },
  { path: "/access", label: "Capabilities" },
  { path: "/settings", label: "Settings" },
];

export function matchRouteMeta(pathname: string): RouteMeta {
  return (
    routeMeta.find((item) =>
      item.path === "/" ? pathname === "/" : pathname.startsWith(item.path),
    ) ?? routeMeta[0]!
  );
}
