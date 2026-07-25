import { SiAnthropic, SiGooglegemini, SiOpenai, SiX } from "@icons-pack/react-simple-icons";
import { SquaresFour } from "@phosphor-icons/react/ssr";

export function PlatformIcon({ platform, size = 16 }: { platform: string; size?: number }) {
  const props = { "aria-hidden": true, size, className: "shrink-0" } as const;
  if (platform === "OpenAI") return <SiOpenai {...props} />;
  if (platform === "Claude") return <SiAnthropic {...props} />;
  if (platform === "Gemini") return <SiGooglegemini {...props} />;
  if (platform === "Grok") return <SiX {...props} />;
  return <SquaresFour aria-hidden size={size} className="shrink-0" />;
}
