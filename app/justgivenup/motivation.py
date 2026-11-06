"""Motivational content: quotes, benefits timeline and recovery notes.

All text is original to this project (Arabic + English) so it can ship
offline with the package.
"""

from __future__ import annotations

from datetime import datetime, timezone

# (ar, en) -- one line each, chosen deterministically per day
QUOTES = [
    (
        "الرغبة عابرة… والقرار الذي اتخذته اليوم هو اللي هيفضل وراك.",
        "The urge passes; the decision you make today is what stays with you.",
    ),
    (
        "كل يوم تتجاوز فيه اللحظة، عضلة الإرادة عندك بتكبر شوية.",
        "Every moment you get past is a small rep for your willpower muscle.",
    ),
    (
        "أنت مش بتحارب الشاشة، أنت بتحارب نسخة منك عايزة تفوز على نسخة تانية.",
        "You are not fighting the screen; you are one version of you refusing to lose to another.",
    ),
    (
        "الفتنة لو اتشالت من قدامك، القرار بقى سهل. المشكلة كانت في الباب المفتوح.",
        "Remove the temptation and the choice gets easy. The problem was the open door.",
    ),
    (
        "التاريخ الطويل بيبدأ بساعة واحدة مفيهاش استسلام.",
        "A long streak is just one hour at a time without giving in.",
    ),
    (
        "الندم بعد اللحظة أثقل من التعب في اللحظة.",
        "Regret afterwards weighs more than the effort during.",
    ),
    (
        "جسمك وعقلك بيتعاملوا معاك بميزان: كل ضربة بتاخدها منهم، هتاخدها تاني.",
        "Your body and mind keep a ledger: every hit you deal them comes back.",
    ),
    (
        "خلي قفل النهاردة هو فعلاً قفل، مش تجربة هتتجاهلها بعد ساعة.",
        "Make today's lock a real lock, not a test you ignore in an hour.",
    ),
    (
        "أوقات الكسل والتوتر بتيجي في نفس الترتيب دايمًا: توتر → بحث → ندم.",
        "The weak moments arrive in the same order: tension, search, regret.",
    ),
    (
        "أنت هنا مش لأنك ضعيف، أنت هنا لأنك اخترت تواجه.",
        "You are here not because you are weak, but because you chose to face it.",
    ),
    (
        "الوقت اللي تضييعه في المحتوى ده، عمره ما هيترجع.",
        "Time lost to this content never comes back.",
    ),
    (
        "اسأل نفسك: هل هتكتب لوحدك إن النهاردة يوم ضايع؟",
        "Ask yourself: would you write down that today was wasted?",
    ),
    (
        "أقوى نسخة منك هي اللي تعرف تقفل الباب قبل ما الفكرة تفتحه.",
        "The strongest version of you closes the door before the thought opens it.",
    ),
    (
        "الشفافية مع نفسك أصل الإصلاح.",
        "Honesty with yourself is the beginning of repair.",
    ),
    (
        "مش محتاج تكون مثالي، محتاج بس متستسلمش.",
        "You do not have to be perfect, you only have to refuse to surrender.",
    ),
    (
        "التعب اللي بيجي من الشغل بيريحك، والتعب اللي بيجي من الإدمان بيزودك.",
        "Tiredness from work rests you; tiredness from the habit drains you.",
    ),
    (
        "لو القفل مش صعب، فهو مش قفل.",
        "If the lock is not hard, it was never a lock.",
    ),
    (
        "بعد ما تخلص المدة، هتفتكر اللحظة دي كنقطة تحول مش نقطة ضعف.",
        "When the time ends, you will remember this moment as a turning point, not a failure.",
    ),
    (
        "العقارة النفسية بتترمم بالثبات، مش بالحماسة المؤقتة.",
        "The mind is repaired by consistency, not by short-lived hype.",
    ),
    (
        "كل مرة تقاوم، صوتك الداخلي بيتأكد إنه لسه معاك.",
        "Every time you resist, the inner voice proves it is still on your side.",
    ),
    (
        "الراحة الحقيقية بتيجي بعد التحمل، مش قبله.",
        "Real rest comes after endurance, not before it.",
    ),
    (
        "ارسم اليوم كأنه يوم هتشرحه لحد تحترمه بكرة.",
        "Live today as if you will explain it to someone you respect tomorrow.",
    ),
    (
        "الدماغ بيعود على الحافز القوي بالملل؛ خد وقتك وهيفضل يهدا.",
        "The brain adapts to strong stimulation with boredom; give it time and it settles.",
    ),
    (
        "مش لازم تعرف إنت هتوصل فين، لازم بس متوقّفش.",
        "You do not need to know where you end up; you only need to not stop.",
    ),
    (
        "أول ٣ أيام أصعب حاجة؛ بعدها القفل بيصبح عادة.",
        "The first three days are the hardest; after that the lock becomes routine.",
    ),
    (
        "لو مفيش عقبات، فأنت مش ماشي في اتجاه يستاهل.",
        "If there is no friction, you are probably not heading anywhere worth going.",
    ),
    (
        "الخوف من إنك ترجع أقوى من الرغبة إنك ترجع.",
        "Fear of going back is stronger than the urge to go back.",
    ),
    (
        "ما تقارنش بدايتك بذروة غيري؛ قارن بقديمك أنت.",
        "Do not compare your start to someone else's peak; compare it to your own past.",
    ),
    (
        "النوم الكويس والحركة والشغل هما الدوا، مش الردود السريعة.",
        "Good sleep, movement and work are the medicine, not quick fixes.",
    ),
    (
        "أنت اخترت القفل بنفسك… فافتخر بنفسك قبل ما تخلص.",
        "You chose the lock yourself; be proud of yourself before it even ends.",
    ),
]

# (days, ar, en) -- what many people report over time
BENEFITS = [
    (1, "أول يوم: بتاخد خطوة اعتراف فيها إنك عايز تغير.", "Day 1: you take the first step and admit you want change."),
    (3, "٣ أيام: التوتر اللي بيوديك للمحتوى بيقل شوية وتلاقي نفسك بتفكر في اللي حواليك.", "3 days: the tension that pushes you to the content softens and your surroundings come back into focus."),
    (7, "أسبوع: نوم أهدأ وصحيان أسهل، والوقت اللي كان بيضيع بيظهر فجأة.", "A week: calmer sleep, easier mornings, and the lost time suddenly reappears."),
    (14, "أسبوعين: التركيز يبدأ يرتجع، ومفيش داعي تفتح الموقع \"بس من الفضول\".", "Two weeks: focus starts returning, and \"just out of curiosity\" stops being an argument."),
    (21, "٣ أسابيع: العادة القديمة بتفقد تلقائيتها؛ اللحظة الصعبة بقت لها مدة أقصر.", "Three weeks: the old habit loses its automatic pull; the hard moment passes faster."),
    (30, "شهر: ثقة في نفسك ووقفة قدام المرآة من غير حزن.", "A month: self-confidence, and facing the mirror without disappointment."),
    (60, "٦٠ يوم: دفاع أقوى بكتير وقت الملل والتوتر.", "60 days: much stronger defense against boredom and stress."),
    (90, "٩٠ يوم: فترة كفاية إن مسار الدوبامين يبدأ يتعود تاني.", "90 days: enough time for the dopamine pathway to start rebalancing."),
    (180, "١٨٠ يوم: القصة بقت عن هوية مش عن محاولة.", "180 days: it stops being an attempt and becomes identity."),
    (365, "سنة: الاتجاه بقى اتجاه حياتك مش مجهود مؤقت.", "A year: the direction becomes your life's direction, not a temporary effort."),
]

NOTES_EN = [
    "This is not surveillance — it is a commitment you made to yourself.",
    "Relapse is data, not destiny: log it honestly and lock again.",
    "The lock cannot be shortened. That is the whole point.",
    "Talk to someone you trust if the urge feels bigger than you.",
    "Recovery is boring on purpose — that is what healing looks like.",
]

NOTES_AR = [
    "دي مش مراقبة — دي التزام اخترته بنفسك.",
    "الانتكاسة مش حكم نهائي: سجّلها بصدق واقفل من جديد.",
    "القفل مينفعش يتقصر، وهادا بالضبط معناه.",
    "كلّم حد تثق فيه لو الحركة بقت أكبر منك.",
    "التعافي ممل عن قصد — ده شكل الشفاء الحقيقي.",
]


def _day_index() -> int:
    return int(datetime.now(timezone.utc).strftime("%Y%m%d"))


def quote(lang: str = "ar") -> str:
    idx = _day_index() % len(QUOTES)
    return QUOTES[idx][0] if lang == "ar" else QUOTES[idx][1]


def benefits(lang: str = "ar") -> list[dict]:
    return [
        {"days": d, "text": ar if lang == "ar" else en}
        for d, ar, en in BENEFITS
    ]


def notes(lang: str = "ar") -> list[str]:
    return list(NOTES_AR if lang == "ar" else NOTES_EN)


def payload(lang: str = "ar") -> dict:
    return {
        "quote": quote(lang),
        "benefits": benefits(lang),
        "notes": notes(lang),
        "day_index": _day_index(),
    }
