import Image from "next/image";
import { SiAnthropic, SiGooglegemini, SiOpenai, SiX } from "@icons-pack/react-simple-icons";
import { ArrowsLeftRight, DeviceMobile, SquaresFour } from "@phosphor-icons/react/ssr";

function BrandImage({ src, size }: { src: string; size: number }) {
  return <Image src={src} alt="" aria-hidden width={size} height={size} unoptimized className="shrink-0 object-contain" />;
}

function BrandMark({ src, size }: { src: string; size: number }) {
  return <span aria-hidden="true" className="inline-block shrink-0 bg-current" style={{ width: size, height: size, mask: `url(${src}) center / contain no-repeat`, WebkitMask: `url(${src}) center / contain no-repeat` }} />;
}

export function PlatformIcon({ platform, size = 16 }: { platform: string; size?: number }) {
  const props = { "aria-hidden": true, size, className: "shrink-0" } as const;
  if (platform === "OpenAI") return <SiOpenai {...props} />;
  if (platform === "Claude") return <SiAnthropic {...props} />;
  if (platform === "Gemini") return <SiGooglegemini {...props} />;
  if (platform === "Grok") return <BrandImage src="/brand/grok-ai.jpg" size={size} />;
  if (platform === "X") return <SiX {...props} />;
  if (platform === "Cursor") return <BrandImage src="/brand/cursor.svg" size={size} />;
  if (platform === "MUSE") return <BrandMark src="/brand/muse-mark.png" size={size} />;
  if (platform === "JEV") return <BrandMark src="/brand/jev-mark.png" size={size} />;
  if (platform === "手机接码") return <DeviceMobile {...props} />;
  if (platform === "中转站" || platform === "relay") return <ArrowsLeftRight {...props} />;
  return <SquaresFour aria-hidden size={size} className="shrink-0" />;
}
