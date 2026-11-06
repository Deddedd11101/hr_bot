import { useState } from "react";
import { SkillRubric } from "./skill-rubric";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ColleagueReview, Score } from "@/grades/types";

export function ReviewDetails({
  scores,
  reviewers,
}: {
  scores: Score[];
  reviewers: ColleagueReview[];
}) {
  return (
    <div className="min-w-0 space-y-6">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Навык</TableHead>
            <TableHead className="hidden sm:table-cell">Категория</TableHead>
            <TableHead className="text-right">Оценка · 0–4</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {scores.map((score) => (
            <TableRow key={score.skillId}>
              <TableCell className="max-w-64 whitespace-normal break-words">
                {score.skillName}
                <SkillRubric rubric={score.rubric} />
                <span className="block text-xs text-muted-foreground sm:hidden">
                  {score.categoryName}
                </span>
              </TableCell>
              <TableCell className="hidden max-w-48 whitespace-normal break-words text-muted-foreground sm:table-cell">
                {score.categoryName}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {score.assessed === false
                  ? "Не оценено"
                  : Number(score.currentLevel.toFixed(2))}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {reviewers.map(
        (reviewer) =>
          !!reviewer.comments?.length && (
            <section key={reviewer.employee_id} className="space-y-3">
              <h4 className="font-medium">Комментарии · {reviewer.name}</h4>
              {reviewer.comments.map((comment, index) => (
                <div key={index} className="space-y-1 border-b pb-3">
                  <p className="text-sm font-medium break-words">
                    {comment.question}
                  </p>
                  <p className="whitespace-pre-wrap break-words text-sm text-muted-foreground">
                    {comment.answer ?? "Ответ ещё не получен"}
                  </p>
                </div>
              ))}
            </section>
          ),
      )}
    </div>
  );
}

export function ReviewDetailDialog({
  title,
  scores,
  reviewers,
}: {
  title: string;
  scores: Score[];
  reviewers: ColleagueReview[];
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        Подробная оценка
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="min-w-0 max-h-[85vh] overflow-x-hidden overflow-y-auto sm:max-w-3xl">
          <DialogHeader className="min-w-0">
            <DialogTitle className="break-words">{title}</DialogTitle>
            <DialogDescription>
              Оценки навыков и ответы на открытые вопросы
            </DialogDescription>
          </DialogHeader>
          <ReviewDetails scores={scores} reviewers={reviewers} />
        </DialogContent>
      </Dialog>
    </>
  );
}
