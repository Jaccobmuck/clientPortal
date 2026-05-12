type FreelioLogoProps = {
  compact?: boolean;
};

export function FreelioLogo({ compact = false }: FreelioLogoProps) {
  return (
    <div className="freelio-logo" aria-label="Freelio">
      <span className="freelio-logo__mark">F</span>
      {!compact && <span>Freelio</span>}
    </div>
  );
}
