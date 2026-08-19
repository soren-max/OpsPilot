import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import type { ReactNode } from "react";

export function DataTable({ children, ariaLabel }: { children: ReactNode; ariaLabel: string }) {
  return (
    <div className="data-table" role="region" aria-label={ariaLabel} tabIndex={0}>
      <table>{children}</table>
    </div>
  );
}

export function SortButton({
  active,
  direction,
  onClick,
  children,
}: {
  active: boolean;
  direction: "ascending" | "descending";
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      className={`table-sort ${active ? "is-active" : ""}`}
      aria-pressed={active}
      onClick={onClick}
    >
      {children}
      <ChevronDown
        className={direction === "ascending" ? "is-ascending" : ""}
        size={13}
        aria-hidden="true"
      />
    </button>
  );
}

export function TablePagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(page, pages);
  if (total <= pageSize) return null;
  return (
    <nav className="table-pagination" aria-label="表格分页">
      <span>
        第 {safePage} / {pages} 页 · 共 {total} 条
      </span>
      <div>
        <button
          className="icon-button"
          aria-label="上一页"
          disabled={safePage <= 1}
          onClick={() => onPageChange(safePage - 1)}
        >
          <ChevronLeft size={16} />
        </button>
        <button
          className="icon-button"
          aria-label="下一页"
          disabled={safePage >= pages}
          onClick={() => onPageChange(safePage + 1)}
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </nav>
  );
}
