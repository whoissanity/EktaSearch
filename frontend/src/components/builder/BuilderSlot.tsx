// src/components/builder/BuilderSlot.tsx
// One row in the PC builder — shows slot name, selected part (if any),
// and a button to search + pick a part for that slot.

import { Plus, X, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { BuildSlot, BuildPart } from "../../types";
import { SLOT_COMPONENT_ID, SLOT_LABELS } from "../../types";
import { formatBDT } from "../../utils";
import { useBuilderStore } from "../../store/builderStore";

interface Props {
  slot: BuildSlot;
}

export default function BuilderSlot({ slot }: Props) {
  const navigate = useNavigate();
  const part = useBuilderStore((s) => s.build.parts.find((p) => p.slot === slot));
  const removePart = useBuilderStore((s) => s.removePart);
  const openPicker = () => navigate(`/builder/choose?component_id=${SLOT_COMPONENT_ID[slot]}`);

  return (
    <>
      <div className={`card-flat p-3 flex items-center gap-3 transition-all
                       ${part ? "border-accent/30" : "border-dashed"}`}>
        {/* Slot label */}
        <div className="w-36 shrink-0">
          <p className="text-xs font-medium text-zinc-400">{SLOT_LABELS[slot]}</p>
        </div>

        {part ? (
          <>
            {/* Selected part */}
            <div className="flex-1 min-w-0">
              <p className="text-sm text-zinc-100 font-medium truncate">{part.product_name}</p>
              <p className="text-xs text-zinc-500">{part.retailer}</p>
            </div>
            <span className="text-sm font-semibold text-zinc-200 shrink-0">
              {formatBDT(part.price_bdt)}
            </span>
            <button
              onClick={openPicker}
              className="btn-ghost p-1.5"
              title="Change part"
            >
              <Search size={14} />
            </button>
            <button
              onClick={() => removePart(slot)}
              className="btn-ghost p-1.5 text-zinc-600 hover:text-danger"
              title="Remove part"
            >
              <X size={14} />
            </button>
          </>
        ) : (
          <>
            <p className="flex-1 text-xs text-zinc-500 italic">No part selected</p>
            <button
              onClick={openPicker}
              className="btn-secondary text-xs py-1 px-3"
            >
              <Plus size={12} /> Choose
            </button>
          </>
        )}
      </div>

    </>
  );
}
