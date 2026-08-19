import { Moon, Sun, Monitor } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTheme } from "../theme/useTheme";

const options = [
  { value: "light" as const, label: "浅色模式", icon: Sun },
  { value: "dark" as const, label: "深色值班模式", icon: Moon },
  { value: "system" as const, label: "跟随系统", icon: Monitor },
];

export function ThemeSwitcher() {
  const { preference, setTheme, isDark } = useTheme();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(e.target as Node) &&
        btnRef.current &&
        !btnRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        btnRef.current?.focus();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const items = menuRef.current?.querySelectorAll<HTMLButtonElement>("[role='menuitem']");
      if (!items) return;
      const current = document.activeElement;
      const idx = Array.from(items).indexOf(current as HTMLButtonElement);
      const next =
        e.key === "ArrowDown" ? (idx + 1) % items.length : (idx - 1 + items.length) % items.length;
      items[next]?.focus();
    }
  }, []);

  const select = useCallback(
    (value: typeof preference) => {
      setTheme(value);
      setOpen(false);
      btnRef.current?.focus();
    },
    [setTheme],
  );

  const CurrentIcon = isDark ? Moon : Sun;

  return (
    <div className="theme-switcher">
      <button
        ref={btnRef}
        className="theme-switcher__btn"
        onClick={() => setOpen((v) => !v)}
        aria-label="切换主题"
        aria-haspopup="true"
        aria-expanded={open}
      >
        <CurrentIcon size={16} aria-hidden="true" />
      </button>
      {open && (
        <div
          ref={menuRef}
          className="theme-switcher__menu"
          role="menu"
          aria-label="主题选择"
          onKeyDown={handleKeyDown}
        >
          {options.map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              role="menuitem"
              className={`theme-switcher__option${preference === value ? " is-selected" : ""}`}
              onClick={() => select(value)}
              aria-checked={preference === value}
            >
              <Icon size={16} aria-hidden="true" />
              <span>{label}</span>
              {preference === value && (
                <span className="theme-switcher__check" aria-hidden="true">
                  ✓
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
