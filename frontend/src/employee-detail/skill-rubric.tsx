import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import type { SkillRubric as Rubric } from "@/grades/types";

export function SkillRubric({rubric}: {rubric?: Rubric | null}) {
  if (!rubric) return null;
  return <Collapsible className="mt-2 text-xs">
    <CollapsibleTrigger className="cursor-pointer text-muted-foreground underline underline-offset-4">Критерии уровней</CollapsibleTrigger>
    <CollapsibleContent className="space-y-2 pt-3">
      {Object.entries(rubric.levels).map(([level, description]) => <p key={level} className="whitespace-normal break-words text-muted-foreground"><strong className="text-foreground">{level}.</strong> {description}</p>)}
      <p className="whitespace-normal break-words text-muted-foreground">{rubric.na} — не учитывается в среднем.</p>
    </CollapsibleContent>
  </Collapsible>;
}
