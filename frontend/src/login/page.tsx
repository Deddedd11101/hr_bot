import { AlertTriangle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

export type LoginPageProps = {
  errorMessage?: string;
};

export function LoginPage({ errorMessage = "" }: LoginPageProps) {
  return (
    <main className="grid min-h-screen place-items-center bg-background px-4 py-8 text-foreground">
      <Card className="w-full max-w-[420px] border border-border/80 bg-card shadow-none ring-0">
        <CardHeader className="border-b border-border/70 pb-4">
          <CardTitle className="text-2xl font-semibold tracking-tight">Вход</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-5 pt-5">
          {errorMessage ? (
            <Alert variant="destructive">
              <AlertTriangle data-icon="inline-start" />
              <AlertTitle>Ошибка входа</AlertTitle>
              <AlertDescription>{errorMessage}</AlertDescription>
            </Alert>
          ) : null}

          <form method="post" action="/login">
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="login">Логин</FieldLabel>
                <Input id="login" name="login" type="text" autoComplete="username" required autoFocus />
              </Field>
              <Field>
                <FieldLabel htmlFor="password">Пароль</FieldLabel>
                <Input id="password" name="password" type="password" autoComplete="current-password" required />
              </Field>
              <Button type="submit" className="w-full" size="lg">
                Войти
              </Button>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
