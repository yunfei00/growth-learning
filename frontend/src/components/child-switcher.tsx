"use client";

import type { Child } from "@/lib/api/client";

export function ChildSwitcher({
  childOptions,
  activeChildId,
  onChange,
}: {
  childOptions: Child[];
  activeChildId: string;
  onChange: (childId: string) => void;
}) {
  return (
    <label className="child-switcher">
      <span>孩子</span>
      <select onChange={(event) => onChange(event.target.value)} value={activeChildId}>
        {childOptions.map((child) => (
          <option key={child.id} value={child.id}>
            {child.nickname || child.display_name}
          </option>
        ))}
      </select>
    </label>
  );
}
