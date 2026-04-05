import { Wrench, Save, RotateCcw, Zap, CheckCircle, AlertTriangle, XCircle } from "lucide-react";
import { useBuilderStore } from "../store/builderStore";
import BuilderSlot from "../components/builder/BuilderSlot";
import { SLOT_LABELS, BuildSlot } from "../types";
import { formatBDT } from "../utils";

const SLOTS = Object.keys(SLOT_LABELS) as BuildSlot[];

export default function BuilderPage() {
  const { build, analysis, analyzing, saving, budget, setBudget,
          setBuildName, save, reset, totalBdt, budgetRemaining } = useBuilderStore();

  const handleSave = async () => {
    const id = await save();
    if (id) alert(`Build saved! Share ID: ${id}`);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Wrench size={20} className="text-accent" />
          <h1>PC Builder</h1>
        </div>
        <div className="flex gap-2">
          <button onClick={reset} className="btn-ghost text-sm">
            <RotateCcw size={14} /> Reset
          </button>
          <button onClick={handleSave} disabled={saving} className="btn-primary text-sm">
            <Save size={14} /> {saving ? "Saving…" : "Save Build"}
          </button>
        </div>
      </div>

      {/* Build name + budget */}
      <div className="card-flat p-4 flex flex-wrap gap-4">
        <div className="flex-1 min-w-40">
          <label className="text-xs text-silver-500 mb-1 block">Build name</label>
          <input
            className="input text-sm"
            value={build.name}
            onChange={(e) => setBuildName(e.target.value)}
          />
        </div>
        <div className="w-44">
          <label className="text-xs text-silver-500 mb-1 block">Budget (৳)</label>
          <input
            type="number"
            className="input text-sm"
            placeholder="0 = no limit"
            value={budget || ""}
            onChange={(e) => setBudget(+e.target.value)}
          />
        </div>
      </div>

      {/* Part slots */}
      <div className="space-y-2">
        {SLOTS.map((slot) => <BuilderSlot key={slot} slot={slot} />)}
      </div>

      {/* Summary panel */}
      <div className="grid sm:grid-cols-2 gap-4">
        {/* Cost summary */}
        <div className="card p-4 space-y-2">
          <p className="text-xs font-medium text-silver-500 uppercase tracking-wide">Cost</p>
          <div className="flex justify-between text-sm">
            <span className="text-silver-600">Total</span>
            <span className="font-semibold text-silver-900">{formatBDT(totalBdt)}</span>
          </div>
          {budget > 0 && (
            <div className="flex justify-between text-sm">
              <span className="text-silver-600">Budget remaining</span>
              <span className={`font-semibold ${budgetRemaining < 0 ? "text-danger" : "text-success"}`}>
                {formatBDT(Math.abs(budgetRemaining))}
                {budgetRemaining < 0 ? " over" : " left"}
              </span>
            </div>
          )}
        </div>

        {/* Wattage */}
        {analysis?.wattage && (
          <div className="card p-4 space-y-2">
            <div className="flex items-center gap-2">
              <Zap size={14} className="text-warning" />
              <p className="text-xs font-medium text-silver-500 uppercase tracking-wide">Power</p>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-silver-600">Estimated draw</span>
              <span className="font-semibold">{analysis.wattage.total_estimated_watts} W</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-silver-600">Recommended PSU</span>
              <span className="font-semibold text-accent">
                {analysis.wattage.recommended_psu_watts} W
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Compatibility */}
      {analyzing && (
        <p className="text-xs text-silver-400 text-center">Checking compatibility…</p>
      )}
      {analysis && (
        <div className="card p-4 space-y-3">
          <div className="flex items-center gap-2">
            {analysis.compatibility.compatible
              ? <CheckCircle size={16} className="text-success" />
              : <XCircle     size={16} className="text-danger" />}
            <p className="text-sm font-medium">
              {analysis.compatibility.compatible ? "No compatibility issues" : "Compatibility issues found"}
            </p>
          </div>
          {analysis.compatibility.issues.map((issue, i) => (
            <div key={i} className={`flex gap-2 text-xs rounded p-2
              ${issue.severity === "error" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}`}>
              <AlertTriangle size={13} className="shrink-0 mt-0.5" />
              <span>{issue.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
