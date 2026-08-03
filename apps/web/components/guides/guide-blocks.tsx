import type { GuideBlock } from "@/lib/guides/types";
import { GuideCallout } from "./guide-callout";
import { GuideChecklist } from "./guide-checklist";
import { GuideComparison } from "./guide-comparison";
import { GuideFaq } from "./guide-faq";
import { GuideSteps } from "./guide-steps";

export function GuideBlocks({ blocks }: { blocks: readonly GuideBlock[] }) {
  return (
    <div className="space-y-6">
      {blocks.map((block, index) => {
        if (block.type === "paragraph") {
          return <p key={index} className="text-base leading-8 text-black/70">{block.text}</p>;
        }
        if (block.type === "steps") {
          return <GuideSteps key={index} title={block.title} items={block.items} />;
        }
        if (block.type === "checklist") {
          return <GuideChecklist key={index} title={block.title} items={block.items} />;
        }
        if (block.type === "callout") {
          return <GuideCallout key={index} tone={block.tone} title={block.title}>{block.text}</GuideCallout>;
        }
        if (block.type === "comparison") {
          return <GuideComparison key={index} title={block.title} columns={block.columns} rows={block.rows} />;
        }
        return <GuideFaq key={index} items={block.items} />;
      })}
    </div>
  );
}
