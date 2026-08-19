import { ChevronRight, Home } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { matchRouteMeta } from "../routing/routeMeta";

export function Breadcrumbs() {
  const { pathname } = useLocation();
  const current = matchRouteMeta(pathname);
  return (
    <nav className="breadcrumbs" aria-label="面包屑">
      <Link to="/" aria-label="返回运维总览">
        <Home size={14} aria-hidden="true" />
        <span>控制台</span>
      </Link>
      {current.path !== "/" && (
        <>
          <ChevronRight size={13} aria-hidden="true" />
          <span aria-current="page">{current.label}</span>
        </>
      )}
    </nav>
  );
}
