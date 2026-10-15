const stages = [
    { value: "hr_interview", label: "HR", mobileLabel: "HR" },
    { value: "manager_interview", label: "Руководитель", mobileLabel: "Рук-ль" },
    { value: "testing", label: "Тестовое", mobileLabel: "Тест" },
    { value: "offer", label: "Оффер", mobileLabel: "Оффер" },
    { value: "preonboarding", label: "Преонбординг", mobileLabel: "Преонб." },
    { value: "contract", label: "Договор", mobileLabel: "Договор" },
];

export function CandidateStage({ value, label }: { value: string; label: string }) {
    const activeIndex = stages.findIndex(stage => stage.value === value);
    return (
        <section className="employee-stage" aria-label={`Текущий этап кандидата: ${label}`}>
            <div className="employee-stage-heading"><strong>Этапы найма</strong><span>Текущий этап: {label}</span></div>
            {activeIndex >= 0 ? <div className="employee-stage-scroll"><ol className="employee-stage-track">
                {stages.map((stage, index) => <li key={stage.value} className={index === activeIndex ? "employee-stage-current" : ""} aria-current={index === activeIndex ? "step" : undefined}>
                    <span className="employee-stage-dot" aria-hidden="true" />
                    <span className="employee-stage-label-full">{stage.label}</span>
                    <span className="employee-stage-label-mobile">{stage.mobileLabel}</span>
                </li>)}
            </ol></div> : null}
        </section>
    );
}
