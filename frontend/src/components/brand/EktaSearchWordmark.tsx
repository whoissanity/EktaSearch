interface Props {
  className?: string;
  /** Navbar scale */
  size?: "sm" | "hero";
}

export default function EktaSearchWordmark({ className = "", size = "sm" }: Props) {
  const scale =
    size === "hero"
      ? "text-4xl sm:text-5xl font-semibold tracking-tight"
      : "text-sm font-semibold tracking-tight";

  return (
    <span className={`${scale} ${className}`} style={{ fontFamily: "var(--font-ekta)" }}>
      <span className="text-white">Ekta</span>
      <span className="text-shine-cyan">Search</span>
    </span>
  );
}
